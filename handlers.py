import asyncio
import html
import logging
import re
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiohttp import web
from api_client import HeroSMSClient, check_telegram_numbers
import database as db
import keyboards as kb
from states import BotStates

router = Router()
global_bot = None


def set_bot_instance(bot):
  global global_bot
  global_bot = bot


def get_bot_instance():
  return global_bot


ADMIN_ID = 7266067201
COLOMBIA_ID = 33
TG_SERVICE = "tg"
MAX_PRICE = 0.145

MENU_BUTTONS = [
    "Buy Telegram Number",
    "Bulk Buy Numbers",
    "Active Numbers",
    "Balance",
    "Profile",
    "Support",
]


def format_tg_status(raw_status: any) -> str:
  """Checker status filter kore emoji o badge return kore"""
  if raw_status is None:
    return "⚠️ Check Failed"

  if isinstance(raw_status, dict):
    st = str(raw_status.get("status") or raw_status.get("result") or raw_status.get("msg") or raw_status).strip().lower()
  elif isinstance(raw_status, bool):
    st = "occupied" if raw_status else "unoccupied"
  else:
    st = str(raw_status).strip().lower()

  if "api_error" in st or "check_failed" in st or not st:
    return "⚠️ Check Failed"

  # Fresh / Unoccupied
  fresh_signals = [
      "unoccupied", "phone_number_unoccupied",
      "unregistered", "not_registered", "not registered", "non_registered",
      "not_occupied", "not occupied", "free", "fresh", "available",
      "ready", "allow", "ok", "valid", "clean", "false", "0",
      "no_account", "no account", "does_not_exist", "not_exists"
  ]
  if any(w in st for w in fresh_signals):
    if "banned" in st and not any(neg in st for neg in ["not", "un", "no", "non", "false"]):
      return "🚫 Banned"
    return "✅ Fresh"

  # Locked / Flood / 2FA
  locked_signals = ["flood", "locked", "lock", "wait", "restricted", "2fa", "password", "has_password"]
  if any(w in st for w in locked_signals):
    return "🔒 Locked"

  # Registered / Occupied
  occupied_signals = ["occupied", "registered", "taken", "used", "true", "1"]
  if any(w in st for w in occupied_signals) and not any(neg in st for neg in ["not", "un", "no", "non", "false"]):
    return "❌ Registered"

  # Banned
  banned_signals = ["banned", "ban", "blocked"]
  if any(w in st for w in banned_signals) and not any(neg in st for neg in ["not", "un", "no", "non", "without", "false"]):
    return "🚫 Banned"

  clean = re.sub(r'phone_number_', '', st, flags=re.IGNORECASE).replace('_', ' ').strip().title()
  return f"⚠️ {clean}"


async def handle_herosms_webhook(request):
  action = request.query.get("action")
  aid = request.query.get("activationId") or request.query.get("id")
  code = request.query.get("code")

  if not action or not aid:
    return web.Response(text="Missing parameters", status=400)

  if action == "STATUS_OK" and code:
    row = await db.get_activation(aid)
    if row:
      user_id = row["user_id"]
      phone = row["phone"]
      msg_id = row["message_id"]
      text = f"Number: <code>+{phone}</code>\nOTP: <code>{code}</code>"
      bot = get_bot_instance()
      if bot:
        try:
          if msg_id:
            await bot.edit_message_text(
                text=text,
                chat_id=user_id,
                message_id=msg_id,
                reply_markup=kb.otp_copy_menu(code),
            )
          else:
            await bot.send_message(
                user_id, text, reply_markup=kb.otp_copy_menu(code)
            )

          user = await db.get_user(user_id)
          client = HeroSMSClient(user["api_key"])
          await client.set_status(aid, 6)
          await db.delete_activation(aid)
        except Exception as e:
          logging.error(f"Failed to update webhook OTP for {user_id}: {e}")
    return web.Response(text="OK")
  return web.Response(text="Ignored")


async def is_allowed(user_id: int) -> bool:
  if user_id == ADMIN_ID:
    return True
  user = await db.get_user(user_id)
  if user and user["is_banned"]:
    return False
  maintenance = await db.get_setting("maintenance")
  if maintenance == "1":
    return False
  return True


async def poll_sms(
    bot, chat_id: int, activation_id: str, phone: str, client: HeroSMSClient
):
  for _ in range(200):
    await asyncio.sleep(3)
    row = await db.get_activation(activation_id)
    if not row:
      return

    try:
      res = await client.get_status(activation_id)
      if isinstance(res, str):
        if res.startswith("STATUS_OK:"):
          code = res.split(":", 1)[1]
          text = f"Number: <code>+{phone}</code>\nOTP: <code>{code}</code>"
          msg_id = row["message_id"]
          if msg_id:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=kb.otp_copy_menu(code),
            )
          else:
            await bot.send_message(
                chat_id, text, reply_markup=kb.otp_copy_menu(code)
            )

          await client.set_status(activation_id, 6)
          await db.delete_activation(activation_id)
          return
        elif res.startswith("STATUS_CANCEL"):
          await db.delete_activation(activation_id)
          return
    except Exception:
      pass


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
  await state.clear()
  await db.add_user(message.from_user.id)
  user = await db.get_user(message.from_user.id)

  if user and user["is_banned"]:
    await message.answer("You are banned from using this bot.")
    return

  maintenance = await db.get_setting("maintenance")
  if maintenance == "1" and message.from_user.id != ADMIN_ID:
    await message.answer("Bot is under maintenance. Contact Admin.")
    return

  if not user or not user["api_key"]:
    await message.answer(
        "Welcome to HeroSMS Bot!\n\nPlease send your HeroSMS API Key to get"
        " started.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(BotStates.waiting_for_api_key)
  else:
    await message.answer("Welcome back!", reply_markup=kb.main_reply_menu())


@router.message(BotStates.waiting_for_api_key)
async def process_api_key(message: Message, state: FSMContext):
  text = message.text.strip()
  if text in MENU_BUTTONS:
    await state.clear()
    return await message.answer("Action cancelled. Please try again.")

  api_key = text.strip("\"'").strip()
  client = HeroSMSClient(api_key)
  balance = await client.get_balance()

  if balance is not None:
    await db.update_api_key(message.from_user.id, api_key)
    await state.clear()
    await message.answer(
        f"API Key saved successfully!\nBalance: <code>{balance:.4f} USD</code>",
        reply_markup=kb.main_reply_menu(),
    )
  else:
    await message.answer("Invalid API Key. Please check and try again.")


@router.callback_query(F.data == "menu_main")
async def cb_menu_main(callback: CallbackQuery, state: FSMContext):
  await state.clear()
  if not await is_allowed(callback.from_user.id):
    return
  try:
    await callback.message.delete()
  except:
    pass
  await callback.message.answer(
      "Welcome back!", reply_markup=kb.main_reply_menu()
  )


@router.message(F.text == "Profile")
async def text_profile(message: Message):
  if not await is_allowed(message.from_user.id):
    return
  user = await db.get_user(message.from_user.id)
  if not user or not user["api_key"]:
    return
  client = HeroSMSClient(user["api_key"])
  balance = await client.get_balance()
  bal_str = f"<code>{balance:.4f} USD</code>" if balance is not None else "Error"
  text = (
      f"Profile\n\nBalance: {bal_str}\nAPI Key:"
      f" <code>{user['api_key'][:12]}...</code>"
  )
  await message.answer(text, reply_markup=kb.profile_menu())


@router.callback_query(F.data == "profile_change_key")
async def cb_change_key(callback: CallbackQuery, state: FSMContext):
  if not await is_allowed(callback.from_user.id):
    return
  await callback.message.edit_text(
      "Please send your new HeroSMS API Key.", reply_markup=kb.back_button()
  )
  await state.set_state(BotStates.waiting_for_api_key)


@router.message(F.text == "Balance")
async def text_balance(message: Message):
  if not await is_allowed(message.from_user.id):
    return
  user = await db.get_user(message.from_user.id)
  client = HeroSMSClient(user["api_key"])
  balance = await client.get_balance()
  if balance is not None:
    await message.answer(f"Balance: <code>{balance:.4f} USD</code>")
  else:
    await message.answer("Error fetching balance.")


@router.message(F.text == "Support")
async def text_support(message: Message):
  await message.answer("Support: @Syedmahinislam")


@router.message(F.text == "Buy Telegram Number")
async def text_buy_tg_number(message: Message):
  if not await is_allowed(message.from_user.id):
    return
  user = await db.get_user(message.from_user.id)
  client = HeroSMSClient(user["api_key"])
  prices = await client.get_prices(country=COLOMBIA_ID, service=TG_SERVICE)
  try:
    cost = prices[str(COLOMBIA_ID)][TG_SERVICE]["cost"]
    count = prices[str(COLOMBIA_ID)][TG_SERVICE]["count"]
  except:
    await message.answer("Pricing not available right now.")
    return
  text = (
      f"Purchase Info\n\nCountry: Colombia\nService: Telegram\n\nPrice:"
      f" <code>{cost} USD</code>\nAvailable: <code>{count}</code> numbers\n\nDo"
      " you want to buy?"
  )
  await message.answer(
      text, reply_markup=kb.confirm_number_menu(COLOMBIA_ID, TG_SERVICE)
  )


async def buy_single_number_process(
    bot, user_id: int, chat_id: int, service: str, country_id: int, client
):
  res = await client.get_number(
      service=service, country=country_id, max_price=MAX_PRICE
  )
  if not isinstance(res, dict) or "activationId" not in res:
    err = res.get("title", str(res)) if isinstance(res, dict) else str(res)
    await bot.send_message(chat_id, f"Failed to buy number: {html.escape(err)}")
    return False

  aid = str(res["activationId"])
  phone = res.get("phoneNumber", "Unknown")

  # Telegram Checker দিয়ে চেক করা
  check_res = await check_telegram_numbers([phone])
  badge = format_tg_status(check_res.get(f"+{phone}") or check_res.get(phone))

  # আপনার আগের স্টাইলে মেসেজ পাঠানো
  msg = await bot.send_message(
      chat_id,
      f"Number: <code>+{phone}</code> — <b>{badge}</b>\nOTP: Waiting for SMS...",
      reply_markup=kb.number_action_menu(aid),
  )

  await db.save_activation(aid, user_id, phone, msg.message_id)
  asyncio.create_task(poll_sms(bot, chat_id, aid, phone, client))
  return True


@router.callback_query(F.data.startswith("buy_"))
async def cb_buy_number(callback: CallbackQuery):
  parts = callback.data.split("_")
  country_id, service = parts[1], parts[2]
  user = await db.get_user(callback.from_user.id)
  client = HeroSMSClient(user["api_key"])
  await callback.message.delete()
  await buy_single_number_process(
      callback.bot,
      callback.from_user.id,
      callback.message.chat.id,
      service,
      country_id,
      client,
  )


@router.callback_query(F.data.startswith("refresh_"))
async def cb_refresh_sms(callback: CallbackQuery):
  aid = callback.data[len("refresh_"):]
  user = await db.get_user(callback.from_user.id)
  client = HeroSMSClient(user["api_key"])
  res = await client.get_status(aid)

  if isinstance(res, str):
    if res.startswith("STATUS_OK:"):
      code = res.split(":", 1)[1]
      row = await db.get_activation(aid)
      phone = row["phone"] if row else "Unknown"
      await callback.message.edit_text(
          f"Number: <code>+{phone}</code>\nOTP: <code>{code}</code>",
          reply_markup=kb.otp_copy_menu(code),
      )
      await client.set_status(aid, 6)
      await db.delete_activation(aid)
      await callback.answer("OTP Received!")
    elif res.startswith("STATUS_WAIT_CODE"):
      await callback.answer("Still waiting for OTP...", show_alert=True)
    elif res.startswith("STATUS_CANCEL"):
      await db.delete_activation(aid)
      await callback.message.edit_text("Activation cancelled.")
    else:
      await callback.answer(f"Status: {res}", show_alert=True)
  else:
    await callback.answer("Error checking status.", show_alert=True)


@router.callback_query(F.data.startswith("single_cancel_"))
async def cb_cancel_single(callback: CallbackQuery):
  aid = callback.data[len("single_cancel_"):]
  user = await db.get_user(callback.from_user.id)
  client = HeroSMSClient(user["api_key"])
  res = await client.set_status(aid, 8)
  if isinstance(res, str) and (
      res.startswith("ACCESS_CANCEL") or res.startswith("STATUS_CANCEL")
  ):
    await db.delete_activation(aid)
    await callback.message.edit_text("Cancelled. Balance refunded.")
  elif isinstance(res, str) and "EARLY_CANCEL_DENIED" in res:
    await callback.answer(
        "Cannot cancel within first 2 minutes.", show_alert=True
    )
  else:
    err = res.get("title", str(res)) if isinstance(res, dict) else str(res)
    await callback.answer(f"Error: {err}", show_alert=True)


@router.message(F.text == "Bulk Buy Numbers")
async def text_bulk_buy(message: Message, state: FSMContext):
  if not await is_allowed(message.from_user.id):
    return
  user = await db.get_user(message.from_user.id)
  if not user or not user["api_key"]:
    return
  await message.answer("Bulk Purchase\n\nHow many numbers do you want to buy?")
  await state.set_state(BotStates.waiting_for_bulk_amount)


@router.message(BotStates.waiting_for_bulk_amount)
async def process_bulk_amount(message: Message, state: FSMContext):
  text = message.text.strip()
  if text in MENU_BUTTONS:
    await state.clear()
    return await message.answer("Bulk buy cancelled.")

  try:
    amount = int(text)
    if amount < 1 or amount > 100:
      raise ValueError
  except:
    await message.answer("Enter a valid number between 1 and 100.")
    return

  await state.clear()
  user = await db.get_user(message.from_user.id)
  client = HeroSMSClient(user["api_key"])

  await message.answer(f"Starting bulk purchase of {amount} numbers...")

  # আপনার স্ক্রিপ্টের আগের সিস্টেমে ঠিক যেভাবে একটার পর একটা বাই হতো:
  for i in range(amount):
    success = await buy_single_number_process(
        message.bot,
        message.from_user.id,
        message.chat.id,
        TG_SERVICE,
        COLOMBIA_ID,
        client,
    )
    if not success:
      await message.answer(f"Stopped bulk purchase at item #{i+1}.")
      break
    await asyncio.sleep(0.5)


@router.message(F.text == "Active Numbers")
async def text_active_numbers(message: Message):
  if not await is_allowed(message.from_user.id):
    return
  user = await db.get_user(message.from_user.id)
  if not user or not user["api_key"]:
    return
  client = HeroSMSClient(user["api_key"])
  res = await client.get_active_activations()

  if not (isinstance(res, dict) and res.get("status") == "success"):
    err = res.get("title", str(res)) if isinstance(res, dict) else str(res)
    await message.answer(f"Error: {html.escape(err)}")
    return

  activations = res.get("data", [])
  if not activations:
    await message.answer("No active numbers.")
    return

  await message.answer(
      f"Active Numbers ({len(activations)}):",
      reply_markup=kb.active_numbers_menu(activations),
  )


@router.callback_query(F.data == "cancel_all_active")
async def cb_cancel_all_active(callback: CallbackQuery):
  if not await is_allowed(callback.from_user.id):
    return
  user = await db.get_user(callback.from_user.id)
  client = HeroSMSClient(user["api_key"])
  res = await client.get_active_activations()
  if not (isinstance(res, dict) and res.get("status") == "success"):
    await callback.answer("Failed to fetch active numbers.", show_alert=True)
    return
  activations = res.get("data", [])
  if not activations:
    await callback.answer("No active numbers to cancel.", show_alert=True)
    return

  await callback.message.edit_text(
      f"Cancelling {len(activations)} numbers... please wait."
  )

  async def cancel_one(act):
    aid = str(act.get("activationId", ""))
    if not aid:
      return False
    try:
      r = await client.set_status(aid, 8)
      if isinstance(r, str) and (
          r.startswith("ACCESS_CANCEL") or r.startswith("STATUS_CANCEL")
      ):
        await db.delete_activation(aid)
        return True
      if isinstance(r, dict) and r.get("status") == "success":
        await db.delete_activation(aid)
        return True
    except:
      pass
    return False

  results = await asyncio.gather(*[cancel_one(a) for a in activations])
  ok = sum(1 for x in results if x)
  await callback.message.edit_text(
      f"Cancelled {ok}/{len(activations)} numbers. Balance refunded."
  )


@router.callback_query(F.data.startswith("active_cancel_"))
async def cb_active_cancel(callback: CallbackQuery):
  aid = callback.data[len("active_cancel_"):]
  user = await db.get_user(callback.from_user.id)
  client = HeroSMSClient(user["api_key"])
  r = await client.set_status(aid, 8)
  if isinstance(r, str) and (
      r.startswith("ACCESS_CANCEL") or r.startswith("STATUS_CANCEL")
  ):
    await db.delete_activation(aid)
    await callback.answer("Cancelled!", show_alert=True)
    res = await client.get_active_activations()
    if isinstance(res, dict) and res.get("status") == "success":
      acts = res.get("data", [])
      if not acts:
        await callback.message.edit_text("No active numbers left.")
      else:
        await callback.message.edit_reply_markup(
            reply_markup=kb.active_numbers_menu(acts)
        )
  elif isinstance(r, str) and "EARLY_CANCEL_DENIED" in r:
    await callback.answer(
        "Cannot cancel within first 2 minutes.", show_alert=True
    )
  else:
    await callback.answer("Failed to cancel.", show_alert=True)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
  if message.from_user.id != ADMIN_ID:
    return
  maintenance = await db.get_setting("maintenance")
  await message.answer(
      "Admin Panel", reply_markup=kb.admin_menu(maintenance == "1")
  )


@router.callback_query(F.data == "admin_maintenance")
async def cb_admin_maintenance(callback: CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return
  current = await db.get_setting("maintenance")
  new_val = "0" if current == "1" else "1"
  await db.set_setting("maintenance", new_val)
  await callback.message.edit_reply_markup(
      reply_markup=kb.admin_menu(new_val == "1")
  )
  await callback.answer("Maintenance updated.")


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
  if callback.from_user.id != ADMIN_ID:
    return
  await callback.message.answer(
      "Send the broadcast message:", reply_markup=kb.back_button()
  )
  await state.set_state(BotStates.waiting_for_broadcast)


@router.message(BotStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
  if message.from_user.id != ADMIN_ID:
    return
  if message.text.strip() in MENU_BUTTONS:
    await state.clear()
    return await message.answer("Broadcast cancelled.")

  users = await db.get_all_users()
  sent = 0
  for uid in users:
    try:
      await message.bot.send_message(
          uid, f"Broadcast Message:\n\n{message.text}"
      )
      sent += 1
    except:
      pass
  await message.answer(f"Sent to {sent} users.")
  await state.clear()


@router.callback_query(F.data == "admin_ban")
async def cb_admin_ban(callback: CallbackQuery, state: FSMContext):
  if callback.from_user.id != ADMIN_ID:
    return
  await callback.message.answer(
      "Send the user ID to ban/unban:", reply_markup=kb.back_button()
  )
  await state.set_state(BotStates.waiting_for_ban_id)


@router.message(BotStates.waiting_for_ban_id)
async def process_ban_id(message: Message, state: FSMContext):
  if message.from_user.id != ADMIN_ID:
    return
  try:
    target = int(message.text.strip())
  except:
    await message.answer("Invalid ID.")
    return
  user = await db.get_user(target)
  if not user:
    await message.answer("User not found.")
    return
  new_status = not bool(user["is_banned"])
  await db.set_ban_status(target, new_status)
  label = "Banned" if new_status else "Unbanned"
  await message.answer(f"User {target} {label}.")
  await state.clear()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
  await callback.answer()

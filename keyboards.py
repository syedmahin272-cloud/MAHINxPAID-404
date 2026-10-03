from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_reply_menu() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.button(text="Bulk Buy Numbers")
    b.button(text="Active Numbers")
    b.button(text="Balance")
    b.button(text="Profile")
    b.adjust(2, 2)
    return b.as_markup(resize_keyboard=True)


def admin_reply_menu(restock_on: bool = True) -> ReplyKeyboardMarkup:
    restock_label = "🔔 Restock Alert: ON" if restock_on else "🔕 Restock Alert: OFF"
    b = ReplyKeyboardBuilder()
    b.button(text="📊 Users & OTP Monitor")
    b.button(text="👥 Live Active Users")
    b.button(text="📢 Broadcast Message")
    b.button(text="🚫 Ban / Unban User")
    b.button(text="❌ Unapprove / Revoke Access")
    b.button(text="⏳ Extend User Subscription")
    b.button(text=restock_label)
    b.button(text="⚙️ Toggle Maintenance")
    b.button(text="⬅️ Back to User Menu")
    b.adjust(2, 2, 2, 2, 1)
    return b.as_markup(resize_keyboard=True)


def profile_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Change API Key", callback_data="profile_change_key")
    b.button(text="Back", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


def back_button(callback_data: str = "menu_main") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Back", callback_data=callback_data)
    return b.as_markup()


def number_action_menu(activation_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Refresh OTP", callback_data=f"refresh_{activation_id}")
    b.button(text="Cancel Number", callback_data=f"single_cancel_{activation_id}")
    b.adjust(2)
    return b.as_markup()


def active_numbers_menu(activations: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for act in activations:
        aid = str(act.get("activationId", ""))
        phone = str(act.get("phoneNumber", "Unknown"))
        if aid:
            b.button(text=f"Cancel +{phone}", callback_data=f"active_cancel_{aid}")

    b.button(text="Cancel All Active", callback_data="cancel_all_active")
    b.button(text="Back", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


def otp_copy_menu(otp_code: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    try:
        from aiogram.types import CopyTextButton
        b.row(
            InlineKeyboardButton(
                text=f"Copy OTP: {otp_code}", copy_text=CopyTextButton(text=str(otp_code))
            )
        )
    except ImportError:
        b.button(text=f"Copy OTP: {otp_code}", callback_data="noop")
    return b.as_markup()


def approval_duration_menu(user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="1 Day", callback_data=f"appr_{user_id}_1")
    b.button(text="3 Days", callback_data=f"appr_{user_id}_3")
    b.button(text="7 Days", callback_data=f"appr_{user_id}_7")
    b.button(text="30 Days", callback_data=f"appr_{user_id}_30")
    b.button(text="Lifetime", callback_data=f"appr_{user_id}_life")
    b.button(text="❌ Reject", callback_data=f"appr_{user_id}_reject")
    b.adjust(2, 3, 1)
    return b.as_markup()

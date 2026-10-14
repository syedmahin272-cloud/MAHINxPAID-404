from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    CopyTextButton
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
    b.button(text="📦 Check Live Stock")
    b.button(text="📊 Users & OTP Monitor")
    b.button(text="📈 Daily & Lifetime Stats")
    b.button(text="👥 Live Active Users")
    b.button(text="⚙️ Buy Config (Operator/Price)")
    b.button(text="🚫 Manage Excluded Prefixes")
    b.button(text="📢 Broadcast Message")
    b.button(text="🚫 Ban / Unban User")
    b.button(text="❌ Unapprove / Revoke Access")
    b.button(text="⏳ Extend User Subscription")
    b.button(text=restock_label)
    b.button(text="⚙️ Toggle Maintenance")
    b.button(text="⬅️ Back to User Menu")
    b.adjust(1, 2, 2, 2, 2, 2, 1, 1)
    return b.as_markup(resize_keyboard=True)

def admin_config_menu(current_op: str, current_price: float) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=f"🏢 Operator: {current_op.upper()}", callback_data="cfg_set_operator", style="success"))
    b.row(InlineKeyboardButton(text=f"💲 Max Price: ${current_price:.3f}", callback_data="cfg_set_price", style="success"))
    b.row(
        InlineKeyboardButton(text="Set Any", callback_data="cfg_op_any", style="success"),
        InlineKeyboardButton(text="Set Claro", callback_data="cfg_op_claro", style="success")
    )
    b.row(
        InlineKeyboardButton(text="Set Movistar", callback_data="cfg_op_movistar", style="success"),
        InlineKeyboardButton(text="Set Tigo", callback_data="cfg_op_tigo", style="success")
    )
    b.row(InlineKeyboardButton(text="Back", callback_data="menu_admin_close", style="success"))
    return b.as_markup()

def prefix_manage_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="➕ Add Prefix", callback_data="pfx_add", style="success"),
        InlineKeyboardButton(text="➖ Remove Prefix", callback_data="pfx_remove", style="success")
    )
    b.row(
        InlineKeyboardButton(text="🗑️ Clear All", callback_data="pfx_clear_all", style="success"),
        InlineKeyboardButton(text="📋 View All", callback_data="pfx_view", style="success")
    )
    b.row(InlineKeyboardButton(text="Back", callback_data="menu_admin_close", style="success"))
    return b.as_markup()

def stock_broadcast_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📢 Broadcast Alert", callback_data="broadcast_live_stock", style="success"))
    return b.as_markup()

def profile_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Change API Key", callback_data="profile_change_key", style="success"))
    b.row(InlineKeyboardButton(text="Back", callback_data="menu_main", style="success"))
    return b.as_markup()

def back_button(callback_data: str = "menu_main") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Back", callback_data=callback_data, style="success"))
    return b.as_markup()

def number_action_menu(activation_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="Refresh OTP", callback_data=f"refresh_{activation_id}", style="success"),
        InlineKeyboardButton(text="Cancel Number", callback_data=f"single_cancel_{activation_id}", style="success")
    )
    return b.as_markup()

def active_numbers_menu(activations: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for act in activations:
        aid = str(act.get("activationId", ""))
        phone = str(act.get("phoneNumber", "Unknown"))
        if aid:
            b.row(InlineKeyboardButton(text=f"Cancel +{phone}", callback_data=f"active_cancel_{aid}", style="success"))

    b.row(InlineKeyboardButton(text="Cancel All Active", callback_data="cancel_all_active", style="success"))
    b.row(InlineKeyboardButton(text="Back", callback_data="menu_main", style="success"))
    return b.as_markup()

def otp_copy_menu(otp_code: str) -> InlineKeyboardMarkup:
    """Only OTP code on the button with Telegram green style success"""
    b = InlineKeyboardBuilder()
    code_str = str(otp_code).strip()
    try:
        b.row(InlineKeyboardButton(text=code_str, copy_text=CopyTextButton(text=code_str), style="success"))
    except:
        b.row(InlineKeyboardButton(text=code_str, callback_data="noop", style="success"))
    return b.as_markup()

def bulk_report_menu(batch_id: str, show_only_fresh: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if not show_only_fresh:
        b.row(InlineKeyboardButton(text="View Only Fresh", callback_data=f"filter_fresh_{batch_id}", style="success"))
    else:
        b.row(InlineKeyboardButton(text="📋 Show All", callback_data=f"filter_all_{batch_id}", style="success"))
    return b.as_markup()

def approval_duration_menu(user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="1 Day", callback_data=f"appr_{user_id}_1", style="success"),
        InlineKeyboardButton(text="3 Days", callback_data=f"appr_{user_id}_3", style="success")
    )
    b.row(
        InlineKeyboardButton(text="7 Days", callback_data=f"appr_{user_id}_7", style="success"),
        InlineKeyboardButton(text="30 Days", callback_data=f"appr_{user_id}_30", style="success")
    )
    b.row(InlineKeyboardButton(text="Lifetime", callback_data=f"appr_{user_id}_life", style="success"))
    b.row(InlineKeyboardButton(text="❌ Reject", callback_data=f"appr_{user_id}_reject", style="success"))
    return b.as_markup()

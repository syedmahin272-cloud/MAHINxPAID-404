from aiogram.fsm.state import State, StatesGroup

class BotStates(StatesGroup):
    waiting_for_api_key = State()
    waiting_for_bulk_amount = State()
    waiting_for_ban_id = State()
    waiting_for_unapprove_id = State()
    waiting_for_extend_id = State()
    waiting_for_extend_days = State()
    waiting_for_broadcast = State()
    
    # --- New Admin Dynamic States ---
    waiting_for_operator = State()
    waiting_for_max_price = State()
    waiting_for_add_prefix = State()
    waiting_for_remove_prefix = State()

from aiogram.fsm.state import State, StatesGroup

# States
class PurchaseState(StatesGroup):
    amount = State()
    recipient = State()
    payment_type = State()

class BalanceState(StatesGroup):
    amount = State()
    receipt = State()

class AdminState(StatesGroup):
    broadcast_message = State()
    add_channel = State()
    add_channel_name = State()
    add_promo = State()
    add_card = State()
    change_price = State()
    change_referral_bonus = State()
    remove_channel = State()
    search_user = State()
    manage_user_balance = State()
    ban_user = State()
    add_admin = State()
    remove_admin = State()
    edit_card_number = State()
    edit_card_holder = State()
    waiting_for_broadcast = State()
    waiting_for_user_id = State()
    waiting_for_channel_id = State()
    waiting_for_channel_name = State()
    waiting_for_promo_code = State()
    waiting_for_promo_discount = State()
    waiting_for_promo_uses = State()
    waiting_for_card_number = State()
    waiting_for_card_holder = State()
    waiting_for_price_key = State()
    waiting_for_price_value = State()
    waiting_for_ton_wallet = State()
    waiting_for_ton_price = State()
    waiting_for_ton_percentage = State()
    waiting_for_ton_bonus = State()
    waiting_for_stars_bonus = State()
    waiting_for_uc_bonus = State()

class TonSettingsState(StatesGroup):
    waiting_for_ton_wallet = State()
    waiting_for_ton_price = State()
    waiting_for_ton_percentage = State()

class TonPurchaseState(StatesGroup):
    amount = State()
    recipient = State()
    wallet_address = State()
    payment_type = State()

class StarsPurchaseState(StatesGroup):
    amount = State()
    recipient = State()

class WithdrawalStates(StatesGroup):
    amount = State()
    card_details = State()

class PremiumPurchaseState(StatesGroup):
    waiting_for_recipient = State()
    recipient_username = State()

class TonSellState(StatesGroup):
    amount = State()

class StarsSellState(StatesGroup):
    amount = State()

class PubgUcPurchaseState(StatesGroup):
    amount = State()
    user_id = State()

class CaptchaState(StatesGroup):
    waiting_for_captcha = State()

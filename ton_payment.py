import asyncio
import logging
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_TON_WALLET

class TONPaymentProcessor:
    def __init__(self, bot: Bot):
        self.bot = bot
    
    def generate_ton_keper_url(self, amount: float, description: str = "TON to'lov") -> str:
        """Generate TON keper URL for payment"""
        # TON keper URL format: ton://transfer?address=<address>&amount=<amount>&text=<description>
        # Proper URL encoding for description
        import urllib.parse
        encoded_description = urllib.parse.quote(description)
        return f"ton://transfer?address={ADMIN_TON_WALLET}&amount={amount}&text={encoded_description}"
    
    def generate_screenpay_url(self, amount: float, description: str = "TON to'lov") -> str:
        """Generate ScreenPay URL for payment"""
        # ScreenPay URL format (example - you'll need to get actual API)
        # Proper URL encoding for description
        import urllib.parse
        encoded_description = urllib.parse.quote(description)
        return f"https://screenpay.me/pay?ton={amount}&to={ADMIN_TON_WALLET}&desc={encoded_description}"
    
    async def create_payment_keyboard(self, amount: float, description: str = "TON to'lov") -> InlineKeyboardMarkup:
        """Create payment keyboard with TON keper and ScreenPay options"""
        builder = InlineKeyboardBuilder()
        
        # TON keper button
        ton_keper_url = self.generate_ton_keper_url(amount, description)
        builder.row(InlineKeyboardButton(
            text="💎 TON Keper orqali to'lash",
            url=ton_keper_url
        ))
        
        # ScreenPay button
        screenpay_url = self.generate_screenpay_url(amount, description)
        builder.row(InlineKeyboardButton(
            text="📱 ScreenPay orqali to'lash",
            url=screenpay_url
        ))
        
        # Manual transfer button
        builder.row(InlineKeyboardButton(
            text="🏦 Manzilni nusxalash",
            callback_data=f"copy_ton_address_{amount}"
        ))
        
        return builder.as_markup()
    
    async def copy_ton_address_callback(self, callback: types.CallbackQuery):
        """Handle TON address copy callback"""
        amount = callback.data.split("_")[-1]
        
        try:
            float_amount = float(amount)
        except ValueError:
            await callback.answer("Xatolik! Noto'g'ri miqdor.", show_alert=True)
            return
        
        # Create address text for copying
        address_text = f"💎 TON manzili:\n\n{ADMIN_TON_WALLET}\n\n💰 Miqdor: {float_amount} TON"
        
        # Send message with address
        await callback.message.answer(
            address_text,
            parse_mode="Markdown"
        )
        
        await callback.answer("Manzil nusxalandi!", show_alert=True)

# Global instance
ton_payment_processor = None

def init_ton_payment(bot: Bot):
    """Initialize TON payment processor"""
    global ton_payment_processor
    ton_payment_processor = TONPaymentProcessor(bot)
    return ton_payment_processor

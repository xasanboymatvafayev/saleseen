import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, WebAppInfo
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.methods import SendInvoice
from config import BOT_TOKEN, ADMINS, REQUIRED_CHANNELS, PAYMENT_CARD, CARD_HOLDER, OFFICIAL_CHANNEL, TRADE_GROUP, ADMIN_USERNAME, DEVELOPER_USERNAME, STARS_GIFT_IMAGE, PROVIDER_TOKEN, ADMIN_TON_WALLET
import sqlite3
import os
from PIL import Image, ImageDraw, ImageFont
import random
import io
import base64

# Get the absolute path to the database file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop.db')
import os
import logging
from datetime import datetime, timedelta
import random
import string

# Import from local modules
import admin_panel as ap
from states import AdminState, TonPurchaseState, StarsPurchaseState, BalanceState, PurchaseState, WithdrawalStates, PremiumPurchaseState, TonSellState, StarsSellState, PubgUcPurchaseState, CaptchaState
from ton_purchase import register_ton_handlers
from ton_payment import init_ton_payment
from pixy_api import PixyAPIClient
from pixy_manager import PixyAPIManager, handle_pixy_error
from ton_price_updater import start_ton_price_updates
from referral import track_referral, generate_referral_code, get_referral_stats, get_referral_bonus, track_referral_new, get_referral_bonus_by_type, get_referral_bonus_text, withdraw_referral_earnings
from utils import (
    get_user, is_user_banned, is_admin, get_all_admins, get_required_channels,
    get_price, get_ton_wallet, get_ton_sell_price, get_ton_buy_price, get_ton_market_price,
    set_ton_setting
)
from config import (
    BOT_TOKEN, ADMINS, REQUIRED_CHANNELS, PAYMENT_CARD, CARD_HOLDER,
    OFFICIAL_CHANNEL, TRADE_GROUP, ADMIN_USERNAME, DEVELOPER_USERNAME,
    STARS_GIFT_IMAGE, PROVIDER_TOKEN, DATABASE_PATH, PIXY_API_URL,
    PIXY_SEED_PHRASE, PIXY_MODE, ADMIN_TON_WALLET, ORDER_CHANNEL
)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def send_order_notification(message_text: str):
    """Send notification to order channel"""
    try:
        await bot.send_message(
            ORDER_CHANNEL,
            message_text,
            parse_mode="Markdown"
        )
        logging.info(f"Order notification sent to {ORDER_CHANNEL}")
    except Exception as e:
        logging.error(f"Failed to send order notification: {e}")

# Initialize PixyAPI client
pixy_client = PixyAPIClient.from_env()
pixy_manager = PixyAPIManager()

# This function needs to be defined before it's used in handlers
async def send_premium_admin_notification(user_id: int, recipient_username: str, price: float, order_id: str = None):
    """Send notification to admins about 1-month premium purchase"""
    try:
        logging.info(f"Starting admin notification for user {user_id}, order {order_id}")
        
        user = get_user(user_id)
        buyer_username = f"@{user[1]}" if user and user[1] else f"ID: {user_id}"
        buyer_full_name = user[2] if user else "Noma'lum"
        
        # Sanitize full name to avoid any parsing issues
        safe_buyer_full_name = buyer_full_name.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
        if not safe_buyer_full_name.strip():
            safe_buyer_full_name = "Foydalanuvchi"
        
        logging.info(f"User info: {safe_buyer_full_name} ({buyer_username})")
        
        # Create inline keyboard with approval buttons and profile link
        raw_username = user[1] if user else None
        profile_url = (f"https://t.me/{raw_username}" if raw_username else f"tg://user?id={user_id}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_purchase_{order_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_purchase_{order_id}")
            ],
            [InlineKeyboardButton(text="👤 Profilni ko'rish", url=profile_url)]
        ])
        
        # Use plain text instead of Markdown to avoid parsing issues
        text = f"🆕 1 oylik Premium so'rovi!\n\n"
        text += f"👤 Sotib oluvchi: {safe_buyer_full_name} ({buyer_username})\n"
        text += f"🎯 Qabul qiluvchi: @{recipient_username}\n"
        text += f"💰 Narxi: {price:,.0f} so'm\n"
        text += f"🆔 So'rov ID: #{order_id}\n"
        text += f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        text += "⚡ Tasdiqlash yoki rad etish:"
        
        logging.info(f"Notification text prepared: {text}")
        
        # Send to all admins
        merged_admins = get_all_admins()
        logging.info(f"Found {len(merged_admins)} admins: {merged_admins}")
        
        success_count = 0
        for admin_id in merged_admins:
            try:
                await bot.send_message(admin_id, text, reply_markup=keyboard)
                logging.info(f"Successfully sent notification to admin {admin_id}")
                success_count += 1
            except Exception as e:
                logging.error(f"Admin {admin_id} ga xabar yuborilmadi: {e}")
        
        logging.info(f"Admin notification completed. Sent to {success_count}/{len(merged_admins)} admins")
        
    except Exception as e:
        logging.error(f"Critical error in send_premium_admin_notification: {e}")
        raise

async def send_premium_completed_notification(user_id: int, recipient_username: str, price: float, order_id: str = None):
    """Send notification to admins about completed 1-month premium purchase"""
    user = get_user(user_id)
    buyer_username = f"@{user[1]}" if user and user[1] else f"ID: {user_id}"
    buyer_full_name = user[2] if user else "Noma'lum"
    
    # Create inline keyboard with profile link
    raw_username = user[1] if user else None
    profile_url = (f"https://t.me/{raw_username}" if raw_username else f"tg://user?id={user_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Profilni ko'rish", url=profile_url)]
    ])
    
    text = f"✅ *1 oylik Premium tasdiqlandi!*\n\n"
    text += f"👤 *Sotib oluvchi:* {buyer_full_name} ({buyer_username})\n"
    text += f"🎯 *Qabul qiluvchi:* @{recipient_username}\n"
    text += f"💰 *Narxi:* {price:,} so'm\n"
    text += f"🆔 *So'rov ID: #{order_id}\n"
    text += f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    text += "✅ *Premium muvaffaqiyatli berildi!*"
    
    # Send to all admins
    merged_admins = get_all_admins()
    for admin_id in merged_admins:
        try:
            await bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Admin {admin_id} ga xabar yuborilmadi: {e}")

async def send_purchase_to_admins(purchase_id: int, user_id: int, product_type: str, product_id: int, price: float):
    """Send purchase request to all admins with approval buttons"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username, full_name FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        username = f"ID: {user_id}"
        full_name = "Noma'lum"
    else:
        username = f"@{user[0]}" if user[0] else f"ID: {user_id}"
        full_name = user[1]
    
    # Create inline keyboard for approval with profile link
    raw_username = user[0] if user else None
    profile_url = (f"https://t.me/{raw_username}" if raw_username else f"tg://user?id={user_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_purchase_{purchase_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_purchase_{purchase_id}")
        ],
        [
            InlineKeyboardButton(text="👤 Profilni ko'rish", url=profile_url)
        ]
    ])
    
    # Format product info
    if product_type == "stars":
        product_info = f"{product_id:,} Stars"
        quantity_info = f"Miqdori: {product_id:,}"
    elif product_type == "premium":
        product_info = f"{product_id} kun Premium"
        quantity_info = f"Muddati: {product_id} kun"
    else:
        product_info = "Noma'lum mahsulot"
        quantity_info = "Miqdor: -"
    
    text = f"🆕 *Yangi xarid so'rovi!*\n\n"
    text += f"📋 *ID:* {purchase_id}\n"
    text += f"👤 *Foydalanuvchi:* {full_name} ({username})\n"
    text += f"🧾 *Turi:* `{product_type}`\n"
    text += f"📦 *Mahsulot:* {product_info}\n"
    text += f"📏 {quantity_info}\n"
    text += f"💰 *Narx:* {price:,.0f} so'm\n"
    text += f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    text += "⚡ *Tasdiqlash uchun tugmalardan foydalanning:*"
    
    # Send to all admins
    merged_admins = get_all_admins()

    for admin_id in merged_admins:
        try:
            await bot.send_message(
                admin_id,
                text,
                reply_markup=keyboard
            )
        except Exception as e:
            logging.error(f"Admin {admin_id} ga xabar yuborilmadi: {e}")


async def notify_admins_withdrawal(withdrawal_id: int, user_id: int, amount: float, wallet_address: str):
    """Notify admins about a new referral withdrawal request"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username, full_name FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        username = f"ID: {user_id}"
        full_name = "Noma'lum"
    else:
        username = f"@{user[0]}" if user[0] else f"ID: {user_id}"
        full_name = user[1]
    
    # Create profile URL
    profile_url = f"tg://user?id={user_id}"
    
    # Create inline keyboard for approval
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_ton_withdraw_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject_ton_withdraw_{withdrawal_id}")
        ],
        [
            InlineKeyboardButton(text="👤 Profilni ko'rish", url=profile_url)
        ]
    ])
    
    text = f"💰 *Yangi Referal Yechib Olish So'rovi!*\n\n"
    text += f"📋 *ID:* {withdrawal_id}\n"
    text += f"👤 *Foydalanuvchi:* {full_name} ({username})\n"
    text += f"💎 *Miqdor:* {amount:.3f} TON\n"
    text += f"💳 *Hamyon:* `{wallet_address}`\n"
    text += f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    text += "⚡ *Tasdiqlash uchun tugmalardan foydalaning:*"
    
    # Get all admins
    db_admins: list[int] = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE is_admin = 1")
        db_admins = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()
    
    merged_admins = list(set(list(ADMINS) + db_admins))
    
    for admin_id in merged_admins:
        try:
            await bot.send_message(
                admin_id,
                text,
                reply_markup=keyboard
            )
        except Exception as e:
            logging.error(f"Admin {admin_id} ga yechib olish xabari yuborilmadi: {e}")

# Database setup
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure the database directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance REAL DEFAULT 0,
            stars_purchased INTEGER DEFAULT 0,
            premium_purchased INTEGER DEFAULT 0,
            ton_purchased REAL DEFAULT 0,
            is_admin BOOLEAN DEFAULT 0,
            is_banned BOOLEAN DEFAULT 0,
            has_received_referral_bonus BOOLEAN DEFAULT 0,
            referral_code TEXT,
            referred_by INTEGER,
            earned_ton REAL DEFAULT 0,
            withdrawn_ton REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Ensure all columns exist on users
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [column[1] for column in cursor.fetchall()]
    
    # List of columns to check and add if missing
    columns_to_add = {
        'is_banned': 'BOOLEAN DEFAULT 0',
        'has_received_referral_bonus': 'BOOLEAN DEFAULT 0',
        'referral_code': 'TEXT',
        'referred_by': 'INTEGER',
        'earned_ton': 'REAL DEFAULT 0',
        'withdrawn_ton': 'REAL DEFAULT 0',
        'captcha_passed': 'BOOLEAN DEFAULT 0'
    }
    
    for col_name, col_def in columns_to_add.items():
        if col_name not in user_columns:
            cursor.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_def}')
    
    # Generate referral codes for users who don't have one
    cursor.execute('SELECT user_id FROM users WHERE referral_code IS NULL')
    users_without_code = cursor.fetchall()
    if users_without_code:
        import hashlib
        for (u_id,) in users_without_code:
            code = hashlib.md5(f"ref_{u_id}".encode()).hexdigest()[:8].upper()
            cursor.execute('UPDATE users SET referral_code = ? WHERE user_id = ?', (code, u_id))
    
    # Transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            stars INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP,
            details TEXT
        )
    ''')
    
    # Add missing columns if they don't exist
    cursor.execute('PRAGMA table_info(transactions)')
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'details' not in columns:
        cursor.execute('ALTER TABLE transactions ADD COLUMN details TEXT')
    
    if 'photo_id' not in columns:
        cursor.execute('ALTER TABLE transactions ADD COLUMN photo_id TEXT')
    
    conn.commit()
    
    # Payment requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            receipt TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP
        )
    ''')
    
    # Purchase requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_type TEXT,
            product_id INTEGER,
            price REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP
        )
    ''')
    
    # Channels table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            channel_name TEXT,
            channel_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Promo codes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            bonus_amount REAL,
            usage_limit INTEGER,
            used_count INTEGER DEFAULT 0,
            channel_id TEXT,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Promo redemptions table (to prevent multiple claims per user)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, code)
        )
    ''')
    
    # Cards table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number TEXT,
            card_holder TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Pending star sales table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_star_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            amount_in_uzs INTEGER,
            order_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    
    # Make sure is_active column exists
    cursor.execute("PRAGMA table_info(cards)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'is_active' not in columns:
        cursor.execute('ALTER TABLE cards ADD COLUMN is_active BOOLEAN DEFAULT 1')
    
    # Prices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY,
            item_type TEXT UNIQUE,
            price REAL
        )
    ''')
    
    # Insert default prices - 1 TON = 35,000 UZS
    cursor.execute('''
        INSERT OR IGNORE INTO prices (item_type, price) VALUES 
        ('stars', 200),
        ('ton', 35000),
        ('premium_1month', 50000),
        ('premium_3months', 140000),
        ('premium_6months', 250000),
        ('premium_12months', 450000)
    ''')
    
    # TON Purchases table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ton_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            price REAL,
            recipient TEXT,
            wallet_address TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_id INTEGER
        )
    ''')
    
    # Withdrawals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            card_number TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_id INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def create_user(user_id, username=None, first_name=None, referrer_id=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.execute('''
                INSERT INTO users (user_id, username, full_name, referred_by)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, referrer_id))
            conn.commit()
            return True, True  # (Success, Created new)
        return True, False  # (Success, Already existed)
    except Exception as e:
        print(f"Error in create_user: {e}")
        return False, False
    finally:
        if 'conn' in locals():
            conn.close()

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def get_user_balance(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def update_user_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    
    # Record transaction if amount is not zero
    if amount != 0:
        trans_type = "refund" if amount > 0 else "purchase"
        details = f"Balance {'refund' if amount > 0 else 'deduction'}: {abs(amount):,.0f} so'm"
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, status, details, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, trans_type, amount, "completed", details, datetime.now()))
    
    conn.commit()
    conn.close()

def get_user_ton_balance(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT ton_balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

async def process_premium_purchase(user_id: int, months: int, price: float, api_order_id: str = None, 
                                  username: str = None, full_name: str = None, use_api: bool = True,
                                  recipient_username: str = None):
    """Process premium purchase and update database (balance will be deducted here)
    
    Args:
        user_id: Buyer's user ID (who pays)
        months: Premium duration in months
        price: Price paid
        api_order_id: PixyAPI order ID (if used)
        username: Buyer's username (for display)
        full_name: Buyer's full name (for display)
        use_api: Whether PixyAPI was used
        recipient_username: Username of the recipient (who gets premium). If None, premium goes to buyer.
    """
    try:
        # Additional validation to prevent automatic purchases
        if not username and not recipient_username:
            logging.warning(f"process_premium_purchase called without username or recipient_username for user {user_id}")
            return False, "Username talab qilinadi!"
        
        # Deduct balance first (only after API success)
        update_user_balance(user_id, -price)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Determine recipient user_id
        recipient_user_id = user_id  # Default: premium goes to buyer
        
        if recipient_username:
            # Find recipient user_id by username
            clean_recipient_username = recipient_username.lstrip('@')
            cursor.execute('SELECT user_id, full_name FROM users WHERE username = ?', (clean_recipient_username,))
            recipient_user = cursor.fetchone()
            
            if recipient_user:
                recipient_user_id = recipient_user[0]
                recipient_full_name = recipient_user[1]
            else:
                # Recipient not found in database - PixyAPI will handle it
                # But we still record the purchase for the buyer
                logging.warning(f"Recipient username {clean_recipient_username} not found in database. PixyAPI will handle premium delivery.")
                recipient_user_id = user_id  # Fallback to buyer
        
        # Get buyer info if not provided
        if not username or not full_name:
            cursor.execute('SELECT username, full_name FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            if user:
                username, full_name = user
            else:
                return False, "Foydalanuvchi topilmadi"
        
        # Create purchase request (record who bought it)
        cursor.execute('''
            INSERT INTO purchase_requests (user_id, product_type, product_id, price, status, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, 'premium', months, price, 'confirmed', datetime.now()))
        
        purchase_id = cursor.lastrowid
        
        # Update recipient's premium count (who receives premium)
        cursor.execute('''
            UPDATE users SET premium_purchased = premium_purchased + ? WHERE user_id = ?
        ''', (months, recipient_user_id))
        
        # Record transaction
        details = f'Purchased {months} months premium'
        if api_order_id:
            details += f' (API Order: {api_order_id})'
        if use_api:
            details += ' via PixyAPI'
        
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, stars, status, details, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, 'premium', price, 0, 'completed', details, datetime.now()))
        
        conn.commit()
        conn.close()
        
        # Notify buyer about successful purchase
        try:
            message_text = (
                f"🎉 *Tabriklaymiz! Premium muvaffaqiyatli sotib olindi!*\n\n"
                f"👑 *Premium muddati:* {months} oy\n"
            )
            
            if recipient_username and recipient_username != username:
                message_text += f"👤 *Qabul qiluvchi:* @{recipient_username.lstrip('@')}\n"
            
            message_text += (
                f"📅 *Sotib olingan sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"💰 *To'langan summa:* {price:,} so'm\n"
            )
            
            if api_order_id:
                message_text += f"🆔 *Buyurtma raqami:* {api_order_id}\n"
            
            message_text += f"\n✅ *Premium xususiyatlaridan hoziroq foydalanishingiz mumkin!*"
            
            await bot.send_message(
                user_id,
                message_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Failed to notify user {user_id} about premium purchase: {e}")
        
        # Notify recipient if different from buyer
        if recipient_username and recipient_user_id != user_id:
            try:
                sender_name = username.lstrip('@') if username else "Noma'lum"
                recipient_message = (
                    f"🎉 *Sizga premium obuna berildi!*\n\n"
                    f"👑 *Premium muddati:* {months} oy\n"
                    f"👤 *Beruvchi:* @{sender_name}\n"
                    f"📅 *Berilgan sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"✅ *Premium xususiyatlaridan hoziroq foydalanishingiz mumkin!*"
                )
                
                await bot.send_message(
                    recipient_user_id,
                    recipient_message,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Failed to notify recipient {recipient_user_id} about premium: {e}")
        
        return True, f"Successfully processed {months} months premium purchase"
        
    except Exception as e:
        logging.error(f"Error in process_premium_purchase: {e}")
        return False, f"Xatolik yuz berdi: {str(e)}"

def update_user_ton_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET ton_balance = ton_balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

async def auto_assign_premium(user_id: int, months: int, admin_id: int = None, use_api: bool = True):
    """Avtomatik ravishda premium obunani berish (PixyAPI orqali)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute('SELECT username, full_name FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return False, "Foydalanuvchi topilmadi"
        
        username, full_name = user
        
        # Calculate price
        price_key = f"premium_{months}month" if months == 1 else f"premium_{months}months"
        price = get_price(price_key)
        
        # Try to purchase via PixyAPI if requested
        api_order_id = None
        
        if use_api:
            try:
                if not username:
                    logging.warning(f"Username is required for PixyAPI. User {user_id} has no username. Using local mode.")
                else:
                    # Remove @ if present
                    clean_username = username.lstrip('@')
                    
                    # Generate order ID
                    import uuid
                    order_id = f"PIXY-{uuid.uuid4().hex[:8].upper()}"
                    
                    # Use enhanced PixyAPI manager with retry logic
                    api_response = await pixy_manager.safe_buy_premium(
                        username=clean_username,
                        months=months,
                        order_id=order_id
                    )
                    
                    success, message = await handle_pixy_error(api_response, "Premium purchase")
                    
                    if success:
                        api_order_id = api_response.get("order_id", order_id)
                        logging.info(f"PixyAPI premium purchase successful: {api_order_id}")
                    else:
                        logging.warning(f"PixyAPI failed: {message}")
                        use_api = False  # Fallback to local only
            except Exception as api_error:
                logging.error(f"PixyAPI error: {api_error}")
                use_api = False  # Fallback to local only
        
        # Create purchase request with auto-approved status
        cursor.execute('''
            INSERT INTO purchase_requests (user_id, product_type, product_id, price, status, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, 'premium', months, price, 'confirmed', datetime.now()))
        
        purchase_id = cursor.lastrowid
        
        # Update user's premium count
        cursor.execute('''
            UPDATE users SET premium_purchased = premium_purchased + ? WHERE user_id = ?
        ''', (months, user_id))
        
        # Record transaction
        details = f'Auto-assigned {months} months premium'
        if api_order_id:
            details += f' (API Order: {api_order_id})'
        
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, stars, status, details, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, 'premium', price, 0, 'completed', details, datetime.now()))
        
        conn.commit()
        conn.close()
        
        # Notify user
        try:
            message_text = (
                f"🎉 *Tabriklaymiz! Sizga avtomatik ravishda premium obuna berildi!*\n\n"
                f"👑 *Premium muddati:* {months} oy\n"
                f"📅 *Berilgan sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            )
            
            if api_order_id:
                message_text += f"🆔 *Buyurtma raqami:* {api_order_id}\n"
            
            message_text += f"\n✅ *Premium xususiyatlaridan foydalanishingiz mumkin!*"
            
            await bot.send_message(
                user_id,
                message_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Failed to notify user {user_id} about auto premium: {e}")
        
        # Notify admin if provided
        if admin_id:
            try:
                admin_message = (
                    f"🤖 *Avtomatik premium berildi!*\n\n"
                    f"👤 *Foydalanuvchi:* {full_name} (@{username})\n"
                    f"👑 *Premium muddati:* {months} oy\n"
                    f"💰 *Narxi:* {price:,} so'm\n"
                    f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                
                if api_order_id:
                    admin_message += f"\n🆔 *API Buyurtma:* {api_order_id}"
                
                if use_api:
                    admin_message += f"\nManba: PixyAPI (Premium Gift)"
                else:
                    admin_message += f"\nManba: Mahalliy tizim"
                
                await bot.send_message(
                    admin_id,
                    admin_message
                )
            except Exception as e:
                logging.error(f"Failed to notify admin {admin_id} about auto premium: {e}")
        
        result_msg = f"Successfully assigned {months} months premium to user {user_id}"
        if api_order_id:
            result_msg += f" (API Order: {api_order_id})"
        
        return True, result_msg
        
    except Exception as e:
        logging.error(f"Error in auto_assign_premium: {e}")
        return False, f"Xatolik yuz berdi: {str(e)}"

async def auto_assign_stars(user_id: int, stars_amount: int, admin_id: int = None, use_api: bool = True, recipient_username: str = None):
    """Avtomatik ravishda stars sotib olish (PixyAPI orqali)"""
    logging.info(f"auto_assign_stars called: user_id={user_id}, stars_amount={stars_amount}, recipient_username={recipient_username}, use_api={use_api}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute('SELECT username, full_name FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            logging.error(f"User not found: {user_id}")
            return False, "Foydalanuvchi topilmadi"
        
        username, full_name = user
        logging.info(f"User found: {username}, {full_name}")
        
        # Calculate price (1 star = 1 UZS or get from price table)
        price_per_star = get_price("stars") if get_price("stars") else 1
        price = stars_amount * price_per_star
        logging.info(f"Price calculated: {price_per_star} UZS per star, total: {price} UZS")
        
        # Check user balance
        user_balance = get_user_balance(user_id)
        logging.info(f"User balance: {user_balance} UZS")
        
        if user_balance < price:
            logging.error(f"Insufficient balance: need {price}, have {user_balance}")
            return False, f"Balans yetarli emas. Kerak: {price} UZS, Bor: {user_balance} UZS"
        
        # Determine recipient username
        target_username = recipient_username.lstrip('@') if recipient_username else username
        logging.info(f"Target username: {target_username}")
        
        # Try to purchase via PixyAPI if requested
        api_order_id = None
        
        if use_api:
            try:
                # Generate order ID
                import uuid
                order_id = f"PIXY-STARS-{uuid.uuid4().hex[:8].upper()}"
                logging.info(f"Generated order ID: {order_id}")
                
                # Use enhanced PixyAPI manager with retry logic
                logging.info(f"Calling pixy_manager.safe_buy_stars...")
                api_response = await pixy_manager.safe_buy_stars(
                    username=target_username,
                    amount=stars_amount,
                    order_id=order_id
                )
                logging.info(f"PixyAPI response: {api_response}")
                
                success, message = await handle_pixy_error(api_response, "Stars purchase")
                logging.info(f"PixyAPI result: success={success}, message={message}")
                
                if success:
                    api_order_id = api_response.get("order_id", order_id)
                    logging.info(f"PixyAPI stars purchase successful: {api_order_id}")
                else:
                    logging.warning(f"PixyAPI stars failed: {message}")
                    # Return error immediately - don't deduct balance
                    return False, message
            except Exception as api_error:
                logging.error(f"PixyAPI stars error: {api_error}")
                # Return error immediately - don't deduct balance
                return False, f"API xatoligi: {str(api_error)}"
        
        # Deduct balance only after API success
        update_user_balance(user_id, -price)
        
        # Create purchase request with auto-approved status
        cursor.execute('''
            INSERT INTO purchase_requests (user_id, product_type, product_id, amount, status, created_at, confirmed_at, confirmed_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, "stars", stars_amount, price, "confirmed", datetime.now(), datetime.now(), admin_id or user_id))
        
        purchase_id = cursor.lastrowid
        
        # Record transaction
        details = f"Stars sotib olish: {stars_amount} ⭐"
        if recipient_username:
            details += f" (Qabul qiluvchi: @{recipient_username})"
        if api_order_id:
            details += f' (API Order: {api_order_id})'
            details += ' via PixyAPI ✅'
        elif use_api:
            details += " via PixyAPI ❌ (Qo'lda ishlov kerak)"
        else:
            details += ' - Mahalliy tizim'
        
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, stars, status, details, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, "stars_purchase", price, stars_amount, "confirmed", details, datetime.now()))
        
        # Update user stats
        cursor.execute('''
            UPDATE users SET stars_purchased = stars_purchased + ? WHERE user_id = ?
        ''', (stars_amount, user_id))
        
        conn.commit()
        conn.close()
        
        # Send notification to admin
        admin_message = f"⭐ *Yangi Stars sotib olish!*\n\n"
        admin_message += f"👤 *Sotib oluvchi:* {full_name} (@{username})\n"
        admin_message += f"🆔 *User ID:* {user_id}\n"
        admin_message += f"⭐ *Miqdori:* {stars_amount} ⭐\n"
        admin_message += f"💰 *Narxi:* {price} UZS\n"
        if recipient_username:
            admin_message += f"👤 *Qabul qiluvchi:* @{recipient_username}\n"
        admin_message += f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        
        if api_order_id:
            admin_message += f"🆔 *API Buyurtma:* {api_order_id}\n"
        
        if use_api:
            admin_message += f"🌐 *Manba:* PixyAPI"
        else:
            admin_message += f"🏪 *Manba:* Mahalliy tizim"
        
        # Send to all admins
        for admin_id in ADMINS:
            try:
                await bot.send_message(admin_id, admin_message, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Failed to send stars purchase notification to admin {admin_id}: {e}")
        
        result_msg = f"Successfully purchased {stars_amount} stars"
        if recipient_username:
            result_msg += f" for @{recipient_username}"
        if api_order_id:
            result_msg += f" (API Order: {api_order_id})"
        
        return True, result_msg
        
    except Exception as e:
        logging.error(f"Error in auto_assign_stars: {e}")
        return False, f"Xatolik yuz berdi: {str(e)}"

# Captcha functions
def generate_captcha_image():
    """Generate captcha image with random number"""
    # Generate random 4-digit number
    captcha_text = ''.join([str(random.randint(0, 9)) for _ in range(4)])
    
    # Create image
    width, height = 200, 80
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # Add noise lines
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill='gray', width=1)
    
    # Add dots
    for _ in range(100):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill='gray')
    
    # Try to use a font, fallback to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        try:
            font = ImageFont.load_default()
        except:
            font = None
    
    # Draw text
    if font:
        text_width = draw.textlength(captcha_text, font=font)
        text_height = 40
        x = (width - text_width) / 2
        y = (height - text_height) / 2
        draw.text((x, y), captcha_text, fill='black', font=font)
    else:
        # Fallback positioning
        x = 50
        y = 20
        draw.text((x, y), captcha_text, fill='black')
    
    # Convert to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr, captcha_text

# Keyboards
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars olish", callback_data="stars_purchase"),
            InlineKeyboardButton(text="💸 Stars sotish", callback_data="sell_stars")
        ],
        [
            InlineKeyboardButton(text="💎 TON olish", callback_data="ton_purchase"),
            InlineKeyboardButton(text="💱 TON sotish", callback_data="ton_sell")
        ],
        [
            InlineKeyboardButton(text="🎮 PUBG UC", callback_data="pubg_uc_purchase"),
            InlineKeyboardButton(text="👑 Premium olish", callback_data="premium_purchase")
        ],
        [
            InlineKeyboardButton(text="💰 Hisobim", callback_data="my_account")
        ],
        [InlineKeyboardButton(text="ℹ️ Maʼlumotlar", callback_data="information")]
    ])
    return keyboard

def stars_amount_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 ⭐", callback_data="stars_50")],
        [InlineKeyboardButton(text="100 ⭐", callback_data="stars_100")],
        [InlineKeyboardButton(text="150 ⭐", callback_data="stars_150")],
        [InlineKeyboardButton(text="200 ⭐", callback_data="stars_200")],
        [InlineKeyboardButton(text="500 ⭐", callback_data="stars_500")],
        [InlineKeyboardButton(text="1000 ⭐", callback_data="stars_1000")],
        [InlineKeyboardButton(text="10000 ⭐", callback_data="stars_10000")],
        [InlineKeyboardButton(text="📝 Boshqa miqdor", callback_data="stars_custom")]
    ])
    return keyboard

def ton_amount_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 TON", callback_data="ton_1")],
        [InlineKeyboardButton(text="5 TON", callback_data="ton_5")],
        [InlineKeyboardButton(text="10 TON", callback_data="ton_10")],
        [InlineKeyboardButton(text="20 TON", callback_data="ton_20")],
        [InlineKeyboardButton(text="50 TON", callback_data="ton_50")],
        [InlineKeyboardButton(text="100 TON", callback_data="ton_100")],
        [InlineKeyboardButton(text="📝 Boshqa miqdor", callback_data="ton_custom")]
    ])
    return keyboard

def premium_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 oy", callback_data="premium_1month")],
        [InlineKeyboardButton(text="3 oy", callback_data="premium_3months")],
        [InlineKeyboardButton(text="6 oy", callback_data="premium_6months")],
        [InlineKeyboardButton(text="12 oy", callback_data="premium_12months")]
    ])
    return keyboard

def recipient_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Oʻzimga", callback_data="recipient_self")],
        [InlineKeyboardButton(text="📝 Boshqa username", callback_data="recipient_other")]
    ])
    return keyboard

def information_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Rasmiy Kanalimiz", url="https://t.me/MyNewProfit")],
        [InlineKeyboardButton(text="💬 Savdo Guruhimiz", url="https://t.me/PentagonForum")],
        [InlineKeyboardButton(text="👨‍💼 Admen", url="https://t.me/ibrokhim_717")],
        [InlineKeyboardButton(text="👨‍💻 Dasturchi", url="https://t.me/MamurZokirov")]
    ])
    return keyboard

def admin_menu():
    # Admin menu is now fully managed in admin_panel.py
    return None

# TON Settings Callbacks and state handlers have been moved to admin_panel.py

# Handlers
from utils import get_required_channels

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Parse deep-link payload (e.g., /start ref_12345, /start 12345, /start 12345_stars, /start 12345_uc)
    payload = None
    referrer_id = None
    referral_type = "ton"  # Default referral type
    
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2:
            payload = parts[1].strip()
            
            # Check if it's a referral link
            if payload.startswith('ref_'):
                # Legacy format: ref_12345 or ref_HASH
                try:
                    ref_part = payload.replace('ref_', '')
                    if ref_part.isdigit():
                        referrer_id = int(ref_part)
                    else:
                        # Try to find user by referral code (new format: ref_HASH)
                        from referral import get_user_by_referral_code
                        user_by_code = get_user_by_referral_code(ref_part)
                        if user_by_code:
                            referrer_id = user_by_code[0] # user_id is the first column
                except Exception as e:
                    print(f"Error resolving referral: {e}")
            elif payload.isdigit():
                # New format: 12345 (TON referral)
                referrer_id = int(payload)
                referral_type = "ton"
            elif '_' in payload:
                # New format: 12345_stars or 12345_uc
                parts = payload.split('_')
                if len(parts) == 2 and parts[0].isdigit():
                    referrer_id = int(parts[0])
                    referral_type = parts[1]  # "stars" or "uc"
                    
    except Exception as e:
        print(f"Error parsing payload: {e}")

    # Ensure user exists first
    try:
        # Pass referrer_id to create_user
        # It will only be stored if the user is new
        create_user(user_id, message.from_user.username, message.from_user.full_name, referrer_id)
    except Exception as e:
        print(f"Error creating user: {e}")
    
    # Block banned users
    if is_user_banned(user_id):
        await message.answer(
            "🚫 *Siz botdan foydalanishdan banlangansiz!*\n\n📝 *Iltimos, admin bilan bog'laning.*",
            parse_mode="Markdown"
        )
        return
    
    # Handle promo redemption if payload provided
    if payload and payload.startswith("promo_"):
        code = payload.replace("promo_", "", 1)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            # Check code
            cursor.execute('SELECT bonus_amount, usage_limit, used_count, expires_at FROM promo_codes WHERE code = ?', (code,))
            row = cursor.fetchone()
            if not row:
                await message.answer("❌ *Promokod topilmadi!*", parse_mode="Markdown")
            else:
                bonus, limit, used, expires_at = row
                # Check expiry if set
                if expires_at is not None:
                    cursor.execute('SELECT datetime(?) <= datetime("now")', (expires_at,))
                    expired = cursor.fetchone()[0]
                    if expired:
                        await message.answer("❌ *Promokod muddati tugagan!*", parse_mode="Markdown")
                        conn.close()
                        return
                # Check already redeemed by this user
                cursor.execute('SELECT 1 FROM promo_redemptions WHERE user_id = ? AND code = ?', (user_id, code))
                if cursor.fetchone():
                    await message.answer("ℹ️ *Siz bu promokodni allaqachon ishlatgansiz.*", parse_mode="Markdown")
                elif used >= limit:
                    await message.answer("❌ *Promokod ishlatilish cheklami tugagan!*", parse_mode="Markdown")
                else:
                    # Atomic apply: insert redemption, add balance, increment used_count
                    try:
                        cursor.execute('INSERT INTO promo_redemptions (user_id, code) VALUES (?, ?)', (user_id, code))
                        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bonus, user_id))
                        cursor.execute('UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?', (code,))
                        conn.commit()
                        await message.answer(
                            f"✅ *Promokod muvaffaqiyatli qabul qilindi!*\n\n💰 *Bonus:* {bonus:,.0f} so'm balansingizga qo'shildi.",
                            parse_mode="Markdown"
                        )
                    except sqlite3.IntegrityError:
                        # Unique(user_id, code) violation (race)
                        conn.rollback()
                        await message.answer("ℹ️ *Siz bu promokodni allaqachon ishlatgansiz.*", parse_mode="Markdown")
        finally:
            conn.close()
    
    # Get all channels (config + DB)
    channels = await get_required_channels()
    
    if not channels:
        # No channels required, show main menu directly
        await message.answer(
            "🌟 *Asosiy menuga xush kelibsiz!*",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        return
    
    # Check if user is already subscribed to all required channels
    all_subscribed = True
    channels_to_sub = []
    for channel_id, channel_name in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ('left', 'kicked'):
                all_subscribed = False
                channels_to_sub.append((channel_id, channel_name))
        except Exception as e:
            logging.error(f"Error checking channel {channel_id}: {e}")
            all_subscribed = False
            channels_to_sub.append((channel_id, channel_name))
            
    if all_subscribed:
        # Check if user has already passed captcha
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT captcha_passed FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == 1:
            # User already passed captcha, show main menu directly
            # Track referral if applicable
            if referrer_id:
                try:
                    res = await track_referral_new(bot, user_id, referrer_id, referral_type)
                    success = res[0]
                    actual_referrer_id = res[2] if len(res) > 2 else None
                    
                    if success and actual_referrer_id:
                        bonus_amount = get_referral_bonus_by_type(referral_type)
                        bonus_text = get_referral_bonus_text(referral_type, bonus_amount)
                        await bot.send_message(
                            actual_referrer_id,
                            f"👥 *Yangi referal qo'shildi!*\n\n"
                            f"🎉 Tabriklaymiz! Sizning taklif havolangiz orqali yangi foydalanuvchi obuna bo'ldi!\n"
                            f"{bonus_text}",
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    logging.error(f"Failed to track referral: {e}")
            
            await message.answer(
                "🌟 *Asosiy menuga xush kelibsiz!*",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        else:
            # New user, show captcha
            # Generate and send captcha
            captcha_image, captcha_text = generate_captcha_image()
            
            # Store captcha answer in FSM state
            await state.set_state(CaptchaState.waiting_for_captcha)
            await state.update_data(captcha_answer=captcha_text, referrer_id=referrer_id, referral_type=referral_type)
            
            # Send captcha image
            await message.answer_photo(
                photo=types.BufferedInputFile(captcha_image.getvalue(), filename="captcha.png"),
                caption="🔐 *Iltimos, suratdagi sonlarni kiriting:*\n\n"
                       "Bu botning xavfsizligi uchun kerak. Iltimos, yuqoridagi rasmga chiqqan 4 xonali sonni kiriting.",
                parse_mode="Markdown"
            )
    else:
        # Show subscription requirements
        keyboard = []
        for channel_id, channel_name in channels_to_sub:
            url = f"https://t.me/{str(channel_id).replace('@', '')}"
            keyboard.append([InlineKeyboardButton(text=f"➕ {channel_name}", url=url)])
        
        # Add a check button with the referrer_id if present
        check_data = f"check_sub_{referrer_id}" if referrer_id else "check_sub"
        keyboard.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=check_data)])
        
        await message.answer(
            "⚠️ *Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz shart:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

@dp.callback_query(F.data.startswith("check_sub"))
async def check_subscription_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # Extract referrer_id from callback data if present
    data_parts = callback.data.split("_")
    referrer_id = None
    if len(data_parts) > 2 and data_parts[2].isdigit():
        referrer_id = int(data_parts[2])
    
    channels = await get_required_channels()
    all_subscribed = True
    not_subscribed = []
    
    for channel_id, channel_name in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ('left', 'kicked'):
                all_subscribed = False
                not_subscribed.append((channel_id, channel_name))
        except Exception as e:
            logging.error(f"Error checking channel {channel_id}: {e}")
            all_subscribed = False
            not_subscribed.append((channel_id, channel_name))
            
    if all_subscribed:
        # Award referral bonus if applicable
        res = await track_referral(bot, user_id, referrer_id)
        success = res[0]
        result_msg = res[1]
        actual_referrer_id = res[2] if len(res) > 2 else None
        
        if success and actual_referrer_id:
            try:
                bonus_amount = get_referral_bonus()
                await bot.send_message(
                    actual_referrer_id,
                    f"👥 *Yangi referal qo'shildi!*\n\n"
                    f"🎉 Tabriklaymiz! Sizning taklif havolangiz orqali yangi foydalanuvchi obuna bo'ldi!\n"
                    f"💰 Sizga {bonus_amount} TON bonus qo'shildi.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Failed to notify referrer {actual_referrer_id}: {e}")
        
        await callback.message.edit_text(
            "✅ *Rahmat! Barcha kanallarga obuna bo'lingan.*",
            parse_mode="Markdown"
        )
        await callback.message.answer(
            "🌟 *Asosiy menuga xush kelibsiz!*",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    else:
        await callback.answer("⚠️ Iltimos, barcha kanallarga obuna bo'ling!", show_alert=True)

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_general(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.message.edit_text("🚫 *Siz botdan foydalanishdan banlangansiz!*", parse_mode="Markdown")
        return
    
    channels = await get_required_channels()
    if not channels:
        await callback.message.edit_text("✅ Obuna tasdiqlandi!\n\n🌟 *Asosiy menuga xush kelibsiz!*", parse_mode="Markdown", reply_markup=main_menu())
        return
    
    all_subscribed = True
    for channel_id, channel_name in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ('left', 'kicked'):
                all_subscribed = False
                break
        except Exception as e:
            logging.error(f"Error checking channel {channel_id}: {e}")
            all_subscribed = False
            break
    
    if all_subscribed:
        await callback.message.edit_text("✅ Obuna tasdiqlandi!\n\n🌟 *Asosiy menuga xush kelibsiz!*", parse_mode="Markdown", reply_markup=main_menu())
    else:
        await callback.answer("⚠️ Iltimos, barcha kanallarga obuna bo'ling!", show_alert=True)


@dp.callback_query(F.data == "stars_purchase")
async def stars_purchase(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    # Send new photo message and delete old text message
    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=STARS_GIFT_IMAGE,
            caption="⭐ *Stars miqdorini tanlang:*",
            parse_mode="Markdown",
            reply_markup=stars_amount_keyboard()
        )
    except Exception as e:
        logging.error(f"Error sending photo: {e}")
        await callback.message.answer(
            text="⭐ *Stars miqdorini tanlang:*",
            parse_mode="Markdown",
            reply_markup=stars_amount_keyboard()
        )

@dp.callback_query(F.data.startswith("stars_"))
async def stars_amount_selected(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    amount = callback.data.split("_")[1]
    
    if amount == "custom":
        await callback.message.edit_text(
            text="📝 Qancha Stars sotib olmoqchisiz?\n\n"
                 "Iltimos, miqdorni kiriting (masalan: 500):"
        )
        await state.set_state(StarsPurchaseState.amount)
        await state.update_data(purchase_type="stars")
    else:
        stars_count = int(amount)
        price = get_price("stars")
        total_price = stars_count * price
        
        await state.set_state(StarsPurchaseState.recipient)
        await state.update_data(
            purchase_type="stars",
            stars_count=stars_count,
            total_price=total_price
        )
        
        caption_text = (f"⭐ *{stars_count} ta stars*\n"
                        f"💰 *Narxi: {total_price:,} so'm*\n\n"
                        f"👤 *Qabul qiluvchini tanlang:*")
        if callback.message.content_type == types.ContentType.PHOTO:
            await callback.message.edit_caption(
                caption=caption_text,
                parse_mode="Markdown",
                reply_markup=recipient_keyboard()
            )
        else:
            await callback.message.edit_text(
                text=caption_text,
                parse_mode="Markdown",
                reply_markup=recipient_keyboard()
            )

@dp.callback_query(F.data == "recipient_self")
async def recipient_self(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    data = await state.get_data()
    username = callback.from_user.username
    user_id = callback.from_user.id
    # Ensure user exists
    try:
        create_user(user_id, callback.from_user.username, callback.from_user.full_name)
    except Exception:
        pass
    
    # Prepare purchase info - check if purchase_type exists
    purchase_type = data.get('purchase_type', 'stars')  # Default to stars if not set
    
    if purchase_type == 'stars':
        # Show processing message first
        await callback.message.edit_text(
            "🔄 *Buyurtma bajarilmoqda...*\n\n"
            f"⭐ Miqdori: {data['stars_count']} ⭐\n"
            f"👤 Qabul qiluvchi: @{username}\n"
            f"💰 Narxi: {data['total_price']:,} so'm\n\n"
            "⏳ Iltimos, biroz kutib turing...",
            parse_mode="Markdown"
        )
        
        # Use auto_assign_stars for automatic purchase via PixyAPI
        stars_count = data['stars_count']
        success, result = await auto_assign_stars(
            user_id=user_id,
            stars_amount=stars_count,
            admin_id=None,  # Self-purchase
            use_api=True,
            recipient_username=username
        )
        
        if success:
            msg_text = (
                f"✅ Stars muvaffaqiyatli sotib olindi!\n\n"
                f"⭐ Miqdori: {stars_count} ⭐\n"
                f"👤 Qabul qiluvchi: @{username}\n"
                f"💰 Narxi: {data['total_price']:,} so'm\n\n"
                f"🌐 Buyurtma PixyAPI orqali amalga oshirildi.\n"
                f"📱 Stars tez orada @{username} ga tushadi."
            )
        else:
            # Show error message (no refund needed - auto_assign_stars handles it)
            msg_text = (
                f"❌ Stars sotib olish xatoligi!\n\n"
                f"⭐ Miqdori: {stars_count} ⭐\n"
                f"💰 Narxi: {data['total_price']:,} so'm\n\n"
                f"🔄 Xatolik: {result}\n\n"
                f"💰 Pul qaytarildi.\n"
                f"🔧 Iltimos, admin bilan bog'laning."
            )
        
        if callback.message.content_type == types.ContentType.PHOTO:
            await callback.message.edit_caption(caption=msg_text, reply_markup=main_menu())
        else:
            await callback.message.edit_text(msg_text, reply_markup=main_menu())
        
        await state.clear()
        return
    elif data['purchase_type'] == 'premium':
        # Extract months from period string
        if 'month' in data['period']:
            product_id = int(data['period'].replace('months', '').replace('month', ''))
        else:
            product_id = 1
        product_name = data['period_name']
    else:
        product_id = 0
        product_name = "Noma'lum mahsulot"
    
    # Check balance and reserve funds atomically
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?',
            (data['total_price'], user_id, data['total_price'])
        )
        if cursor.rowcount == 0:
            conn.rollback()
            conn.close()
            msg_text = "❌ *Hisobingizda yetarli mablag' mavjud emas!*\n\n💰 *Hisobni to'ldirish bo'limiga o'ting:*"
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Hisobni to'ldirish", callback_data="my_account")]
            ])
            
            if callback.message.content_type == types.ContentType.PHOTO:
                await callback.message.edit_caption(caption=msg_text, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await callback.message.edit_text(msg_text, parse_mode="Markdown", reply_markup=reply_markup)
            
            await state.clear()
            return
        # Balance reserved, create purchase request
        cursor.execute('''
            INSERT INTO purchase_requests (user_id, product_type, product_id, price)
            VALUES (?, ?, ?, ?)
        ''', (user_id, data['purchase_type'], product_id, data['total_price']))
        purchase_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    
    await state.clear()
    
    msg_text = (
        f"🆕 *Xarid so'rovi yuborildi!*\n\n"
        f"📦 *Mahsulot:* {product_name}\n"
        f"👤 *Qabul qiluvchi: @{username}*\n"
        f"💰 *Narxi: {data['total_price']:,} so'm*\n\n"
        f"🔄 *Admin tasdiqlashini kuting...*\n"
        f"⏱ *Tasdiqlash 5-30 daqiqa ichida amalga oshiriladi.*"
    )
    
    if callback.message.content_type == types.ContentType.PHOTO:
        await callback.message.edit_caption(caption=msg_text, parse_mode="Markdown")
    else:
        await callback.message.edit_text(msg_text, parse_mode="Markdown")
    
    # Send purchase request to admins
    await send_purchase_to_admins(purchase_id, user_id, data['purchase_type'], product_id, data['total_price'])

@dp.callback_query(F.data == "recipient_other")
async def recipient_other(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    if callback.message.photo:
        await callback.message.edit_caption(
            caption="👤 *Qabul qiluvchi username'ini kiriting (@ belgisiz):*",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            "👤 *Qabul qiluvchi username'ini kiriting (@ belgisiz):*",
            parse_mode="Markdown"
        )
    await state.set_state(StarsPurchaseState.recipient)

@dp.message(StarsPurchaseState.amount)
async def process_stars_amount(message: types.Message, state: FSMContext):
    """Process custom stars amount input"""
    if is_user_banned(message.from_user.id):
        await message.answer("🚫 Siz banlangansiz!")
        await state.clear()
        return
    
    try:
        stars_count = int(message.text.strip())
        if stars_count < 50:
            await message.answer("❌ Minimal miqdor 50 Stars!")
            return
        
        price = get_price("stars")
        total_price = stars_count * price
        
        # Check user balance
        user_balance = get_user_balance(message.from_user.id)
        if user_balance < total_price:
            await message.answer(
                f"❌ Balansingiz yetarli emas!\n\n"
                f"💰 Kerak: {total_price:,} so'm\n"
                f"💳 Sizda: {user_balance:,} so'm"
            )
            return
        
        await state.set_state(StarsPurchaseState.recipient)
        await state.update_data(
            purchase_type="stars",
            stars_count=stars_count,
            total_price=total_price
        )
        
        await message.answer(
            "👤 Qabul qiluvchi username ni kiriting:\n\n"
            "Iltimos, qabul qiluvchi Telegram usernameni kiriting:\n"
            "Masalan: @username"
        )
        return
        
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri miqdorni kiriting!\n\nMasalan: 500")
        return

@dp.message(StarsPurchaseState.recipient)
async def process_recipient(message: types.Message, state: FSMContext):
    logging.info(f"process_recipient called: user_id={message.from_user.id}, username={message.text}")
    
    if is_user_banned(message.from_user.id):
        await message.answer("🚫 Siz banlangansiz!")
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    data = await state.get_data()
    user_id = message.from_user.id
    
    logging.info(f"State data: {data}")
    logging.info(f"Username: {username}, User ID: {user_id}")
    
    # Validate username
    if not username:
        await message.answer("❌ Username kiritish shart!\n\nIltimos, qabul qiluvchi usernameni kiriting:")
        return
    
    # Ensure user exists
    try:
        create_user(user_id, message.from_user.username, message.from_user.full_name)
    except Exception:
        pass
    
    # Prepare purchase info
    purchase_type = data.get('purchase_type', 'stars')  # Default to stars if not set
    
    if purchase_type == 'stars':
        # Show processing message first (send new message, don't edit)
        await message.answer(
            "🔄 Buyurtma bajarilmoqda...\n\n"
            f"⭐ Miqdori: {data['stars_count']} ⭐\n"
            f"👤 Qabul qiluvchi: @{username}\n"
            f"💰 Narxi: {data['total_price']:,} so'm\n\n"
            "⏳ Iltimos, biroz kutib turing..."
        )
        
        # Use auto_assign_stars for automatic purchase via PixyAPI
        stars_count = data['stars_count']
        success, result = await auto_assign_stars(
            user_id=user_id,
            stars_amount=stars_count,
            admin_id=None,  # Self-purchase
            use_api=True,
            recipient_username=username
        )
        
        if success:
            msg_text = (
                f"✅ Stars muvaffaqiyatli sotib olindi!\n\n"
                f"⭐ Miqdori: {stars_count} ⭐\n"
                f"👤 Qabul qiluvchi: @{username}\n"
                f"💰 Narxi: {data['total_price']:,} so'm\n\n"
                f"🌐 Buyurtma PixyAPI orqali amalga oshirildi.\n"
                f"📱 Stars tez orada @{username} ga tushadi."
            )
        else:
            # Show error message (no refund needed - auto_assign_stars handles it)
            msg_text = (
                f"❌ Stars sotib olish xatoligi!\n\n"
                f"⭐ Miqdori: {stars_count} ⭐\n"
                f"👤 Qabul qiluvchi: @{username}\n"
                f"💰 Narxi: {data['total_price']:,} so'm\n\n"
                f"🔄 Xatolik: {result}\n\n"
                f"💰 Pul qaytarildi.\n"
                f"🔧 Iltimos, admin bilan bog'laning."
            )
        
        await message.answer(msg_text, reply_markup=main_menu())
        await state.clear()
        return
    elif data['purchase_type'] == 'premium':
        # Extract months from period string (e.g., "1month" -> 1, "3months" -> 3)
        if 'month' in data['period']:
            product_id = int(data['period'].replace('months', '').replace('month', ''))
        else:
            product_id = 1  # default to 1 month
    else:
        product_id = 0
    
    # Check balance and reserve funds atomically
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?',
            (data['total_price'], user_id, data['total_price'])
        )
        if cursor.rowcount == 0:
            conn.rollback()
            conn.close()
            await message.answer(
                "❌ *Hisobingizda yetarli mablag' mavjud emas!*\n\n"
                "💰 *Hisobni to'ldirish bo'limiga o'ting:*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Hisobni to'ldirish", callback_data="my_account")]
                ])
            )
            await state.clear()
            return
        # Balance reserved, create purchase request
        cursor.execute('''
            INSERT INTO purchase_requests (user_id, product_type, product_id, price)
            VALUES (?, ?, ?, ?)
        ''', (user_id, data['purchase_type'], product_id, data['total_price']))
        purchase_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    
    await state.clear()
    
    product_name = f"{product_id:,} Stars" if data['purchase_type'] == 'stars' else data['period_name']
    
    await message.answer(
        f"🆕 *Xarid so'rovi yuborildi!*\n\n"
        f"📦 *Mahsulot:* {product_name}\n"
        f"👤 *Qabul qiluvci: @{username}*\n"
        f"💰 *Narxi: {data['total_price']:,} so'm*\n\n"
        f"🔄 *Admin tasdiqlashini kuting...*\n"
        f"⏱ *Tasdiqlash 5-30 daqiqa ichida amalga oshiriladi.*",
        parse_mode="Markdown"
    )
    
    # Send purchase request to admins
    await send_purchase_to_admins(purchase_id, user_id, data['purchase_type'], product_id, data['total_price'])

@dp.callback_query(F.data == "confirm_payment")
async def confirm_payment(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user and user[3] >= data['total_price']:  # balance check
        # Process payment
        update_balance(user_id, -data['total_price'])
        
        # Record transaction
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, stars, status) 
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, data['purchase_type'], data['total_price'], data['stars_count'], 'completed'))
        conn.commit()
        conn.close()
        
        if getattr(callback.message, "text", None):
            await callback.message.edit_text(
                f"✅ *To'lov muvaffaqiyatli amalga oshirildi!*\n\n"
                f"⭐ *{data['stars_count']} ta stars @{data['recipient']} ga yuborildi!*",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        else:
            await callback.message.edit_caption(
                f"✅ *To'lov muvaffaqiyatli amalga oshirildi!*\n\n"
                f"⭐ *{data['stars_count']} ta stars @{data['recipient']} ga yuborildi!*",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
    else:
        await callback.message.edit_text(
            "❌ *Hisobingizda yetarli mablag' mavjud emas!*\n\n"
            "💰 *Hisobni to'ldirish bo'limiga o'ting:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Hisobni to'ldirish", callback_data="my_account")]
            ])
        )
    
    await state.clear()

# TON purchase handlers are now in ton_purchase.py

@dp.callback_query(F.data == "premium_purchase")
async def premium_purchase(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    user_id = callback.from_user.id
    try:
        create_user(user_id, callback.from_user.username, callback.from_user.full_name)
    except Exception:
        pass
    
    await callback.message.edit_text(
        "👑 *Premium obuna muddatini tanlang:*",
        parse_mode="Markdown",
        reply_markup=premium_keyboard()
    )

@dp.callback_query(F.data.regexp(r'^premium_(1month|3months|6months|12months)$'))
async def premium_selected(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    # Extract period from callback data (e.g., "1month" from "premium_1month")
    period = callback.data.split("_", 1)[1]  # Split on first underscore only
    price_key = f"premium_{period}"
    
    # Get price from database or fallback to defaults
    price = get_price(price_key)
    
    period_names = {
        "1month": "1 oy",
        "3months": "3 oy",
        "6months": "6 oy",
        "12months": "12 oy"
    }
    
    period_name = period_names[period]
    months = int(period.replace('months', '').replace('month', ''))
    
    # Check user balance
    user_balance = get_user_balance(user_id)
    
    if user_balance >= price:
        # Save purchase data to state
        await state.update_data(
            period=period,
            period_name=period_name,
            months=months,
            price=price,
            user_balance=user_balance
        )
        
        # Ask for recipient username
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 O'zimga", callback_data="premium_recipient_self")],
            [InlineKeyboardButton(text="📝 Boshqa username", callback_data="premium_recipient_other")]
        ])
        
        await callback.message.edit_text(
            f"👑 *Premium obuna sotib olish*\n\n"
            f"📦 *Mahsulot:* {period_name} Premium\n"
            f"💰 *Narxi:* {price:,} so'm\n"
            f"💳 *Balansingiz:* {user_balance:,} so'm\n\n"
            f"👤 *Qabul qiluvchini tanlang:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        # Set state to wait for recipient selection
        await state.set_state(PremiumPurchaseState.waiting_for_recipient)
    else:
        # Insufficient balance - offer to top up
        needed_amount = price - user_balance
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Hisobni to'ldirish", callback_data="add_balance")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
        ])
        
        await callback.message.edit_text(
            f"❌ *Balansingizda yetarli mablag' yo'q!*\n\n"
            f"👑 *Mahsulot:* {period_name} Premium\n"
            f"💰 *Narxi:* {price:,} so'm\n"
            f"💳 *Balansingiz:* {user_balance:,} so'm\n"
            f"➕ *Kerakli summa:* {needed_amount:,} so'm\n\n"
            f"💳 *Iltimos, avval hisobni to'ldiring!*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

@dp.callback_query(F.data == "premium_recipient_self")
async def premium_recipient_self(callback: types.CallbackQuery, state: FSMContext):
    """Process premium purchase for self"""
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    # Check if we're in the correct state
    current_state = await state.get_state()
    if current_state != PremiumPurchaseState.waiting_for_recipient:
        await callback.answer("Xatolik! Iltimos, qaytadan urinib ko'ring.", show_alert=True)
        await state.clear()
        return
    
    user_id = callback.from_user.id
    username = callback.from_user.username
    full_name = callback.from_user.full_name
    
    data = await state.get_data()
    period = data.get('period')
    period_name = data.get('period_name')
    months = data.get('months')
    price = data.get('price')
    user_balance = data.get('user_balance')
    
    if not username:
        await callback.message.edit_text(
            f"❌ Username talab qilinadi!\n\n"
            f"📝 Iltimos, Telegram hisobingizda username o'rnating va qayta urinib ko'ring.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    # Show processing message
    await callback.message.edit_text(
        f"🔄 Premium sotib olinmoqda...\n\n"
        f"👑 Mahsulot: {period_name} Premium\n"
        f"👤 Qabul qiluvchi: @{username}\n"
        f"💰 Narxi: {price:,} so'm\n\n"
        f"⏳ Iltimos, biroz kutib turing..."
    )
    
    # Process premium purchase (API call first, then deduct balance)
    await process_premium_purchase_flow(user_id, months, price, username, full_name, period_name, user_balance, callback, state)

@dp.callback_query(F.data == "premium_recipient_other")
async def premium_recipient_other(callback: types.CallbackQuery, state: FSMContext):
    """Ask for recipient username"""
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    # Check if we're in the correct state
    current_state = await state.get_state()
    if current_state != PremiumPurchaseState.waiting_for_recipient:
        await callback.answer("Xatolik! Iltimos, qaytadan urinib ko'ring.", show_alert=True)
        await state.clear()
        return
    
    await callback.message.edit_text(
        "👤 *Qabul qiluvchi username'ini kiriting (@ belgisiz):*\n\n"
        "📝 *Misol:* `username` yoki `testuser`",
        parse_mode="Markdown"
    )
    await state.set_state(PremiumPurchaseState.recipient_username)

@dp.message(PremiumPurchaseState.recipient_username)
async def process_premium_recipient_username(message: types.Message, state: FSMContext):
    """Process premium recipient username"""
    if is_user_banned(message.from_user.id):
        await message.answer("🚫 *Siz banlangansiz!*", parse_mode="Markdown")
        await state.clear()
        return
    
    # Check if we're in the correct state
    current_state = await state.get_state()
    if current_state != PremiumPurchaseState.recipient_username:
        await message.answer("❌ *Xatolik! Iltimos, premium sotib olishni qaytadan boshlang.*", parse_mode="Markdown")
        await state.clear()
        return
    
    user_id = message.from_user.id
    recipient_username = message.text.strip().lstrip('@')
    full_name = message.from_user.full_name
    
    data = await state.get_data()
    period = data.get('period')
    period_name = data.get('period_name')
    months = data.get('months')
    price = data.get('price')
    user_balance = data.get('user_balance')
    
    # Validate username format
    import re
    username_pattern = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{2,31}$')
    if not recipient_username or not username_pattern.match(recipient_username):
        await message.answer(
            f"❌ *Noto'g'ri username formati!*\n\n"
            f"📝 *Username quyidagi qoidalarga javob berishi kerak:*\n"
            f"• Harf bilan boshlanishi kerak\n"
            f"• 3-31 belgi uzunligida bo'lishi kerak\n"
            f"• Faqat harflar, raqamlar va _ belgisi bo'lishi mumin\n\n"
            f"👤 *Qabul qiluvchi username'ini qayta kiriting:*",
            parse_mode="Markdown"
        )
        return
    
    # Reserve balance first (deduct from user account)
    update_user_balance(user_id, -price)
    
    await message.answer(
        f"🔄 *Premium sotib olinmoqda...*\n\n"
        f"👑 *Mahsulot:* {period_name} Premium\n"
        f"👤 *Qabul qiluvchi:* @{recipient_username}\n"
        f"💰 *Narxi:* {price:,} so'm\n"
        f"💳 *Balansingiz:* {user_balance - price:,} so'm\n\n"
        f"⏳ Iltimos, biroz kutib turing...",
        parse_mode="Markdown"
    )
    
    # Process premium purchase
    await process_premium_purchase_flow(user_id, months, price, recipient_username, full_name, period_name, user_balance, None, message, state)

async def process_premium_purchase_flow(user_id: int, months: int, price: float, recipient_username: str, 
                                       buyer_full_name: str, period_name: str, user_balance: float,
                                       callback: types.CallbackQuery = None, message: types.Message = None, state: FSMContext = None):
    """Process premium purchase flow with admin approval for 1-month, PixyAPI for others"""
    try:
        # Show processing message first
        processing_msg = (
            "🔄 *Buyurtma bajarilmoqda...*\n\n"
            f"👑 Mahsulot: {period_name} Premium\n"
            f"👤 Qabul qiluvchi: @{recipient_username}\n"
            f"💰 Narxi: {price:,} so'm\n\n"
            "⏳ Iltimos, biroz kutib turing..."
        )
        
        if callback:
            await callback.message.edit_text(processing_msg, parse_mode="Markdown")
        else:
            await message.answer(processing_msg, parse_mode="Markdown")
        
        # For 1-month premium, use admin approval instead of PixyAPI
        if months == 1:
            # Create purchase request for admin approval
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO purchase_requests (user_id, product_type, product_id, price, status, details)
                VALUES (?, ?, ?, ?, 'pending', ?)
            ''', (user_id, 'premium_1month', months, price, recipient_username))
            purchase_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Send notification to user
            success_text = (
                f"✅ *1 oylik Premium so'rovi yuborildi!*\n\n"
                f"📋 So'rov ID: #{purchase_id}\n"
                f"👑 *Mahsulot:* {period_name} Premium\n"
                f"👤 *Qabul qiluvchi:* @{recipient_username}\n"
                f"💰 *Narxi:* {price:,} so'm\n"
                f"💳 *Balansingiz:* {user_balance - price:,} so'm\n\n"
                f"⏳ *Holati: Admin tasdiqlashini kutishda*\n\n"
                f"👤 Admin tasdiqlagandan so'ng Premium beriladi."
            )
            
            # Send notification to admins
            try:
                await send_premium_admin_notification(user_id, recipient_username, price, str(purchase_id))
                logging.info(f"Admin notification sent for premium purchase ID: {purchase_id}")
            except Exception as e:
                logging.error(f"Failed to send admin notification for premium purchase ID {purchase_id}: {e}")
                # Fallback: send simple notification to admins
                try:
                    user = get_user(user_id)
                    buyer_username = f"@{user[1]}" if user and user[1] else f"ID: {user_id}"
                    buyer_full_name = user[2] if user else "Noma'lum"
                    
                    text = f"🆕 *1 oylik Premium so'rovi!*\n\n"
                    text += f"👤 *Sotib oluvchi:* {buyer_full_name} ({buyer_username})\n"
                    text += f"🎯 *Qabul qiluvchi:* @{recipient_username}\n"
                    text += f"💰 *Narxi:* {price:,} so'm\n"
                    text += f"🆔 *So'rov ID: #{purchase_id}\n"
                    text += f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    text += "⚡ *Tasdiqlash uchun admin paneliga o'ting!*"
                    
                    for admin_id in get_all_admins():
                        try:
                            await bot.send_message(admin_id, text, parse_mode="Markdown")
                        except Exception as e2:
                            logging.error(f"Failed to send fallback notification to admin {admin_id}: {e2}")
                except Exception as e2:
                    logging.error(f"Failed to send fallback notification: {e2}")
            
            if callback:
                await callback.message.edit_text(success_text, parse_mode="Markdown", reply_markup=main_menu())
            else:
                await message.answer(success_text, parse_mode="Markdown", reply_markup=main_menu())
            
            await state.clear() if state else None
            return
        
        # For other premium durations (3, 6, 12 months), use PixyAPI
        use_pixy_api = True  # PixyAPI supports all premium durations
        
        if use_pixy_api:
            try:
                # Remove @ if present
                clean_username = recipient_username.lstrip('@')
                
                # Generate order ID
                import uuid
                order_id = f"PIXY-PREMIUM-{uuid.uuid4().hex[:8].upper()}"
                
                # Use enhanced PixyAPI manager with retry logic
                api_response = await pixy_manager.safe_buy_premium(
                    username=clean_username,
                    months=months,
                    order_id=order_id,
                    show_sender=False
                )
                
                # Check if API call was successful
                success, message = await handle_pixy_error(api_response, "Premium purchase")
                
                if success:
                    # Extract order_id from various possible response formats
                    final_order_id = (
                        api_response.get("order_id") or 
                        order_id or  # Use our generated order_id as fallback
                        api_response.get("id") or 
                        api_response.get("transaction_id") or
                        api_response.get("data", {}).get("order_id") or
                        None
                    )
                    
                    # API successful - process the purchase
                    success, result = await process_premium_purchase(
                        user_id, months, price, final_order_id, 
                        None, buyer_full_name, use_api=True,
                        recipient_username=recipient_username
                    )
                    
                    if success:
                        success_msg = (
                            f"✅ *Muvaffaqiyatli sotib olindi!*\n\n"
                            f"👑 *Mahsulot:* {period_name} Premium\n"
                            f"👤 *Qabul qiluvchi:* @{recipient_username}\n"
                            f"💰 *Narxi:* {price:,} so'm\n"
                            f"💳 *Yangi balans:* {user_balance - price:,} so'm\n"
                        )
                        if final_order_id:
                            success_msg += f"🆔 *Buyurtma raqami:* {final_order_id}\n\n"
                        success_msg += f"🎉 *Premium xususiyatlaridan foydalanishingiz mumkin!*"
                        
                        if callback:
                            await callback.message.edit_text(
                                success_msg,
                                parse_mode="Markdown",
                                reply_markup=main_menu()
                            )
                        else:
                            # This is from message handler, need to send new message
                            pass  # Will be handled by process_premium_purchase notification
                        
                        await state.clear() if state else None
                        return
                    else:
                        # Purchase processing failed - show error (no refund needed)
                        error_msg = f"❌ *Xatolik yuz berdi!*\n\n📝 *Tafsilot:* {result}\n\n💰 *Pul qaytarildi*"
                        if callback:
                            await callback.message.edit_text(error_msg, parse_mode="Markdown", reply_markup=main_menu())
                        else:
                            await message.answer(error_msg, parse_mode="Markdown", reply_markup=main_menu())
                        await state.clear() if state else None
                        return
                else:
                    # API failed - show error (no refund needed)
                    error_text = f"❌ *PixyAPI xatoligi!*\n\n📝 *Xatolik:* {message}\n\n💰 *Pul qaytarildi*\n\n🔧 *Iltimos, admin bilan bog'laning*"
                    if callback:
                        await callback.message.edit_text(error_text, parse_mode="Markdown", reply_markup=main_menu())
                    else:
                        await message.answer(error_text, parse_mode="Markdown", reply_markup=main_menu())
                    await state.clear() if state else None
                    return
                
            except ValueError as ve:
                # Username validation error (no refund needed)
                logging.error(f"Username validation error: {ve}")
                error_text = f"❌ *Username formati noto'g'ri!*\n\n📝 *Xatolik:* {str(ve)}\n\n💰 *Pul qaytarildi*\n\n🔧 *Iltimos, admin bilan bog'laning*"
                if callback:
                    await callback.message.edit_text(error_text, parse_mode="Markdown", reply_markup=main_menu())
                else:
                    await message.answer(error_text, parse_mode="Markdown", reply_markup=main_menu())
                await state.clear() if state else None
                return
            except Exception as e:
                # Critical error (no refund needed)
                logging.error(f"Critical error in premium purchase: {e}")
                error_text = f"❌ *Kritik xatolik yuz berdi!*\n\n📝 *Tafsilot:* {str(e)}\n\n💰 *Pul qaytarildi*\n\n🔧 *Iltimos, admin bilan bog'laning*"
                if callback:
                    await callback.message.edit_text(error_text, parse_mode="Markdown", reply_markup=main_menu())
                else:
                    await message.answer(error_text, parse_mode="Markdown", reply_markup=main_menu())
                await state.clear() if state else None
                return
        else:
            # Process locally (for 1 month - PixyAPI doesn't support it)
            success, result = await process_premium_purchase(
                user_id, months, price, None, 
                None, buyer_full_name, use_api=False,
                recipient_username=recipient_username
            )
            
            if success:
                success_msg = (
                    f"✅ *Muvaffaqiyatli sotib olindi!*\n\n"
                    f"👑 *Mahsulot:* {period_name} Premium\n"
                    f"👤 *Qabul qiluvchi:* @{recipient_username}\n"
                    f"💰 *Narxi:* {price:,} so'm\n"
                    f"💳 *Yangi balans:* {user_balance - price:,} so'm\n\n"
                    f"🎉 *Premium xususiyatlaridan foydalanishingiz mumkin!*"
                )
                if callback:
                    await callback.message.edit_text(success_msg, parse_mode="Markdown", reply_markup=main_menu())
                # process_premium_purchase already sends notification to user
                await state.clear() if state else None
                return
            else:
                # Refund balance if purchase processing failed
                update_user_balance(user_id, price)
                error_text = f"❌ *Xatolik yuz berdi!*\n\n📝 *Tafsilot:* {result}\n\n💰 *Pul qaytarildi*"
                if callback:
                    await callback.message.edit_text(error_text, parse_mode="Markdown", reply_markup=main_menu())
                else:
                    await message.answer(error_text, parse_mode="Markdown", reply_markup=main_menu())
                await state.clear() if state else None
                return
                
    except Exception as e:
        logging.error(f"Error in process_premium_purchase_flow: {e}")
        update_user_balance(user_id, price)
        error_text = f"❌ *Xatolik yuz berdi!*\n\n📝 *Tafsilot:* {str(e)}\n\n💰 *Pul qaytarildi*"
        if callback:
            await callback.message.edit_text(error_text, parse_mode="Markdown", reply_markup=main_menu())
        await state.clear() if state else None

@dp.callback_query(F.data == "my_account")
async def my_account(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    # Ensure user exists
    try:
        create_user(user_id, callback.from_user.username, callback.from_user.full_name)
    except Exception:
        pass
    user = get_user(user_id)
    
    balance = user[3] if user else 0
    stars_purchased = user[4] if user else 0
    premium_purchased = user[5] if user else 0
    
    # Calculate total Stars balance (purchased + referral)
    referral_stars = 0  # get_referral_stars_balance(user_id)
    total_stars = stars_purchased + referral_stars
    
    # Get TON balance and referral stats
    ton_balance = 0.0
    if user and len(user) > 6:  # Check if ton_balance column exists
        ton_balance = user[6] or 0.0
    
    # Get referral stats
    ref_stats = get_referral_stats(user_id)
    available_ton = ref_stats['available_ton']
    
    # Show only referral TON
    ton_balance_display = available_ton
    
    # Get referral links for different types
    bot_username = (await bot.get_me()).username
    ref_code = str(user_id)  # generate_referral_code(user_id)
    
    # New referral system with separate links
    ton_referral_link = f"https://t.me/{bot_username}?start={ref_code}_ton"
    stars_referral_link = f"https://t.me/{bot_username}?start={ref_code}_stars"
    
    # Get correct TON price from database (buy price)
    ton_price = get_ton_buy_price()
    
    # Get referral bonuses from settings
    from referral import get_referral_bonus_by_type
    ton_bonus = get_referral_bonus_by_type("ton")
    stars_bonus = get_referral_bonus_by_type("stars")
    
    text = (
        f"📊 🇭 🇮 🇸 🇴 🇧 🇮 🇳 🇬 🇮 🇿\n"
        f"👤 Foydalanuvchi\n"
        f"🔎 ID: {user_id}\n\n"
        f"💎 TON: {float(ton_balance_display):.3f} TON \n"
        f"⭐️ Stars: {total_stars:,} \n"
        f"💳 So'm balansi: {balance:,.0f} so'm\n\n"
        f"💎 TON referral havolasi:\n"
        f" 👉 {ton_referral_link}\n"
        f"Ushbu havola orqali kirgan do'stingiz uchun\n"
        f"{ton_bonus} TON beriladi.\n\n"
        f"⭐️ Stars referral havolasi:\n"
        f" 👉 {stars_referral_link}\n"
        f"Ushbu havola orqali kirgan dostingiz uchun sizga\n"
        f"{stars_bonus} STARS beriladi\n\n"
        f"🔄 Kurs: 1 TON = {ton_price:,.0f} so'm"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(text="💳 Hisobni to'ldirish", callback_data="add_balance"),
            InlineKeyboardButton(text="💰 Yechib olish", callback_data="withdrawal_menu")
        ],
        [
            InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")
        ]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data == "add_balance")
async def add_balance(callback: types.CallbackQuery, state: FSMContext):
    # Get active card from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT card_number, card_holder FROM cards WHERE is_active = 1 ORDER BY id DESC LIMIT 1')
    card = cursor.fetchone()
    conn.close()
    
    if card:
        card_number, card_holder = card
        await callback.message.edit_text(
            f"💳 *Hisobni to'ldirish uchun to'lov karta ma'lumotlari:*\n\n"
            f"📇 Karta raqami: `{card_number}`\n"
            f"👤 Karta egasi: {card_holder}\n\n"
            f"💰 *To'ldirish miqdorini kiriting (so'm):*",
            parse_mode="Markdown"
        )
    else:
        # Fallback to config
        await callback.message.edit_text(
            "💳 *To'ldirish miqdorini kiriting (so'm):*",
            parse_mode="Markdown"
        )
    
    await state.set_state(BalanceState.amount)

@dp.message(BalanceState.amount)
async def process_balance_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ *Miqdor musbat son bo'lishi kerak!*", parse_mode="Markdown")
            return
        
        await state.update_data(amount=amount)
        
        # Get active card from database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT card_number, card_holder FROM cards WHERE is_active = 1 ORDER BY id DESC LIMIT 1')
        card = cursor.fetchone()
        conn.close()
        
        if card:
            card_number, card_holder = card
            await message.answer(
                f"💳 *To'lov ma'lumotlari:*\n\n"
                f"📇 Karta raqami: `{card_number}`\n"
                f"👤 Karta egasi: {card_holder}\n"
                f"💰 Miqdor: {amount:,} so'm\n\n"
                f"To'lov qilgach, chek rasmini yuboring:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ To'lov qildim", callback_data="payment_made")],
                    [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
                ])
            )
        else:
            # Fallback to config
            await message.answer(
                f"💳 *To'lov ma'lumotlari:*\n\n"
                f"📇 Karta raqami: `{PAYMENT_CARD}`\n"
                f"👤 Karta egasi: {CARD_HOLDER}\n"
                f"💰 Miqdor: {amount:,} so'm\n\n"
                f"To'lov qilgach, chek rasmini yuboring:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ To'lov qildim", callback_data="payment_made")],
                    [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
                ])
            )
        
        await state.set_state(BalanceState.receipt)
        
    except ValueError:
        await message.answer("❌ *Iltimos, to'g'ri miqdorni kiriting!*", parse_mode="Markdown")

@dp.callback_query(F.data == "payment_made")
async def payment_made(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📸 *To'lov chekini yuboring:*",
        parse_mode="Markdown"
    )

@dp.message(BalanceState.receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data['amount']
    user_id = message.from_user.id
    
    # Save payment request for admin review
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payment_requests (user_id, amount, receipt) 
        VALUES (?, ?, ?)
    ''', (user_id, amount, message.photo[-1].file_id))
    payment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    await message.answer(
        "✅ *To'lov cheki qabul qilindi!*\n\n"
        "🔄 *To'lov tasdiqlash jarayoni 5-30 daqiqa ichida amalga oshiriladi.*\n"
        "💰 *Hisobingizga pul qo'shilgach xabar olasiz.*",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    
    # Send payment request to admins with inline buttons
    await send_payment_to_admins(payment_id, user_id, amount, message.photo[-1].file_id)
    
    await state.clear()

@dp.callback_query(F.data == "withdraw_money")
async def withdraw_money_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)
    balance = user[3] if user else 0
    
    # Get min withdrawal from settings
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'withdrawal_min'")
    res = cursor.fetchone()
    conn.close()
    withdrawal_min = 10000  # int(res[0]) if res else 50000
    
    if balance < withdrawal_min:
        await callback.answer(f"❌ Hisobingizda yetarli mablag' mavjud emas! Minimal yechish miqdori: {withdrawal_min:,} so'm", show_alert=True)
        return
        
    await callback.message.edit_text(
        f"💰 *Hisobingizdagi mablag'ni yechish*\n\n"
        f"💳 Balans: {balance:,.0f} so'm\n"
        f"📉 Minimal yechish: {withdrawal_min:,.0f} so'm\n\n"
        f"📝 *Yechmoqchi bo'lgan miqdorni kiriting:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="my_account")]
        ])
    )
    await state.set_state(WithdrawalStates.amount)

@dp.callback_query(F.data == "withdraw_all")
async def withdraw_all_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)
    balance = user[3] if user else 0
    
    # Get min withdrawal
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'withdrawal_min'")
    res = cursor.fetchone()
    conn.close()
    withdrawal_min = int(res[0]) if res else 50000
    
    if balance < withdrawal_min:
        await callback.answer(f"❌ Minimal yechish miqdori: {withdrawal_min:,} so'm", show_alert=True)
        return
        
    await state.update_data(amount=balance)
    await callback.message.edit_text(
        f"💰 *Barcha mablag'ni yechish:* {balance:,.0f} so'm\n\n"
        "💳 *Karta raqamini kiriting:*\n"
        "Masalan: `8600 1234 5678 9012`",
        parse_mode="Markdown"
    )
    await state.set_state(WithdrawalStates.card_details)

@dp.message(WithdrawalStates.amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(" ", ""))
        user_id = message.from_user.id
        
        # Get withdrawal type from state
        data = await state.get_data()
        withdrawal_type = data.get('withdrawal_type', 'uzs')  # Default to UZS
        max_amount = data.get('max_amount', float('inf'))
        
        # Validate based on withdrawal type
        if withdrawal_type == "stars":
            if amount < 1:
                await message.answer("❌ Minimal Stars yechish miqdori: 1 Stars")
                return
            if amount > max_amount:
                await message.answer(f"❌ Sizda yetarli Stars yo'q! Maksimal: {max_amount:,} Stars")
                return
                
            # Create Stars withdrawal request
            await create_stars_withdrawal_request(user_id, amount, state)
            
        elif withdrawal_type == "ton":
            # Validate TON amount
            if amount < 0.1:
                await message.answer("❌ Minimal TON yechish miqdori: 0.1 TON")
                return
            if amount > max_amount:
                await message.answer(f"❌ Sizda yetarli TON yo'q! Maksimal: {max_amount:.3f} TON")
                return
            
            # Ask for wallet address
            await state.update_data(amount=amount)
            await message.answer(
                f"💰 *Yechib olish miqdori:* {amount:.3f} TON\n\n"
                f"📝 *Iltimos, TON hamyon manzilingizni kiriting:*\n"
                f"Misol: `EQBBv8a1R3gXhXkJxJbDGYteZYZHhYJ4wjZQZJzXyFjWqj6X`\n\n"
                f"⚠️ *Eslatma:* Manzil 'EQ' bilan boshlanishi va 48 ta belgidan iborat bo'lishi kerak!",
                parse_mode="Markdown"
            )
            await state.set_state(WithdrawState.waiting_for_wallet)
            
        else:  # UZS withdrawal
            user = get_user(user_id)
            balance = user[3] if user else 0
            
            # Get min withdrawal from settings
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'withdrawal_min'")
            res = cursor.fetchone()
            conn.close()
            withdrawal_min = int(res[0]) if res else 50000
            
            if amount < withdrawal_min:
                await message.answer(f"❌ Minimal yechish miqdori: {withdrawal_min:,} so'm")
                return
                
            if amount > balance:
                await message.answer(f"❌ Hisobingizda yetarli mablag' yo'q! Balans: {balance:,.0f} so'm")
                return
                
            await state.update_data(amount=amount)
            await message.answer(
                "💳 *Karta raqamini kiriting:*\n\n"
                "Format: `8600 1234 5678 9012`",
                parse_mode="Markdown"
            )
            await state.set_state(WithdrawalStates.card_details)
            
    except ValueError:
        await message.answer("❌ Iltimos, miqdorni raqamda kiriting!")

async def create_stars_withdrawal_request(user_id: int, amount: float, state: FSMContext):
    """Create Stars withdrawal request for admin approval"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get user's total Stars balance
    user = get_user(user_id)
    stars_purchased = user[4] if user else 0
    total_stars = stars_purchased  # Total available Stars
    
    if amount > total_stars:
        conn.close()
        await state.clear()
        try:
            await bot.send_message(
                user_id,
                f"❌ *Stars yechish xatoligi!*\n\n"
                f"💰 *So'ralgan miqdor:* {amount:,} Stars\n"
                f"💳 *Mavjud balans:* {total_stars:,} Stars\n\n"
                f"⚠️ *Faqat mavjud Stars miqdorini yechishingiz mumkin!*",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error sending message to user {user_id}: {e}")
        return
    
    # Deduct Stars from user balance
    new_balance = total_stars - amount
    cursor.execute('''
        UPDATE users 
        SET stars_purchased = ?
        WHERE user_id = ?
    ''', (new_balance, user_id))
    
    # Create withdrawal request
    cursor.execute('''
        INSERT INTO withdrawal_requests (user_id, amount, withdrawal_type, status, created_at)
        VALUES (?, ?, 'stars', 'pending', CURRENT_TIMESTAMP)
    ''', (user_id, amount))
    withdrawal_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    await state.clear()
    
    # Send confirmation to user
    try:
        await bot.send_message(
            user_id,
            f"⭐ *Stars yechish so'rovi yuborildi!*\n\n"
            f"📋 *So'rov ID:* #{withdrawal_id}\n"
            f"💰 *Miqdori:* {amount:,} Stars\n"
            f"💳 *Qolgan balans:* {new_balance:,} Stars\n\n"
            f"⏳ *Holati: Admin tasdiqlashini kutishda*\n\n"
            f"👤 Admin tasdiqlagandan so'ng Stars yechib olinadi.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error sending message to user {user_id}: {e}")
    
    # Send notification to admins
    await send_stars_withdrawal_to_admins(withdrawal_id, user_id, amount)

async def create_uc_withdrawal_request(user_id: int, amount: float, state: FSMContext):
    """Create UC withdrawal request for admin approval"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create withdrawal request
    cursor.execute('''
        INSERT INTO withdrawal_requests (user_id, amount, withdrawal_type, status, created_at)
        VALUES (?, ?, 'uc', 'pending', CURRENT_TIMESTAMP)
    ''', (user_id, amount))
    withdrawal_id = cursor.lastrowid
    
    # Deduct UC from user balance (when UC balance is implemented)
    # cursor.execute('UPDATE users SET uc_balance = uc_balance - ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()
    
    await state.clear()
    
    # Send confirmation to user
    try:
        await bot.send_message(
            user_id,
            f"🛡 *UC yechish so'rovi yuborildi!*\n\n"
            f"📋 *So'rov ID:* #{withdrawal_id}\n"
            f"💰 *Miqdori:* {amount:,} UC\n\n"
            f"⏳ *Holati: Admin tasdiqlashini kutishda*\n\n"
            f"👤 Admin tasdiqlagandan so'ng UC yechib olinadi.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error sending message to user {user_id}: {e}")
    
    # Send notification to admins
    await send_uc_withdrawal_to_admins(withdrawal_id, user_id, amount)

async def send_stars_withdrawal_to_admins(withdrawal_id: int, user_id: int, amount: float):
    """Send Stars withdrawal notification to admins"""
    user = get_user(user_id)
    username = f"@{user[1]}" if user and user[1] else f"ID: {user_id}"
    full_name = user[2] if user else "Noma'lum"
    
    # Create profile URL
    profile_url = f"tg://user?id={user_id}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_stars_withdraw_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_stars_withdraw_{withdrawal_id}")
        ],
        [
            InlineKeyboardButton(text="👤 Profilni ko'rish", url=profile_url)
        ]
    ])
    
    text = (
        f"⭐ *Yangi Stars yechish so'rovi!*\n\n"
        f"📋 ID: {withdrawal_id}\n"
        f"👤 Foydalanuvchi: {full_name} ({username})\n"
        f"💰 Miqdor: {amount:,} Stars\n\n"
        f"⚡ Tasdiqlash yoki rad etish:"
    )
    
    for admin_id in get_all_admins():
        try:
            await bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=keyboard)
        except:
            pass

async def send_uc_withdrawal_to_admins(withdrawal_id: int, user_id: int, amount: float):
    """Send UC withdrawal notification to admins"""
    user = get_user(user_id)
    username = f"@{user[1]}" if user and user[1] else f"ID: {user_id}"
    full_name = user[2] if user else "Noma'lum"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_uc_withdraw_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_uc_withdraw_{withdrawal_id}")
        ]
    ])
    
    text = (
        f"🛡 *Yangi UC yechish so'rovi!*\n\n"
        f"📋 ID: {withdrawal_id}\n"
        f"👤 Foydalanuvchi: {full_name} ({username})\n"
        f"💰 Miqdor: {amount:,} UC\n\n"
        f"⚡ Tasdiqlash yoki rad etish:"
    )
    
    for admin_id in get_all_admins():
        try:
            await bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=keyboard)
        except:
            pass

@dp.message(WithdrawalStates.card_details)
async def process_withdrawal_card(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data['amount']
    card_details = message.text.strip()
    user_id = message.from_user.id
    
    # Save withdrawal request and deduct balance immediately
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check user balance again before deducting
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user_balance = cursor.fetchone()
    
    if not user_balance or user_balance[0] < amount:
        await message.answer("❌ Hisobingizda yetarli mablag' mavjud emas!")
        conn.close()
        await state.clear()
        return
    
    # Deduct balance immediately
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    
    # Insert withdrawal request with 'kutilmoqda' status
    cursor.execute('''
        INSERT INTO withdrawals (user_id, amount, card_number, status) 
        VALUES (?, ?, ?, 'kutilmoqda')
    ''', (user_id, amount, card_details))
    withdrawal_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ *Pul yechish so'rovi yuborildi!*\n\n"
        f"📋 So'rov ID: #{withdrawal_id}\n"
        f"💰 Miqdor: {amount:,.0f} so'm\n"
        f"💳 Karta: `{card_details}`\n\n"
        f"⏳ *Holati: Kutilmoqda (admin tasdiqlashini kutishda)*\n\n"
        f"👤 Admin tasdiqlagandan so'ng pul kartangizga tushadi.",
        parse_mode="Markdown"
    )
    
    # Notify admins
    await send_withdrawal_to_admins(withdrawal_id, user_id, amount, card_details)
    await state.clear()

async def send_withdrawal_to_admins(withdrawal_id: int, user_id: int, amount: float, card_details: str):
    user = get_user(user_id)
    username = f"@{user[1]}" if user and user[1] else f"ID: {user_id}"
    full_name = user[2] if user else "Noma'lum"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_withdraw_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_withdraw_{withdrawal_id}")
        ]
    ])
    
    text = (
        f"💸 *Yangi pul yechish so'rovi!*\n\n"
        f"📋 ID: {withdrawal_id}\n"
        f"👤 Foydalanuvchi: {full_name} ({username})\n"
        f"💰 Miqdor: {amount:,.0f} so'm\n"
        f"💳 Karta: `{card_details}`\n\n"
        f"⚡ Tasdiqlash yoki rad etish:"
    )
    
    for admin_id in get_all_admins():
        try:
            await bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=keyboard)
        except:
            pass

@dp.callback_query(F.data.startswith("approve_withdraw_"))
async def approve_withdrawal(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    
    withdrawal_id = int(callback.data.split("_")[-1])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, status FROM withdrawals WHERE id = ?", (withdrawal_id,))
    res = cursor.fetchone()
    
    if not res or res[2] != 'kutilmoqda':
        await callback.answer("❌ So'rov topilmadi yoki allaqachon bajarilgan", show_alert=True)
        conn.close()
        return
        
    user_id, amount, _ = res
    
    # Update withdrawal status to 'pul tushdi' (money sent)
    cursor.execute("UPDATE withdrawals SET status = 'pul tushdi', updated_at = CURRENT_TIMESTAMP, admin_id = ? WHERE id = ?", (callback.from_user.id, withdrawal_id))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text(f"✅ So'rov #{withdrawal_id} tasdiqlandi! Pul foydalanuvchiga yuborildi.", parse_mode="Markdown")
    
    try:
        await bot.send_message(user_id, f"✅ *Pul yechish so'rovingiz tasdiqlandi!*\n\n💰 {amount:,.0f} so'm kartangizga tushdi! 🎉", parse_mode="Markdown")
    except:
        pass

@dp.callback_query(F.data.startswith("reject_withdraw_"))
async def reject_withdrawal(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    
    withdrawal_id = int(callback.data.split("_")[-1])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, status FROM withdrawals WHERE id = ?", (withdrawal_id,))
    res = cursor.fetchone()
    
    if not res or res[2] != 'kutilmoqda':
        await callback.answer("❌ So'rov topilmadi yoki allaqachon bajarilgan", show_alert=True)
        conn.close()
        return
        
    user_id, amount, _ = res
    
    # Refund money back to user's balance
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("UPDATE withdrawals SET status = 'rad etilgan', updated_at = CURRENT_TIMESTAMP, admin_id = ? WHERE id = ?", (callback.from_user.id, withdrawal_id))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text(f"❌ So'rov #{withdrawal_id} rad etildi. Pul foydalanuvchiga qaytarildi.", parse_mode="Markdown")
    
    try:
        await bot.send_message(user_id, f"❌ *Pul yechish so'rovingiz rad etildi!*\n\n💰 {amount:,.0f} so'm hisobingizga qaytarildi.", parse_mode="Markdown")
    except:
        pass

async def send_payment_to_admins(payment_id: int, user_id: int, amount: float, receipt_file_id: str):
    """Send payment request to all admins with approval buttons"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT username, full_name FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        username = f"ID: {user_id}"
        full_name = "Noma'lum"
    else:
        username = f"@{user[0]}" if user[0] else f"ID: {user_id}"
        full_name = user[1]
    
    # Create inline keyboard for approval
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_payment_{payment_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_payment_{payment_id}")
        ]
    ])
    
    text = f"🆕 *Yangi to'lov so'rovi!*\n\n"
    text += f"📋 *ID:* {payment_id}\n"
    text += f"👤 *Foydalanuvchi:* {full_name} ({username})\n"
    text += f"💰 *Miqdor:* {amount:,.0f} so'm\n"
    text += f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    text += "⚡ *Tasdiqlash uchun tugmalardan foydalaning:*"
    
    # Send to all admins
    admins = get_all_admins()
    for admin_id in admins:
        try:
            await bot.send_photo(
                admin_id,
                receipt_file_id,
                caption=text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as e:
            logging.error(f"Admin {admin_id} ga xabar yuborilmadi: {e}")


@dp.callback_query(F.data == "information")
async def information(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    stars_purchased = user[4] if user else 0
    premium_purchased = user[5] if user else 0
    
    await callback.message.edit_text(
        f"ℹ️ *Maʼlumotlar*\n\n"
        f"⭐ *Stars sotib olingan:* {stars_purchased:,}\n"
        f"👑 *Premium sotib olingan:* {premium_purchased:,}\n\n"
        f"🌟 *Stars Shop - Eng ishonchli xizmat!*",
        parse_mode="Markdown",
        reply_markup=information_keyboard()
    )

@dp.callback_query(F.data == "pubg_uc_purchase")
async def pubg_uc_purchase(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    user_id = callback.from_user.id
    try:
        create_user(user_id, callback.from_user.username, callback.from_user.full_name)
    except Exception:
        pass
    
    await callback.message.edit_text(
        "🎮 *PUBG UC miqdorini tanlang:*",
        parse_mode="Markdown",
        reply_markup=pubg_uc_keyboard()
    )

def pubg_uc_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="60 UC", callback_data="pubg_uc_60")],
        [InlineKeyboardButton(text="300 UC", callback_data="pubg_uc_300")],
        [InlineKeyboardButton(text="600 UC", callback_data="pubg_uc_600")],
        [InlineKeyboardButton(text="1500 UC", callback_data="pubg_uc_1500")],
        [InlineKeyboardButton(text="3000 UC", callback_data="pubg_uc_3000")],
        [InlineKeyboardButton(text="6000 UC", callback_data="pubg_uc_6000")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    return keyboard

@dp.callback_query(F.data.regexp(r'^pubg_uc_(\d+)$'))
async def pubg_uc_selected(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    user_id = callback.from_user.id
    uc_amount = int(callback.data.split("_")[-1])
    
    # Get price from database or fallback to defaults
    price_key = f"pubg_uc_{uc_amount}"
    price = get_price(price_key)
    
    # Check user balance
    user_balance = get_user_balance(user_id)
    
    if user_balance >= price:
        # Save purchase data to state
        await state.update_data(
            uc_amount=uc_amount,
            price=price
        )
        
        await callback.message.edit_text(
            f"🎮 *PUBG UC sotib olish*\n\n"
            f"💰 Miqdor: {uc_amount} UC\n"
            f"💵 Narx: {price:,.0f} so'm\n\n"
            f"📝 *O'yinchi ID-ingizni kiriting:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="pubg_uc_purchase")]
            ])
        )
        await state.set_state(PubgUcPurchaseState.user_id)
    else:
        await callback.answer(
            f"❌ Hisobingizda yetarli mablag' mavjud emas! Kerak: {price:,.0f} so'm, Balans: {user_balance:,.0f} so'm",
            show_alert=True
        )

@dp.message(PubgUcPurchaseState.user_id)
async def process_pubg_uc_user_id(message: types.Message, state: FSMContext):
    user_id_input = message.text.strip()
    user_id = message.from_user.id
    
    # Validate player ID (should be numeric, 10-20 digits)
    if not user_id_input.isdigit() or len(user_id_input) < 10 or len(user_id_input) > 20:
        await message.answer(
            "❌ *Noto'g'ri o'yinchi ID formati!*\n\n"
            "📝 O'yinchi ID kiriting:\n\n"
            "Masalan: `12345678901234567890`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="pubg_uc_purchase")]
            ])
        )
        return
    
    data = await state.get_data()
    uc_amount = data['uc_amount']
    price = data['price']
    
    # Save PUBG UC purchase request
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO purchase_requests (user_id, product_type, product_id, price, status, details)
        VALUES (?, ?, ?, ?, 'pending', ?)
    ''', (user_id, 'pubg_uc', uc_amount, price, user_id_input))
    purchase_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ *PUBG UC sotib olish so'rovi yuborildi!*\n\n"
        f"📋 So'rov ID: #{purchase_id}\n"
        f"🎮 Miqdor: {uc_amount} UC\n"
        f"👤 O'yinchi ID: {user_id_input}\n"
        f"💵 Narx: {price:,.0f} so'm\n\n"
        f"⏳ *Holati: Admin tasdiqlashini kutishda*\n\n"
        f"👤 Admin tasdiqlagandan so'ng UC hisobingizga tushadi.",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    
    # Notify admins
    await send_pubg_uc_to_admins(purchase_id, user_id, uc_amount, price, user_id_input)
    await state.clear()

async def send_pubg_uc_to_admins(purchase_id: int, user_id: int, uc_amount: int, price: float, player_id: str):
    user = get_user(user_id)
    username = f"@{user[1]}" if user and user[1] else f"ID: {user_id}"
    full_name = user[2] if user else "Noma'lum"
    
    # Create inline keyboard for approval with profile link
    raw_username = user[1] if user else None
    profile_url = (f"https://t.me/{raw_username}" if raw_username else f"tg://user?id={user_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_pubg_uc_{purchase_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_pubg_uc_{purchase_id}")
        ],
        [
            InlineKeyboardButton(text="👤 Profilni ko'rish", url=profile_url)
        ]
    ])
    
    text = f"🆕 *Yangi PUBG UC xarid so'rovi!*\n\n"
    text += f"📋 *ID:* {purchase_id}\n"
    text += f"👤 *Foydalanuvchi:* {full_name} ({username})\n"
    text += f"🎮 *Mahsulot:* {uc_amount} UC\n"
    text += f"👤 *O'yinchi ID:* `{player_id}`\n"
    text += f"💰 *Narx:* {price:,.0f} so'm\n"
    text += f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    text += "⚡ *Tasdiqlash uchun tugmalardan foydalaning:*"
    
    # Send to all admins
    merged_admins = get_all_admins()

    for admin_id in merged_admins:
        try:
            await bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Admin {admin_id} ga xabar yuborilmadi: {e}")

@dp.callback_query(F.data.startswith("confirm_pubg_uc_"))
async def confirm_pubg_uc(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    
    purchase_id = int(callback.data.split("_")[-1])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, product_id, price, status FROM purchase_requests WHERE id = ?", (purchase_id,))
    res = cursor.fetchone()
    
    if not res or res[3] != 'pending':
        await callback.answer("❌ So'rov topilmadi yoki allaqachon bajarilgan", show_alert=True)
        conn.close()
        return
        
    user_id, uc_amount, price, _ = res
    
    # Check if user still has enough balance
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user_balance_res = cursor.fetchone()
    if not user_balance_res or user_balance_res[0] < price:
        await callback.answer("❌ Foydalanuvchi hisobida yetarli mablag' qolmagan!", show_alert=True)
        cursor.execute("UPDATE purchase_requests SET status = 'failed_balance', confirmed_at = CURRENT_TIMESTAMP WHERE id = ?", (purchase_id,))
        conn.commit()
        conn.close()
        return

    # Deduct balance and update purchase status
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
    cursor.execute("UPDATE purchase_requests SET status = 'confirmed', confirmed_at = CURRENT_TIMESTAMP WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text(f"✅ So'rov #{purchase_id} tasdiqlandi!", parse_mode="Markdown")
    
    try:
        await bot.send_message(user_id, f"✅ *PUBG UC xaridingiz tasdiqlandi!*\n\n🎮 {uc_amount} UC hisobingizga tushdi! 🎉", parse_mode="Markdown")
    except:
        pass

@dp.callback_query(F.data.startswith("cancel_pubg_uc_"))
async def cancel_pubg_uc(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    
    purchase_id = int(callback.data.split("_")[-1])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, product_id, price, status FROM purchase_requests WHERE id = ?", (purchase_id,))
    res = cursor.fetchone()
    
    if not res or res[3] != 'pending':
        await callback.answer("❌ So'rov topilmadi yoki allaqachon bajarilgan", show_alert=True)
        conn.close()
        return
        
    user_id, uc_amount, price, _ = res
    cursor.execute("UPDATE purchase_requests SET status = 'cancelled', confirmed_at = CURRENT_TIMESTAMP WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text(f"❌ So'rov #{purchase_id} bekor qilindi.", parse_mode="Markdown")
    
    try:
        await bot.send_message(user_id, f"❌ *PUBG UC xaridingiz bekor qilindi!*\n\n💰 {price:,.0f} so'm hisobingizdan yechilmadi.", parse_mode="Markdown")
    except:
        pass

@dp.callback_query(F.data == "referral_menu")
async def referral_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
        
    # Get referral statistics
    ref_stats = get_referral_stats(user_id)
    available_ton = ref_stats['available_ton']
    
    # Get referral link
    bot_username = (await bot.get_me()).username
    
    # Try to get user's referral code from DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    
    ref_code = res[0] if res and res[0] else user_id
    referral_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    
    # Get bonus amount
    bonus_amount = get_referral_bonus()
    
    text = (
        f"👥 *Referal Tizimi*\n\n"
        f"Har bir taklif qilingan do'stingiz uchun sizga *{bonus_amount} TON* bonus beriladi!\n\n"
        f"📊 *Sizning statistikangiz:*\n"
        f"🔗 Referallar soni: {ref_stats['referral_count']}\n"
        f"💎 Jami yig'ilgan: {ref_stats['earned_ton']:.3f} TON\n"
        f"💵 Yechib olingan: {ref_stats['withdrawn_ton']:.3f} TON\n"
        f"💰 *Mavjud balans: {available_ton:.3f} TON*\n\n"
        f"💸 Minimal yechib olish: {MIN_WITHDRAWAL} TON\n\n"
        f"📢 *Sizning referal havolangiz:*\n`{referral_link}`"
    )
    
    # URL encoded share text
    from urllib.parse import quote
    encoded_text = quote(f"🚀 Botga kiring va TON yutib oling!\n\n{referral_link}")
    share_url = f"https://t.me/share/url?text={encoded_text}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Tekshirish", callback_data="check_referral")],
        [InlineKeyboardButton(text="🔗 Maxsus referal linkim", callback_data="my_referral_link")],
        [InlineKeyboardButton(text="📢 Do'stni taklif qilish", callback_data="share_referral")],
        [InlineKeyboardButton(text="💰 Yechib olish", callback_data="withdrawal_menu")],
        [InlineKeyboardButton(text="📲 Havolani ulashish", url=share_url)],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "check_referral")
async def check_referral(callback: types.CallbackQuery, state: FSMContext):
    """Check referral link status"""
    await state.clear()
    await callback.answer()
    
    user_id = callback.from_user.id
    
    # Get user's referral code
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    
    if res and res[0]:
        bot_username = (await bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=ref_{res[0]}"
        
        text = (
            f"🔍 *Referal link holati:*\n\n"
            f"✅ *Sizning referal kodingiz:* `{res[0]}`\n"
            f"🔗 *Referal link:* `{referral_link}`\n\n"
            f"📋 *Ushbu link orqali do'stlaringizga yuboring!*\n"
            f"🎁 *Har bir do'stingiz uchun {get_referral_bonus()} TON bonus!*"
        )
    else:
        text = (
            f"❌ *Referal link topilmadi!*\n\n"
            f"📝 *Iltimos, qayta urinib ko'ring.*"
        )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="referral_menu")]
        ])
    )

@dp.callback_query(F.data == "my_referral_link")
async def my_referral_link(callback: types.CallbackQuery, state: FSMContext):
    """Show user's special referral link"""
    await state.clear()
    await callback.answer()
    
    user_id = callback.from_user.id
    
    # Get or create user's referral code
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if user has referral code
    cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    
    if not res or not res[0]:
        # Generate new referral code
        from referral import generate_referral_code
        new_code = generate_referral_code(user_id)
        cursor.execute('UPDATE users SET referral_code = ? WHERE user_id = ?', (new_code, user_id))
        conn.commit()
        ref_code = new_code
    else:
        ref_code = res[0]
    
    conn.close()
    
    bot_username = (await bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    
    text = (
        f"🔗 *Maxsus Referal Linkingiz:*\n\n"
        f"`{referral_link}`\n\n"
        f"🎯 *Referal kodingiz:* `{ref_code}`\n\n"
        f"📊 *Statistika:*\n"
        f"🔗 Taklif soni: {get_referral_stats(user_id)['referral_count']}\n"
        f"💰 Bonus miqdori: {get_referral_bonus()} TON\n\n"
        f"📢 *Ushbu linkni do'stlaringizga ulashingiz mumkin!*"
    )
    
    # URL encoded share text
    from urllib.parse import quote
    encoded_text = quote(f"🚀 Stars Shop botiga kiring va meni taklif qilingan!\n\n{referral_link}")
    share_url = f"https://t.me/share/url?text={encoded_text}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📲 Ulashish", url=share_url)],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="referral_menu")]
        ])
    )

@dp.callback_query(F.data == "share_referral")
async def share_referral(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_username = (await bot.get_me()).username
    ref_code = generate_referral_code(user_id)
    referral_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    
    # Get the current referral bonus amount
    bonus_amount = get_referral_bonus()
    
    share_text = (
        f"🎉 *Sizni taklif qilaman!*\n\n"
        f"💎 Har bir do'stingiz uchun {bonus_amount} TON bonus oling!\n"
        f"🔗 Sizning havolangiz:\n`{referral_link}`\n\n"
        f"📢 Ushbu havolani do'stlaringizga yuboring va ular botga kirganda sizga {bonus_amount} TON bonus qo'shiladi!"
    )
    
    # URL encoded share text
    from urllib.parse import quote
    encoded_text = quote(f"🚀 Botga kiring va TON yutib oling!\n\n{referral_link}")
    share_url = f"https://t.me/share/url?text={encoded_text}"
    
    await callback.message.edit_text(
        share_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📲 Ulashish", url=share_url)],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="my_account")]
        ])
    )

class WithdrawState(StatesGroup):
    waiting_for_wallet = State()

@dp.callback_query(F.data == "withdrawal_menu")
async def withdrawal_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    # Get user balances
    user = get_user(user_id)
    balance = user[3] if user else 0  # UZS balance
    
    # Calculate total Stars balance (purchased + referral)
    stars_purchased = user[4] if user else 0  # Stars purchased
    referral_stars = 0  # get_referral_stars_balance(user_id)  # Stars from referrals
    total_stars = stars_purchased + referral_stars
    
    # Show total Stars in withdrawal menu
    stars_balance = total_stars
    
    # Get referral stats first
    ref_stats = get_referral_stats(user_id)
    available_ton = ref_stats['available_ton']
    
    # Get TON balance (show only referral TON)
    ton_balance_display = available_ton
    
    text = (
        f"💰 *Yechib olish menyusi*\n\n"
        f"💳 *Balansingiz:* {balance:,.0f} so'm\n"
        f"💎 *TON balansi:* {float(ton_balance_display):.3f} TON\n"
        f"⭐ *Stars:* {stars_balance:,}\n\n"
        f"📋 *Yechib olish turini tanlang:*"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 TON yechish", callback_data="withdraw_referral")],
        [InlineKeyboardButton(text="⭐ Stars yechish", callback_data="withdraw_stars")],
        [InlineKeyboardButton(text="💳 Pul yechish (so'm)", callback_data="withdraw_money")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="my_account")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "withdraw_stars")
async def withdraw_stars(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    # Get user balances
    user = get_user(user_id)
    
    # Get total Stars balance (purchased + referral)
    stars_purchased = user[4] if user else 0  # Stars purchased
    referral_stars = 0  # get_referral_stars_balance(user_id)  # Stars from referrals
    total_stars = stars_purchased + referral_stars
    
    if total_stars < 15:
        await callback.answer(
            "Kechirasiz, minimal yechib olish miqdori 15 Stars!",
            show_alert=True
        )
        return
    
    text = (
        f"⭐ *Stars yechish*\n\n"
        f"💰 *Sizda mavjud:* {total_stars:,} Stars\n\n"
        f"📝 *Yechib olish miqdorini kiriting:*\n"
        f"Minimal: 15 Stars\n\n"
        f"⚠️ *Eslatma:* Stars yechib olish uchun admin tasdiqlashi kerak!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="withdrawal_menu")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await state.set_state(WithdrawalStates.amount)
    await state.update_data(withdrawal_type="stars", max_amount=total_stars)

@dp.callback_query(F.data == "withdraw_referral")
async def withdraw_referral(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    ref_stats = get_referral_stats(user_id)
    available_ton = ref_stats['available_ton']
    
    if available_ton < 0.1:  # MIN_WITHDRAWAL
        await callback.answer(
            f"Kechirasiz, minimal yechib olish miqdori 0.1 TON. Sizda {available_ton:.3f} TON mavjud.",
            show_alert=True
        )
        return
    
    # Ask for amount
    text = (
        f"💎 *TON yechish*\n\n"
        f"Mavjud balans: {available_ton:.3f} TON\n"
        f"Minimal yechib olish: 0.1 TON\n\n"
        f"📝 Iltimos, yechib olish miqdorini kiriting (TON):"
    )
    
    await callback.message.answer(text, parse_mode="Markdown")
    await state.set_state(WithdrawalStates.amount)
    await state.update_data(withdrawal_type="ton", max_amount=available_ton)

@dp.message(WithdrawState.waiting_for_wallet)
async def process_wallet_address(message: types.Message, state: FSMContext):
    wallet_address = message.text.strip()
    user_id = message.from_user.id
    
    # Get withdrawal data from state
    data = await state.get_data()
    amount = data.get('amount', 0)
    
    # No validation for TON wallet address - accept any address
    # User can enter any wallet address they want
    
    # Process withdrawal with specific amount
    success, result, withdrawn_amount = withdraw_referral_earnings(user_id, wallet_address, amount)
    
    if success:
        withdrawal_id = result
        await message.answer(
            f"✅ *Yechib olish so'rovi yuborildi!*\n\n"
            f"💰 Miqdor: *{withdrawn_amount:.3f} TON*\n"
            f"💳 Hamyon: `{wallet_address}`\n\n"
            f"🔄 Admin tasdiqlashini kuting...",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="back_to_menu")]
            ])
        )
        
        # Notify admins
        await notify_admins_withdrawal(withdrawal_id, user_id, amount, wallet_address)
    else:
        await message.answer(
            f"❌ Xatolik: {result}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="referral_menu")]
            ])
        )
    
    await state.clear()

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🏠 Bosh menyu",
        reply_markup=main_menu()
    )

@dp.message(Command("autopremium"))
async def cmd_auto_premium(message: types.Message):
    """Admin command to auto-assign premium to a user via PixyAPI"""
    user_id = message.from_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await message.answer(
            "🚫 *Bu komanda faqat adminlar uchun!*",
            parse_mode="Markdown"
        )
        return
    
    # Parse command arguments
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ *Noto'g'ri format!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/autopremium <user_id> <months>`\n\n"
            "🔹 *user_id:* Foydalanuvchi ID raqami\n"
            "🔹 *months:* Premium muddati (1, 3, 6, 12)\n\n"
            "💡 *Misol:* `/autopremium 123456789 3`\n\n"
            "🌐 *PixyAPI orqali avtomatik sotib olish*",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(args[1])
        months = int(args[2])
        
        if months not in [1, 3, 6, 12]:
            await message.answer(
                "❌ *Noto'g'ri oy miqdori!*\n\n"
                "📋 *Ruxsat etilgan muddatlar:* 1, 3, 6, 12 oy",
                parse_mode="Markdown"
            )
            return
        
        # Send processing message
        processing_msg = await message.answer(
            "🔄 *PixyAPI orqali premium sotib olinmoqda...*\n\n"
            "⏳ Iltimos, biroz kutib turing...",
            parse_mode="Markdown"
        )
        
        # Call auto premium function with API integration
        success, result = await auto_assign_premium(target_user_id, months, user_id, use_api=True)
        
        # Delete processing message
        await processing_msg.delete()
        
        if success:
            await message.answer(
                f"✅ *Muvaffaqiyatli amalga oshirildi!*\n\n"
                f"👤 *Foydalanuvchi ID:* {target_user_id}\n"
                f"👑 *Premium muddati:* {months} oy\n"
                f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🎉 *Foydalanuvchi xabardor qilindi!*\n"
                f"🌐 *Manba:* PixyAPI\n\n"
                f"📝 *Tafsilot:* {result}",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ *Xatolik yuz berdi!*\n\n"
                f"📝 *Tafsilot:* {result}\n\n"
                "⚠️ *Agar API ishlamasa, mahalliy tizim orqali urinib ko'ring:* "
                f"`/autopremium_local {target_user_id} {months}`",
                parse_mode="Markdown"
            )
            
    except ValueError:
        await message.answer(
            "❌ *Noto'g'ri argumentlar!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/autopremium <user_id> <months>`\n\n"
            "💡 *Misol:* `/autopremium 123456789 3`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error in cmd_auto_premium: {e}")
        await message.answer(
            "❌ *Noma'lum xatolik yuz berdi!*\n\n"
            f"📝 *Tafsilot:* {str(e)}",
            parse_mode="Markdown"
        )

@dp.message(Command("autopremium_local"))
async def cmd_auto_premium_local(message: types.Message):
    """Admin command to auto-assign premium to a user locally (without API)"""
    user_id = message.from_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await message.answer(
            "🚫 *Bu komanda faqat adminlar uchun!*",
            parse_mode="Markdown"
        )
        return
    
    # Parse command arguments
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ *Noto'g'ri format!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/autopremium_local <user_id> <months>`\n\n"
            "🔹 *user_id:* Foydalanuvchi ID raqami\n"
            "🔹 *months:* Premium muddati (1, 3, 6, 12)\n\n"
            "💡 *Misol:* `/autopremium_local 123456789 3`\n\n"
            "🏪 *Mahalliy tizim orqali berish*",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(args[1])
        months = int(args[2])
        
        if months not in [1, 3, 6, 12]:
            await message.answer(
                "❌ *Noto'g'ri oy miqdori!*\n\n"
                "📋 *Ruxsat etilgan muddatlar:* 1, 3, 6, 12 oy",
                parse_mode="Markdown"
            )
            return
        
        # Call auto premium function without API
        success, result = await auto_assign_premium(target_user_id, months, user_id, use_api=False)
        
        if success:
            await message.answer(
                f"✅ *Muvaffaqiyatli amalga oshirildi!*\n\n"
                f"👤 *Foydalanuvchi ID:* {target_user_id}\n"
                f"👑 *Premium muddati:* {months} oy\n"
                f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🎉 *Foydalanuvchi xabardor qilindi!*\n"
                f"🏪 *Manba:* Mahalliy tizim\n\n"
                f"📝 *Tafsilot:* {result}",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ *Xatolik yuz berdi!*\n\n"
                f"📝 *Tafsilot:* {result}",
                parse_mode="Markdown"
            )
            
    except ValueError:
        await message.answer(
            "❌ *Noto'g'ri argumentlar!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/autopremium_local <user_id> <months>`\n\n"
            "💡 *Misol:* `/autopremium_local 123456789 3`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error in cmd_auto_premium_local: {e}")

@dp.message(Command("autostars"))
async def cmd_auto_stars(message: types.Message):
    """Admin command to auto-assign stars to a user via PixyAPI"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer(
            "🚫 *Bu komanda faqat adminlar uchun!*",
            parse_mode="Markdown"
        )
        return
    
    # Parse command arguments
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ *Noto'g'ri format!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/autostars <user_id> <stars_amount> [username]`\n\n"
            "🔹 *user_id:* Foydalanuvchi ID raqami\n"
            "🔹 *stars_amount:* Stars miqdori (50 dan 1000000 gacha)\n"
            "🔹 *username:* Qabul qiluvchi username (ixtiyoriy)\n\n"
            "💡 *Misol:* `/autostars 123456789 500`\n"
            "💡 *Misol:* `/autostars 123456789 1000 targetuser`\n\n"
            "🌐 *PixyAPI orqali avtomatik sotib olish*",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(args[1])
        stars_amount = int(args[2])
        recipient_username = args[3] if len(args) > 3 else None
        
        if stars_amount < 50 or stars_amount > 1000000:
            await message.answer(
                "❌ *Noto'g'ri stars miqdori!*\n\n"
                "📋 *Ruxsat etilgan miqdor:* 50 dan 1000000 gacha",
                parse_mode="Markdown"
            )
            return
        
        # Send processing message
        processing_msg = await message.answer(
            "🔄 *PixyAPI orqali stars sotib olinmoqda...*\n\n"
            "⏳ Iltimos, biroz kutib turing...",
            parse_mode="Markdown"
        )
        
        # Call auto stars function with API
        success, result = await auto_assign_stars(
            target_user_id, 
            stars_amount, 
            user_id, 
            use_api=True, 
            recipient_username=recipient_username
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        if success:
            response_text = (
                f"✅ *Stars muvaffaqiyatli sotib olindi!*\n\n"
                f"👤 *Foydalanuvchi ID:* {target_user_id}\n"
                f"⭐ *Stars miqdori:* {stars_amount} ⭐\n"
                f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🎉 *Foydalanuvchi xabardor qilindi!*\n"
                f"🌐 *Manba:* PixyAPI\n\n"
                f"📝 *Tafsilot:* {result}"
            )
            if recipient_username:
                response_text += f"\n👤 *Qabul qiluvchi:* @{recipient_username}"
        else:
            response_text = (
                f"❌ *Stars sotib olish xatoligi!*\n\n"
                f"👤 *Foydalanuvchi ID:* {target_user_id}\n"
                f"⭐ *Stars miqdori:* {stars_amount} ⭐\n\n"
                f"📝 *Xatolik:* {result}"
            )
        
        await message.answer(response_text)
            
    except ValueError:
        await message.answer(
            "❌ *Noto'g'ri argumentlar!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/autostars <user_id> <stars_amount> [username]`\n\n"
            "💡 *Misol:* `/autostars 123456789 500`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error in cmd_auto_stars: {e}")
        await message.answer(
            f"❌ *Xatolik yuz berdi!*\n\n"
            f"📝 *Tafsilot:* {str(e)}",
            parse_mode="Markdown"
        )

@dp.message(Command("pixypremium"))
async def cmd_pixy_premium(message: types.Message):
    """Admin command to test PixyAPI premium gift purchase"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer(
            "🚫 *Bu komanda faqat adminlar uchun!*",
            parse_mode="Markdown"
        )
        return
    
    # Parse command arguments
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ *Noto'g'ri format!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/pixypremium <username> <duration> [order_id]`\n\n"
            "🔹 *username:* Telegram username (@ siz)\n"
            "🔹 *duration:* Premium muddati (3, 6, 12 oy)\n"
            "🔹 *order_id:* Buyurtma ID (ixtiyoriy)\n\n"
            "💡 *Misol:* `/pixypremium targetuser 6`\n"
            "💡 *Misol:* `/pixypremium targetuser 12 ORDER-123`\n\n"
            "🌐 *PixyAPI orqali Premium Gift yuborish*",
            parse_mode="Markdown"
        )
        return
    
    try:
        username = args[1].lstrip('@')
        duration = int(args[2])
        order_id = args[3] if len(args) > 3 else None
        
        if duration not in [3, 6, 12]:
            await message.answer(
                "❌ *Noto'g'ri muddat!*\n\n"
                "📋 *Ruxsat etilgan muddatlar:* 3, 6, 12 oy",
                parse_mode="Markdown"
            )
            return
        
        # Send processing message
        processing_msg = await message.answer(
            "🔄 *PixyAPI orqali Premium Gift yuborilmoqda...*\n\n"
            f"👤 *Qabul qiluvchi:* @{username}\n"
            f"👑 *Muddat:* {duration} oy\n\n"
            "⏳ Iltimos, biroz kutib turing...",
            parse_mode="Markdown"
        )
        
        # Call PixyAPI using enhanced manager
        response = await pixy_manager.safe_buy_premium(
            username=username,
            months=duration,
            order_id=order_id
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        if response.get("ok"):
            response_text = (
                f"✅ *Premium Gift muvaffaqiyatli yuborildi!*\n\n"
                f"👤 *Qabul qiluvchi:* @{username}\n"
                f"👑 *Muddat:* {duration} oy\n"
                f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🌐 *Manba:* PixyAPI\n"
            )
            
            # Add order info if available
            if response.get("order_id"):
                response_text += f"🆔 *Buyurtma ID:* {response.get('order_id')}\n"
            
            if response.get("cost"):
                response_text += f"💰 *Narx:* {response.get('cost')} TON\n"
            
            response_text += f"\n🎉 *Premium tez orada @{username} ga ulanadi!*"
        else:
            error_type = response.get("error_type", "UNKNOWN")
            error_msg = response.get("message", "Noma'lum xatolik")
            
            response_text = (
                f"❌ *Premium Gift yuborish xatoligi!*\n\n"
                f"👤 *Qabul qiluvchi:* @{username}\n"
                f"👑 *Muddat:* {duration} oy\n\n"
                f"🔄 *Xatolik turi:* {error_type}\n"
                f"📝 *Xatolik:* {error_msg}"
            )
        
        await message.answer(response_text)
            
    except ValueError:
        await message.answer(
            "❌ *Noto'g'ri argumentlar!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/pixypremium <username> <duration> [order_id]`\n\n"
            "💡 *Misol:* `/pixypremium targetuser 6`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error in cmd_pixy_premium: {e}")
        await message.answer(
            f"❌ *Xatolik yuz berdi!*\n\n"
            f"📝 *Tafsilot:* {str(e)}",
            parse_mode="Markdown"
        )

@dp.message(Command("pixystars"))
async def cmd_pixy_stars(message: types.Message):
    """Admin command to test PixyAPI stars purchase"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer(
            "🚫 *Bu komanda faqat adminlar uchun!*",
            parse_mode="Markdown"
        )
        return
    
    # Parse command arguments
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ *Noto'g'ri format!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/pixystars <username> <amount> [order_id]`\n\n"
            "🔹 *username:* Telegram username (@ siz)\n"
            "🔹 *amount:* Stars miqdori (minimum 50)\n"
            "🔹 *order_id:* Buyurtma ID (ixtiyoriy)\n\n"
            "💡 *Misol:* `/pixystars targetuser 100`\n"
            "💡 *Misol:* `/pixystars targetuser 500 ORDER-123`\n\n"
            "🌐 *PixyAPI orqali Stars yuborish*",
            parse_mode="Markdown"
        )
        return
    
    try:
        username = args[1].lstrip('@')
        amount = int(args[2])
        order_id = args[3] if len(args) > 3 else None
        
        if amount < 50:
            await message.answer(
                "❌ *Noto'g'ri miqdor!*\n\n"
                "📋 *Minimum miqdor:* 50 stars",
                parse_mode="Markdown"
            )
            return
        
        # Send processing message
        processing_msg = await message.answer(
            "🔄 *PixyAPI orqali Stars yuborilmoqda...*\n\n"
            f"👤 *Qabul qiluvchi:* @{username}\n"
            f"⭐ *Miqdori:* {amount} ⭐\n\n"
            "⏳ Iltimos, biroz kutib turing...",
            parse_mode="Markdown"
        )
        
        # Call PixyAPI using enhanced manager
        response = await pixy_manager.safe_buy_stars(
            username=username,
            amount=amount,
            order_id=order_id
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        if response.get("ok"):
            response_text = (
                f"✅ *Stars muvaffaqiyatli yuborildi!*\n\n"
                f"👤 *Qabul qiluvchi:* @{username}\n"
                f"⭐ *Miqdori:* {amount} ⭐\n"
                f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🌐 *Manba:* PixyAPI\n"
            )
            
            # Add order info if available
            if response.get("order_id"):
                response_text += f"🆔 *Buyurtma ID:* {response.get('order_id')}\n"
            
            if response.get("cost"):
                response_text += f"💰 *Narx:* {response.get('cost')} TON\n"
            
            response_text += f"\n🎉 *Stars tez orada @{username} ga tushadi!*"
        else:
            error_type = response.get("error_type", "UNKNOWN")
            error_msg = response.get("message", "Noma'lum xatolik")
            
            response_text = (
                f"❌ *Stars yuborish xatoligi!*\n\n"
                f"👤 *Qabul qiluvchi:* @{username}\n"
                f"⭐ *Miqdori:* {amount} ⭐\n\n"
                f"🔄 *Xatolik turi:* {error_type}\n"
                f"📝 *Xatolik:* {error_msg}"
            )
        
        await message.answer(response_text)
            
    except ValueError:
        await message.answer(
            "❌ *Noto'g'ri argumentlar!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/pixystars <username> <amount> [order_id]`\n\n"
            "💡 *Misol:* `/pixystars targetuser 100`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error in cmd_pixy_stars: {e}")
        await message.answer(
            f"❌ Xatolik yuz berdi!\n\n"
            f"📝 Tafsilot: {str(e)}"
        )

@dp.message(Command("pixyton"))
async def cmd_pixy_ton(message: types.Message):
    """Admin command to test PixyAPI TON purchase"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer(
            "🚫 *Bu komanda faqat adminlar uchun!*",
            parse_mode="Markdown"
        )
        return
    
    # Parse command arguments
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ *Noto'g'ri format!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/pixyton <username> <amount> [order_id]`\n\n"
            "🔹 *username:* Telegram username (@ siz)\n"
            "🔹 *amount:* TON miqdori (masalan: 1.5)\n"
            "🔹 *order_id:* Buyurtma ID (ixtiyoriy)\n\n"
            "💡 *Misol:* `/pixyton targetuser 2.5`\n"
            "💡 *Misol:* `/pixyton targetuser 1 ORDER-123`\n\n"
            "🌐 *PixyAPI orqali TON to'ldirish*",
            parse_mode="Markdown"
        )
        return
    
    try:
        username = args[1].lstrip('@')
        amount = float(args[2])
        order_id = args[3] if len(args) > 3 else None
        
        if amount <= 0:
            await message.answer(
                "❌ *Noto'g'ri miqdor!*\n\n"
                "📋 *Miqdor musbat son bo'lishi kerak*",
                parse_mode="Markdown"
            )
            return
        
        # Send processing message
        processing_msg = await message.answer(
            "🔄 *PixyAPI orqali TON to'ldirilmoqda...*\n\n"
            f"👤 *Qabul qiluvchi:* @{username}\n"
            f"💎 *Miqdori:* {amount} TON\n\n"
            "⏳ Iltimos, biroz kutib turing...",
            parse_mode="Markdown"
        )
        
        # Call PixyAPI using enhanced manager for TON top-up
        response = await pixy_manager.safe_transfer_ton(
            to_address=username,  # For TON top-up, username is treated as address
            amount=amount,
            comment=f"TON to'ldirish - @{username}",
            order_id=order_id
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        if response.get("ok"):
            response_text = (
                f"✅ *TON muvaffaqiyatli to'ldirildi!*\n\n"
                f"👤 *Qabul qiluvchi:* @{username}\n"
                f"💎 *Miqdori:* {amount} TON\n"
                f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🌐 *Manba:* PixyAPI\n"
            )
            
            # Add order info if available
            if response.get("order_id"):
                response_text += f"🆔 *Buyurtma ID:* {response.get('order_id')}\n"
            
            if response.get("cost"):
                response_text += f"💰 *Narx:* {response.get('cost')} TON\n"
            
            response_text += f"\n🎉 *TON tez orada @{username} ning TON balansiga tushadi!*"
        else:
            error_type = response.get("error_type", "UNKNOWN")
            error_msg = response.get("message", "Noma'lum xatolik")
            
            response_text = (
                f"❌ *TON to'ldirish xatoligi!*\n\n"
                f"👤 *Qabul qiluvchi:* @{username}\n"
                f"💎 *Miqdori:* {amount} TON\n\n"
                f"🔄 *Xatolik turi:* {error_type}\n"
                f"📝 *Xatolik:* {error_msg}"
            )
        
        await message.answer(response_text)
            
    except ValueError:
        await message.answer(
            "❌ *Noto'g'ri argumentlar!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/pixyton <username> <amount> [order_id]`\n\n"
            "💡 *Misol:* `/pixyton targetuser 2.5`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error in cmd_pixy_ton: {e}")
        await message.answer(
            f"❌ *Xatolik yuz berdi!*\n\n"
            f"📝 *Tafsilot:* {str(e)}",
            parse_mode="Markdown"
        )

@dp.message(Command("pixytransfer"))
async def cmd_pixy_transfer(message: types.Message):
    """Admin command to test PixyAPI TON transfer"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer(
            "🚫 *Bu komanda faqat adminlar uchun!*",
            parse_mode="Markdown"
        )
        return
    
    # Parse command arguments
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ *Noto'g'ri format!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/pixytransfer <address> <amount> [comment]`\n\n"
            "🔹 *address:* Qabul qiluvchi hamyon (UQ/EQ...)\n"
            "🔹 *amount:* TON miqdori (masalan: 1.5)\n"
            "🔹 *comment:* Izoh (ixtiyoriy)\n\n"
            "💡 *Misol:* `/pixytransfer UQDa4Vz-0e... 0.5 To'lov uchun`\n\n"
            "🌐 *PixyAPI orqali TON o'tkazish*",
            parse_mode="Markdown"
        )
        return
    
    try:
        to_address = args[1]
        amount = float(args[2])
        comment = " ".join(args[3:]) if len(args) > 3 else None
        
        if amount <= 0:
            await message.answer(
                "❌ *Noto'g'ri miqdor!*\n\n"
                "📋 *Miqdor musbat son bo'lishi kerak*",
                parse_mode="Markdown"
            )
            return
        
        # Send processing message
        processing_msg = await message.answer(
            "🔄 *PixyAPI orqali TON o'tkazilmoqda...*\n\n"
            f"🏦 *Qabul qiluvchi:* `{to_address[:20]}...`\n"
            f"💎 *Miqdori:* {amount} TON\n\n"
            "⏳ Iltimos, biroz kutib turing...",
            parse_mode="Markdown"
        )
        
        # Call PixyAPI using enhanced manager
        response = await pixy_manager.safe_transfer_ton(
            to_address=to_address,
            amount=amount,
            comment=comment
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        if response.get("ok"):
            response_text = (
                f"✅ TON muvaffaqiyatli o'tkazildi!\n\n"
                f"🏦 Qabul qiluvchi: {to_address}\n"
                f"💎 Miqdori: {amount} TON\n"
                f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🌐 Manba: PixyAPI\n"
            )
            
            # Add transaction info if available
            if response.get("tx_hash"):
                response_text += f"🔗 Tx Hash: {response.get('tx_hash')}\n"
            
            if response.get("fee"):
                response_text += f"💸 Komissiya: {response.get('fee')} TON\n"
            
            if comment:
                response_text += f"📝 Izoh: {comment}\n"
            
            response_text += f"\n🎉 O'tkazma muvaffaqiyatli amalga oshdi!"
        else:
            error_type = response.get("error_type", "UNKNOWN")
            error_msg = response.get("message", "Noma'lum xatolik")
            
            response_text = (
                f"❌ TON o'tkazish xatoligi!\n\n"
                f"🏦 Qabul qiluvchi: {to_address}\n"
                f"💎 Miqdori: {amount} TON\n\n"
                f"🔄 Xatolik turi: {error_type}\n"
                f"📝 Xatolik: {error_msg}"
            )
        
        await message.answer(response_text)
            
    except ValueError:
        await message.answer(
            "❌ *Noto'g'ri argumentlar!*\n\n"
            "📝 *To'g'ri foydalanish:*\n"
            "`/pixytransfer <address> <amount> [comment]`\n\n"
            "💡 *Misol:* `/pixytransfer UQDa4Vz-0e... 0.5`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error in cmd_pixy_transfer: {e}")
        await message.answer(
            f"❌ *Xatolik yuz berdi!*\n\n"
            f"📝 *Tafsilot:* {str(e)}",
            parse_mode="Markdown"
        )

@dp.message(Command("pixystatus"))
async def cmd_pixy_status(message: types.Message):
    """Admin command to check PixyAPI status and balance"""
    user_id = message.from_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await message.answer(
            "❌ *Bu faqat adminlar uchun komanda!*",
            parse_mode="Markdown"
        )
        return
    
    try:
        # Send initial message
        status_msg = await message.answer(
            "🔍 *PixyAPI status tekshirilmoqda...*",
            parse_mode="Markdown"
        )
        
        # Get comprehensive status
        await get_pixy_status()  # Refresh cache
        status_message = format_pixy_status_message()
        
        # Perform health check
        is_healthy, health_message = await check_pixy_health()
        
        # Add health check result
        if is_healthy:
            status_message += f"\n\n✅ *Health Check:* {health_message}"
        else:
            status_message += f"\n\n❌ *Health Check:* {health_message}"
        
        # Update message with status
        await status_msg.edit_text(
            status_message,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logging.error(f"Error in cmd_pixy_status: {e}")
        await message.answer(
            f"❌ *Xatolik yuz berdi!*\n\n"
            f"📝 *Tafsilot:* {str(e)}",
            parse_mode="Markdown"
        )

# Admin panel handler - Handled in admin_panel.py
# Note: All admin panel handlers (balance, banning, users, channels, etc.) 
# are now centrally managed in stars_shop/admin_panel.py via register_admin_handlers()

async def back_to_main_menu(message: types.Message):
    # Only handle non-admin users going back to main menu
    # Admin users will be handled by admin_panel handler
    if not is_admin(message.from_user.id):
        await message.answer(
            "🌟 *Asosiy menuga xush kelibsiz!*",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

def add_purchase_callbacks(dp: Dispatcher):
    # This function is kept for structural compatibility but all handlers 
    # are now registered through admin_panel.register_admin_handlers()
    pass

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle main menu callback"""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🌟 Asosiy menuga xush kelibsiz!",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle back to main menu callback"""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🌟 Asosiy menuga xush kelibsiz!",
        reply_markup=main_menu()
    )

def register_payment_callbacks(dp: Dispatcher):
    # This function is kept for structural compatibility but all handlers 
    # are now registered through admin_panel.register_admin_handlers()
    pass

# TON Sell Handlers
@dp.callback_query(F.data == "ton_sell")
async def ton_sell_callback(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 TON", callback_data="ton_sell_amount_1")],
        [InlineKeyboardButton(text="5 TON", callback_data="ton_sell_amount_5")],
        [InlineKeyboardButton(text="10 TON", callback_data="ton_sell_amount_10")],
        [InlineKeyboardButton(text="25 TON", callback_data="ton_sell_amount_25")],
        [InlineKeyboardButton(text="50 TON", callback_data="ton_sell_amount_50")],
        [InlineKeyboardButton(text="📝 Boshqa miqdor", callback_data="ton_sell_custom")]
    ])
    
    await callback.message.edit_text(
        "💱 *TON Sotish*\n\n"
        "Qancha TON sotmoqchisiz?\n\n"
        "🔸 *Avtomatik o'tkazma:* Sizning TONingiz admin hamyoniga o'tkaziladi\n"
        "🔸 *Balansga qo'shiladi:* TON qiymati so'mda hisobingizga qo'shiladi\n\n"
        "Miqdorni tanlang:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("ton_sell_amount_"))
async def ton_sell_amount_selected(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    await callback.answer()
    
    amount_str = callback.data.replace("ton_sell_amount_", "")
    amount = float(amount_str)
    
    await process_ton_sell_auto(amount, callback, state)

@dp.callback_query(F.data == "ton_sell_custom")
async def ton_sell_custom_amount(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(TonSellState.amount)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_ton_sell")]
    ])
    
    await callback.message.edit_text(
        "💱 *TON Sotish - Boshqa miqdor*\n\n"
        "Sotmoqchi bo'lgan TON miqdorini kiriting:\n\n"
        "💡 *Masalan:* 2.5, 10, 15.5\n"
        "🔸 *Minimal:* 0.1 TON\n"
        "🔸 *Maksimal:* Chegarasiz\n\n"
        "Miqdorni kiriting:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.message(TonSellState.amount)
async def ton_sell_custom_amount_input(message: types.Message, state: FSMContext):
    if is_user_banned(message.from_user.id):
        await message.answer("Siz banlangansiz")
        await state.clear()
        return
    
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Miqdor 0 dan katta bo'lishi kerak!")
            return
        
        await state.clear()
        await process_ton_sell_auto(amount, message, state)
        
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri miqdorni kiriting (masalan: 2.5 yoki 10)")

@dp.callback_query(F.data == "sell_stars")
async def sell_stars_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle stars selling request"""
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
    
    # Get user's actual Telegram stars balance
    try:
        # Check user's Telegram stars balance via bot API
        user_info = await bot.get_chat(user_id)
        # Note: Telegram doesn't provide direct stars balance via bot API
        # We'll show the interface and let user know they need stars in their account
        telegram_stars_available = True  # We assume user has stars to sell
    except Exception as e:
        logging.error(f"Error getting user info: {e}")
        telegram_stars_available = True
    
    await callback.message.edit_text(
        f"💸 *Stars sotish*\n\n"
        f"⭐ *Telegram akkauntingizdagi starslarni sotishingiz mumkin*\n"
        f"💰 *1 star = {get_price('stars_sell')} UZS*\n\n"
        f"📝 *Sotmoqchi bo'lgan stars miqdorini kiriting:*\n"
        f"🔸 *Minimal: 1 star*\n"
        f"🔸 *Masalan: 100, 500, 1000*\n\n"
        f"🎯 *Yoki quyidagilardan birini tanlang:*",
        parse_mode="Markdown",
        reply_markup=stars_sell_amount_keyboard()
    )
    
    # Set state to wait for stars amount
    await state.set_state(StarsSellState.amount)

@dp.message(StarsSellState.amount)
async def process_stars_sell_amount(message: types.Message, state: FSMContext):
    """Process manual stars selling amount input"""
    user_id = message.from_user.id
    
    try:
        amount = int(message.text.strip())
        
        # Validate minimum amount
        if amount < 1:
            await message.answer(
                "❌ *Minimal miqdor 1 star!*\n\n"
                "📝 Iltimos, 1 yoki ko'p stars miqdorini kiriting:",
                parse_mode="Markdown"
            )
            return
        
        await state.clear()
        
        # Process with payment interface directly
        await process_stars_sell_direct(amount, message)
        
    except ValueError:
        await message.answer(
            "❌ *Noto'g'ri format!*\n\n"
            "📝 Iltimos, faqat raqam kiriting (masalan: 100, 500, 1000):",
            parse_mode="Markdown"
        )

def stars_sell_amount_keyboard():
    """Create keyboard for stars selling amount selection"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Boshqa miqdor", callback_data="sell_stars_custom")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_stars_sell")]
    ])
    return keyboard

@dp.callback_query(F.data == "cancel_stars_sell")
async def cancel_stars_sell_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handle cancel stars sell"""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "❌ Stars sotish bekor qilindi.",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data.startswith("sell_stars_"))
async def sell_stars_amount_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle stars selling amount selection"""
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
    
    if callback.data == "sell_stars_custom":
        await callback.message.edit_text(
            "📝 *Sotmoqchi bo'lgan stars miqdorini kiriting:*\n\n"
            "🔸 *Minimal: 1 star*\n"
            "🔸 *Masalan: 100, 500, 1000*",
            parse_mode="Markdown"
        )
        return
    
    # Extract amount from callback data
    amount_str = callback.data.replace("sell_stars_", "")
    try:
        amount = int(amount_str)
    except ValueError:
        await callback.answer("Noto'g'ri miqdor!", show_alert=True)
        return
    
    if amount <= 0:
        await callback.answer("Miqdor 0 dan katta bo'lishi kerak!", show_alert=True)
        return
    
    # Show processing message first
    await callback.message.edit_text(
        "🔄 *Buyurtma bajarilmoqda...*\n\n"
        f"⭐ Miqdori: {amount} ⭐\n"
        f"💰 Balansga qo'shiladigan summa: {amount} so'm\n\n"
        "⏳ Iltimos, biroz kutib turing...",
        parse_mode="Markdown"
    )
    
    await state.clear()
    await process_stars_sell_direct(amount, callback)

async def process_stars_sell_direct(amount: int, message: types.Message):
    """Process stars selling with Telegram Stars invoice"""
    user_id = message.from_user.id
    amount_in_uzs = amount * get_price("stars_sell")
    
    # Generate order ID
    import uuid
    order_id = f"STARS-SELL-{uuid.uuid4().hex[:8].upper()}"
    
    # Save order data
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create temporary table for pending star sales if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_star_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            amount_in_uzs INTEGER,
            order_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        INSERT INTO pending_star_sales (user_id, amount, amount_in_uzs, order_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, amount, amount_in_uzs, order_id))
    
    conn.commit()
    conn.close()
    
    # Show payment interface
    await show_stars_payment_interface_from_message(amount, message)

async def show_stars_payment_interface_from_message(amount: int, message: types.Message):
    """Show payment interface for stars selling"""
    user_id = message.from_user.id
    amount_in_uzs = amount * get_price("stars_sell")
    
    # Get the most recent pending order for this user and amount
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT order_id FROM pending_star_sales 
        WHERE user_id = ? AND amount = ? AND status = 'pending'
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id, amount))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        await message.answer("❌ Buyurtma topilmadi!")
        return
    
    order_id = result[0]
    
    # Generate unique invoice payload
    invoice_payload = f"stars_sell_{order_id}_{user_id}"
    
    # Create Telegram Stars invoice only
    await bot.send_invoice(
        chat_id=user_id,
        title=f"⭐ {amount} Stars sotish",
        description=f"⭐ {amount} Telegram Stars sotish orqali {amount_in_uzs:,} so'm olish",
        payload=invoice_payload,
        provider_token="",  # Empty for Telegram Stars
        currency="XTR",  # Telegram Stars currency
        prices=[types.LabeledPrice(label=f"{amount} Stars", amount=amount)]
    )

async def show_stars_payment_interface(amount: int, callback: types.CallbackQuery):
    """Show payment interface for stars selling"""
    user_id = callback.from_user.id
    amount_in_uzs = amount * get_price("stars_sell")
    
    # Get the most recent pending order for this user and amount
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT order_id FROM pending_star_sales 
        WHERE user_id = ? AND amount = ? AND status = 'pending'
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id, amount))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        await callback.answer("❌ Buyurtma topilmadi!", show_alert=True)
        return
    
    order_id = result[0]
    
    # Generate unique invoice payload
    invoice_payload = f"stars_sell_{order_id}_{user_id}"
    
    # Create Telegram Stars invoice
    await bot.send_invoice(
        chat_id=user_id,
        title=f"⭐ {amount} Stars sotish",
        description=f"⭐ {amount} Telegram Stars sotish orqali {amount_in_uzs:,} so'm olish",
        payload=invoice_payload,
        provider_token="",  # Empty for Telegram Stars
        currency="XTR",  # Telegram Stars currency
        prices=[types.LabeledPrice(label=f"{amount} Stars", amount=amount)]
    )
    
    # Also send a message with cancel option
    await bot.send_message(
        chat_id=user_id,
        text=f"💸 *Stars sotish to'lovi*\n\n"
        f"⭐ *Miqdori: {amount} stars*\n"
        f"💰 *Olingan summa: {amount_in_uzs:,} so'm*\n\n"
        f"📝 *To'lovni amalga oshiring:*\n"
        f"Yuqoridagi to'lov tugmasini bosing va Stars to'lovini tasdiqlang.\n\n"
        f"❌ *To'lovni bekor qilish uchun quyidagi tugmani bosing:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Telegram Stars to'lash", callback_data=f"pay_stars_{order_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_stars_sell")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
        ])
    )

async def process_stars_sell(amount: int, callback: types.CallbackQuery):
    """Process stars selling"""
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
    
    stars_balance = user['stars'] if user and 'stars' in user and user['stars'] else 0
    
    if amount > stars_balance:
        await callback.answer("Balansingizda yetarli stars yo'q!", show_alert=True)
        return
    
    # Calculate amount in UZS using current sell price
    amount_in_uzs = amount * get_price("stars_sell")
    
    # Update user balance
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Deduct stars
    cursor.execute('UPDATE users SET stars = stars - ? WHERE user_id = ?', (amount, user_id))
    
    # Add UZS to balance
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount_in_uzs, user_id))
    
    # Record transaction
    cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, stars, status, details, confirmed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, 'stars_sell', amount_in_uzs, amount, 'completed', f'Sold {amount} stars for {amount_in_uzs} UZS', datetime.now()))
    
    conn.commit()
    conn.close()
    
    # Notify admins
    for admin_id in ADMINS:
        try:
            await bot.send_message(
                admin_id,
                f"💸 *Yangi Stars sotildi!*\n\n"
                f"👤 *Sotuvchi:* ID {user_id}\n"
                f"⭐ *Sotilgan stars:* {amount} ⭐\n"
                f"💰 *Balansga qo'shildi:* {amount_in_uzs} UZS\n"
                f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Failed to notify admin {admin_id}: {e}")
    
    await callback.message.edit_text(
        f"✅ *Stars muvaffaqiyatli sotildi!*\n\n"
        f"⭐ *Sotilgan:* {amount} ⭐\n"
        f"💰 *Balansingizga qo'shildi:* {amount_in_uzs} UZS\n\n"
        f"🎉 *Balansingiz to'ldirildi!*",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars_callback(callback: types.CallbackQuery):
    """Handle Telegram Stars payment"""
    order_id = callback.data.replace("pay_stars_", "")
    
    # Get order details
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, amount, amount_in_uzs FROM pending_star_sales 
        WHERE order_id = ? AND status = 'pending'
    ''', (order_id,))
    
    order = cursor.fetchone()
    if not order:
        await callback.answer("❌ Buyurtma topilmadi yoki allaqachon to'langan!", show_alert=True)
        conn.close()
        return
    
    user_id, amount, amount_in_uzs = order
    
    # Generate unique invoice payload
    invoice_payload = f"stars_sell_{order_id}_{user_id}"
    
    # Create Telegram Stars invoice
    await bot.send_invoice(
        chat_id=user_id,
        title=f"⭐ {amount} Stars sotish",
        description=f"⭐ {amount} Telegram Stars sotish orqali {amount_in_uzs:,} so'm olish",
        payload=invoice_payload,
        provider_token="",  # Empty for Telegram Stars
        currency="XTR",  # Telegram Stars currency
        prices=[types.LabeledPrice(label=f"{amount} Stars", amount=amount)]
    )
    
    conn.close()
    await callback.answer("✅ To'lov yuborildi!")

@dp.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
    """Handle pre-checkout query for Telegram Stars payments"""
    try:
        # Extract order info from payload
        payload = pre_checkout_query.invoice_payload
        
        if not payload.startswith("stars_sell_"):
            await pre_checkout_query.answer(ok=False, error_message="Noto'g'ri to'lov turi!")
            return
        
        # Parse payload: stars_sell_{order_id}_{user_id}
        parts = payload.split("_")
        if len(parts) < 4:
            await pre_checkout_query.answer(ok=False, error_message="Buyurtma ma'lumotlari xato!")
            return
        
        order_id = parts[2]
        user_id_from_payload = parts[3]
        
        # Verify order exists and is pending
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, amount, amount_in_uzs, status FROM pending_star_sales 
            WHERE order_id = ?
        ''', (order_id,))
        
        order = cursor.fetchone()
        conn.close()
        
        if not order:
            await pre_checkout_query.answer(ok=False, error_message="Buyurtma topilmadi!")
            return
        
        db_user_id, amount, amount_in_uzs, status = order
        
        # Verify user ID matches
        if db_user_id != pre_checkout_query.from_user.id or db_user_id != int(user_id_from_payload):
            await pre_checkout_query.answer(ok=False, error_message="Foydalanuvchi mos kelmaydi!")
            return
        
        # Verify order status
        if status != 'pending':
            await pre_checkout_query.answer(ok=False, error_message="Buyurtma allaqachon qayta ishlangan!")
            return
        
        # Verify amount matches
        if pre_checkout_query.total_amount != amount:
            await pre_checkout_query.answer(ok=False, error_message="To'lov miqdori mos kelmaydi!")
            return
        
        # All checks passed
        await pre_checkout_query.answer(ok=True)
        
    except Exception as e:
        logging.error(f"Error in pre_checkout_query: {e}")
        await pre_checkout_query.answer(ok=False, error_message="To'lovni tasdiqlashda xatolik!")

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    """Handle successful payment for Telegram Stars"""
    successful_payment = message.successful_payment
    try:
        # Extract order info from payload
        payload = successful_payment.invoice_payload
        
        if not payload.startswith("stars_sell_"):
            logging.warning(f"Unknown payment payload: {payload}")
            return
        
        # Parse payload: stars_sell_{order_id}_{user_id}
        parts = payload.split("_")
        if len(parts) < 4:
            logging.error(f"Invalid payload format: {payload}")
            return
        
        order_id = parts[2]
        user_id_from_payload = int(parts[3])
        
        # Verify user ID matches
        if message.from_user.id != user_id_from_payload:
            logging.error(f"User ID mismatch: {message.from_user.id} != {user_id_from_payload}")
            return
        
        # Get order details
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, amount, amount_in_uzs, status FROM pending_star_sales 
            WHERE order_id = ?
        ''', (order_id,))
        
        order = cursor.fetchone()
        
        if not order:
            logging.error(f"Order not found: {order_id}")
            conn.close()
            return
        
        db_user_id, amount, amount_in_uzs, status = order
        
        # Verify order status
        if status != 'pending':
            logging.warning(f"Order {order_id} has invalid status: {status}")
            conn.close()
            return
        
        # Update order status to completed
        cursor.execute('''
            UPDATE pending_star_sales SET status = 'completed', completed_at = ?
            WHERE order_id = ?
        ''', (datetime.now(), order_id))
        
        # Add UZS to user balance
        cursor.execute('''
            UPDATE users SET balance = balance + ? WHERE user_id = ?
        ''', (amount_in_uzs, db_user_id))
        
        # Record transaction
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, stars, status, details, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (db_user_id, 'stars_sell', amount_in_uzs, amount, 'completed', 
              f'Sold {amount} stars for {amount_in_uzs} UZS via Telegram Stars', datetime.now()))
        
        conn.commit()
        conn.close()
        
        # Notify user
        try:
            import re
            # Escape special characters for Markdown
            amount_str = str(amount).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
            amount_in_uzs_str = f"{amount_in_uzs:,}".replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
            payment_id_str = str(successful_payment.telegram_payment_charge_id).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
            
            await message.answer(
                f"✅ *To'lov muvaffaqiyatli amalga oshdi!*\n\n"
                f"⭐ *Sotilgan:* {amount_str} ⭐\n"
                f"💰 *Balansingizga qo'shildi:* {amount_in_uzs_str} UZS\n\n"
                f"🎉 *Balansingiz to'ldirildi!*\n\n"
                f"🆔 *To'lov ID:* {payment_id_str}",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        except Exception as e:
            logging.error(f"Failed to notify user {db_user_id}: {e}")
        
        # Notify admins
        for admin_id in ADMINS:
            try:
                # Escape special characters for Markdown
                amount_str = str(amount).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                amount_in_uzs_str = f"{amount_in_uzs:,}".replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                order_id_str = str(order_id).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                payment_id_str = str(successful_payment.telegram_payment_charge_id).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                date_str = datetime.now().strftime('%Y-%m-%d %H:%M').replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                
                await bot.send_message(
                    admin_id,
                    f"💸 *Yangi Stars sotildi! (Telegram Stars)*\n\n"
                    f"👤 *Sotuvchi:* ID {db_user_id}\n"
                    f"⭐ *Sotilgan stars:* {amount_str} ⭐\n"
                    f"💰 *Balansga qo'shildi:* {amount_in_uzs_str} UZS\n"
                    f"🆔 *Buyurtma:* {order_id_str}\n"
                    f"💳 *To'lov ID:* {payment_id_str}\n"
                    f"📅 *Sana:* {date_str}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Failed to notify admin {admin_id}: {e}")
        
        logging.info(f"Successfully processed stars payment: order_id={order_id}, user_id={db_user_id}, amount={amount}")
        
        # Send notification to order channel
        await send_order_notification(
            f"💸 *Yangi Stars sotildi!*\n\n"
            f"👤 *Sotuvchi:* ID {db_user_id}\n"
            f"⭐ *Sotilgan stars:* {amount_str} ⭐\n"
            f"💰 *Balansga qo'shildi:* {amount_in_uzs_str} UZS\n"
            f"🆔 *Buyurtma:* {order_id_str}\n"
            f"💳 *To'lov ID:* {payment_id_str}\n"
            f"📅 *Sana:* {date_str}"
        )
        
    except Exception as e:
        logging.error(f"Error in successful_payment_handler: {e}")

async def process_stars_payment_success(user_id: int, amount: int, amount_in_uzs: int, order_id: str, callback: types.CallbackQuery):
    """Process successful stars payment"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Update pending order status
    cursor.execute('''
        UPDATE pending_star_sales SET status = 'completed', completed_at = ?
        WHERE order_id = ?
    ''', (datetime.now(), order_id))
    
    # Add UZS to user balance
    cursor.execute('''
        UPDATE users SET balance = balance + ? WHERE user_id = ?
    ''', (amount_in_uzs, user_id))
    
    # Record transaction
    cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, stars, status, details, confirmed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, 'stars_sell', amount_in_uzs, amount, 'completed', f'Sold {amount} stars for {amount_in_uzs} UZS', datetime.now()))
    
    conn.commit()
    conn.close()
    
    # Notify admins
    for admin_id in ADMINS:
        try:
            await bot.send_message(
                admin_id,
                f"💸 *Yangi Stars sotildi!*\n\n"
                f"👤 *Sotuvchi:* ID {user_id}\n"
                f"⭐ *Sotilgan stars:* {amount} ⭐\n"
                f"💰 *Balansga qo'shildi:* {amount_in_uzs} UZS\n"
                f"🆔 *Buyurtma:* {order_id}\n"
                f"📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Failed to notify admin {admin_id}: {e}")
    
    await callback.message.edit_text(
        f"✅ *To'lov muvaffaqiyatli amalga oshdi!*\n\n"
        f"⭐ *Sotilgan:* {amount} ⭐\n"
        f"💰 *Balansingizga qo'shildi:* {amount_in_uzs} UZS\n\n"
        f"🎉 *Balansingiz to'ldirildi!*",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    """Handle cancel payment"""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "❌ To'lov bekor qilindi.",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data.startswith("cancel_payment_"))
async def cancel_payment_with_id(callback: types.CallbackQuery, state: FSMContext):
    """Handle cancel payment with ID"""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "❌ To'lov bekor qilindi.",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "cancel_ton_sell")
async def cancel_ton_sell(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "❌ TON sotish bekor qilindi.",
        reply_markup=main_menu()
    )

async def process_ton_sell_auto(amount: float, message_or_callback, state: FSMContext):
    """Process TON sell - manual transfer to admin wallet"""
    user_id = message_or_callback.from_user.id
    price_per_ton = get_ton_sell_price()
    total_amount = amount * price_per_ton
    
    # Get current prices for display
    market_price = get_ton_market_price()
    buy_price = get_ton_buy_price()
    
    # Generate order ID
    import uuid
    order_id = f"TON-SELL-{uuid.uuid4().hex[:8].upper()}"
    
    # Show admin wallet address for manual transfer
    from config import ADMIN_TON_WALLET
    
    transfer_text = (
        f"💱 *TON Sotish - To'lov kerak!*\n\n"
        f"💎 *Miqdor:* {amount:.2f} TON\n"
        f"📊 *Bozor narxi:* {market_price:,.0f} so'm/TON\n"
        f"💵 *Sotish narxi:* {price_per_ton:,.0f} so'm/TON\n"
        f"💰 *Jami:* {total_amount:,.0f} so'm\n\n"
        f"🏦 *Admin TON hamyoni:*\n"
        f"[`{ADMIN_TON_WALLET}`]({ADMIN_TON_WALLET})\n\n"
        f"📋 *To'lov usullari:*\n"
        f"1️⃣ 💎 TON Keper orqali to'lash (tavsiya etiladi)\n"
        f"2️⃣ 📱 ScreenPay orqali to'lash\n"
        f"3️⃣ 🏦 Manzilni nusxalab qo'lda o'tkazish\n\n"
        f"⚠️ *Eslatma:* To'lov qilinganidan so'ng pul avtomatik balansingizga qo'shiladi!"
    )
    
    # Save order data for later verification
    await state.set_state(TonSellState.amount)
    await state.update_data(
        sell_amount=amount,
        sell_total=total_amount,
        sell_price_per_ton=price_per_ton,
        order_id=order_id
    )
    
    # Initialize TON payment processor
    ton_payment = init_ton_payment(bot)
    
    # Create payment keyboard
    payment_keyboard = await ton_payment.create_payment_keyboard(
        amount=amount, 
        description=f"TON sotish - Order {order_id}"
    )
    
    # Add receipt upload option
    final_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 TON Keper orqali to'lash", url=ton_payment.generate_ton_keper_url(amount, f"TON sotish - Order {order_id}"))],
        [InlineKeyboardButton(text="📱 ScreenPay orqali to'lash", url=ton_payment.generate_screenpay_url(amount, f"TON sotish - Order {order_id}"))],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_ton_sell")]
    ])
    
    if hasattr(message_or_callback, 'message'):
        await message_or_callback.message.answer(transfer_text, parse_mode="Markdown", reply_markup=final_keyboard)
    else:
        await message_or_callback.answer(transfer_text, parse_mode="Markdown", reply_markup=final_keyboard)

async def main():
    try:
        # Initialize database
        init_db()
        
        # Start TON price updater background task
        logging.info("Starting TON price updater...")
        price_update_task = asyncio.create_task(start_ton_price_updates())
        
        # Register TON purchase and sell handlers
        register_ton_handlers(dp)
        
        # Register admin panel handlers
        ap.register_admin_handlers(dp)
        
        # Start the bot
        logging.info("Starting bot...")
        await dp.start_polling(bot, drop_pending_updates=True)
        
    except Exception as e:
        logging.error(f"Error in main(): {e}", exc_info=True)
    finally:
        # Cancel background task
        if 'price_update_task' in locals():
            price_update_task.cancel()
            try:
                await price_update_task
            except asyncio.CancelledError:
                pass
        
        # Close the bot session
        await bot.session.close()
        logging.info("Bot stopped")

# Captcha handler
@dp.message(CaptchaState.waiting_for_captcha)
async def handle_captcha(message: types.Message, state: FSMContext):
    """Handle captcha input from user"""
    user_input = message.text.strip()
    user_id = message.from_user.id
    
    # Get stored captcha answer
    data = await state.get_data()
    correct_answer = data.get('captcha_answer')
    referrer_id = data.get('referrer_id')
    referral_type = data.get('referral_type')
    waiting_for_phone = data.get('waiting_for_phone', False)
    
    # If waiting for phone number
    if waiting_for_phone:
        phone_number = user_input.strip()
        
        # Phone number is valid, mark captcha as passed and show main menu
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET captcha_passed = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await state.clear()
        
        # Send success message and main menu
        await message.answer(
            "✅ *To'g'ri! Botdan foydalanishingiz mumkin.*\n\n"
            "🌟 *Asosiy menuga xush kelibsiz!*",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        
        # Track referral if applicable
        if referrer_id:
            try:
                res = await track_referral_new(bot, user_id, referrer_id, referral_type)
                success = res[0]
                actual_referrer_id = res[2] if len(res) > 2 else None
                
                if success and actual_referrer_id:
                    try:
                        bonus_amount = get_referral_bonus()
                        await bot.send_message(
                            actual_referrer_id,
                            f"👥 *Yangi referal qo'shildi!*\n\n"
                            f"🎉 Tabriklaymiz! Sizning taklif havolangiz orqali yangi foydalanuvchi ro'yxatdan o'tdi!\n"
                            f"💰 Sizga {bonus_amount} TON bonus qo'shildi.",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logging.error(f"Failed to notify referrer {actual_referrer_id}: {e}")
            except Exception as e:
                logging.error(f"Error in referral tracking: {e}")
        
        return
    
    if user_input == correct_answer:
        # Correct captcha answer
        # Mark captcha as passed in database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET captcha_passed = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await state.clear()
        
        # Send success message and main menu
        await message.answer(
            "✅ *To'g'ri! Botdan foydalanishingiz mumkin.*\n\n"
            "🌟 *Asosiy menuga xush kelibsiz!*",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        
        # Track referral if applicable
        if referrer_id:
            try:
                res = await track_referral_new(bot, user_id, referrer_id, referral_type)
                success = res[0]
                actual_referrer_id = res[2] if len(res) > 2 else None
                
                if success and actual_referrer_id:
                    bonus_amount = get_referral_bonus_by_type(referral_type)
                    bonus_text = get_referral_bonus_text(referral_type, bonus_amount)
                    await bot.send_message(
                        actual_referrer_id,
                        f"👥 *Yangi referal qo'shildi!*\n\n"
                        f"🎉 Tabriklaymiz! Sizning taklif havolangiz orqali yangi foydalanuvchi obuna bo'ldi!\n"
                        f"{bonus_text}",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logging.error(f"Failed to track referral: {e}")
    else:
        # Wrong captcha answer, generate new captcha
        captcha_image, captcha_text = generate_captcha_image()
        
        # Update stored captcha answer
        await state.update_data(captcha_answer=captcha_text)
        
        # Send new captcha
        await message.answer_photo(
            photo=types.BufferedInputFile(captcha_image.getvalue(), filename="captcha.png"),
            caption="❌ *Noto'g'ri javob! Iltimos, qayta urinib ko'ring:*\n\n"
                   "Yuqoridagi rasmga chiqqan 4 xonali sonni kiriting.",
            parse_mode="Markdown"
        )

if __name__ == "__main__":
    asyncio.run(main())

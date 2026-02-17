from config import REQUIRED_CHANNELS, DATABASE_PATH
import sqlite3
import hashlib
import logging

# Minimum TON that can be withdrawn
MIN_WITHDRAWAL = 0.1

# Use the same DATABASE_PATH from config
DB_PATH = DATABASE_PATH

def get_referral_bonus_by_type(referral_type: str):
    """Get bonus amount based on referral type from settings"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Try to get from settings first
    setting_key = f'referral_bonus_{referral_type}'
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = ?", (setting_key,))
    result = cursor.fetchone()
    
    if result:
        try:
            bonus = float(result[0])
            logging.info(f"Found {referral_type} bonus in settings: {bonus}")
            conn.close()
            return bonus
        except (ValueError, TypeError):
            pass
    
    # Fallback to default values
    defaults = {
        "ton": 0.03,
        "stars": 2,
        "uc": 2
    }
    
    default_bonus = defaults.get(referral_type, 0.03)  # Default to TON bonus
    logging.info(f"Using default {referral_type} bonus: {default_bonus}")
    conn.close()
    return default_bonus

def get_referral_bonus_text(referral_type: str, amount):
    """Get bonus text based on referral type and amount"""
    texts = {
        "ton": f"💰 Sizga {amount} TON bonus qo'shildi.",
        "stars": f"⭐ Sizga {amount} STARS bonus qo'shildi.",
        "uc": f"🛡 Sizga {amount} UC bonus qo'shildi."
    }
    return texts.get(referral_type, f"💰 Sizga {amount} TON bonus qo'shildi.")

def get_referral_stars_balance(user_id: int) -> int:
    """Get total Stars earned from referrals (Stars + UC converted to Stars)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Calculate Stars from referrals (2 Stars per referral)
    cursor.execute('''
        SELECT COUNT(*) 
        FROM users 
        WHERE referred_by = ? AND has_received_referral_bonus = 1
    ''', (user_id,))
    
    referral_count = cursor.fetchone()[0] or 0
    referral_stars = referral_count * 2  # 2 Stars per referral
    
    # Also get UC balance and convert to Stars (2 UC = 1 Star for display purposes)
    cursor.execute('SELECT stars_purchased FROM users WHERE user_id = ?', (user_id,))
    uc_result = cursor.fetchone()
    uc_balance = uc_result[0] if uc_result else 0
    
    conn.close()
    return referral_stars + uc_balance  # Total Stars balance (referral Stars + UC balance)

async def track_referral_new(bot, referred_id: int, referrer_id: int = None, referral_type: str = "ton") -> tuple[bool, str]:
    """
    Track a new referral and give bonus based on referral type
    Returns: (success: bool, message: str, referrer_id: int)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get user's registration and activity status
        cursor.execute('''
            SELECT referred_by, has_received_referral_bonus 
            FROM users 
            WHERE user_id = ?
        ''', (referred_id,))
        
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False, "Foydalanuvchi topilmadi!", None
            
        db_referred_by, has_received_bonus = result
        
        # Determine effective referrer_id
        effective_referrer_id = db_referred_by if db_referred_by else referrer_id
        
        if not effective_referrer_id:
            conn.close()
            return False, "Referal ma'lumoti topilmadi.", None

        if effective_referrer_id == referred_id:
            conn.close()
            return False, "O'zingizga referal bo'la olmaysiz!", None
            
        # Check if user has already received bonus
        if has_received_bonus:
            conn.close()
            return False, "Siz allaqachon referal bonusini olgansiz!", None
            
        # STRICT NEW USER CHECK:
        if db_referred_by is None:
            conn.close()
            return False, "Referal bonus faqat yangi foydalanuvchilarga beriladi!", None

        # Check if user is subscribed to all required channels
        is_subscribed = await check_user_subscribed(bot, referred_id)
        if not is_subscribed:
            conn.close()
            return False, "Referal bonusini olish uchun barcha kanallarga obuna bo'lishingiz kerak!", None
        
        # Update referred user with referrer info if not already set
        if db_referred_by is None:
            cursor.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (effective_referrer_id, referred_id))
        
        # Add bonus based on referral type
        bonus_amount = get_referral_bonus_by_type(referral_type)
        
        if referral_type == "ton":
            # Update referrer's earned_ton
            cursor.execute('''
                UPDATE users 
                SET earned_ton = COALESCE(earned_ton, 0) + ?
                WHERE user_id = ?
            ''', (bonus_amount, effective_referrer_id))
        elif referral_type == "stars":
            # Update referrer's stars_purchased
            cursor.execute('''
                UPDATE users 
                SET stars_purchased = COALESCE(stars_purchased, 0) + ?
                WHERE user_id = ?
            ''', (bonus_amount, effective_referrer_id))
        elif referral_type == "uc":
            # Update referrer's stars_purchased (using stars_purchased as UC balance)
            cursor.execute('''
                UPDATE users 
                SET stars_purchased = COALESCE(stars_purchased, 0) + ?
                WHERE user_id = ?
            ''', (bonus_amount, effective_referrer_id))
        
        # Mark referred user as having received bonus
        cursor.execute('''
            UPDATE users 
            SET has_received_referral_bonus = 1
            WHERE user_id = ?
        ''', (referred_id,))
        
        conn.commit()
        bonus_text = get_referral_bonus_text(referral_type, bonus_amount)
        return True, f"Tabriklaymiz! {bonus_text}", effective_referrer_id
        
    except Exception as e:
        conn.rollback()
        print(f"Error in track_referral_new: {e}")
        return False, f"Xatolik yuz berdi: {str(e)}", None
        
    finally:
        conn.close()

def get_referral_bonus() -> float:
    """Get the current referral bonus amount from settings"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'referral_bonus'")
    result = cursor.fetchone()
    conn.close()
    
    if result:
        try:
            return float(result[0])
        except (ValueError, TypeError):
            return 0.001  # Default value if conversion fails
    return 0.001  # Default value if not set

def generate_referral_code(user_id: int) -> str:
    """Generate a unique referral code for a user"""
    return hashlib.md5(f"ref_{user_id}".encode()).hexdigest()[:8].upper()

def get_user_by_referral_code(code: str) -> tuple:
    """Get user by referral code"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE referral_code = ?', (code,))
    user = cursor.fetchone()
    conn.close()
    return user

from utils import get_required_channels

async def check_user_subscribed(bot, user_id: int) -> bool:
    """Check if user is subscribed to all required channels (Config + DB)"""
    required_channels = await get_required_channels()
    if not required_channels:
        return True
        
    for channel_id, channel_name in required_channels:
        try:
            # Handle both usernames (with @) and numeric IDs
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ('left', 'kicked'):
                return False
        except Exception as e:
            print(f"Error checking subscription for user {user_id} in channel {channel_id}: {e}")
            return False
    return True

async def track_referral(bot, referred_id: int, referrer_id: int = None) -> tuple[bool, str]:
    """
    Track a new referral and give bonus if conditions are met
    Only awards bonus for new users who register through referral link
    Returns: (success: bool, message: str)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get user's registration and activity status
        cursor.execute('''
            SELECT referred_by, has_received_referral_bonus, 
                   (SELECT COUNT(*) FROM purchase_requests WHERE user_id = ?) as purchase_count,
                   (SELECT COUNT(*) FROM ton_purchases WHERE user_id = ?) as ton_purchase_count,
                   (SELECT COUNT(*) FROM payment_requests WHERE user_id = ?) as payment_count,
                   (SELECT COUNT(*) FROM transactions WHERE user_id = ?) as action_count
            FROM users 
            WHERE user_id = ?
        ''', (referred_id, referred_id, referred_id, referred_id, referred_id))
        
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False, "Foydalanuvchi topilmadi!"
            
        db_referred_by, has_received_bonus, purchase_count, ton_purchase_count, payment_count, action_count = result
        
        # Determine effective referrer_id
        # Source of truth for "new user from link" is the referred_by column set during registration
        effective_referrer_id = db_referred_by if db_referred_by else referrer_id
        
        if not effective_referrer_id:
            conn.close()
            return False, "Referal ma'lumoti topilmadi.", None

        if effective_referrer_id == referred_id:
            conn.close()
            return False, "O'zingizga referal bo'la olmaysiz!", None
            
        # Check if user was already referred by someone else
        if db_referred_by is not None and db_referred_by != effective_referrer_id:
            conn.close()
            return False, "Ushbu foydalanuvchi allaqachon boshqa orqali ro'yxatdan o'tgan!", None
        
        # Check if user has already received bonus
        if has_received_bonus:
            conn.close()
            return False, "Siz allaqachon referal bonusini olgansiz!", None
            
        # STRICT NEW USER CHECK:
        # If referred_by was not set during create_user (registration), 
        # it means the user was already in the database before clicking the link.
        if db_referred_by is None:
            conn.close()
            return False, "Referal bonus faqat yangi foydalanuvchilarga beriladi!", None

        
        # Check if user is subscribed to all required channels
        is_subscribed = await check_user_subscribed(bot, referred_id)
        if not is_subscribed:
            conn.close()
            return False, "Referal bonusini olish uchun barcha kanallarga obuna bo'lishingiz kerak!"
        
        # Update referred user with referrer info if not already set
        if db_referred_by is None:
            cursor.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (effective_referrer_id, referred_id))
        
        # Add bonus to referrer's earned_ton
        bonus_amount = get_referral_bonus()
        
        # 1. Update referrer's earned_ton
        cursor.execute('''
            UPDATE users 
            SET earned_ton = COALESCE(earned_ton, 0) + ?
            WHERE user_id = ?
        ''', (bonus_amount, effective_referrer_id))
        
        # 2. Mark referred user as having received bonus (to prevent multiple bonuses for same user)
        cursor.execute('''
            UPDATE users 
            SET has_received_referral_bonus = 1
            WHERE user_id = ?
        ''', (referred_id,))
        
        conn.commit()
        return True, f"Tabriklaymiz! Sizga {bonus_amount} TON referal bonusi qo'shildi!", effective_referrer_id
        
    except Exception as e:
        conn.rollback()
        print(f"Error in track_referral: {e}")
        return False, f"Xatolik yuz berdi: {str(e)}", None
        
    finally:
        conn.close()

def get_referral_stats(user_id: int) -> dict:
    """Get user's referral statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get number of referrals
    cursor.execute('''
        SELECT COUNT(*) 
        FROM users 
        WHERE referred_by = ?
    ''', (user_id,))
    referral_count = cursor.fetchone()[0] or 0
    
    # Get earned and withdrawn TON
    cursor.execute('''
        SELECT 
            COALESCE(earned_ton, 0) as earned_ton,
            COALESCE(withdrawn_ton, 0) as withdrawn_ton
        FROM users 
        WHERE user_id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    earned_ton = result[0] if result else 0
    withdrawn_ton = result[1] if result else 0
    
    conn.close()
    
    return {
        'referral_count': referral_count,
        'earned_ton': earned_ton,
        'withdrawn_ton': withdrawn_ton,
        'available_ton': earned_ton - withdrawn_ton
    }

def withdraw_referral_earnings(user_id: int, wallet_address: str, amount: float = None) -> tuple[bool, str]:
    """Withdraw referral earnings to TON wallet"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get user's available TON
    cursor.execute('''
        SELECT 
            COALESCE(earned_ton, 0) as earned_ton,
            COALESCE(withdrawn_ton, 0) as withdrawn_ton
        FROM users 
        WHERE user_id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    if not result:
        conn.close()
        return False, "Foydalanuvchi topilmadi"
    
    earned_ton, withdrawn_ton = result
    available_ton = earned_ton - withdrawn_ton
    
    # Use provided amount or all available if not specified
    withdrawal_amount = amount if amount is not None else available_ton
    
    if withdrawal_amount > available_ton:
        withdrawal_amount = available_ton
    
    if withdrawal_amount < MIN_WITHDRAWAL:
        conn.close()
        return False, f"Minimal yechib olish miqdori {MIN_WITHDRAWAL} TON"
    
    # Update withdrawn amount
    cursor.execute('''
        UPDATE users 
        SET withdrawn_ton = COALESCE(withdrawn_ton, 0) + ? 
        WHERE user_id = ?
    ''', (withdrawal_amount, user_id))
    
    # Record the withdrawal request
    cursor.execute('''
        INSERT INTO ton_purchases 
        (user_id, amount, price, recipient, wallet_address, status)
        VALUES (?, ?, 0, 'withdrawal', ?, 'pending')
    ''', (user_id, withdrawal_amount, wallet_address))
    
    withdrawal_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return True, withdrawal_id, withdrawal_amount

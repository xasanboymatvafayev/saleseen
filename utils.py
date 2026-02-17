import sqlite3
import os
import logging
from config import REQUIRED_CHANNELS, DATABASE_PATH, ADMINS, ADMIN_TON_WALLET

# Get absolute path to DB
if os.path.isabs(DATABASE_PATH):
    DB_PATH = DATABASE_PATH
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATABASE_PATH)

def get_user(user_id):
    """Get user data from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception as e:
        logging.error(f"Error getting user {user_id}: {e}")
        return None

def is_user_banned(user_id):
    """Check if user is banned"""
    user = get_user(user_id)
    if user:
        return bool(user['is_banned'])
    return False

def is_admin(user_id):
    """Check if user is an admin"""
    if str(user_id) in [str(a) for a in ADMINS]:
        return True
    user = get_user(user_id)
    if user:
        return bool(user['is_admin'])
    return False

def get_all_admins():
    """Get all admin IDs from config and database"""
    admin_ids = set(str(a) for a in ADMINS)
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE is_admin = 1')
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            admin_ids.add(str(row[0]))
    except Exception as e:
        logging.error(f"Error getting all admins: {e}")
    return [int(aid) for aid in admin_ids]

async def get_required_channels():
    """Get all required channels from config and database, excluding deleted main channels"""
    deleted_main_ids = set()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS deleted_main_channels (channel_id TEXT PRIMARY KEY)')
        cursor.execute('SELECT channel_id FROM deleted_main_channels')
        deleted_main_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
    except Exception as e:
        logging.error(f"Error fetching deleted main channels: {e}")

    channels = []
    for c in REQUIRED_CHANNELS:
        if str(c['id']) not in [str(did) for did in deleted_main_ids]:
            channels.append((c['id'], c['name']))
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id, channel_name FROM channels')
        db_channels = cursor.fetchall()
        conn.close()
        for cid, name in db_channels:
            if not any(str(cid) == str(existing[0]) for existing in channels):
                channels.append((cid, name))
    except Exception as e:
        logging.error(f"Error fetching DB channels: {e}")
        
    return channels

def get_price(item_type):
    """Get price for a specific item type from the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT price FROM prices WHERE item_type = ?', (item_type,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return float(row[0])
    except Exception as e:
        logging.error(f"Error getting price for {item_type}: {e}")
    
    # Default values if not in DB
    defaults = {
        "stars": 1000.0,
        "stars_sell": 900.0,
        "ton": 70000.0,
        "premium_3month": 150000.0,
        "premium_6month": 250000.0,
        "premium_12month": 400000.0
    }
    return defaults.get(item_type, 0.0)

def get_ton_wallet():
    """Get TON wallet address from settings"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT setting_value FROM settings WHERE setting_key = ?', ('ton_wallet',))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else ADMIN_TON_WALLET
    except Exception as e:
        logging.error(f"Error getting TON wallet: {e}")
        return ADMIN_TON_WALLET

def get_ton_setting(key):
    """Get a TON setting from settings table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT setting_value FROM settings WHERE setting_key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception as e:
        logging.error(f"Error getting TON setting {key}: {e}")
    return None

def get_ton_sell_price():
    """Get TON sell price from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT price FROM prices WHERE item_type = "ton_sell"')
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return float(result[0])
        else:
            # Fallback to default price
            return 18000.0  # Default sell price
    except Exception as e:
        logging.error(f"Error getting TON sell price: {e}")
        return 18000.0  # Fallback price

def get_ton_buy_price():
    """Get TON buy price from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT price FROM prices WHERE item_type = "ton_buy"')
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return float(result[0])
        else:
            # Fallback to default price
            return 22000.0  # Default buy price
    except Exception as e:
        logging.error(f"Error getting TON buy price: {e}")
        return 22000.0  # Fallback price

def get_ton_market_price():
    """Get TON market price from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT price FROM prices WHERE item_type = "ton_market"')
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return float(result[0])
        else:
            # Fallback to default price
            return 20000.0  # Default market price
    except Exception as e:
        logging.error(f"Error getting TON market price: {e}")
        return 20000.0  # Fallback price

def set_ton_setting(key, value, user_id=None):
    """Save a setting to the settings table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (setting_key TEXT PRIMARY KEY, setting_value TEXT)')
        cursor.execute('INSERT OR REPLACE INTO settings (setting_key, setting_value) VALUES (?, ?)', (key, str(value)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error saving setting {key}: {e}")
        return False

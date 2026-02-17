import sqlite3
import sys

def setup_ton_settings():
    """Create the ton_settings table if it doesn't exist"""
    try:
        conn = sqlite3.connect('stars_shop.db')
        cursor = conn.cursor()
        
        # Create ton_settings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ton_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER DEFAULT 0
        )
        ''')
        
        # Insert default values if they don't exist
        default_settings = [
            ('ton_wallet_address', 'EQBBv8a1R3gXhXkJxJbDGYteZYZHhYJ4wjZQZJzXyFjWqj6X'),
            ('ton_sell_price', '35000')
        ]
        
        for key, value in default_settings:
            cursor.execute('''
            INSERT OR IGNORE INTO ton_settings (setting_key, setting_value)
            VALUES (?, ?)
            ''', (key, value))
        
        conn.commit()
        conn.close()
        print("[SUCCESS] TON settings table created and initialized successfully!")
        return True
    except sqlite3.Error as e:
        print(f"[ERROR] Error setting up TON settings: {e}")
        return False

if __name__ == "__main__":
    # Set console output encoding to UTF-8
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    setup_ton_settings()

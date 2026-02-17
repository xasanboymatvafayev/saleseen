import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop', 'stars_shop.db')

def setup_ton_percentage():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Ensure settings table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Set default TON percentage to 10%
        cursor.execute('''
            INSERT OR REPLACE INTO settings (setting_key, setting_value, updated_at)
            VALUES ('ton_percentage', '10', datetime('now'))
        ''')
        
        conn.commit()
        print("✅ TON percentage muvaffaqiyatli sozlandi: 10%")
        
    except Exception as e:
        print(f"❌ Xatolik: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_ton_percentage()

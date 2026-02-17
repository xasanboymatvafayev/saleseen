import sqlite3

def setup_settings_table():
    try:
        # Connect to the database
        conn = sqlite3.connect('stars_shop.db')
        cursor = conn.cursor()
        
        # Create settings table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Initialize default referral bonus if not set
        cursor.execute("INSERT OR IGNORE INTO settings (setting_key, setting_value) VALUES (?, ?)",
                     ('referral_bonus', '10'))
        
        # Commit changes and close connection
        conn.commit()
        print("Successfully set up settings table")
        
    except Exception as e:
        print(f"Error setting up settings table: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    setup_settings_table()

import sqlite3

def update_referral_settings():
    conn = sqlite3.connect('stars_shop.db')
    cursor = conn.cursor()
    
    # Create settings table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key TEXT UNIQUE NOT NULL,
        setting_value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Initialize referral bonus if it doesn't exist
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'referral_bonus'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)",
            ('referral_bonus', '0.001')  # Default 0.001 TON
        )
    
    conn.commit()
    conn.close()
    print("Referral settings updated successfully!")

if __name__ == "__main__":
    update_referral_settings()

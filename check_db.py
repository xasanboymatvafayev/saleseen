import sqlite3

def check_database():
    try:
        # Connect to the database
        conn = sqlite3.connect('stars_shop.db')
        cursor = conn.cursor()
        
        # List all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("\nTables in the database:")
        for table in tables:
            print(f"- {table[0]}")
        
        # Check if settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings';")
        if not cursor.fetchone():
            print("\nERROR: 'settings' table does not exist!")
            print("Creating 'settings' table now...")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            cursor.execute("INSERT OR IGNORE INTO settings (setting_key, setting_value) VALUES (?, ?)",
                         ('referral_bonus', '10'))
            conn.commit()
            print("Successfully created 'settings' table")
        else:
            print("\n'settings' table exists. Checking its structure...")
            cursor.execute("PRAGMA table_info(settings)")
            columns = cursor.fetchall()
            print("\nColumns in 'settings' table:")
            for col in columns:
                print(f"- {col[1]} ({col[2]})")
            
            # Check if referral_bonus exists
            cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'referral_bonus'")
            result = cursor.fetchone()
            if result:
                print(f"\nReferral bonus is set to: {result[0]}")
            else:
                print("\nNo referral_bonus setting found. Adding default value...")
                cursor.execute("INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)",
                             ('referral_bonus', '10'))
                conn.commit()
                print("Added default referral_bonus = 10")
        
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_database()

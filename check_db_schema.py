import sqlite3
import logging

def check_and_fix_db():
    conn = None
    try:
        conn = sqlite3.connect('stars_shop.db')
        cursor = conn.cursor()
        
        # Check if ton_purchases table exists and has required columns
        cursor.execute("PRAGMA table_info('ton_purchases')")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add missing columns if they don't exist
        if 'completed_at' not in columns:
            cursor.execute('ALTER TABLE ton_purchases ADD COLUMN completed_at TIMESTAMP')
            print("Added 'completed_at' column to ton_purchases table")
        
        if 'admin_id' not in columns:
            cursor.execute('ALTER TABLE ton_purchases ADD COLUMN admin_id INTEGER')
            print("Added 'admin_id' column to ton_purchases table")
        
        # Check if users table has ton_purchased column
        cursor.execute("PRAGMA table_info('users')")
        user_columns = [col[1] for col in cursor.fetchall()]
        
        if 'ton_purchased' not in user_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN ton_purchased FLOAT DEFAULT 0')
            print("Added 'ton_purchased' column to users table")
        
        # Create transactions table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount FLOAT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        print("Database schema is up to date")
        
    except Exception as e:
        print(f"Error updating database schema: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_and_fix_db()

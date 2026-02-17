import sqlite3
import sys

# Set console output encoding to UTF-8
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def create_ton_sales_table():
    """Create the ton_sales table if it doesn't exist"""
    try:
        conn = sqlite3.connect('stars_shop.db')
        cursor = conn.cursor()
        
        # Create ton_sales table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ton_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            price_per_ton REAL NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            photo_id TEXT,
            updated_at TIMESTAMP,
            admin_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')
        
        # Add ton_balance column to users table if it doesn't exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'ton_balance' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN ton_balance REAL DEFAULT 0.0')
        
        conn.commit()
        print("[SUCCESS] Database setup completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Error setting up database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    create_ton_sales_table()

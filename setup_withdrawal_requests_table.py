import sqlite3

DB_PATH = "stars_shop.db"

def setup_withdrawal_requests_table():
    """Create withdrawal_requests table if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawal_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            withdrawal_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP NULL,
            admin_id INTEGER NULL,
            wallet_address TEXT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("withdrawal_requests table created successfully!")

if __name__ == "__main__":
    setup_withdrawal_requests_table()

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop', 'stars_shop.db')

def add_details_column():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Add details column to purchase_requests table
        cursor.execute('''
            ALTER TABLE purchase_requests 
            ADD COLUMN details TEXT
        ''')
        
        conn.commit()
        print("✅ 'details' column successfully added to purchase_requests table")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ 'details' column already exists in purchase_requests table")
        else:
            print(f"❌ Error adding column: {e}")
    
    conn.close()

if __name__ == "__main__":
    add_details_column()

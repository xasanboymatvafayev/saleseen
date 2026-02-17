import sqlite3

def update_ton_sales_table():
    """Add completed_at column to ton_sales table if it doesn't exist"""
    conn = None
    try:
        conn = sqlite3.connect('stars_shop.db')
        cursor = conn.cursor()
        
        # Check if the column already exists
        cursor.execute("PRAGMA table_info(ton_sales)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'completed_at' not in columns:
            print("Adding 'completed_at' column to ton_sales table...")
            cursor.execute('ALTER TABLE ton_sales ADD COLUMN completed_at TIMESTAMP')
            conn.commit()
            print("Successfully added 'completed_at' column to ton_sales table.")
        else:
            print("'completed_at' column already exists in ton_sales table.")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_ton_sales_table()

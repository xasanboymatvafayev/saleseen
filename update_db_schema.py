import sqlite3

def update_ton_purchases_table():
    try:
        conn = sqlite3.connect('stars_shop.db')
        cursor = conn.cursor()
        
        # Check if completed_at column exists
        cursor.execute("PRAGMA table_info(ton_purchases)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'completed_at' not in columns:
            # Add completed_at column if it doesn't exist
            cursor.execute('''
                ALTER TABLE ton_purchases 
                ADD COLUMN completed_at TIMESTAMP
            ''')
            conn.commit()
            print("✅ Successfully added 'completed_at' column to ton_purchases table")
        else:
            print("ℹ️ 'completed_at' column already exists in ton_purchases table")
            
        # Check if admin_id column exists
        if 'admin_id' not in columns:
            # Add admin_id column if it doesn't exist
            cursor.execute('''
                ALTER TABLE ton_purchases 
                ADD COLUMN admin_id INTEGER
            ''')
            conn.commit()
            print("✅ Successfully added 'admin_id' column to ton_purchases table")
        else:
            print("ℹ️ 'admin_id' column already exists in ton_purchases table")
            
    except Exception as e:
        print(f"❌ Error updating database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_ton_purchases_table()

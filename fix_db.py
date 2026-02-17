import sqlite3
import os

DB_PATH = 'stars_shop.db'
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check if table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_star_sales'")
table_exists = cursor.fetchone()

if table_exists:
    # Check if status column exists
    cursor.execute('PRAGMA table_info(pending_star_sales)')
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'status' not in columns:
        print('Adding status column...')
        cursor.execute('ALTER TABLE pending_star_sales ADD COLUMN status TEXT DEFAULT "pending"')
        
    if 'completed_at' not in columns:
        print('Adding completed_at column...')
        cursor.execute('ALTER TABLE pending_star_sales ADD COLUMN completed_at TIMESTAMP')
        
    print('Table updated successfully!')
else:
    print('Table does not exist, will be created on bot startup')

conn.commit()
conn.close()
print('Database update completed!')

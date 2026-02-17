import sqlite3
import os

db_path = 'stars_shop/stars_shop.db'
if not os.path.exists(db_path):
    db_path = 'stars_shop.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT user_id, username, is_admin FROM users WHERE user_id = 5735723011')
print(f"User 5735723011: {cursor.fetchone()}")

cursor.execute('SELECT user_id FROM users WHERE is_admin = 1')
print(f"Admins in DB: {cursor.fetchall()}")
conn.close()

import sqlite3
conn = sqlite3.connect('stars_shop.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)
for table in tables:
    cursor.execute(f"PRAGMA table_info({table[0]})")
    print(f"Schema for {table[0]}:", cursor.fetchall())
conn.close()

import sqlite3
conn = sqlite3.connect('stars_shop/stars_shop.db')
cursor = conn.cursor()
try:
    cursor.execute('SELECT * FROM channels')
    print("Channels in DB:", cursor.fetchall())
except Exception as e:
    print("Error:", e)
conn.close()

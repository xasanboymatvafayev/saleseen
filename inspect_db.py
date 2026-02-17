import sqlite3
conn = sqlite3.connect('stars_shop/stars_shop.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM channels')
print("Channels:", cursor.fetchall())
conn.close()
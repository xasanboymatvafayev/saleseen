import sqlite3
conn = sqlite3.connect('stars_shop/stars_shop.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM channels')
print(f"Removed {cursor.rowcount} channels.")
conn.commit()
conn.close()
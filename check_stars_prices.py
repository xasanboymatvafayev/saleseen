import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check all prices
cursor.execute("SELECT item_type, price FROM prices WHERE item_type LIKE 'stars%'")
stars_prices = cursor.fetchall()

print("Stars prices in database:")
for item_type, price in stars_prices:
    print(f"{item_type}: {price}")

conn.close()

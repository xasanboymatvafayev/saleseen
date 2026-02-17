import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check all TON prices
cursor.execute("SELECT item_type, price FROM prices WHERE item_type LIKE 'ton%'")
ton_prices = cursor.fetchall()

print("TON prices in database:")
for item_type, price in ton_prices:
    print(f"{item_type}: {price}")

# Check settings table for percentage
cursor.execute("SELECT setting_key, setting_value FROM settings WHERE setting_key = 'ton_percentage'")
percentage = cursor.fetchone()
if percentage:
    print(f"TON percentage: {percentage[1]}%")

conn.close()

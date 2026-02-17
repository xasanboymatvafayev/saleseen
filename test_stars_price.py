import sqlite3
import os
from utils import get_price

# Test get_price function
stars_price = get_price("stars")
stars_sell_price = get_price("stars_sell")

print(f"get_price('stars'): {stars_price}")
print(f"get_price('stars_sell'): {stars_sell_price}")

# Check database directly
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT item_type, price FROM prices WHERE item_type LIKE 'stars%'")
db_prices = cursor.fetchall()

print("\nDatabase prices:")
for item_type, price in db_prices:
    print(f"{item_type}: {price}")

conn.close()

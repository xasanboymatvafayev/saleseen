import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop', 'stars_shop.db')

def check_prices():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM prices')
    all_prices = cursor.fetchall()
    
    print("All prices in database:")
    for price in all_prices:
        print(f"  {price}")
    
    cursor.execute('SELECT * FROM prices WHERE item_type LIKE "pubg%"')
    pubg_prices = cursor.fetchall()
    
    print("\nPUBG prices:")
    for price in pubg_prices:
        print(f"  {price}")
    
    conn.close()

if __name__ == "__main__":
    check_prices()

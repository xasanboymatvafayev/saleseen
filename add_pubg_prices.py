import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop', 'stars_shop.db')

def add_pubg_prices():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Default PUBG UC prices
    pubg_prices = {
        'pubg_uc_60': 12000,      # 60 UC = 12,000 so'm
        'pubg_uc_300': 55000,     # 300 UC = 55,000 so'm  
        'pubg_uc_600': 105000,    # 600 UC = 105,000 so'm
        'pubg_uc_1500': 250000,   # 1500 UC = 250,000 so'm
        'pubg_uc_3000': 480000,   # 3000 UC = 480,000 so'm
        'pubg_uc_6000': 950000,   # 6000 UC = 950,000 so'm
    }
    
    for item_type, price in pubg_prices.items():
        # Check if price already exists
        cursor.execute('SELECT id FROM prices WHERE item_type = ?', (item_type,))
        existing = cursor.fetchone()
        
        if not existing:
            cursor.execute('INSERT INTO prices (item_type, price) VALUES (?, ?)', (item_type, price))
            print(f"✅ Added {item_type}: {price:,} so'm")
        else:
            cursor.execute('UPDATE prices SET price = ? WHERE item_type = ?', (price, item_type))
            print(f"🔄 Updated {item_type}: {price:,} so'm")
    
    conn.commit()
    conn.close()
    print("\n✅ PUBG UC prices successfully added/updated!")

if __name__ == "__main__":
    add_pubg_prices()

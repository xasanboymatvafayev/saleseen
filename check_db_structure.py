import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), 'stars_shop.db')

def check_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Tables:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table[0]}")
        cursor.execute(f"PRAGMA table_info({table[0]})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"    - {col[1]} ({col[2]})")
    
    conn.close()

if __name__ == "__main__":
    check_db()

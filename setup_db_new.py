import sqlite3
import os

DB_PATH = "stars_shop.db"

def setup_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS deleted_main_channels (channel_id TEXT PRIMARY KEY)')
    conn.commit()
    conn.close()
    print("Table deleted_main_channels created or already exists.")

if __name__ == "__main__":
    setup_db()

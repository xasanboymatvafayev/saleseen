#!/usr/bin/env python3
"""
Database fix script
"""

import sqlite3

def fix_database():
    conn = sqlite3.connect('stars_shop.db')
    cursor = conn.cursor()
    
    # Drop and recreate cards table
    cursor.execute('DROP TABLE IF EXISTS cards')
    cursor.execute('''
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number TEXT,
            card_holder TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default card
    cursor.execute('''
        INSERT INTO cards (card_number, card_holder, is_active) 
        VALUES (?, ?, 1)
    ''', ("8600123456789012", "STARS SHOP"))
    
    conn.commit()
    conn.close()
    print("✅ Database muvaffaqiyatli tuzatildi!")

if __name__ == "__main__":
    fix_database()

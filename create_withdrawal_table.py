#!/usr/bin/env python3
"""
Script to create withdrawal_requests table for the new withdrawal system
"""

import sqlite3
import os

# Get the absolute path to the database file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop.db')

def create_withdrawal_requests_table():
    """Create withdrawal_requests table if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Create withdrawal_requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawal_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                withdrawal_type TEXT NOT NULL DEFAULT 'uzs',
                status TEXT NOT NULL DEFAULT 'pending',
                card_details TEXT,
                wallet_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admin_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (admin_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_withdrawal_user_id ON withdrawal_requests(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_withdrawal_status ON withdrawal_requests(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_withdrawal_type ON withdrawal_requests(withdrawal_type)')
        
        conn.commit()
        print("✅ withdrawal_requests table created successfully!")
        
        # Show table structure
        cursor.execute("PRAGMA table_info(withdrawal_requests)")
        columns = cursor.fetchall()
        print("\n📋 Table structure:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
            
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_withdrawal_requests_table()

import sqlite3
import logging

def setup_database():
    conn = sqlite3.connect('stars_shop.db')
    cursor = conn.cursor()
    
    try:
        # Create admin_notifications table if not exists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            price REAL NOT NULL,
            recipient TEXT NOT NULL,
            wallet_address TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            admin_id INTEGER,
            completed_at TIMESTAMP
        )''')
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            # Add is_admin column if it doesn't exist
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'is_admin' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        
        # Get current users to set admin
        cursor.execute("SELECT user_id, username FROM users")
        users = cursor.fetchall()
        
        if users:
            print("\nCurrent users in the database:")
            for idx, (user_id, username) in enumerate(users, 1):
                print(f"{idx}. ID: {user_id}, Username: {username}")
            
            while True:
                try:
                    admin_choice = input("\nWhich user should be admin? (enter number): ")
                    admin_idx = int(admin_choice) - 1
                    if 0 <= admin_idx < len(users):
                        admin_id, admin_username = users[admin_idx]
                        cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (admin_id,))
                        print(f"\n✅ Success! User @{admin_username} (ID: {admin_id}) is now an admin.")
                        break
                    else:
                        print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")
        else:
            print("No users found in the database. Please add a user first.")
        
        conn.commit()
        print("\n✅ Database setup completed successfully!")
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=== Admin Setup Tool ===")
    print("This script will help you set up admin notifications.")
    setup_database()
    input("\nPress Enter to exit...")

import sqlite3

def check_admins():
    try:
        conn = sqlite3.connect('stars_shop.db')
        cursor = conn.cursor()
        print("Connected to database")
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        if not cursor.fetchone():
            print("Users table does not exist!")
            return
            
        # Get all admin users
        cursor.execute("SELECT user_id, username, is_admin FROM users WHERE is_admin = 1")
        admins = cursor.fetchall()
        
        if not admins:
            print("No admin users found in the database!")
            print("\nAll users:")
            cursor.execute("SELECT user_id, username, is_admin FROM users")
            for user in cursor.fetchall():
                print(f"User ID: {user[0]}, Username: {user[1]}, Is Admin: {user[2]}")
        else:
            print("Admin users found:")
            for admin in admins:
                print(f"Admin ID: {admin[0]}, Username: {admin[1]}, Is Admin: {admin[2]}")
                
    except Exception as e:
        print(f"Error checking admins: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_admins()

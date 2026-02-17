import sqlite3

def setup_referral_system():
    conn = sqlite3.connect('stars_shop.db')
    cursor = conn.cursor()
    
    # Add referral columns if they don't exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'referral_code' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN referral_code TEXT')
        print("Added referral_code column to users table")
        
        # Generate referral codes for existing users
        cursor.execute('SELECT user_id FROM users WHERE referral_code IS NULL')
        users = cursor.fetchall()
        for user_id, in users:
            # Generate a simple referral code based on user_id
            import hashlib
            code = hashlib.md5(str(user_id).encode()).hexdigest()[:8].upper()
            cursor.execute('UPDATE users SET referral_code = ? WHERE user_id = ?', (code, user_id))
        print(f"Generated referral codes for {len(users)} users")
    
    if 'referred_by' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN referred_by INTEGER')
        print("Added referred_by column to users table")
    
    if 'earned_ton' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN earned_ton REAL DEFAULT 0.0')
        print("Added earned_ton column to users table")
    
    if 'withdrawn_ton' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN withdrawn_ton REAL DEFAULT 0.0')
        print("Added withdrawn_ton column to users table")
    
    conn.commit()
    conn.close()
    print("Referral system setup completed!")

if __name__ == "__main__":
    setup_referral_system()
import asyncio
import logging
import aiohttp
import sqlite3
import os
from datetime import datetime

# Get the absolute path to the database file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop.db')

class TONPriceUpdater:
    def __init__(self):
        self.session = None
        self.market_price = 20000  # Default market price
        self.buy_price = 22000     # Market price + 2000
        self.sell_price = 18000    # Market price - 2000
        self.price_margin = 2000   # Margin for buy/sell prices
        
    async def get_market_price(self):
        """Get current TON market price from API"""
        try:
            # Using CoinGecko API for TON price
            url = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd"
            
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    usd_price = data['the-open-network']['usd']
                    
                    # Validate USD price
                    if usd_price <= 0:
                        logging.error(f"Invalid USD price received: {usd_price}")
                        return None
                    
                    # Convert USD to UZS (using current exchange rate)
                    # You may want to use a real USD/UZS exchange rate API
                    usd_to_uzs = 12500
                    self.market_price = int(usd_price * usd_to_uzs)
                    
                    # Validate UZS price
                    if self.market_price <= 0:
                        logging.error(f"Invalid UZS price calculated: {self.market_price}")
                        return None
                    
                    logging.info(f"TON market price updated: ${usd_price:.2f} USD = {self.market_price:,} UZS")
                    return self.market_price
                else:
                    logging.error(f"Failed to fetch TON price: HTTP {response.status}")
                    return None
                    
        except Exception as e:
            logging.error(f"Error fetching TON market price: {e}")
            return None
    
    def calculate_prices(self, market_price):
        """Calculate buy and sell prices based on market price and percentage"""
        if market_price and market_price > 0:  # Ensure positive price
            self.market_price = market_price
            
            # Get percentage from settings
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'ton_percentage'")
                result = cursor.fetchone()
                percentage = int(result[0]) if result else 10
                conn.close()
            except:
                percentage = 10  # Default to 10%
            
            # Calculate prices based on percentage
            margin = int(market_price * percentage / 100)
            self.buy_price = market_price + margin
            self.sell_price = max(market_price - margin, 1000)  # Ensure minimum sell price
            
            logging.info(f"Price calculation: Market={market_price:,}, Percentage={percentage}%, Margin={margin:,}, Buy={self.buy_price:,}, Sell={self.sell_price:,}")
        else:
            logging.warning(f"Invalid market price: {market_price}, keeping current prices")
    
    def update_database(self):
        """Update TON prices in database"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Update or insert buy price
            cursor.execute('''
                INSERT OR REPLACE INTO prices (item_type, price)
                VALUES ('ton_buy', ?)
            ''', (self.buy_price,))
            
            # Update or insert sell price
            cursor.execute('''
                INSERT OR REPLACE INTO prices (item_type, price)
                VALUES ('ton_sell', ?)
            ''', (self.sell_price,))
            
            # Update market price for reference
            cursor.execute('''
                INSERT OR REPLACE INTO prices (item_type, price)
                VALUES ('ton_market', ?)
            ''', (self.market_price,))
            
            conn.commit()
            conn.close()
            
            logging.info(f"Database updated: Buy={self.buy_price:,}, Sell={self.sell_price:,}")
            return True
            
        except Exception as e:
            logging.error(f"Error updating database: {e}")
            return False
    
    async def update_prices(self):
        """Main function to update all prices"""
        logging.info("Starting TON price update...")
        
        # Get market price
        market_price = await self.get_market_price()
        
        if market_price and market_price > 0:
            # Calculate buy/sell prices
            self.calculate_prices(market_price)
            
            # Update database
            success = self.update_database()
            
            if success:
                logging.info("✅ TON prices updated successfully!")
                return True
            else:
                logging.error("❌ Failed to update database")
                return False
        else:
            logging.warning(f"⚠️ Could not get valid market price: {market_price}, keeping current prices")
            return False
    
    async def start_price_updates(self):
        """Start background task for price updates"""
        self.session = aiohttp.ClientSession()
        
        try:
            while True:
                await self.update_prices()
                
                # Wait 1 minute before next update
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            logging.info("TON price updater stopped")
        finally:
            if self.session:
                await self.session.close()
    
    async def stop(self):
        """Stop the price updater"""
        if self.session:
            await self.session.close()

# Global instance
ton_price_updater = TONPriceUpdater()

# Background task
async def start_ton_price_updates():
    """Start the TON price update background task"""
    await ton_price_updater.start_price_updates()

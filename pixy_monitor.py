import logging
from datetime import datetime, timedelta
from pixy_api import PixyAPIClient
from config import PIXY_API_URL, PIXY_SEED_PHRASE, PIXY_MODE

# Global cache for API status
_api_status_cache = {
    "last_check": None,
    "status": None,
    "balance": None,
    "error": None
}

async def get_pixy_status() -> dict:
    """Get PixyAPI status and balance with caching"""
    global _api_status_cache
    
    # Check if we have recent cached data (within 5 minutes)
    if (_api_status_cache["last_check"] and 
        datetime.now() - _api_status_cache["last_check"] < timedelta(minutes=5)):
        return _api_status_cache
    
    try:
        client = PixyAPIClient.from_env()
        
        # Get API status
        status_response = client.get_status()
        
        # Get balance
        balance_response = client.get_balance()
        
        # Update cache
        _api_status_cache.update({
            "last_check": datetime.now(),
            "status": status_response,
            "balance": balance_response,
            "error": None
        })
        
        logging.info(f"PixyAPI status checked: Status={status_response.get('ok', False)}, "
                    f"Balance={balance_response.get('balance', 'Unknown')}")
        
        return _api_status_cache
        
    except Exception as e:
        error_msg = f"PixyAPI status check failed: {str(e)}"
        logging.error(error_msg)
        
        _api_status_cache.update({
            "last_check": datetime.now(),
            "status": {"ok": False, "message": str(e)},
            "balance": None,
            "error": str(e)
        })
        
        return _api_status_cache

async def is_pixy_available() -> bool:
    """Check if PixyAPI is available and working"""
    try:
        status_data = await get_pixy_status()
        return status_data["status"].get("ok", False)
    except Exception:
        return False

async def get_pixy_balance() -> dict:
    """Get PixyAPI wallet balance information"""
    try:
        status_data = await get_pixy_status()
        return status_data["balance"] or {"ok": False, "message": "Balance unavailable"}
    except Exception as e:
        return {"ok": False, "message": f"Balance check failed: {str(e)}"}

def format_pixy_status_message() -> str:
    """Format PixyAPI status for admin display"""
    if not _api_status_cache["last_check"]:
        return "🔍 *PixyAPI status:* Not checked yet"
    
    status = _api_status_cache["status"]
    balance = _api_status_cache["balance"]
    last_check = _api_status_cache["last_check"]
    
    message = f"🔍 *PixyAPI Status*\n\n"
    message += f"📅 *Last checked:* {last_check.strftime('%Y-%m-%d %H:%M:%S')}\n"
    message += f"🌐 *API URL:* {PIXY_API_URL}\n"
    message += f"🔧 *Mode:* {PIXY_MODE.upper()}\n\n"
    
    # Status
    if status and status.get("ok"):
        message += f"✅ *API Status:* Working\n"
    else:
        message += f"❌ *API Status:* Error\n"
        if status and status.get("message"):
            message += f"📝 *Error:* {status.get('message')}\n"
    
    # Balance
    if balance and balance.get("ok"):
        balance_info = balance.get("balance", {})
        if isinstance(balance_info, dict):
            ton_balance = balance_info.get("ton", "Unknown")
            message += f"💰 *TON Balance:* {ton_balance}\n"
        else:
            message += f"💰 *Balance:* {balance_info}\n"
    elif balance:
        message += f"❌ *Balance:* Unavailable\n"
        if balance.get("message"):
            message += f"📝 *Error:* {balance.get('message')}\n"
    
    # Configuration status
    if PIXY_SEED_PHRASE:
        message += f"🔑 *Seed Phrase:* Configured ✅\n"
    else:
        message += f"🔑 *Seed Phrase:* Not configured ❌\n"
    
    return message

async def check_pixy_health() -> tuple[bool, str]:
    """Perform comprehensive PixyAPI health check"""
    try:
        # Test API connectivity
        client = PixyAPIClient.from_env()
        
        # Test status endpoint
        status_response = client.get_status()
        if not status_response.get("ok"):
            return False, f"API status check failed: {status_response.get('message', 'Unknown error')}"
        
        # Test balance endpoint
        balance_response = client.get_balance()
        if not balance_response.get("ok"):
            return False, f"Balance check failed: {balance_response.get('message', 'Unknown error')}"
        
        # Check if seed phrase is configured
        if not PIXY_SEED_PHRASE:
            return False, "Seed phrase not configured"
        
        return True, "PixyAPI is healthy and ready"
        
    except Exception as e:
        return False, f"Health check failed: {str(e)}"

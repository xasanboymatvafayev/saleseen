import logging
import asyncio
from typing import Optional, Dict, Any, Callable
from pixy_api import PixyAPIClient

class PixyAPIManager:
    """Enhanced PixyAPI manager with retry logic and fallback mechanisms"""
    
    def __init__(self):
        self.client = PixyAPIClient.from_env()
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    async def safe_api_call(
        self, 
        api_method: Callable, 
        *args, 
        fallback_value: Any = None,
        require_success: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Safely call PixyAPI method with retry logic and error handling
        
        Args:
            api_method: The PixyAPI method to call
            *args: Arguments to pass to the API method
            fallback_value: Value to return if API call fails
            require_success: Whether to require API success (affects retry logic)
            **kwargs: Keyword arguments to pass to the API method
        
        Returns:
            API response or fallback_value
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Make API call
                response = api_method(*args, **kwargs)
                
                # Check if response is successful
                if response.get("ok"):
                    logging.info(f"PixyAPI call successful on attempt {attempt + 1}")
                    return response
                else:
                    error_msg = response.get("message", "Unknown API error")
                    last_error = f"API error: {error_msg}"
                    
                    # Don't retry for certain errors
                    if any(keyword in error_msg.lower() for keyword in [
                        "hamyon topilmadi", "seed xato", "wallet", "authentication", "unauthorized"
                    ]):
                        logging.warning(f"Non-retryable error: {error_msg}")
                        break
                    
                    logging.warning(f"PixyAPI call failed on attempt {attempt + 1}: {error_msg}")
                    
            except Exception as e:
                last_error = str(e)
                logging.error(f"PixyAPI exception on attempt {attempt + 1}: {last_error}")
            
            # Wait before retry (with exponential backoff)
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        
        # All retries failed
        logging.error(f"PixyAPI call failed after {self.max_retries} attempts: {last_error}")
        
        if fallback_value is not None:
            return fallback_value
        
        return {
            "ok": False,
            "message": f"API call failed after {self.max_retries} attempts: {last_error}",
            "error_type": "MAX_RETRIES_EXCEEDED"
        }
    
    async def safe_buy_stars(
        self, 
        username: str, 
        amount: int, 
        order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Safely buy stars with retry logic"""
        return await self.safe_api_call(
            self.client.buy_stars,
            username=username,
            amount=amount,
            order_id=order_id,
            fallback_value={
                "ok": False,
                "message": "Stars purchase failed - will be processed manually",
                "fallback": True
            }
        )
    
    async def safe_buy_premium(
        self, 
        username: str, 
        months: int, 
        order_id: Optional[str] = None,
        show_sender: bool = False
    ) -> Dict[str, Any]:
        """Safely buy premium with retry logic"""
        return await self.safe_api_call(
            self.client.buy_premium,
            username=username,
            months=months,
            order_id=order_id,
            show_sender=show_sender,
            fallback_value={
                "ok": False,
                "message": "Premium purchase failed - will be processed manually",
                "fallback": True
            }
        )
    
    async def safe_transfer_ton(
        self, 
        to_address: str, 
        amount: float, 
        comment: Optional[str] = None,
        order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Safely transfer TON with retry logic"""
        return await self.safe_api_call(
            self.client.transfer_ton,
            to_address=to_address,
            amount=amount,
            comment=comment,
            order_id=order_id,
            fallback_value={
                "ok": False,
                "message": "TON transfer failed - will be processed manually",
                "fallback": True
            }
        )
    
    async def check_api_health(self) -> tuple[bool, str]:
        """Check if PixyAPI is healthy and accessible"""
        try:
            # Try to get status
            status_response = await self.safe_api_call(
                self.client.get_status,
                require_success=False
            )
            
            if not status_response.get("ok"):
                return False, f"API status check failed: {status_response.get('message', 'Unknown error')}"
            
            # Try to get balance
            balance_response = await self.safe_api_call(
                self.client.get_balance,
                require_success=False
            )
            
            if not balance_response.get("ok"):
                return False, f"Balance check failed: {balance_response.get('message', 'Unknown error')}"
            
            return True, "API is healthy"
            
        except Exception as e:
            return False, f"Health check failed: {str(e)}"

# Global instance
pixy_manager = PixyAPIManager()

async def handle_pixy_error(response: Dict[str, Any], operation: str) -> tuple[bool, str]:
    """
    Handle PixyAPI error responses
    
    Args:
        response: API response
        operation: Description of the operation (e.g., "stars purchase")
    
    Returns:
        tuple of (success, message)
    """
    if response.get("ok"):
        return True, "Success"
    
    error_msg = response.get("message", "Unknown error")
    error_type = response.get("error_type", "UNKNOWN")
    
    # Check if it's a fallback response
    if response.get("fallback"):
        return False, f"{operation} failed - will be processed manually: {error_msg}"
    
    # Handle specific error types from API documentation
    if error_type == "VALIDATION_ERROR":
        if "stars" in operation.lower() and "minimum" in error_msg.lower():
            return False, f"❌ Validatsiya xatoligi!\n\n📝 Xatolik: Stars miqdori kamida 50 ta bo'lishi kerak\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
        elif "ton" in operation.lower() and "transfer" in operation.lower():
            return False, f"❌ Validatsiya xatoligi!\n\n📝 Xatolik: TON manzili yoki summasi noto'g'ri\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
        else:
            return False, f"❌ Validatsiya xatoligi!\n\n📝 Xatolik: Username xato yoki davriy noto'g'ri (faqat 3, 6, 12 oy)\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    if error_type == "INSUFFICIENT_FUNDS":
        return False, f"❌ Hamyonda mablag' yetarli emas!\n\n📝 Xatolik: PixyAPI hamyonida pul yetarli emas\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    if error_type == "WALLET_VM_ERROR":
        return False, f"❌ Hamyon xatosi!\n\n📝 Xatolik: Seed fraza noto'g'ri yoki hamyon xatosi\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    if error_type == "FRAGMENT_API_ERROR":
        return False, f"❌ Fragment API xatoligi!\n\n📝 Xatolik: Userda allaqachon Premium mavjud yoki boshqa Fragment xatosi\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    if error_type == "FRAGMENT_TIMEOUT":
        return False, f"❌ Fragment serveri javob bermadi!\n\n📝 Xatolik: Fragment serveri timeout\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    if error_type == "USER_TRANSFER_FAIL":
        return False, f"❌ Blockchain xatosi!\n\n📝 Xatolik: Tarmoqda o'tkazma amalga oshmadi\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    if error_type == "CRITICAL_SERVER_ERROR":
        return False, f"❌ Server xatosi!\n\n📝 Xatolik: Serverning ichki xatosi\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    if error_type == "ENDPOINT_NOT_FOUND":
        return False, f"❌ Fragment API xatoligi!\n\n📝 Xatolik: API endpoint topilmadi\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning (PixyAPI konfiguratsiyasini tekshirish kerak)"
    
    if error_type == "JSON_ERROR":
        return False, f"❌ Fragment API xatoligi!\n\n📝 Xatolik: Invalid JSON response\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    # Legacy error handling
    if "hamyon" in error_msg.lower() or "seed" in error_msg.lower():
        return False, f"❌ Hamyon xatosi!\n\n📝 Xatolik: {error_msg}\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    if "balance" in error_msg.lower():
        return False, f"❌ Balans yetarli emas!\n\n📝 Xatolik: {error_msg}\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    if "username" in error_msg.lower():
        return False, f"❌ Username xato!\n\n📝 Xatolik: {error_msg}\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"
    
    # Generic error
    return False, f"❌ {operation} failed!\n\n📝 Xatolik: {error_msg}\n\n💰 Pul qaytarildi\n\n🔧 Iltimos, admin bilan bog'laning"

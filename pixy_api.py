import os
import json
import logging
import ssl
from urllib import request, error
from typing import Optional, Dict, Any


class PixyAPIClient:
    def __init__(self, api_url: Optional[str] = None, seed_phrase: Optional[str] = None, mode: Optional[str] = None):
        from config import PIXY_API_URL, PIXY_SEED_PHRASE, PIXY_MODE
        self.api_url = api_url or PIXY_API_URL or os.getenv("PIXY_API_URL", "https://api.pixy.uz")
        self.seed_phrase = seed_phrase or PIXY_SEED_PHRASE or os.getenv("PIXY_SEED_PHRASE")
        self.mode = (mode or PIXY_MODE or os.getenv("PIXY_MODE", "prod")).lower()

    @classmethod
    def from_env(cls) -> "PixyAPIClient":
        return cls()

    def _post(self, endpoint: str, payload: Dict[str, Any], timeout: int = 30, max_retries: int = 3) -> Dict[str, Any]:
        """Make POST request to PixyAPI with proper error handling and retry logic"""
        if not self.api_url:
            raise RuntimeError("PixyAPI URL is not configured")
        
        if not self.seed_phrase:
            raise RuntimeError("PixyAPI seed phrase is not configured")
        
        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        
        url = f"{self.api_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        
        # PixyAPI headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "StarsShopBot/1.0"
        }
        
        context = ssl.create_default_context()
        
        for attempt in range(max_retries):
            try:
                logging.info(f"PixyAPI Request (attempt {attempt + 1}/{max_retries}): POST {url}")
                logging.debug(f"PixyAPI Payload: {payload}")
                
                req = request.Request(url, data=data, headers=headers, method="POST")
                with request.urlopen(req, timeout=timeout, context=context) as resp:
                    body = resp.read().decode("utf-8")
                    status_code = resp.code
                    
                    logging.info(f"PixyAPI Response: Status {status_code}")
                    logging.debug(f"PixyAPI Response Body: {body}")
                    
                    if status_code == 200:
                        try:
                            response_data = json.loads(body) if body else {}
                            return response_data
                        except json.JSONDecodeError as je:
                            logging.warning(f"Failed to parse JSON response: {je}, raw body: {body[:200]}")
                            return {
                                "ok": False, 
                                "message": "Invalid JSON response",
                                "error_type": "JSON_ERROR",
                                "raw_response": body[:200]
                            }
                    else:
                        error_msg = f"HTTP {status_code}: {body[:200]}"
                        logging.error(f"PixyAPI Error: {error_msg}")
                        
                        # Check for 404 - API endpoint not found
                        if status_code == 404:
                            return {
                                "ok": False,
                                "message": f"API endpoint not found: {endpoint}. Please check PixyAPI configuration.",
                                "error_type": "ENDPOINT_NOT_FOUND",
                                "status_code": status_code,
                                "suggestion": "Verify PIXY_API_URL in config or .env file"
                            }
                        
                        return {
                            "ok": False,
                            "message": error_msg,
                            "status_code": status_code
                        }
                        
            except error.HTTPError as e:
                error_body = ""
                try:
                    error_body = e.read().decode("utf-8")
                except:
                    error_body = str(e)
                
                logging.error(f"PixyAPI HTTP Error {e.code}: {error_body}")
                
                # Try to parse error response
                try:
                    error_data = json.loads(error_body) if error_body else {}
                    error_msg = error_data.get("message", error_data.get("error", error_body))
                    error_code = error_data.get("code", error_data.get("error", "HTTP_ERROR"))  # Check both 'code' and 'error' fields
                    
                    # Check if it's a SeqNo error that might be retriable
                    if "Seqno" in error_msg and attempt < max_retries - 1:
                        delay = 5 + (attempt * 2)  # 5s, 7s, 9s delays
                        logging.warning(f"SeqNo error detected, retrying in {delay} seconds... (attempt {attempt + 1})")
                        import time
                        time.sleep(delay)  # Wait longer before retry
                        continue
                    
                    # Check if it's a wallet/seed error - don't retry
                    if "hamyon topilmadi" in error_msg.lower() or "seed xato" in error_msg.lower() or "WALLET_VM_ERROR" in str(error_code):
                        logging.error(f"Wallet/Seed error detected, no retry: {error_msg}")
                        return {
                            "ok": False,
                            "message": error_msg,
                            "error_type": error_code
                        }
                    
                    return {
                        "ok": False,
                        "message": error_msg,
                        "error_type": error_code
                    }
                except json.JSONDecodeError as je:
                    # Handle JSON parsing errors specifically
                    logging.error(f"JSON decode error: {je}, Response body: {error_body[:200]}")
                    return {
                        "ok": False,
                        "message": f"Invalid JSON response from server: {str(error_body[:100]) if error_body else 'Empty response'}",
                        "error_type": "JSON_ERROR"
                    }
                    
            except Exception as e:
                logging.error(f"PixyAPI Request Error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return {
                        "ok": False,
                        "message": str(e),
                        "error_type": "REQUEST_ERROR"
                    }
        
        return {"ok": False, "message": "Max retries exceeded"}

    def buy_premium(self, username: str, months: int, order_id: Optional[str] = None, show_sender: bool = False) -> Dict[str, Any]:
        """Buy premium subscription via PixyAPI"""
        payload = {
            "username": username,
            "duration": months,  # API expects "duration" not "months"
            "seed": self.seed_phrase  # Add seed phrase to payload
        }
        
        if order_id:
            payload["order_id"] = order_id
        
        return self._post("/premium/buy", payload)

    def buy_stars(self, username: str, amount: int, order_id: Optional[str] = None) -> Dict[str, Any]:
        """Buy stars via PixyAPI"""
        # Validate minimum amount
        if amount < 50:
            return {
                "ok": False,
                "message": "Minimum stars amount is 50",
                "error_type": "VALIDATION_ERROR"
            }
        
        payload = {
            "username": username,
            "amount": amount,
            "seed": self.seed_phrase  # Add seed phrase to payload
        }
        
        if order_id:
            payload["order_id"] = order_id
        
        return self._post("/stars/buy", payload)

    def buy_ton(self, username: str, amount: float, order_id: Optional[str] = None) -> Dict[str, Any]:
        """Buy TON for user via PixyAPI"""
        payload = {
            "username": username,
            "amount": amount,
            "seed": self.seed_phrase  # Add seed phrase to payload
        }
        
        if order_id:
            payload["order_id"] = order_id
        
        return self._post("/ton/buy", payload)

    def transfer_ton(self, to_address: str, amount: float, comment: Optional[str] = None, order_id: Optional[str] = None) -> Dict[str, Any]:
        """Transfer TON via PixyAPI"""
        payload = {
            "to": to_address,  # API expects "to" not "to_address"
            "amount": amount,
            "seed": self.seed_phrase  # Add seed phrase to payload
        }
        
        if comment:
            payload["comment"] = comment
        
        if order_id:
            payload["order_id"] = order_id
        
        return self._post("/ton/transfer", payload)

    def transfer_ton_from_user(self, user_wallet: str, amount: float, order_id: Optional[str] = None) -> Dict[str, Any]:
        """Transfer TON from user wallet to admin wallet"""
        from config import ADMIN_TON_WALLET
        
        payload = {
            "to": ADMIN_TON_WALLET,  # Transfer TO admin wallet
            "amount": amount,
            "seed": self.seed_phrase
        }
        
        if order_id:
            payload["order_id"] = order_id
        
        return self._post("/ton/transfer", payload)

    def get_balance(self) -> Dict[str, Any]:
        """Get PixyAPI wallet balance"""
        return self._post("/balance", {})

    def get_status(self) -> Dict[str, Any]:
        """Get PixyAPI status"""
        return self._post("/status", {})

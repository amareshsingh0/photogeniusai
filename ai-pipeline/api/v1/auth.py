"""
API Key Authentication and Rate Limiting for API v1.
Uses local/EFS storage (DATA_DIR). No Modal. AWS-compatible.
"""

import hashlib
import hmac
import time
from typing import Optional, Dict
from fastapi import HTTPException, Depends, status  # type: ignore[reportMissingImports]
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # type: ignore[reportMissingImports]

from .storage import api_data_volume

security = HTTPBearer()


# ==================== API Key Management ====================

class APIKeyManager:
    """Manages API keys and rate limiting"""
    
    def __init__(self):
        self.keys_file = "/data/api_keys.json"
        self.rate_limits_file = "/data/rate_limits.json"
    
    def _load_keys(self) -> Dict:
        """Load API keys from volume"""
        try:
            if api_data_volume.exists(self.keys_file):
                import json
                with api_data_volume.open(self.keys_file, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_keys(self, keys: Dict):
        """Save API keys to volume"""
        try:
            import json
            with api_data_volume.open(self.keys_file, "w") as f:
                json.dump(keys, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save API keys: {e}")
    
    def _load_rate_limits(self) -> Dict:
        """Load rate limit data"""
        try:
            if api_data_volume.exists(self.rate_limits_file):
                import json
                with api_data_volume.open(self.rate_limits_file, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_rate_limits(self, limits: Dict):
        """Save rate limit data"""
        try:
            import json
            with api_data_volume.open(self.rate_limits_file, "w") as f:
                json.dump(limits, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save rate limits: {e}")
    
    def get_user_by_api_key(self, api_key: str) -> Optional[Dict]:
        """Get user data by API key"""
        keys = self._load_keys()
        
        # Hash the provided key for lookup
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        for user_id, user_data in keys.items():
            if user_data.get("api_key_hash") == key_hash:
                tier = user_data.get("tier", "free")
                return {
                    "id": user_id,
                    "tier": tier,
                    "subscription_tier": user_data.get("subscription_tier", tier),
                    "name": user_data.get("name", "Unknown"),
                }
        
        return None
    
    def check_rate_limit(self, user_id: str, tier: str) -> bool:
        """Check if user has exceeded rate limit"""
        limits = {
            "free": {"requests_per_hour": 100},
            "pro": {"requests_per_hour": 1000},
            "enterprise": {"requests_per_hour": 100000},  # Effectively unlimited
        }
        
        tier_limit = limits.get(tier, limits["free"])
        max_requests = tier_limit["requests_per_hour"]
        
        # Load current rate limit data
        rate_data = self._load_rate_limits()
        
        current_hour = int(time.time() // 3600)
        user_key = f"{user_id}_{current_hour}"
        
        # Get current count
        current_count = rate_data.get(user_key, 0)
        
        if current_count >= max_requests:
            return False
        
        # Increment count
        rate_data[user_key] = current_count + 1
        self._save_rate_limits(rate_data)
        
        return True


# Global instance
_key_manager = None

def get_key_manager() -> APIKeyManager:
    """Get or create API key manager instance"""
    global _key_manager
    if _key_manager is None:
        _key_manager = APIKeyManager()
    return _key_manager


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """
    Verify API key and check rate limits.
    
    Returns user data if valid, raises HTTPException if invalid.
    """
    api_key = credentials.credentials
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    # Get user by API key
    key_manager = get_key_manager()
    user = key_manager.get_user_by_api_key(api_key)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    # Check rate limit
    if not key_manager.check_rate_limit(user["id"], user["tier"]):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {user['tier']} tier. "
                  f"Upgrade to Pro or Enterprise for higher limits."
        )
    
    return user


# ==================== Helper Functions ====================

def create_api_key(user_id: str, tier: str = "free", name: str = "") -> str:
    """
    Create a new API key for a user.
    
    In production, this would be called from an admin endpoint
    or user dashboard.
    """
    import secrets
    
    # Generate API key
    api_key = f"pk_live_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Save to volume
    key_manager = get_key_manager()
    keys = key_manager._load_keys()
    keys[user_id] = {
        "api_key_hash": key_hash,
        "tier": tier,
        "name": name,
        "created_at": time.time(),
    }
    key_manager._save_keys(keys)
    
    return api_key

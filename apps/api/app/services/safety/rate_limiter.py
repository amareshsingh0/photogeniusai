"""
Redis-based rate limiting for safety system.
Limits generation requests per user.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json

try:
    import redis.asyncio as redis  # type: ignore[reportMissingImports]
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis not available. Rate limiting will be disabled.")

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimiter:
    """
    Redis-based rate limiter
    
    Limits:
    - 10 generations per minute
    - 100 generations per hour
    - 1000 generations per day
    """
    
    # Rate limits
    PER_MINUTE = 10
    PER_HOUR = 100
    PER_DAY = 1000
    
    def __init__(self):
        """Initialize rate limiter"""
        self.redis_client: Optional[redis.Redis] = None
        self._initialized = False
        
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=False,  # Keep as bytes for performance
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self._initialized = True
                logger.info("Rate limiter initialized with Redis")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Rate limiting disabled.")
                self._initialized = False
        else:
            logger.warning("Redis not installed. Rate limiting disabled.")
    
    async def check_rate_limit(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Check if user has exceeded rate limits
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with:
            - allowed: bool
            - reason: str (if not allowed)
            - retry_after: int (seconds until next allowed request)
        """
        if not self._initialized or not self.redis_client:
            # Fail-safe: Allow if Redis unavailable
            return {"allowed": True}
        
        try:
            now = datetime.utcnow()
            
            # Check minute limit
            minute_key = f"rate_limit:gen:{user_id}:minute"
            minute_count = await self.redis_client.get(minute_key)
            minute_count = int(minute_count) if minute_count else 0
            
            if minute_count >= self.PER_MINUTE:
                ttl = await self.redis_client.ttl(minute_key)
                return {
                    "allowed": False,
                    "reason": f"Rate limit exceeded: {self.PER_MINUTE} generations per minute",
                    "retry_after": ttl if ttl > 0 else 60
                }
            
            # Check hour limit
            hour_key = f"rate_limit:gen:{user_id}:hour"
            hour_count = await self.redis_client.get(hour_key)
            hour_count = int(hour_count) if hour_count else 0
            
            if hour_count >= self.PER_HOUR:
                ttl = await self.redis_client.ttl(hour_key)
                return {
                    "allowed": False,
                    "reason": f"Rate limit exceeded: {self.PER_HOUR} generations per hour",
                    "retry_after": ttl if ttl > 0 else 3600
                }
            
            # Check day limit
            day_key = f"rate_limit:gen:{user_id}:day"
            day_count = await self.redis_client.get(day_key)
            day_count = int(day_count) if day_count else 0
            
            if day_count >= self.PER_DAY:
                ttl = await self.redis_client.ttl(day_key)
                return {
                    "allowed": False,
                    "reason": f"Rate limit exceeded: {self.PER_DAY} generations per day",
                    "retry_after": ttl if ttl > 0 else 86400
                }
            
            # All checks passed
            return {"allowed": True}
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail-safe: Allow on error
            return {"allowed": True}
    
    async def increment_rate_limit(
        self,
        user_id: str
    ):
        """
        Increment rate limit counters after successful check
        
        Args:
            user_id: User ID
        """
        if not self._initialized or not self.redis_client:
            return
        
        try:
            # Increment minute counter
            minute_key = f"rate_limit:gen:{user_id}:minute"
            await self.redis_client.incr(minute_key)
            await self.redis_client.expire(minute_key, 60)  # 1 minute TTL
            
            # Increment hour counter
            hour_key = f"rate_limit:gen:{user_id}:hour"
            await self.redis_client.incr(hour_key)
            await self.redis_client.expire(hour_key, 3600)  # 1 hour TTL
            
            # Increment day counter
            day_key = f"rate_limit:gen:{user_id}:day"
            await self.redis_client.incr(day_key)
            await self.redis_client.expire(day_key, 86400)  # 1 day TTL
            
        except Exception as e:
            logger.error(f"Failed to increment rate limit: {e}")
    
    async def reset_rate_limit(
        self,
        user_id: str
    ):
        """
        Reset rate limits for a user (admin function)
        
        Args:
            user_id: User ID
        """
        if not self._initialized or not self.redis_client:
            return
        
        try:
            keys = [
                f"rate_limit:gen:{user_id}:minute",
                f"rate_limit:gen:{user_id}:hour",
                f"rate_limit:gen:{user_id}:day",
            ]
            await self.redis_client.delete(*keys)
            logger.info(f"Rate limits reset for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to reset rate limit: {e}")
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()


# Global instance
rate_limiter = RateLimiter()

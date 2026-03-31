"""
Rate limiting configuration for PhotoGenius AI API

Implements tiered rate limiting:
- Free tier: 10 requests/minute, 100/hour
- Pro tier: 60 requests/minute, 1000/hour
- Enterprise: 300 requests/minute, 10000/hour

Uses Redis if available, falls back to in-memory storage for development.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException
from typing import Optional
import redis.asyncio as redis
import logging
from .config import settings

logger = logging.getLogger(__name__)

# Redis connection pool
redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> Optional[redis.Redis]:
    """Get or create Redis client for rate limiting"""
    global redis_client

    if redis_client is None:
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            await redis_client.ping()
            logger.info("Redis connected for rate limiting")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory rate limiting: {e}")
            redis_client = None

    return redis_client


def get_user_tier(request: Request) -> str:
    """
    Extract user tier from request

    Priority:
    1. JWT token claim (if authenticated)
    2. API key header
    3. Default to 'free'
    """
    # TODO: Extract from JWT token when auth is implemented
    # For now, check for API key or default to free
    api_key = request.headers.get("X-API-Key")

    if api_key:
        # In production, look up tier from database based on API key
        # For now, pro tier if API key exists
        return "pro"

    return "free"


def get_rate_limit_string(request: Request) -> str:
    """
    Return rate limit string based on user tier

    Formats:
    - "10/minute" = 10 requests per minute
    - "100/hour" = 100 requests per hour
    """
    tier = get_user_tier(request)

    # Tiered limits
    limits = {
        "free": "10/minute",
        "pro": "60/minute",
        "enterprise": "300/minute",
    }

    return limits.get(tier, "10/minute")


# Custom key function that includes user tier
def rate_limit_key_func(request: Request) -> str:
    """
    Generate rate limit key based on IP and tier

    Format: {ip}:{tier}
    This allows different rate limits for different tiers from the same IP
    """
    ip = get_remote_address(request)
    tier = get_user_tier(request)
    return f"{ip}:{tier}"


# Initialize limiter
limiter = Limiter(
    key_func=rate_limit_key_func,
    default_limits=["100/hour"],  # Global fallback
    storage_uri=settings.REDIS_URL if settings.REDIS_URL else "memory://",
    strategy="fixed-window",  # Simple fixed window strategy
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors

    Returns user-friendly error message with retry-after header
    """
    tier = get_user_tier(request)

    # Get upgrade message based on tier
    upgrade_msg = ""
    if tier == "free":
        upgrade_msg = " Upgrade to Pro for 6x more requests!"

    return HTTPException(
        status_code=429,
        detail={
            "error": "Rate limit exceeded",
            "message": f"You've hit the {tier} tier rate limit.{upgrade_msg}",
            "tier": tier,
            "retry_after": exc.detail,
        },
        headers={"Retry-After": str(exc.detail)},
    )


# Decorator helpers for common limits
def generation_rate_limit():
    """Rate limit decorator for image generation endpoints"""
    def decorator(func):
        # Apply dynamic limit based on user tier
        return limiter.limit(get_rate_limit_string)(func)
    return decorator


def api_rate_limit(limit: str = "60/minute"):
    """Rate limit decorator for general API endpoints"""
    def decorator(func):
        return limiter.limit(limit)(func)
    return decorator


# Startup/shutdown hooks
async def init_rate_limiter():
    """Initialize rate limiter on app startup"""
    try:
        client = await get_redis_client()
        if client:
            logger.info("Rate limiter initialized with Redis")
        else:
            logger.info("Rate limiter initialized with in-memory storage")
    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")


async def close_rate_limiter():
    """Clean up rate limiter on app shutdown"""
    global redis_client
    if redis_client:
        try:
            await redis_client.aclose()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis: {e}")
        finally:
            redis_client = None

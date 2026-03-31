#!/usr/bin/env python3
"""
Test Redis connection (Upstash). Run from project root:
  python scripts/test-redis-connection.py
"""
import sys
import os
from pathlib import Path

# Add apps/api to path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "apps" / "api"))

# Load .env.local manually
env_file = root / "apps" / "api" / ".env.local"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)  # override=True to use .env.local values

def test_redis():
    """Test Redis connection"""
    try:
        import redis
        
        # Try to get REDIS_URL from environment first
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            # Fallback to settings
            from app.core.config import get_settings
            settings = get_settings()
            redis_url = settings.REDIS_URL
        
        print("Testing Redis connection...")
        # Mask password in output
        if "@" in redis_url:
            masked_url = redis_url.split("@")[0].split(":")[0] + ":***@" + redis_url.split("@")[1]
        else:
            masked_url = redis_url
        print(f"URL: {masked_url}")
        print("-" * 50)
        
        # Parse URL
        if redis_url.startswith("rediss://"):
            # TLS connection
            client = redis.from_url(
                redis_url,
                ssl_cert_reqs=None,  # Upstash uses self-signed certs
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        else:
            client = redis.from_url(
                redis_url,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        
        # Test connection
        result = client.ping()
        if result:
            print("[OK] Redis connection successful!")
            
            # Test set/get
            client.set("test_key", "test_value", ex=10)
            value = client.get("test_key")
            if value == b"test_value":
                print("[OK] Redis read/write test successful!")
                client.delete("test_key")
            else:
                print("[WARN] Redis read/write test failed")
            
            return 0
        else:
            print("[ERROR] Redis ping failed")
            return 1
            
    except redis.ConnectionError as e:
        print(f"[ERROR] Redis connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check REDIS_URL in apps/api/.env.local")
        print("2. Verify Upstash Redis is active in dashboard")
        print("3. Get correct password from: https://console.upstash.com/redis")
        return 1
    except ImportError:
        print("[ERROR] redis package not installed")
        print("Install with: pip install redis")
        return 1
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_redis())

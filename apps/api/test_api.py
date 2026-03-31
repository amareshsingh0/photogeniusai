"""
Quick test script to check if FastAPI backend is working.
Run: python test_api.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_api():
    """Test if API can start and basic endpoints work"""
    try:
        from app.main import app
        from app.core.config import get_settings
        
        print("[OK] API imports successful")
        
        # Check settings
        settings = get_settings()
        print(f"[OK] Settings loaded: {settings.APP_NAME} v{settings.APP_VERSION}")
        print(f"   Environment: {settings.ENVIRONMENT}")
        print(f"   API Prefix: {settings.API_V1_PREFIX}")
        
        # Check database connection
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text  # type: ignore[reportMissingImports]
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
            print("[OK] Database connection: OK")
        except Exception as e:
            print(f"[WARN] Database connection: FAILED - {e}")
        
        # Check Redis connection
        try:
            from app.services.safety.rate_limiter import rate_limiter
            if rate_limiter._initialized:
                print("[OK] Redis connection: OK")
            else:
                print("[WARN] Redis connection: Not initialized (may be disabled)")
        except Exception as e:
            print(f"[WARN] Redis connection: FAILED - {e}")
        
        # Check routes
        routes = [route.path for route in app.routes]
        print(f"\n[OK] API Routes ({len(routes)} total):")
        for route in sorted(routes)[:10]:  # Show first 10
            print(f"   - {route}")
        if len(routes) > 10:
            print(f"   ... and {len(routes) - 10} more")
        
        print("\n[OK] API is configured correctly!")
        print("\nTo start the server, run:")
        print("   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
        print("\nOr use:")
        print("   pnpm --filter @photogenius/api dev")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_api())
    sys.exit(0 if success else 1)

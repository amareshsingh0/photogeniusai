#!/usr/bin/env python3
"""
Test Modal.com AI Service connection. Run from project root:
  python scripts/test-modal-connection.py
"""
import sys
import os
from pathlib import Path
import httpx
import asyncio

# Add apps/api to path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "apps" / "api"))

# Load .env.local manually
env_file = root / "apps" / "api" / ".env.local"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)

async def test_modal_health():
    """Test Modal health endpoint"""
    ai_service_url = os.getenv("AI_SERVICE_URL", "")
    
    if not ai_service_url:
        print("[ERROR] AI_SERVICE_URL not set in environment")
        return 1
    
    # Extract base URL and construct health endpoint
    # With asgi_app, all routes are under the base URL
    # Format: https://username--app-name-fastapi-app.modal.run
    # Health: https://username--app-name-fastapi-app.modal.run/health
    if ai_service_url.endswith(".modal.run"):
        health_url = f"{ai_service_url}/health"
        generate_url = f"{ai_service_url}/api/generation"
    else:
        # Fallback: try to construct URLs
        base = ai_service_url.rstrip("/")
        health_url = f"{base}/health"
        generate_url = f"{base}/api/generation"
    
    print("Testing Modal AI Service connection...")
    print(f"Base URL: {ai_service_url}")
    print(f"Health URL: {health_url}")
    print(f"Generate URL: {generate_url}")
    print("-" * 50)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test health endpoint
            print("\n1. Testing health endpoint...")
            try:
                response = await client.get(health_url)
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"   Response: {response.json()}")
                    print("   [OK] Health endpoint working!")
                else:
                    print(f"   Response: {response.text[:200]}")
                    print(f"   [WARN] Health endpoint returned {response.status_code}")
            except httpx.TimeoutException:
                print("   [ERROR] Health endpoint timeout (may be starting up)")
                return 1
            except httpx.RequestError as e:
                print(f"   [ERROR] Health endpoint error: {e}")
                return 1
            
            # Test generate endpoint (with minimal payload)
            print("\n2. Testing generate endpoint...")
            test_payload = {
                "prompt": "test image",
                "negative_prompt": "",
                "mode": "REALISM"
            }
            try:
                response = await client.post(
                    generate_url,
                    json=test_payload,
                    timeout=60.0
                )
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        print("   [OK] Generate endpoint working!")
                        print(f"   Images: {len(data.get('images', []))} generated")
                    else:
                        print(f"   [WARN] Generate returned error: {data.get('error', 'Unknown')}")
                else:
                    print(f"   Response: {response.text[:200]}")
                    print(f"   [WARN] Generate endpoint returned {response.status_code}")
            except httpx.TimeoutException:
                print("   [WARN] Generate endpoint timeout (normal for first request - cold start)")
            except httpx.RequestError as e:
                print(f"   [ERROR] Generate endpoint error: {e}")
                return 1
            
            print("\n[OK] Modal connection test completed!")
            print("\nNote: First generate request may take longer (cold start)")
            return 0
            
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(test_modal_health()))

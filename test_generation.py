#!/usr/bin/env python3
"""
Quick test script to verify PhotoGenius AI generation pipeline end-to-end
Run this after restarting the dev server: py test_generation.py
"""

import requests
import json
import sys
from datetime import datetime

def test_backend_generation():
    """Test the backend /generate endpoint directly"""
    print("🧪 Testing Backend API (http://localhost:8000/generate)...")

    try:
        response = requests.post(
            "http://localhost:8000/generate",
            json={
                "prompt": "A beautiful sunset over mountains, vibrant colors",
                "quality_tier": "FAST",
                "width": 512,
                "height": 512
            },
            timeout=60
        )

        data = response.json()

        if data.get("success"):
            print("✅ Backend generation SUCCESSFUL")
            print(f"   - Mode: {data.get('orchestration', {}).get('detected_mode', 'N/A')}")
            print(f"   - Model: {data.get('orchestration', {}).get('selected_model', 'N/A')}")

            image_url = data.get("image_url", "")
            if image_url.startswith("data:image"):
                print(f"   - Image: base64 data URL ({len(image_url)} chars)")
            else:
                print(f"   - Image URL: {image_url[:80]}...")

            quality = data.get("quality_scores", {})
            if quality:
                print(f"   - Quality scores: {len(quality)} metrics")

            return True
        else:
            print(f"❌ Backend generation FAILED: {data.get('error', 'Unknown error')}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Backend not running! Start it with: turbo dev")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_frontend_api():
    """Test the Next.js API route"""
    print("\n🧪 Testing Frontend API (http://localhost:3002/api/generate/smart)...")

    # Check which port the frontend is on
    frontend_ports = [3002, 3000, 3001, 3003]

    for port in frontend_ports:
        try:
            response = requests.post(
                f"http://localhost:{port}/api/generate/smart",
                json={
                    "prompt": "A cozy cottage in the woods",
                    "settings": {
                        "quality": "fast",
                        "width": 512,
                        "height": 512
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print(f"✅ Frontend API SUCCESSFUL (port {port})")
                    print(f"   - Image returned: {bool(data.get('image'))}")
                    return True
                else:
                    print(f"⚠️  Frontend returned error: {data.get('error', 'Unknown')}")
                    return False

        except requests.exceptions.ConnectionError:
            continue

    print("❌ Frontend not running! Start it with: turbo dev")
    return False

def main():
    print("=" * 60)
    print("PhotoGenius AI - Generation Pipeline Test")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Test backend
    backend_ok = test_backend_generation()

    # Test frontend (optional)
    frontend_ok = test_frontend_api()

    print("\n" + "=" * 60)
    if backend_ok and frontend_ok:
        print("✅ ALL TESTS PASSED - Website is ready for use!")
    elif backend_ok:
        print("⚠️  Backend OK, but frontend had issues")
    else:
        print("❌ TESTS FAILED - Check errors above")
        print("\n💡 Did you restart the dev server after the fixes?")
        print("   Run: Ctrl+C then turbo dev")
    print("=" * 60)

    return 0 if (backend_ok and frontend_ok) else 1

if __name__ == "__main__":
    sys.exit(main())

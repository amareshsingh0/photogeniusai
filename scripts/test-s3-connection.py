#!/usr/bin/env python3
"""
Test S3/R2 connection. Run from project root:
  python scripts/test-s3-connection.py
  OR
  cd apps/api && python -m venv .venv && .venv\\Scripts\\activate && python ../../scripts/test-s3-connection.py
"""
import sys
from pathlib import Path

# Add apps/api to path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "apps" / "api"))

from app.services.storage import get_s3_service

def main():
    print("Testing S3/R2 connection...")
    print("-" * 50)

    s3 = get_s3_service()
    print(f"Bucket: {s3.bucket}")
    print(f"Region: {s3.region}")
    print(f"Endpoint: {s3.endpoint_url or 'AWS S3 (default)'}")
    print(f"Access Key: {s3.access_key[:10]}..." if s3.access_key else "Not set")

    if not s3.bucket or not s3.access_key:
        print("\n[ERROR] S3_BUCKET_NAME or S3_ACCESS_KEY missing in .env")
        return 1

    print("\nTesting connection...")
    try:
        connected = s3.test_connection()
        if connected:
            print("[OK] S3/R2 connection successful!")
            return 0
        else:
            print("[ERROR] S3/R2 connection failed (bucket not accessible)")
            return 1
    except Exception as e:
        print(f"[ERROR] Connection error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

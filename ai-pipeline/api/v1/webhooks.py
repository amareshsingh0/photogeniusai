"""
Webhook delivery system for async job notifications.

Features:
- HMAC-SHA256 signature verification for security
- Exponential backoff retry logic
- Async delivery with timeout handling
"""

import asyncio
try:
    import httpx  # type: ignore[reportMissingImports]
except ImportError:
    httpx = None  # type: ignore[assignment]

import hmac
import hashlib
import json
import os
import time
from typing import Optional
from .models import WebhookPayload, TrainingWebhookPayload, JobStatus

# Webhook configuration
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
WEBHOOK_SIGNATURE_HEADER = "X-PhotoGenius-Signature"
WEBHOOK_TIMESTAMP_HEADER = "X-PhotoGenius-Timestamp"
WEBHOOK_TOLERANCE_SECONDS = 300  # 5 minutes tolerance for timestamp


def generate_webhook_signature(payload: dict, timestamp: int, secret: Optional[str] = None) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.

    Args:
        payload: The webhook payload dict
        timestamp: Unix timestamp
        secret: Webhook secret (uses env var if not provided)

    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    secret = secret or WEBHOOK_SECRET
    if not secret:
        return ""

    # Create signing string: timestamp.json_payload
    payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    signing_string = f"{timestamp}.{payload_str}"

    # Generate HMAC-SHA256
    signature = hmac.new(
        secret.encode('utf-8'),
        signing_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return signature


def verify_webhook_signature(
    payload: dict,
    signature: str,
    timestamp: int,
    secret: Optional[str] = None
) -> bool:
    """
    Verify webhook signature to prevent replay attacks.

    Args:
        payload: The received webhook payload
        signature: The received signature
        timestamp: The received timestamp
        secret: Webhook secret

    Returns:
        True if signature is valid, False otherwise
    """
    secret = secret or WEBHOOK_SECRET
    if not secret:
        # No secret configured, skip verification
        return True

    # Check timestamp tolerance (prevent replay attacks)
    current_time = int(time.time())
    if abs(current_time - timestamp) > WEBHOOK_TOLERANCE_SECONDS:
        return False

    # Verify signature
    expected_signature = generate_webhook_signature(payload, timestamp, secret)
    return hmac.compare_digest(signature, expected_signature)


async def send_webhook(
    webhook_url: str,
    payload: dict,
    max_retries: int = 3,
    timeout: float = 10.0,
    secret: Optional[str] = None
) -> bool:
    """
    Send webhook notification with HMAC signature and retry logic.

    Args:
        webhook_url: Webhook URL to send to
        payload: Payload data
        max_retries: Maximum retry attempts
        timeout: Request timeout in seconds
        secret: Optional webhook secret (uses env var if not provided)

    Returns:
        True if successful, False otherwise
    """
    if httpx is None:
        print("Webhook skipped: httpx not installed")
        return False
    secret = secret or WEBHOOK_SECRET
    timestamp = int(time.time())

    # Generate signature
    signature = generate_webhook_signature(payload, timestamp, secret)

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "PhotoGenius-API/1.0",
        WEBHOOK_TIMESTAMP_HEADER: str(timestamp),
    }

    # Add signature if secret is configured
    if signature:
        headers[WEBHOOK_SIGNATURE_HEADER] = signature

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers=headers
                )

                if response.status_code == 200:
                    print(f"Webhook delivered to {webhook_url}")
                    return True
                elif response.status_code == 401:
                    print(f"Webhook authentication failed: {webhook_url}")
                    return False  # Don't retry auth failures
                else:
                    print(f"Webhook returned {response.status_code}: {response.text[:200]}")

        except httpx.TimeoutException:
            print(f"Webhook timeout (attempt {attempt + 1}/{max_retries})")
        except httpx.ConnectError:
            print(f"Webhook connection failed (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"Webhook error (attempt {attempt + 1}/{max_retries}): {e}")

        # Exponential backoff
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    print(f"Webhook failed after {max_retries} attempts: {webhook_url}")
    return False


async def send_generation_webhook(
    webhook_url: str,
    job_id: str,
    status: JobStatus,
    results: Optional[list] = None,
    error: Optional[str] = None,
    secret: Optional[str] = None
) -> None:
    """Send generation job webhook with signature"""

    payload = WebhookPayload(
        job_id=job_id,
        status=status,
        results=results,
        error=error,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )

    await send_webhook(webhook_url, payload.dict(), secret=secret)


async def send_training_webhook(
    webhook_url: str,
    training_job_id: str,
    status: JobStatus,
    identity_id: Optional[str] = None,
    error: Optional[str] = None,
    secret: Optional[str] = None
) -> None:
    """Send training job webhook with signature"""

    payload = TrainingWebhookPayload(
        training_job_id=training_job_id,
        status=status,
        identity_id=identity_id,
        error=error,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )

    await send_webhook(webhook_url, payload.dict(), secret=secret)


# ==================== Verification Middleware Example ====================

def create_webhook_verification_middleware():
    """
    Create FastAPI middleware for webhook signature verification.

    Usage in receiving application:
    ```python
    from fastapi import FastAPI, Request, HTTPException

    app = FastAPI()

    @app.post("/webhook")
    async def receive_webhook(request: Request):
        body = await request.json()
        signature = request.headers.get("X-PhotoGenius-Signature", "")
        timestamp = int(request.headers.get("X-PhotoGenius-Timestamp", "0"))

        if not verify_webhook_signature(body, signature, timestamp, "your-secret"):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        # Process webhook...
    ```
    """
    pass  # Documentation only

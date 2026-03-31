"""
GPU2 payload size test — graduated sizes to find exact threshold.
Tests with realistic photographic content (gradient + noise), not pure noise.
"""
import boto3, json, base64, io, time, sys
from botocore.config import Config

REGION = "us-east-1"
ORCH_EP = "photogenius-orchestrator"

runtime = boto3.client(
    "sagemaker-runtime", region_name=REGION,
    config=Config(connect_timeout=10, read_timeout=300),
)

def make_test_image(size=1024, quality=95):
    """Create a realistic-looking gradient image (not pure noise)."""
    from PIL import Image
    import random
    # Create gradient with subtle noise (like a real photo)
    img = Image.new("RGB", (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            r = int(100 + 100 * (x / size) + random.randint(-10, 10))
            g = int(80 + 120 * (y / size) + random.randint(-10, 10))
            b = int(60 + 80 * ((x + y) / (2 * size)) + random.randint(-10, 10))
            pixels[x, y] = (min(255, max(0, r)), min(255, max(0, g)), min(255, max(0, b)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, subsampling=0)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def test_gpu2(label, image_b64):
    """Send image to GPU2 and report result."""
    b64_kb = len(image_b64) / 1024
    payload = json.dumps({
        "action": "post_process",
        "image": image_b64,
        "prompt": "a woman in golden silk saree",
        "quality_tier": "PREMIUM",
        "jury_score": 0.75,
        "target_width": 1024,
        "target_height": 1024,
    })
    payload_mb = len(payload) / (1024 * 1024)
    print(f"[{label}] base64={b64_kb:.0f}KB, payload={payload_mb:.2f}MB ... ", end="", flush=True)

    start = time.time()
    try:
        resp = runtime.invoke_endpoint(
            EndpointName=ORCH_EP,
            ContentType="application/json",
            Body=payload,
        )
        raw = json.loads(resp["Body"].read())
        if isinstance(raw, list):
            raw = json.loads(raw[0]) if isinstance(raw[0], str) else raw[0]
        elapsed = time.time() - start
        status = raw.get("status", "unknown")
        print(f"{status} in {elapsed:.1f}s")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"FAILED ({type(e).__name__}) in {elapsed:.1f}s")
        return False

# Health check first
print("=== GPU2 Payload Size Test ===")
print()
print("[HEALTH] Checking GPU2 health...")
try:
    resp = runtime.invoke_endpoint(
        EndpointName=ORCH_EP,
        ContentType="application/json",
        Body=json.dumps({"action": "health_check"}),
    )
    raw = json.loads(resp["Body"].read())
    if isinstance(raw, list):
        raw = json.loads(raw[0]) if isinstance(raw[0], str) else raw[0]
    print(f"[HEALTH] Status: {raw.get('status')}, VRAM: {raw.get('vram_used_gb', '?')}GB")
except Exception as e:
    print(f"[HEALTH] FAILED: {e}")
    sys.exit(1)

print()

# Graduated tests
tests = [
    ("100KB q=70 512px", 512, 70),
    ("300KB q=85 1024px", 1024, 50),
    ("600KB q=90 1024px", 1024, 80),
    ("1MB q=95 1024px", 1024, 95),
    ("2MB q=100 1024px", 1024, 100),
]

for label, size, quality in tests:
    print(f"Generating test image ({label})...")
    b64 = make_test_image(size, quality)
    actual_kb = len(b64) / 1024
    print(f"  Actual base64 size: {actual_kb:.0f}KB")
    success = test_gpu2(label, b64)
    if not success:
        print(f"\n[RESULT] Failed at {label} (actual {actual_kb:.0f}KB base64)")
        print("Threshold found! Stopping.")
        break
    print()

print("\n[DONE] All tests complete!")

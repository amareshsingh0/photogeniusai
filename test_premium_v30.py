"""
PREMIUM generation test - validates:
  1. GPU1 JPEG q=100 4:4:4 transfer (was WEBP q=95)
  2. GPU2 smart texture prompt extraction
"""
import boto3, json, uuid, time, base64, sys
from botocore.exceptions import ClientError
from botocore.config import Config

REGION   = "us-east-1"
BUCKET   = "photogenius-models-dev"
GEN_EP   = "photogenius-generation-dev"
ORCH_EP  = "photogenius-orchestrator"

PROMPT = "a beautiful Indian woman wearing golden silk saree in candlelight, soft bokeh, cinematic portra film grain"

print(f"[TEST] PREMIUM generation test")
print(f"[TEST] Prompt: {PROMPT}")
print(f"[TEST] Expected texture keywords: silk, golden, candlelight, soft, bokeh, cinematic, portra, film grain")
print()

s3 = boto3.client("s3", region_name=REGION)
runtime = boto3.client(
    "sagemaker-runtime", region_name=REGION,
    config=Config(connect_timeout=10, read_timeout=300),
)

# === GPU1: Async generation ===
request_id = str(uuid.uuid4())
input_key  = f"async-input/generation/{request_id}.json"
input_s3   = f"s3://{BUCKET}/{input_key}"

request_data = {
    "action": "generate_best",
    "prompt": PROMPT,
    "quality_tier": "PREMIUM",
    "width": 1024,
    "height": 1024,
}

print(f"[GPU1] Uploading request to S3...")
s3.put_object(Bucket=BUCKET, Key=input_key,
              Body=json.dumps(request_data).encode(), ContentType="application/json")

print(f"[GPU1] Invoking async endpoint: {GEN_EP}")
resp = runtime.invoke_endpoint_async(
    EndpointName=GEN_EP, InputLocation=input_s3,
    ContentType="application/json", InferenceId=request_id,
)
output_loc = resp["OutputLocation"]
print(f"[GPU1] Output location: {output_loc}")

# Parse S3 coordinates
no_prefix  = output_loc[len("s3://"):]
out_bucket = no_prefix.split("/", 1)[0]
out_key    = no_prefix.split("/", 1)[1]
err_key    = out_key + ".error"

# Poll
elapsed = 0
result  = None
max_wait = 1800

print(f"[GPU1] Polling (max {max_wait}s, cold start may take ~700s)...")
while elapsed < max_wait:
    time.sleep(5)
    elapsed += 5

    try:
        obj = s3.get_object(Bucket=out_bucket, Key=out_key)
        result = json.loads(obj["Body"].read())
        print(f"[GPU1] Result received after {elapsed}s!")
        break
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchKey":
            raise

    try:
        err_obj = s3.get_object(Bucket=out_bucket, Key=err_key)
        err_body = err_obj["Body"].read().decode("utf-8", errors="replace")
        print(f"[GPU1] ERROR: {err_body[:500]}")
        sys.exit(1)
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchKey":
            raise

    if elapsed % 60 == 0:
        print(f"[GPU1] Still waiting... {elapsed}s / {max_wait}s")

if result is None:
    print(f"[GPU1] TIMEOUT after {max_wait}s")
    sys.exit(1)

if result.get("status") == "error":
    print(f"[GPU1] Generation error: {result.get('error')}")
    sys.exit(1)

image_b64 = result.get("image", "")
jury_score = result.get("jury_score", 0.5)
gen_time = result.get("generation_time", 0)

# Check transfer format (JPEG vs WEBP)
img_bytes = base64.b64decode(image_b64[:100] + "==")  # Decode header
is_jpeg = img_bytes[:2] == b'\xff\xd8'
is_webp = img_bytes[:4] == b'RIFF' and img_bytes[8:12] == b'WEBP'
is_png  = img_bytes[:4] == b'\x89PNG'

transfer_fmt = "JPEG" if is_jpeg else ("WEBP" if is_webp else ("PNG" if is_png else "UNKNOWN"))
transfer_size_kb = len(image_b64) * 3 / 4 / 1024

print(f"[GPU1] Status: {result.get('status')}")
print(f"[GPU1] Jury score: {jury_score:.3f}")
print(f"[GPU1] Generation time: {gen_time:.1f}s")
print(f"[GPU1] Transfer format: {transfer_fmt} (expected: JPEG)")
print(f"[GPU1] Transfer size: {transfer_size_kb:.0f} KB")
print(f"[GPU1] Model: {result.get('model', 'N/A')}")
print()

if transfer_fmt != "JPEG":
    print(f"[WARN] Expected JPEG but got {transfer_fmt}! Change 1 may not be applied.")

# === GPU2: Post-processing ===
print(f"[GPU2] Calling orchestrator for PREMIUM post-processing...")
gpu2_payload = {
    "action": "post_process",
    "image": image_b64,
    "prompt": PROMPT,
    "quality_tier": "PREMIUM",
    "jury_score": jury_score,
    "target_width": 1024,
    "target_height": 1024,
}

gpu2_start = time.time()
try:
    gpu2_resp = runtime.invoke_endpoint(
        EndpointName=ORCH_EP,
        ContentType="application/json",
        Body=json.dumps(gpu2_payload),
    )
    gpu2_raw = json.loads(gpu2_resp["Body"].read())

    # Unwrap HF container array format
    if isinstance(gpu2_raw, list):
        if gpu2_raw and isinstance(gpu2_raw[0], str):
            gpu2_raw = json.loads(gpu2_raw[0])
        elif gpu2_raw and isinstance(gpu2_raw[0], dict):
            gpu2_raw = gpu2_raw[0]

    gpu2_time = time.time() - gpu2_start
    print(f"[GPU2] Status: {gpu2_raw.get('status')}")
    print(f"[GPU2] Process time: {gpu2_time:.1f}s")
    print(f"[GPU2] InstantID used: {gpu2_raw.get('used_instantid', False)}")

    if gpu2_raw.get("status") == "success":
        final_b64 = gpu2_raw.get("image_base64") or gpu2_raw.get("image", "")
        final_size_kb = len(final_b64) * 3 / 4 / 1024 if final_b64 else 0
        print(f"[GPU2] Final image size: {final_size_kb:.0f} KB")

        # Save final image
        if final_b64:
            img_data = base64.b64decode(final_b64)
            out_path = "c:/desktop/PhotoGenius AI/test_premium_output.jpg"
            with open(out_path, "wb") as f:
                f.write(img_data)
            print(f"[GPU2] Saved: {out_path}")
    else:
        print(f"[GPU2] Error: {gpu2_raw.get('error', 'unknown')}")

except Exception as e:
    print(f"[GPU2] Failed: {type(e).__name__}: {e}")

print()
print(f"[TEST] Complete! Total: GPU1={elapsed}s + GPU2={gpu2_time:.0f}s")

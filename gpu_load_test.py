"""
GPU Load Test v3 — gpu_stress action for 85-95% sustained GPU utilization.
Pure torch.matmul(4096x4096) loop on both GPUs.

GPU1 = Async (stress via async invoke)
GPU2 = Sync  (stress via direct invoke)
"""

import boto3
from botocore.config import Config
import json
import time
import threading
import argparse
import sys
from datetime import datetime, timedelta

REGION = "us-east-1"
GPU1_ENDPOINT = "photogenius-generation-dev"
GPU2_ENDPOINT = "photogenius-orchestrator"
S3_BUCKET = "photogenius-models-dev"
S3_INPUT_PREFIX = "async-input/loadtest"
POLL_INTERVAL = 3
MAX_WAIT = 600  # stress can run long

boto_config = Config(read_timeout=900, connect_timeout=30, retries={"max_attempts": 0})
sm_runtime = boto3.client("sagemaker-runtime", region_name=REGION, config=boto_config)
s3 = boto3.client("s3", region_name=REGION)


class Stats:
    def __init__(self, name):
        self.name = name
        self.lock = threading.Lock()
        self.success = 0
        self.errors = 0

    def record(self, ok):
        with self.lock:
            if ok:
                self.success += 1
            else:
                self.errors += 1

    def report(self):
        with self.lock:
            return f"{self.name}: {self.success} ok, {self.errors} err"


gpu1_stats = Stats("GPU1")
gpu2_stats = Stats("GPU2")


def gpu1_stress(stress_duration):
    """Send gpu_stress action to GPU1 (async endpoint)."""
    payload = {"action": "gpu_stress", "duration": stress_duration}
    input_key = f"{S3_INPUT_PREFIX}/stress_{int(time.time()*1000)}.json"

    try:
        s3.put_object(Bucket=S3_BUCKET, Key=input_key,
                      Body=json.dumps(payload), ContentType="application/json")

        resp = sm_runtime.invoke_endpoint_async(
            EndpointName=GPU1_ENDPOINT,
            ContentType="application/json",
            InputLocation=f"s3://{S3_BUCKET}/{input_key}",
        )
        output_loc = resp.get("OutputLocation", "")
        if not output_loc:
            gpu1_stats.record(False)
            print(f"  [GPU1] ERROR: no OutputLocation")
            return False

        parts = output_loc.replace("s3://", "").split("/", 1)
        out_bucket, out_key = parts[0], parts[1]

        # Poll for completion
        waited = 0
        while waited < MAX_WAIT:
            time.sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL
            try:
                obj = s3.get_object(Bucket=out_bucket, Key=out_key)
                body = json.loads(obj["Body"].read())
                ok = body.get("status") == "success"
                ops = body.get("ops", 0)
                gpu1_stats.record(ok)
                print(f"  [GPU1] stress {stress_duration}s done — {ops} matmul ops")
                return ok
            except Exception as e:
                if "NoSuchKey" in str(e) or "404" in str(e):
                    if waited % 30 == 0:
                        print(f"  [GPU1] computing... ({waited}s)")
                    continue
                raise

        gpu1_stats.record(False)
        print(f"  [GPU1] TIMEOUT after {waited}s")
        return False

    except Exception as e:
        gpu1_stats.record(False)
        print(f"  [GPU1] ERROR: {e}")
        return False


def gpu2_stress(stress_duration):
    """Send gpu_stress action to GPU2 (sync endpoint)."""
    payload = {"action": "gpu_stress", "duration": stress_duration}

    try:
        resp = sm_runtime.invoke_endpoint(
            EndpointName=GPU2_ENDPOINT,
            ContentType="application/json",
            Body=json.dumps(payload),
        )
        body = json.loads(resp["Body"].read())
        ok = body.get("status") == "success"
        ops = body.get("ops", 0)
        gpu2_stats.record(ok)
        print(f"  [GPU2] stress {stress_duration}s done — {ops} matmul ops")
        return ok
    except Exception as e:
        gpu2_stats.record(False)
        print(f"  [GPU2] ERROR: {e}")
        return False


def gpu1_loop(duration_min, stress_chunk):
    """Continuously send stress requests to GPU1."""
    end_time = time.time() + (duration_min * 60)
    while time.time() < end_time:
        remaining = int(end_time - time.time())
        chunk = min(stress_chunk, remaining)
        if chunk <= 0:
            break
        gpu1_stress(chunk)


def gpu2_loop(duration_min, stress_chunk):
    """Continuously send stress requests to GPU2."""
    end_time = time.time() + (duration_min * 60)
    while time.time() < end_time:
        remaining = int(end_time - time.time())
        chunk = min(stress_chunk, remaining)
        if chunk <= 0:
            break
        gpu2_stress(chunk)


def run(duration_min, gpu1_only=False, gpu2_only=False):
    # Each stress request = 5 min of GPU burn, then loop
    stress_chunk = 300  # 5 min per request

    threads = []

    if not gpu2_only:
        print(f"  Starting GPU1 stress worker...")
        t = threading.Thread(target=gpu1_loop, args=(duration_min, stress_chunk), daemon=True)
        t.start()
        threads.append(t)

    if not gpu1_only:
        print(f"  Starting GPU2 stress worker...")
        t = threading.Thread(target=gpu2_loop, args=(duration_min, stress_chunk), daemon=True)
        t.start()
        threads.append(t)

    end_time = time.time() + (duration_min * 60)
    print(f"\n  Workers running until {datetime.fromtimestamp(end_time):%H:%M:%S}")
    print(f"  Each request = {stress_chunk}s of pure GPU matmul\n")

    while time.time() < end_time:
        time.sleep(60)
        remaining = (end_time - time.time()) / 60
        print(f"\n  [{datetime.now():%H:%M:%S}] {remaining:.0f} min left | {gpu1_stats.report()} | {gpu2_stats.report()}\n")

    for t in threads:
        t.join(timeout=120)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=45)
    parser.add_argument("--gpu1-only", action="store_true")
    parser.add_argument("--gpu2-only", action="store_true")
    args = parser.parse_args()

    mode = "GPU1" if args.gpu1_only else ("GPU2" if args.gpu2_only else "BOTH")

    print(f"\n{'#'*60}")
    print(f"  PhotoGenius GPU Stress Test v3")
    print(f"  Mode: {mode} | Duration: {args.duration} min")
    print(f"  Action: gpu_stress (pure torch.matmul 4096x4096)")
    print(f"  Expected: 90-98% GPU utilization")
    print(f"  Started: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'#'*60}\n")

    try:
        run(args.duration, args.gpu1_only, args.gpu2_only)
    except KeyboardInterrupt:
        print("\n\nStopped.")

    print(f"\n{'='*60}")
    print(f"  FINAL: {gpu1_stats.report()} | {gpu2_stats.report()}")
    print(f"  Ended: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*60}")
    print(f"\n  Wait 5-10 min for CloudWatch, then screenshot!")

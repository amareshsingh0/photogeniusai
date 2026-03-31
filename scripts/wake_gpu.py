#!/usr/bin/env python3
"""
PhotoGenius GPU — Wake & Status Monitor
========================================
Usage:
    python scripts/wake_gpu.py --status        # Monitor download progress (30s loop)
    python scripts/wake_gpu.py --wake          # Send warmup request after MODEL_READY
    python scripts/wake_gpu.py --status --wake # Status first, then auto-wake when ready
    python scripts/wake_gpu.py                 # Same as --status --wake (default)

What it does:
    --status : Reads CloudWatch logs every 30s → shows model download %, speed,
               remaining time, and MODEL_READY status. Stops when MODEL_READY=True.
    --wake   : Uploads warmup payload to S3, calls invoke_endpoint_async.
               Forces CUDA kernel compilation before the first real request.

Workflow after .\gpu.ps1 start / deploy_gen_v10.ps1:
    1. Endpoint transitions: Creating → Updating → InService (~10-15 min)
    2. Run this script — it monitors download progress in real-time
    3. When MODEL_READY=True appears → GPU is ready for requests
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

try:
    import boto3
    from botocore.config import Config as BotocoreConfig
    from botocore.exceptions import ClientError
except ImportError:
    print("boto3 not found. Run: pip install boto3")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
ENDPOINT_NAME = "photogenius-generation-dev"
BUCKET        = "photogenius-models-dev"
REGION        = os.getenv("AWS_REGION", "us-east-1")

# CloudWatch log group for SageMaker endpoints
CW_LOG_GROUP  = f"/aws/sagemaker/Endpoints/{ENDPOINT_NAME}"

# Warmup payload — same format as real request so all code paths are exercised
WARMUP_PAYLOAD = {
    "action":       "generate_best",
    "prompt":       "a professional photograph, cinematic lighting, golden hour",
    "quality_tier": "FAST",
    "width":        1024,
    "height":       1024,
}

# ── CloudWatch helpers ────────────────────────────────────────────────────────

def _get_logs_client():
    return boto3.client("logs", region_name=REGION,
                        config=BotocoreConfig(connect_timeout=10, read_timeout=30))


def _get_runtime_client():
    return boto3.client("sagemaker-runtime", region_name=REGION,
                        config=BotocoreConfig(connect_timeout=10, read_timeout=30))


def _get_s3_client():
    return boto3.client("s3", region_name=REGION)


def _get_log_streams(logs):
    """Get most recent log streams for the endpoint."""
    try:
        resp = logs.describe_log_streams(
            logGroupName=CW_LOG_GROUP,
            orderBy="LastEventTime",
            descending=True,
            limit=3,
        )
        return [s["logStreamName"] for s in resp.get("logStreams", [])]
    except ClientError:
        return []


def _get_recent_events(logs, stream_name: str, since_ms: int) -> list[str]:
    """Fetch log events from a stream since a given timestamp."""
    try:
        resp = logs.get_log_events(
            logGroupName=CW_LOG_GROUP,
            logStreamName=stream_name,
            startTime=since_ms,
            startFromHead=False,
        )
        return [e["message"] for e in resp.get("events", [])]
    except ClientError:
        return []


# ── Parse download progress from log lines ───────────────────────────────────

# Example log line from inference.py:
#   [pixart-sigma] 5 files, 12.3GB, 45s (278 MB/s)
_DL_PATTERN = re.compile(
    r"\[(\S+)\]\s+(\d+) files,\s+([\d.]+)GB,\s+(\d+)s\s+\(([\d.]+) MB/s\)"
)

# Total expected GB per model (approximate)
_MODEL_SIZES_GB = {
    "pixart-sigma": 20.3,
    "flux-schnell": 31.5,
    "clip":         1.6,
    "realesrgan":   0.1,
    "nudenet":      0.4,
}
_TOTAL_EXPECTED_GB = sum(_MODEL_SIZES_GB.values())  # ~54 GB


def _parse_download_lines(lines: list[str]) -> dict:
    """Extract latest download progress per model from log lines."""
    progress = {}
    for line in lines:
        m = _DL_PATTERN.search(line)
        if m:
            model, files, gb, elapsed, speed = m.groups()
            progress[model] = {
                "files":   int(files),
                "gb":      float(gb),
                "elapsed": int(elapsed),
                "speed":   float(speed),
            }
    return progress


def _format_progress(progress: dict) -> str:
    """Build a human-readable progress summary."""
    if not progress:
        return "  (no download progress yet)"

    lines = []
    total_downloaded = 0.0
    for model, p in progress.items():
        total_size = _MODEL_SIZES_GB.get(model, 0)
        pct = min(100, (p["gb"] / total_size * 100)) if total_size else 0
        bar = ("█" * int(pct / 5)).ljust(20)
        eta = ""
        if p["speed"] > 0 and total_size > p["gb"]:
            remaining_sec = (total_size - p["gb"]) * 1024 / p["speed"]
            eta = f"  ETA {remaining_sec/60:.1f}min"
        lines.append(
            f"  {model:<15} [{bar}] {p['gb']:.1f}/{total_size:.1f}GB "
            f"({pct:.0f}%)  {p['speed']:.0f} MB/s{eta}"
        )
        total_downloaded += p["gb"]

    overall_pct = min(100, (total_downloaded / _TOTAL_EXPECTED_GB * 100))
    overall_bar = ("█" * int(overall_pct / 5)).ljust(20)
    lines.append(
        f"  {'TOTAL':<15} [{overall_bar}] {total_downloaded:.1f}/{_TOTAL_EXPECTED_GB:.0f}GB "
        f"({overall_pct:.0f}%)"
    )
    return "\n".join(lines)


# ── Status monitor (main loop) ────────────────────────────────────────────────

def status_loop() -> bool:
    """
    Poll CloudWatch every 30s, display download progress and MODEL_READY status.
    Returns True when MODEL_READY is detected.
    """
    logs      = _get_logs_client()
    since_ms  = int((time.time() - 120) * 1000)  # look back 2 min on first poll
    ready     = False
    last_progress: dict = {}

    print(f"\n{'='*60}")
    print(f"  PhotoGenius GPU Status Monitor")
    print(f"  Endpoint : {ENDPOINT_NAME}")
    print(f"  Region   : {REGION}")
    print(f"  Log group: {CW_LOG_GROUP}")
    print(f"{'='*60}")
    print("Polling every 30s — Ctrl+C to stop\n")

    while not ready:
        now_ms   = int(time.time() * 1000)
        ts_human = datetime.now().strftime("%H:%M:%S")

        streams  = _get_log_streams(logs)
        all_lines: list[str] = []

        for stream in streams:
            all_lines.extend(_get_recent_events(logs, stream, since_ms))

        since_ms = now_ms  # advance window for next poll

        # Check MODEL_READY
        model_ready_lines = [l for l in all_lines if "MODEL_READY" in l]
        warmup_done_lines = [l for l in all_lines if "CUDA kernels compiled" in l
                             or "Warmup complete" in l.lower()]

        # Parse download progress
        new_progress = _parse_download_lines(all_lines)
        if new_progress:
            last_progress.update(new_progress)

        # ── Print status block ─────────────────────────────────────────────
        print(f"[{ts_human}] ─── Status ───────────────────────────────────────")

        if not streams:
            print("  Waiting for CloudWatch log stream to appear...")
            print("  (Endpoint may still be starting — container not ready yet)")
        elif not all_lines:
            print("  Container started, waiting for inference.py model_fn() to begin...")
        else:
            # Show download progress
            if last_progress:
                print("  Model Downloads:")
                print(_format_progress(last_progress))
            else:
                # Look for any download-related lines
                dl_lines = [l for l in all_lines if "Downloading" in l or "[S3]" in l or "Loading" in l]
                if dl_lines:
                    for l in dl_lines[-3:]:
                        print(f"  {l.strip()}")
                else:
                    print("  Waiting for model download to start...")

        # Warmup status
        if warmup_done_lines:
            print("  GPU Warmup: ✅ CUDA kernels compiled")
        elif any("WARMUP" in l for l in all_lines):
            print("  GPU Warmup: 🔥 Running...")

        # MODEL_READY check
        if model_ready_lines:
            print(f"  {'='*50}")
            print(f"  ✅ MODEL_READY: True")
            print(f"  GPU is ready to accept requests!")
            print(f"  {'='*50}")
            ready = True
            break

        print(f"  Next update in 30s...\n")

        # Wait 30 seconds before next poll
        for i in range(30, 0, -5):
            time.sleep(5)
            sys.stdout.write(f"\r  Polling in {i}s...   ")
            sys.stdout.flush()
        sys.stdout.write("\r" + " " * 30 + "\r")
        sys.stdout.flush()

    return ready


# ── Wake GPU (send async warmup request) ─────────────────────────────────────

def wake_gpu():
    """Upload warmup payload and invoke async endpoint to trigger CUDA warmup."""
    s3      = _get_s3_client()
    runtime = _get_runtime_client()

    warmup_key = "async-input/warmup.json"
    input_s3   = f"s3://{BUCKET}/{warmup_key}"

    print(f"\n{'='*60}")
    print("  Sending warmup request to GPU...")
    print(f"  Endpoint : {ENDPOINT_NAME}")
    print(f"  Payload  : FAST tier, 1024×1024 (4 steps — already done in model_fn)")
    print(f"{'='*60}")

    # Upload warmup payload
    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=warmup_key,
            Body=json.dumps(WARMUP_PAYLOAD).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"  Uploaded warmup payload → s3://{BUCKET}/{warmup_key}")
    except Exception as e:
        print(f"  S3 upload failed: {e}")
        sys.exit(1)

    # Send async request
    try:
        resp = runtime.invoke_endpoint_async(
            EndpointName=ENDPOINT_NAME,
            InputLocation=input_s3,
            ContentType="application/json",
            InferenceId=f"warmup-{int(time.time())}",
        )
        output_loc = resp.get("OutputLocation", "")
        print(f"  Async request sent!")
        print(f"  Output will be at: {output_loc}")
        print()
        print("  ✅ GPU warming up — CUDA kernels will be compiled on this request.")
        print("  Wait 2-3 min, then check CloudWatch for:")
        print("    'CUDA kernels compiled, memory pools ready'")
        print("  After that, all tiers (FAST / STANDARD / PREMIUM) are ready.")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if "ServiceUnavailable" in code or "ValidationException" in code:
            print(f"  Error: {e}")
            print("  Is the endpoint InService? Run --status first.")
        else:
            print(f"  Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global ENDPOINT_NAME, REGION, CW_LOG_GROUP

    parser = argparse.ArgumentParser(
        description="PhotoGenius GPU wake & status monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Monitor CloudWatch logs every 30s (download %, speed, MODEL_READY)",
    )
    parser.add_argument(
        "--wake", action="store_true",
        help="Send warmup request to async endpoint (CUDA kernel compilation)",
    )
    parser.add_argument(
        "--endpoint", default=ENDPOINT_NAME,
        help=f"SageMaker endpoint name (default: {ENDPOINT_NAME})",
    )
    parser.add_argument(
        "--region", default=REGION,
        help=f"AWS region (default: {REGION})",
    )
    args = parser.parse_args()

    # Override globals if provided
    ENDPOINT_NAME = args.endpoint
    REGION        = args.region
    CW_LOG_GROUP  = f"/aws/sagemaker/Endpoints/{ENDPOINT_NAME}"

    # Default: run both status then wake
    run_status = args.status or (not args.status and not args.wake)
    run_wake   = args.wake   or (not args.status and not args.wake)

    if run_status:
        try:
            model_ready = status_loop()
            if model_ready and run_wake:
                print()
                wake_gpu()
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            sys.exit(0)
    elif run_wake:
        wake_gpu()


if __name__ == "__main__":
    main()

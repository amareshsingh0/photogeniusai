#!/usr/bin/env python3
"""
Quick manual test for Step 2 - Test fast second request
Run this AFTER first cold run completes
"""

import boto3
import json
import time

ENDPOINT_NAME = "photogenius-production"
REGION = "us-east-1"

# Simple test prompt
PROMPT = "A beautiful modern building at sunset"

print("="*60)
print("QUICK TEST - Second Request (should be fast)")
print("="*60)

sm_runtime = boto3.client('sagemaker-runtime', region_name=REGION)

payload = {
    "prompt": PROMPT,
    "quality_tier": "STANDARD",
    "width": 1024,
    "height": 1024
}

print(f"\nPrompt: {PROMPT}")
print("Tier: STANDARD")
print("\nSending request...")

start_time = time.time()

try:
    response = sm_runtime.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType='application/json',
        Body=json.dumps(payload)
    )

    result = json.loads(response['Body'].read())
    elapsed = time.time() - start_time

    if result.get('status') == 'success':
        gen_time = result.get('generation_time', 0)
        model = result.get('model')

        print(f"\nSUCCESS!")
        print(f"  Total Time: {elapsed:.1f}s")
        print(f"  Generation Time: {gen_time}s")
        print(f"  Model Used: {model}")
        print(f"  Steps: {result.get('steps')}")

        # Evaluate speed
        if elapsed < 15:
            print(f"\n  FAST! Model was cached in VRAM")
        elif elapsed < 30:
            print(f"\n  MEDIUM. Model may have been swapped")
        else:
            print(f"\n  SLOW. First run or model download")

    else:
        print(f"\nFAILED: {result.get('error')}")

except Exception as e:
    print(f"\nERROR: {e}")

print("\n" + "="*60)

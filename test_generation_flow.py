#!/usr/bin/env python3
"""
Test script to verify complete generation flow before deployment
Tests: Frontend → API → SageMaker → Response
"""

import requests
import json
import time
from pathlib import Path

API_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

print("=" * 80)
print("PHOTOGENIUS GENERATION FLOW TEST")
print("=" * 80)

# Test prompts covering different scenarios
test_cases = [
    {
        "name": "Architecture (PixArt-Sigma)",
        "prompt": "A pink Indian village house with old time nature feel",
        "expected_model": "pixart-sigma",
        "tier": "STANDARD"
    },
    {
        "name": "Portrait (FLUX preferred)",
        "prompt": "A family of 5 people walking on a rainy road, professional photo",
        "expected_model": "flux-schnell",
        "tier": "STANDARD"
    },
    {
        "name": "Text-heavy (PixArt-Sigma FAST with 10 steps)",
        "prompt": "Beautiful poster with text 'Hello World' in elegant font",
        "expected_model": "pixart-sigma",
        "tier": "FAST"
    },
]

print("\n1. Testing API Health...")
try:
    response = requests.get(f"{API_URL}/health", timeout=5)
    if response.status_code == 200:
        print("   API Status: HEALTHY")
    else:
        print(f"   API Status: ERROR ({response.status_code})")
        exit(1)
except Exception as e:
    print(f"   API Status: UNREACHABLE ({e})")
    print("   Make sure API is running: cd apps/api && python dev.py")
    exit(1)

print("\n2. Testing V3 Orchestrator Endpoints...")
try:
    # Test modes endpoint
    response = requests.get(f"{API_URL}/v3/orchestrator/modes")
    modes = response.json()
    print(f"   Available modes: {len(modes.get('modes', []))} modes")

    # Test categories endpoint
    response = requests.get(f"{API_URL}/v3/orchestrator/categories")
    categories = response.json()
    print(f"   Available categories: {len(categories.get('categories', []))} categories")

except Exception as e:
    print(f"   Orchestrator Error: {e}")

print("\n3. Testing Prompt Enhancement...")
from apps.api.app.services.smart.prompt_enhancer import prompt_enhancer

for test in test_cases[:1]:  # Just test one
    result = prompt_enhancer.enhance(
        user_prompt=test["prompt"],
        quality=test["tier"]
    )
    enhancement_len = len(result['enhanced']) - len(result['original'])
    print(f"   {test['name']}: +{enhancement_len} chars")
    print(f"      Mode: {result['mode']}, Category: {result['category']}")

print("\n4. Testing SageMaker Endpoint (if available)...")
import os
sagemaker_endpoint = os.environ.get('SAGEMAKER_ENDPOINT_NAME', 'photogenius-production')
print(f"   Endpoint: {sagemaker_endpoint}")

try:
    import boto3
    sm_runtime = boto3.client('sagemaker-runtime', region_name='us-east-1')

    # Simple test request
    test_payload = {
        "prompt": "A beautiful sunset",
        "quality_tier": "FAST",
        "width": 1024,
        "height": 1024
    }

    response = sm_runtime.invoke_endpoint(
        EndpointName=sagemaker_endpoint,
        ContentType='application/json',
        Body=json.dumps(test_payload)
    )

    result = json.loads(response['Body'].read())

    if result.get('status') == 'success':
        print(f"   SageMaker Status: WORKING")
        print(f"      Model: {result.get('model')}")
        print(f"      Generation Time: {result.get('generation_time')}s")
        print(f"      Steps: {result.get('steps')}")
    else:
        print(f"   SageMaker Status: ERROR - {result.get('error')}")

except Exception as e:
    print(f"   SageMaker Status: ERROR ({str(e)[:100]})")

print("\n5. Testing Full Generation Flow (API -> SageMaker)...")
for i, test in enumerate(test_cases, 1):
    print(f"\n   Test {i}/{len(test_cases)}: {test['name']}")
    print(f"   Prompt: {test['prompt'][:60]}...")

    try:
        start_time = time.time()

        response = requests.post(
            f"{API_URL}/v3/orchestrator/generate",
            json={
                "prompt": test["prompt"],
                "quality_tier": test["tier"],
                "width": 1024,
                "height": 1024
            },
            timeout=120
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            result = response.json()

            if result.get('success'):
                print(f"      SUCCESS ({elapsed:.1f}s)")
                print(f"      Model Used: {result.get('model_used', 'unknown')}")
                print(f"      Quality Score: {result.get('quality_score', 'N/A')}")

                # Verify expected model was used
                actual_model = result.get('model_used')
                if actual_model == test['expected_model']:
                    print(f"      Model Selection: CORRECT")
                else:
                    print(f"      Model Selection: UNEXPECTED (got {actual_model}, expected {test['expected_model']})")
            else:
                print(f"      FAILED: {result.get('error')}")
        else:
            print(f"      HTTP ERROR: {response.status_code}")
            print(f"      {response.text[:200]}")

    except requests.exceptions.Timeout:
        print(f"      TIMEOUT (>120s)")
    except Exception as e:
        print(f"      ERROR: {str(e)[:100]}")

print("\n" + "=" * 80)
print("FLOW CHECK COMPLETE")
print("=" * 80)

# Summary
print("\nNEXT STEPS:")
print("1. If all tests passed → Implement hot-swapping features")
print("2. If SageMaker failed → Check endpoint status in AWS Console")
print("3. If API failed → Check logs in apps/api/")
print("4. If enhancement failed → Check smart services")

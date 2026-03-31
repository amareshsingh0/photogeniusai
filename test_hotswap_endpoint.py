#!/usr/bin/env python3
"""
Test hot-swap functionality on deployed SageMaker endpoint
Tests model switching between PixArt and FLUX
"""

import boto3
import json
import time

ENDPOINT_NAME = "photogenius-production"
REGION = "us-east-1"

# Test cases to verify hot-swapping
test_cases = [
    {
        "name": "Test 1: Architecture (PixArt from warmup)",
        "prompt": "A beautiful modern skyscraper at sunset",
        "expected_model": "pixart-sigma",
        "tier": "STANDARD"
    },
    {
        "name": "Test 2: Portrait (SWAP to FLUX)",
        "prompt": "A professional portrait photo of a smiling person",
        "expected_model": "flux-schnell",
        "tier": "STANDARD"
    },
    {
        "name": "Test 3: Portrait again (FLUX already loaded)",
        "prompt": "A family of 4 people walking together",
        "expected_model": "flux-schnell",
        "tier": "FAST"
    },
    {
        "name": "Test 4: Architecture (SWAP back to PixArt)",
        "prompt": "Ancient temple with intricate details",
        "expected_model": "pixart-sigma",
        "tier": "STANDARD"
    },
]

def test_endpoint():
    sm_runtime = boto3.client('sagemaker-runtime', region_name=REGION)

    print("="*70)
    print("HOT-SWAP ENDPOINT TEST")
    print("="*70)
    print(f"\nEndpoint: {ENDPOINT_NAME}")
    print(f"Region: {REGION}\n")

    results = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] {test['name']}")
        print(f"  Prompt: {test['prompt'][:50]}...")
        print(f"  Expected Model: {test['expected_model']}")

        payload = {
            "prompt": test["prompt"],
            "quality_tier": test["tier"],
            "width": 1024,
            "height": 1024
        }

        try:
            start_time = time.time()

            response = sm_runtime.invoke_endpoint(
                EndpointName=ENDPOINT_NAME,
                ContentType='application/json',
                Body=json.dumps(payload)
            )

            result = json.loads(response['Body'].read())
            elapsed = time.time() - start_time

            if result.get('status') == 'success':
                actual_model = result.get('model')
                gen_time = result.get('generation_time', 0)

                print(f"  SUCCESS ({elapsed:.1f}s total)")
                print(f"    Model Used: {actual_model}")
                print(f"    Generation Time: {gen_time}s")
                print(f"    Steps: {result.get('steps')}")

                # Verify expected model
                if actual_model == test['expected_model']:
                    print(f"    Model Selection: CORRECT")
                else:
                    print(f"    Model Selection: UNEXPECTED (expected {test['expected_model']})")

                # Detect if swap occurred (longer time)
                if elapsed > 25:
                    print(f"    HOT-SWAP DETECTED (took {elapsed:.1f}s)")

                results.append({
                    'test': test['name'],
                    'success': True,
                    'model': actual_model,
                    'time': elapsed,
                    'gen_time': gen_time
                })
            else:
                print(f"  FAILED: {result.get('error')}")
                results.append({
                    'test': test['name'],
                    'success': False,
                    'error': result.get('error')
                })

        except Exception as e:
            print(f"  ERROR: {str(e)[:100]}")
            results.append({
                'test': test['name'],
                'success': False,
                'error': str(e)
            })

        # Small delay between tests
        if i < len(test_cases):
            time.sleep(2)

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for r in results if r.get('success'))
    print(f"\nPassed: {passed}/{len(results)}")

    print("\nTiming Analysis:")
    for r in results:
        if r.get('success'):
            total = r.get('time', 0)
            gen = r.get('gen_time', 0)
            overhead = total - gen
            print(f"  {r['test']}: {total:.1f}s (gen: {gen:.1f}s, overhead: {overhead:.1f}s)")

    print("\nExpected Behavior:")
    print("  - Test 1: Fast (PixArt pre-loaded from warmup)")
    print("  - Test 2: Slower (HOT-SWAP PixArt -> FLUX, +10-15s)")
    print("  - Test 3: Fast (FLUX already loaded)")
    print("  - Test 4: Slower (HOT-SWAP FLUX -> PixArt, +10-15s)")

    print("\n" + "="*70)

if __name__ == "__main__":
    try:
        # Check endpoint status first
        sm = boto3.client('sagemaker', region_name=REGION)
        status = sm.describe_endpoint(EndpointName=ENDPOINT_NAME)

        if status['EndpointStatus'] != 'InService':
            print(f"Endpoint status: {status['EndpointStatus']}")
            print("Endpoint not ready yet. Please wait for InService status.")
            print("\nCheck status with:")
            print(f"  aws sagemaker describe-endpoint --endpoint-name {ENDPOINT_NAME} --query EndpointStatus")
            exit(1)

        test_endpoint()

    except Exception as e:
        print(f"Error: {e}")
        exit(1)

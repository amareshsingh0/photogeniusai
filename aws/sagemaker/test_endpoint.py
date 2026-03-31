"""
Test enhanced SageMaker endpoint with all three quality tiers.

Usage:
    python test_endpoint.py
    python test_endpoint.py --endpoint photogenius-generation-dev
"""

import boto3
import json
import base64
import argparse
import time
from pathlib import Path

def test_endpoint(endpoint_name: str, region: str = "us-east-1"):
    """Test all three quality tiers."""
    print(f"\n{'='*80}")
    print(f"Testing SageMaker Endpoint: {endpoint_name}")
    print(f"{'='*80}\n")

    # Create SageMaker Runtime client
    runtime = boto3.client("sagemaker-runtime", region_name=region)

    # Output directory
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)

    # Test cases
    test_cases = [
        {
            "name": "FAST (Turbo)",
            "tier": "FAST",
            "prompt": "a beautiful sunset over mountains, professional photography",
            "expected_time": 5,
            "output": "test_fast.png",
        },
        {
            "name": "STANDARD (Base)",
            "tier": "STANDARD",
            "prompt": "a professional portrait of a business woman, studio lighting, sharp focus",
            "expected_time": 30,
            "output": "test_standard.png",
        },
        {
            "name": "PREMIUM (Base+Refiner)",
            "tier": "PREMIUM",
            "prompt": "a romantic couple on beach at sunset, golden hour, dreamy atmosphere, RAW photo",
            "expected_time": 50,
            "output": "test_premium.png",
        },
    ]

    results = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}/3: {test['name']}")
        print(f"{'='*80}")
        print(f"Prompt: {test['prompt']}")
        print(f"Expected time: ~{test['expected_time']}s")
        print(f"Output: {output_dir / test['output']}")
        print()

        # Prepare payload
        payload = {
            "inputs": test['prompt'],
            "quality_tier": test['tier'],
            "parameters": {
                "width": 1024,
                "height": 1024,
                "negative_prompt": (
                    "ugly, blurry, low quality, distorted, deformed, "
                    "bad anatomy, poorly drawn, cartoon, anime"
                ),
            }
        }

        # Add candidates for PREMIUM
        if test['tier'] == "PREMIUM":
            payload["num_candidates"] = 4
            print("Generating 4 candidates and selecting best...")

        try:
            # Invoke endpoint
            print("Invoking endpoint...")
            start_time = time.time()

            response = runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="application/json",
                Body=json.dumps(payload),
            )

            # Parse response
            result = json.loads(response["Body"].read())
            elapsed = time.time() - start_time

            # Debug: print response
            print(f"Response keys: {list(result.keys())}")
            if len(str(result)) < 500:  # Only print if not too large
                print(f"Response: {result}")

            # Check for errors
            if "error" in result:
                print(f"[FAIL] Error: {result['error']}")
                results.append({
                    "test": test['name'],
                    "status": "FAILED",
                    "error": result['error'],
                    "time": elapsed,
                })
                continue

            # Save image
            if "image_base64" in result:
                image_b64 = result["image_base64"]
                image_data = base64.b64decode(image_b64)
                output_path = output_dir / test['output']
                output_path.write_bytes(image_data)

                # Get metadata
                metadata = result.get("metadata", {})

                print(f"\n[OK] Success!")
                print(f"   Time: {elapsed:.1f}s")
                print(f"   Model: {metadata.get('model', 'unknown')}")
                print(f"   Steps: {metadata.get('steps', 'unknown')}")
                print(f"   Tier: {metadata.get('tier', 'unknown')}")

                if metadata.get('candidates_generated'):
                    print(f"   Candidates: {metadata['candidates_generated']}")
                if metadata.get('lora_applied'):
                    print(f"   LoRA: Applied")

                print(f"   Saved: {output_path}")

                results.append({
                    "test": test['name'],
                    "status": "SUCCESS",
                    "time": elapsed,
                    "metadata": metadata,
                    "output": str(output_path),
                })
            else:
                print(f"[FAIL] No image in response")
                results.append({
                    "test": test['name'],
                    "status": "FAILED",
                    "error": "No image in response",
                    "time": elapsed,
                })

        except Exception as e:
            print(f"[FAIL] Exception: {e}")
            results.append({
                "test": test['name'],
                "status": "FAILED",
                "error": str(e),
                "time": 0,
            })

    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}\n")

    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    fail_count = len(results) - success_count

    for result in results:
        status_icon = "[OK]" if result['status'] == 'SUCCESS' else "[FAIL]"
        print(f"{status_icon} {result['test']}")
        if result['status'] == 'SUCCESS':
            print(f"   Time: {result['time']:.1f}s")
            print(f"   Output: {result['output']}")
        else:
            print(f"   Error: {result.get('error', 'Unknown')}")
        print()

    print(f"{'='*80}")
    print(f"Results: {success_count} passed, {fail_count} failed")
    print(f"{'='*80}\n")

    if success_count == 3:
        print("SUCCESS! All tests passed!")
        print(f"\nGenerated images saved in: {output_dir}/")
        print("\nNext steps:")
        print("1. Check image quality in test_outputs/")
        print("2. Compare FAST vs STANDARD vs PREMIUM quality")
        print("3. Continue to Step 4: Update Lambda Configuration")
        return 0
    else:
        print("WARNING: Some tests failed. Check errors above.")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Test SageMaker endpoint")
    parser.add_argument(
        "--endpoint",
        default="photogenius-generation-dev",
        help="Endpoint name to test"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region"
    )
    args = parser.parse_args()

    return test_endpoint(args.endpoint, args.region)


if __name__ == "__main__":
    exit(main())

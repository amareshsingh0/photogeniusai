"""
Test SageMaker endpoints for PhotoGenius AI.

Invokes a deployed endpoint with a prompt and optionally saves the returned image.
Usage:
  python deploy/sagemaker/test_endpoint.py --endpoint photogenius-standard-endpoint --prompt "Person standing in sunlight"
  python deploy/sagemaker/test_endpoint.py --all-tiers --prompt "Mother with children under umbrella"
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from io import BytesIO

import boto3


def test_endpoint(
    endpoint_name: str,
    prompt: str,
    region: str = "us-east-1",
    environment: str = "normal",
    seed: int | None = 42,
    save_image: bool = True,
    output_prefix: str = "test_output",
) -> tuple[object | None, dict]:
    """
    Invoke a deployed SageMaker endpoint and return the image and full result.

    Args:
        endpoint_name: SageMaker endpoint name (e.g. photogenius-standard-endpoint).
        prompt: Text prompt for image generation.
        region: AWS region.
        environment: 'normal' | 'rainy' | 'fantasy'.
        seed: Random seed (optional).
        save_image: If True, save decoded image to a PNG file.
        output_prefix: Prefix for saved filename.

    Returns:
        (PIL Image or None, result dict). Image is None if response had no image or decode failed.
    """
    runtime = boto3.client("sagemaker-runtime", region_name=region)

    payload = {
        "prompt": prompt,
        "environment": environment,
        "seed": seed,
    }

    print(f"Testing endpoint: {endpoint_name}")
    print(f"   Prompt: {prompt}")
    print(f"   Region: {region}\n")

    try:
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Body=json.dumps(payload),
        )
    except Exception as e:
        print(f"Error invoking endpoint: {e}")
        return None, {}

    body = response["Body"].read()
    try:
        result = json.loads(body)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON response: {e}")
        print(f"   Body (first 500 chars): {body[:500]}")
        return None, {}

    if "Failure" in result or "error" in result:
        print(f"Error from endpoint: {result.get('Failure') or result.get('error')}")
        return None, result

    metadata = result.get("metadata") or {}
    img_b64 = result.get("image") or ""

    image = None
    output_path = None

    if img_b64:
        try:
            img_data = base64.b64decode(img_b64)
            try:
                from PIL import Image
            except ImportError:
                print(
                    "   Warning: Install Pillow (pip install Pillow) to decode and save images."
                )
                image = None
            else:
                image = Image.open(BytesIO(img_data))
                if save_image:
                    output_path = (
                        f"{output_prefix}_{endpoint_name.replace('/', '_')}.png"
                    )
                    image.save(output_path)
                    print(f"   Saved: {output_path}")
        except Exception as e:
            print(f"   Warning: Could not decode/save image: {e}")
            image = None
    else:
        print("   No image in response (fallback or error).")

    print(f"   Score: {metadata.get('final_score', 0):.3f}")
    print(f"   Iterations: {metadata.get('total_iterations', 0)}")
    print(f"   Success: {metadata.get('success', False)}")
    print("   Test complete.\n")

    return image, result


def main() -> int:
    parser = argparse.ArgumentParser(description="Test PhotoGenius SageMaker endpoints")
    parser.add_argument(
        "--endpoint",
        default=None,
        help="Endpoint name (e.g. photogenius-standard-endpoint)",
    )
    parser.add_argument(
        "--all-tiers",
        action="store_true",
        help="Test all three tiers (standard, premium, perfect)",
    )
    parser.add_argument(
        "--prompt",
        default="Person standing in sunlight",
        help="Prompt for image generation",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region",
    )
    parser.add_argument(
        "--environment",
        choices=["normal", "rainy", "fantasy"],
        default="normal",
        help="Environment type",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save output images",
    )
    parser.add_argument(
        "--output-prefix",
        default="test_output",
        help="Prefix for saved image filenames",
    )
    args = parser.parse_args()

    if args.endpoint:
        endpoints = [args.endpoint]
    elif args.all_tiers:
        endpoints = [
            "photogenius-standard-endpoint",
            "photogenius-premium-endpoint",
            "photogenius-perfect-endpoint",
        ]
    else:
        # Default: test all tiers (so "python test_endpoint.py" works)
        endpoints = [
            "photogenius-standard-endpoint",
            "photogenius-premium-endpoint",
            "photogenius-perfect-endpoint",
        ]

    success_count = 0
    for ep in endpoints:
        image, result = test_endpoint(
            endpoint_name=ep,
            prompt=args.prompt,
            region=args.region,
            environment=args.environment,
            seed=args.seed,
            save_image=not args.no_save,
            output_prefix=args.output_prefix,
        )
        if result:
            success_count += 1

    print(f"Completed: {success_count}/{len(endpoints)} endpoints responded.")
    return 0 if success_count == len(endpoints) else 1


if __name__ == "__main__":
    sys.exit(main())

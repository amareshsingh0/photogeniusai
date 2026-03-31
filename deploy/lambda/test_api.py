"""
Test client for PhotoGenius API (Lambda Orchestrator).

Usage:
  python test_api.py <API_ENDPOINT> [prompt]
  python test_api.py https://abc123.execute-api.us-east-1.amazonaws.com/prod "Person in rain"

Requires: requests (pip install requests). Optional: Pillow for image decode/save.
"""

from __future__ import annotations

import json
import sys
import time
from io import BytesIO

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)


class PhotoGeniusClient:
    """Client for PhotoGenius AI API (Lambda orchestrator)."""

    def __init__(self, api_endpoint: str):
        self.api_endpoint = api_endpoint.rstrip("/")

    def generate(
        self,
        prompt: str,
        tier: str = "auto",
        environment: str = "normal",
        seed: int | None = None,
        wait_for_completion: bool = True,
        poll_interval: int = 5,
    ):
        """
        Generate image from prompt.

        Args:
            prompt: Text description.
            tier: 'auto', 'standard', 'premium', or 'perfect'.
            environment: 'normal', 'rainy', or 'fantasy'.
            seed: Optional random seed.
            wait_for_completion: If True, poll until complete.
            poll_interval: Seconds between status checks.

        Returns:
            PIL Image if wait_for_completion=True and job completes, else job_id (str).
        """
        payload = {
            "prompt": prompt,
            "tier": tier,
            "environment": environment,
        }
        if seed is not None:
            payload["seed"] = seed

        response = requests.post(
            f"{self.api_endpoint}/generate",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()

        job_id = result["job_id"]
        print(f"[OK] Job created: {job_id}")
        print(
            f"     Tier: {result['tier']} ({result.get('tier_selection_reason', '')})"
        )
        print(f"     Estimated time: {result.get('estimated_time_seconds', 0)}s")

        if not wait_for_completion:
            return job_id

        print("\nWaiting for completion...")
        while True:
            status = self.get_status(job_id)

            if status["status"] == "completed":
                print("\n[OK] Generation complete!")
                print(f"     Time: {status.get('elapsed_time', 0)}s")
                image = self.get_result(job_id)
                return image

            if status["status"] == "failed":
                raise RuntimeError(
                    f"Generation failed: {status.get('error', 'Unknown error')}"
                )

            progress = status.get("progress", 0.0) * 100
            print(f"     Status: {status['status']} ({progress:.0f}%)", end="\r")
            time.sleep(poll_interval)

    def get_status(self, job_id: str) -> dict:
        """Get job status. Returns dict with status, elapsed_time, etc."""
        response = requests.get(
            f"{self.api_endpoint}/status/{job_id}",
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_result(
        self,
        job_id: str,
        save_path: str | None = None,
        include_base64: bool = True,
    ):
        """
        Get final result. Returns PIL Image if include_base64 and image present.

        Args:
            job_id: Job ID from generate().
            save_path: If set, save image to this path (requires Pillow).
            include_base64: Request base64 image in response (needed to return PIL Image).
        """
        params = {"include_base64": "true"} if include_base64 else None
        response = requests.get(
            f"{self.api_endpoint}/result/{job_id}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()

        if save_path and result.get("image_url"):
            # Could download from image_url instead of base64
            pass

        image = None
        if result.get("image_base64"):
            try:
                import base64

                img_data = base64.b64decode(result["image_base64"])
                try:
                    from PIL import Image as PILImage

                    image = PILImage.open(BytesIO(img_data))
                    if save_path:
                        image.save(save_path)
                        print(f"[OK] Saved to: {save_path}")
                except ImportError:
                    if save_path:
                        with open(save_path, "wb") as f:
                            f.write(img_data)
                        print(f"[OK] Saved raw bytes to: {save_path}")
            except Exception as e:
                print(f"Warning: Could not decode image: {e}")
        # If we have no PIL image but have metadata, return result dict for caller
        if image is not None:
            return image
        return result


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python test_api.py <API_ENDPOINT> [prompt]")
        print("")
        print("Example:")
        print(
            "  python test_api.py https://abc123.execute-api.us-east-1.amazonaws.com/prod"
        )
        print('  python test_api.py https://abc123.../prod "Person in rain"')
        return 1

    api_endpoint = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Person standing in sunlight"

    print("Testing PhotoGenius API")
    print(f"   Endpoint: {api_endpoint}")
    print(f"   Prompt: {prompt}\n")

    client = PhotoGeniusClient(api_endpoint)

    try:
        image = client.generate(prompt, tier="auto", wait_for_completion=True)
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                print(e.response.text)
            except Exception:
                pass
        return 1
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1

    output_path = "api_test_output.png"
    if hasattr(image, "save"):
        image.save(output_path)
        print(f"\n[OK] Test complete! Image saved to: {output_path}")
    elif isinstance(image, dict):
        meta = image.get("metadata", {})
        print(
            f"\n[OK] Test complete! Score: {meta.get('final_score', 'N/A')}, iterations: {meta.get('iterations', 'N/A')}"
        )
        if image.get("image_url"):
            print(f"     Image URL: {image['image_url']}")
    else:
        print("\n[OK] Test complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

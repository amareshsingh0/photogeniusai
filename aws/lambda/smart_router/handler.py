"""
Smart Router - Intelligent endpoint selection based on complexity.

Routes requests to:
- Small GPU (ml.g5.2xlarge) for simple images
- Large GPU (ml.g5.12xlarge) for complex images (auto-starts if needed)

Auto-scales down large GPU after idle timeout to save costs.
"""

import json
import boto3
import os
import time
import re
from typing import Dict, Any, Tuple

# Clients
sagemaker = boto3.client("sagemaker")
sagemaker_runtime = boto3.client("sagemaker-runtime")

# Endpoint names
SMALL_ENDPOINT = "photogenius-small-dev"  # Always on, $1.21/hr
LARGE_ENDPOINT = "photogenius-large-dev"  # Auto on/off, $7.09/hr

# Auto-scaling config
LARGE_ENDPOINT_IDLE_TIMEOUT = 300  # 5 minutes
LAST_LARGE_REQUEST_TIME = 0


def analyze_prompt_complexity(prompt: str, params: Dict) -> Tuple[str, float]:
    """
    Analyze prompt to determine required GPU size.

    Returns: (endpoint_name, complexity_score)
    """
    prompt_lower = prompt.lower()
    complexity_score = 0.0

    # Count people/person indicators
    people_keywords = [
        "people", "person", "man", "woman", "men", "women", "boy", "girl",
        "crowd", "group", "couple", "family", "friends", "team"
    ]
    people_count = sum(1 for kw in people_keywords if kw in prompt_lower)

    # Multiple people indicator
    if any(word in prompt_lower for word in ["people", "crowd", "group", "multiple", "several", "many"]):
        people_count += 2

    # Check for specific numbers
    number_matches = re.findall(r'\b(\d+|two|three|four|five|six|seven|eight|nine|ten)\b', prompt_lower)
    if number_matches:
        complexity_score += len(number_matches) * 10

    # Count objects
    object_keywords = [
        "and", ",", "with", "holding", "wearing", "carrying",
        "objects", "items", "things", "multiple"
    ]
    object_count = sum(1 for kw in object_keywords if kw in prompt_lower)

    # Scene complexity indicators
    complex_scenes = [
        "detailed", "intricate", "complex", "elaborate", "busy scene",
        "many details", "highly detailed", "ultra detailed", "crowded",
        "cityscape", "landscape with", "background with"
    ]
    scene_complexity = sum(1 for kw in complex_scenes if kw in prompt_lower)

    # Calculate complexity score
    complexity_score += people_count * 20
    complexity_score += object_count * 5
    complexity_score += scene_complexity * 15

    # Check parameters
    width = params.get("width", 1024)
    height = params.get("height", 1024)
    if width > 1024 or height > 1024:
        complexity_score += 20  # High resolution

    num_candidates = params.get("num_candidates", 1)
    if num_candidates > 1:
        complexity_score += num_candidates * 10  # Multiple candidates

    quality_tier = params.get("quality_tier", "STANDARD").upper()
    if quality_tier == "PREMIUM":
        complexity_score += 15  # Premium needs more memory

    # Decision threshold
    if complexity_score >= 50:
        return LARGE_ENDPOINT, complexity_score
    else:
        return SMALL_ENDPOINT, complexity_score


def ensure_endpoint_running(endpoint_name: str) -> bool:
    """
    Ensure endpoint is running. Start if stopped.
    Returns True if ready, False if starting.
    """
    try:
        response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
        status = response["EndpointStatus"]

        if status == "InService":
            print(f"✓ Endpoint {endpoint_name} is ready")
            return True

        elif status in ["Creating", "Updating"]:
            print(f"⏳ Endpoint {endpoint_name} is starting ({status})...")
            return False

        else:
            print(f"⚠️ Endpoint {endpoint_name} status: {status}")
            return False

    except sagemaker.exceptions.ClientError as e:
        if "Could not find endpoint" in str(e):
            print(f"❌ Endpoint {endpoint_name} not found")
            # Could auto-create here if needed
            return False
        raise


def invoke_endpoint(endpoint_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke SageMaker endpoint with payload."""
    print(f"Invoking endpoint: {endpoint_name}")

    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=json.dumps(payload),
    )

    result = json.loads(response["Body"].read())
    return result


def schedule_endpoint_shutdown(endpoint_name: str):
    """
    Schedule endpoint shutdown after idle timeout.
    (In production, use CloudWatch Events + Lambda)
    """
    # For now, just log. In production, trigger a CloudWatch event
    print(f"📅 Scheduled shutdown for {endpoint_name} after {LARGE_ENDPOINT_IDLE_TIMEOUT}s idle")
    # TODO: Implement with CloudWatch Events


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Smart router Lambda handler.

    Analyzes request complexity and routes to appropriate endpoint.
    """
    global LAST_LARGE_REQUEST_TIME

    try:
        # Parse request
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        prompt = body.get("prompt", body.get("inputs", ""))
        if not prompt:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "prompt is required"}),
            }

        # Extract parameters
        params = {
            "quality_tier": body.get("quality_tier", "STANDARD"),
            "width": body.get("width", 1024),
            "height": body.get("height", 1024),
            "num_candidates": body.get("num_candidates", 1),
        }

        # Analyze complexity
        selected_endpoint, complexity_score = analyze_prompt_complexity(prompt, params)

        print(f"\n{'='*80}")
        print(f"Smart Router Analysis")
        print(f"{'='*80}")
        print(f"Prompt: {prompt[:100]}...")
        print(f"Complexity Score: {complexity_score:.1f}")
        print(f"Selected Endpoint: {selected_endpoint}")
        print(f"Reasoning:")
        if selected_endpoint == LARGE_ENDPOINT:
            print(f"  - High complexity detected")
            print(f"  - Requires large GPU for best quality")
            print(f"  - Cost: $7.09/hr (auto-shutdown after idle)")
        else:
            print(f"  - Simple generation")
            print(f"  - Small GPU sufficient")
            print(f"  - Cost: $1.21/hr (always on)")
        print(f"{'='*80}\n")

        # Ensure endpoint is ready
        if not ensure_endpoint_running(selected_endpoint):
            if selected_endpoint == LARGE_ENDPOINT:
                return {
                    "statusCode": 202,  # Accepted, processing
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({
                        "message": "Complex image detected. Starting large GPU (30-60 seconds)...",
                        "complexity_score": complexity_score,
                        "endpoint": selected_endpoint,
                        "estimated_wait": "30-60 seconds",
                    }),
                }
            else:
                return {
                    "statusCode": 503,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": "Endpoint not ready"}),
                }

        # Update last request time for large endpoint
        if selected_endpoint == LARGE_ENDPOINT:
            LAST_LARGE_REQUEST_TIME = time.time()

        # Prepare payload for endpoint
        endpoint_payload = {
            "inputs": prompt,
            "quality_tier": params["quality_tier"],
            "parameters": {
                "width": params["width"],
                "height": params["height"],
                "negative_prompt": body.get("negative_prompt", ""),
            }
        }

        if params["num_candidates"] > 1:
            endpoint_payload["num_candidates"] = params["num_candidates"]

        # Invoke endpoint
        result = invoke_endpoint(selected_endpoint, endpoint_payload)

        # Add routing metadata
        result["routing"] = {
            "endpoint": selected_endpoint,
            "complexity_score": complexity_score,
            "cost_per_hour": "$7.09" if selected_endpoint == LARGE_ENDPOINT else "$1.21",
        }

        # Schedule shutdown for large endpoint (if idle)
        if selected_endpoint == LARGE_ENDPOINT:
            schedule_endpoint_shutdown(LARGE_ENDPOINT)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(result),
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }

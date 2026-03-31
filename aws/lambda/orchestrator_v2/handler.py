"""
Lambda Orchestrator v2 - Smart routing and cost optimization.

P1: Update Lambda to route requests intelligently.
Features:
- Quality tier detection from user request (simple → STANDARD, complex → PERFECT)
- Smart routing (simple → STANDARD, complex → PREMIUM/PERFECT)
- Progress WebSocket / callback URL updates
- Cost optimization (prefer STANDARD when possible)

Success Metric: 30% cost reduction via smart routing.

Input (body):
  prompt (required), quality_tier (optional; auto-detected if omitted),
  callback_url (optional), websocket_connection_id (optional, for API Gateway WebSocket),
  identity_id, face_image_base64, width, height, ...

Output: Same as orchestrator v1; metadata includes detected_tier, cost_saved.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

import boto3

# Reuse orchestrator v1 when in same package; else invoke v1 Lambda by name
try:
    from handler import (
        generate_with_quality_tier,
        invoke_sagemaker_endpoint,
        get_negative_prompt,
    )

    _has_v1_handler = True
except ImportError:
    generate_with_quality_tier = None
    invoke_sagemaker_endpoint = None
    get_negative_prompt = lambda s: "low quality, blurry, distorted"
    _has_v1_handler = False

ORCHESTRATOR_V1_FUNCTION = os.environ.get(
    "ORCHESTRATOR_V1_FUNCTION", "photogenius-orchestrator-dev"
)
lambda_client = boto3.client("lambda")
sm_runtime = boto3.client("sagemaker-runtime")

# Endpoints from env (same as v1); use production names when deployed via deploy/sagemaker_deployment.py
STANDARD_ENDPOINT = os.environ.get(
    "SAGEMAKER_GENERATION_ENDPOINT",
    os.environ.get("SAGEMAKER_ENDPOINT", "photogenius-standard"),
)
TWO_PASS_ENDPOINT = os.environ.get(
    "SAGEMAKER_TWO_PASS_ENDPOINT", "photogenius-two-pass"
)
FOUR_K_ENDPOINT = os.environ.get("SAGEMAKER_4K_ENDPOINT", "")
REALTIME_ENDPOINT = os.environ.get("SAGEMAKER_REALTIME_ENDPOINT", "")
IDENTITY_V2_ENDPOINT = os.environ.get("SAGEMAKER_IDENTITY_V2_ENDPOINT", "")

# Cost weights per tier (relative; STANDARD = 1.0)
TIER_COST_WEIGHT = {"FAST": 0.4, "STANDARD": 1.0, "PREMIUM": 2.0, "PERFECT": 3.0}

# Complexity heuristics for auto-tier
SIMPLE_PROMPT_MAX_CHARS = 120
COMPLEX_KEYWORDS = [
    "multiple",
    "several",
    "group",
    "family",
    "couple",
    "together",
    "detailed",
    "intricate",
    "complex",
    "fantasy",
    "dragon",
    "unicorn",
    "4k",
    "4K",
    "ultra",
    "high resolution",
    "refined",
    "masterpiece",
]
IDENTITY_INDICATORS = [
    "identity_id",
    "face_image_base64",
    "reference_face_base64",
    "identity_engine_version",
]


def _invoke_sagemaker_direct(
    endpoint_name: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Minimal direct SageMaker invoke (fallback when v1 Lambda not available).
    Returns parsed JSON from endpoint; raises on failure.
    """
    # Transform to HuggingFace Inference Toolkit format
    hf_payload = {
        "inputs": payload.get("prompt", ""),
        "parameters": {
            "num_inference_steps": payload.get("steps", 25),
            "guidance_scale": payload.get("guidance_scale", 7.5),
            "negative_prompt": payload.get("negative_prompt", ""),
            "width": payload.get("width", 1024),
            "height": payload.get("height", 1024),
        }
    }
    if payload.get("seed") is not None:
        hf_payload["parameters"]["seed"] = payload["seed"]
    if payload.get("return_preview"):
        hf_payload["parameters"]["return_preview"] = True
    if payload.get("num_inference_steps"):
        hf_payload["parameters"]["num_inference_steps"] = payload["num_inference_steps"]

    body_str = json.dumps(hf_payload)
    response = sm_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=body_str,
    )
    result_body = response["Body"].read().decode("utf-8")
    return json.loads(result_body)


def _generate_mock_response(prompt: str, quality_tier: str) -> Dict[str, Any]:
    """
    Return a mock/test response (1x1 red PNG) for pipeline testing.
    Use when SageMaker models aren't loaded yet or for CI/CD.
    """
    import base64

    # Minimal 1x1 red PNG (89 bytes)
    red_1x1_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img_b64 = base64.b64encode(red_1x1_png).decode("utf-8")
    return {
        "images": {"preview": img_b64, "final": img_b64},
        "metadata": {
            "quality_tier": quality_tier,
            "total_time": 0.01,
            "test_mode": True,
            "original_prompt": prompt,
            "enhanced_prompt": prompt,
            "mode": "TEST",
        },
        "error": None,
    }


def _direct_generate_with_tier(
    prompt: str, quality_tier: str, steps: int = 25, **kwargs: Any
) -> Dict[str, Any]:
    """
    Direct SageMaker invoke (no v1 Lambda). STANDARD → single-pass endpoint;
    PREMIUM/PERFECT/FAST → two-pass endpoint. Returns same shape as v1.
    """
    tier = (quality_tier or "STANDARD").upper()
    if tier == "PERFECT":
        tier = "PREMIUM"
    payload = {
        "prompt": prompt,
        "steps": kwargs.get("num_inference_steps") or steps,
        "negative_prompt": kwargs.get("negative_prompt") or "",
        "width": kwargs.get("width", 1024),
        "height": kwargs.get("height", 1024),
        "seed": kwargs.get("seed"),
    }
    if tier == "STANDARD":
        try:
            result = _invoke_sagemaker_direct(STANDARD_ENDPOINT, payload)
            img_b64 = result.get("image_base64") or result.get("final_base64")
            if (
                not img_b64
                and isinstance(result.get("images"), list)
                and result["images"]
            ):
                img_b64 = result["images"][0].get("image") or result["images"][0].get(
                    "b64"
                )
            if not img_b64 and isinstance(result.get("images"), dict):
                img_b64 = result["images"].get("final") or result["images"].get(
                    "preview"
                )
            return {
                "images": {"preview": None, "final": img_b64},
                "metadata": {
                    "quality_tier": "STANDARD",
                    "total_time": result.get("generation_time")
                    or result.get("inference_time")
                    or 0,
                },
                "error": result.get("error"),
            }
        except Exception as e:
            return {
                "images": {"preview": None, "final": None},
                "metadata": {"quality_tier": "STANDARD"},
                "error": str(e),
            }
    # PREMIUM / FAST → two-pass endpoint
    payload["return_preview"] = True
    payload["num_inference_steps"] = payload.get("steps", 50)
    try:
        result = _invoke_sagemaker_direct(TWO_PASS_ENDPOINT, payload)
        return {
            "images": {
                "preview": result.get("preview_base64"),
                "final": result.get("final_base64") or result.get("preview_base64"),
            },
            "metadata": {
                "quality_tier": tier,
                "preview_time": result.get("preview_time", 0),
                "final_time": result.get("final_time", 0),
                "total_time": result.get("preview_time", 0)
                + result.get("final_time", 0),
            },
            "error": result.get("error"),
        }
    except Exception as e:
        return {
            "images": {"preview": None, "final": None},
            "metadata": {"quality_tier": tier},
            "error": str(e),
        }


def detect_quality_tier_from_request(body: Dict[str, Any]) -> str:
    """
    Detect quality tier from request: simple → STANDARD, complex → PREMIUM/PERFECT.
    Reduces cost by using STANDARD when user does not need two-pass/4K.
    """
    explicit = (body.get("quality_tier") or "").strip().upper()
    if explicit in ("FAST", "STANDARD", "PREMIUM", "PERFECT"):
        return explicit

    prompt = (body.get("prompt") or "").strip()
    width = body.get("width") or 1024
    height = body.get("height") or 1024
    resolution_4k = (
        (body.get("resolution") or "").lower() == "4k"
        or width >= 3840
        or height >= 2160
    )

    # Identity / face → PREMIUM or PERFECT
    if any(body.get(k) for k in IDENTITY_INDICATORS if body.get(k)):
        return "PERFECT" if resolution_4k else "PREMIUM"

    # Explicit 4K → PERFECT
    if resolution_4k:
        return "PERFECT"

    # Long or complex prompt → PREMIUM
    if len(prompt) > SIMPLE_PROMPT_MAX_CHARS:
        return "PREMIUM"
    if any(kw in prompt.lower() for kw in COMPLEX_KEYWORDS):
        return "PREMIUM"

    # Default: STANDARD (cost optimization)
    return "STANDARD"


def send_progress(
    callback_url: Optional[str],
    connection_id: Optional[str],
    stage: str,
    payload: Dict[str, Any],
) -> None:
    """Send progress update via HTTP callback or API Gateway WebSocket."""
    data = {"stage": stage, "timestamp": time.time(), **payload}
    if callback_url:
        try:
            import urllib.request

            req = urllib.request.Request(
                callback_url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"Progress callback failed: {e}")
    if connection_id and os.environ.get("API_GATEWAY_WEBSOCKET_ENDPOINT"):
        try:
            apigw = boto3.client(
                "apigatewaymanagementapi",
                endpoint_url=os.environ["API_GATEWAY_WEBSOCKET_ENDPOINT"],
            )
            apigw.post_to_connection(ConnectionId=connection_id, Data=json.dumps(data))
        except Exception as e:
            print(f"WebSocket post failed: {e}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Orchestrator v2: detect tier, send progress, invoke generation, return result.
    Cost optimization: auto-select STANDARD when request is simple.
    """
    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)
    except Exception:
        body = {}

    user_prompt = (body.get("prompt") or "").strip()
    if not user_prompt:
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": "prompt is required"}),
        }

    # Test mode: return mock response without calling SageMaker (for pipeline testing)
    test_mode = (
        body.get("test_mode")
        or body.get("test")
        or os.environ.get("TEST_MODE") == "true"
    )
    if test_mode:
        result = _generate_mock_response(user_prompt, "STANDARD")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(result),
        }

    requested_tier = (body.get("quality_tier") or "").strip().upper()
    detected_tier = detect_quality_tier_from_request(body)
    quality_tier = (
        requested_tier
        if requested_tier in ("FAST", "STANDARD", "PREMIUM", "PERFECT")
        else detected_tier
    )

    callback_url = body.get("callback_url") or body.get("progress_callback_url")
    connection_id = event.get("requestContext", {}).get("connectionId") or body.get(
        "websocket_connection_id"
    )

    # Map PERFECT to PREMIUM for v1 handler (v1 uses FAST/STANDARD/PREMIUM)
    tier_for_invoke = "PREMIUM" if quality_tier == "PERFECT" else quality_tier

    send_progress(
        callback_url,
        connection_id,
        "queued",
        {"tier": quality_tier, "detected_tier": detected_tier},
    )

    send_progress(callback_url, connection_id, "invoking", {"tier": tier_for_invoke})

    result = None
    steps = body.get("num_inference_steps") or body.get("steps", 25)

    # 1) Use in-package v1 handler if available
    if _has_v1_handler and generate_with_quality_tier is not None:
        try:
            result = generate_with_quality_tier(
                prompt=user_prompt,
                quality_tier=tier_for_invoke,
                identity_id=body.get("identity_id"),
                user_id=body.get("user_id", "anonymous"),
                negative_prompt=body.get("negative_prompt")
                or get_negative_prompt(body.get("mode", "REALISM")),
                width=body.get("width", 1024),
                height=body.get("height", 1024),
                num_inference_steps=body.get("num_inference_steps"),
                guidance_scale=body.get("guidance_scale"),
                seed=body.get("seed"),
                style_lora=body.get("style_lora"),
                face_image_base64=body.get("face_image_base64")
                or body.get("reference_face_base64"),
                identity_engine_version=body.get("identity_engine_version"),
                identity_method=body.get("identity_method"),
            )
        except Exception as e:
            result = None
            print(f"v1 in-package failed: {e}")

    # 2) Else try invoking v1 Lambda by name
    if result is None:
        try:
            invoke_payload = {**body, "quality_tier": tier_for_invoke}
            resp = lambda_client.invoke(
                FunctionName=ORCHESTRATOR_V1_FUNCTION,
                InvocationType="RequestResponse",
                Payload=json.dumps({"body": json.dumps(invoke_payload)}),
            )
            payload_bytes = resp["Payload"].read()
            v1_response = json.loads(payload_bytes)
            if v1_response.get("statusCode") == 200:
                result = json.loads(v1_response.get("body", "{}"))
            else:
                body_str = v1_response.get("body", "{}")
                err = json.loads(body_str) if isinstance(body_str, str) else body_str
                raise RuntimeError(err.get("error", body_str))
        except Exception as e:
            print(f"v1 Lambda invoke failed: {e}")
            result = None

    # 3) Fallback: direct SageMaker invoke (no v1 needed)
    if result is None:
        result = _direct_generate_with_tier(
            prompt=user_prompt,
            quality_tier=tier_for_invoke,
            steps=steps,
            negative_prompt=body.get("negative_prompt")
            or get_negative_prompt(body.get("mode", "REALISM")),
            width=body.get("width", 1024),
            height=body.get("height", 1024),
            num_inference_steps=body.get("num_inference_steps"),
            seed=body.get("seed"),
        )

    if result is None or (
        result.get("error") and not result.get("images", {}).get("final")
    ):
        err = (result or {}).get("error", "Generation failed")
        send_progress(callback_url, connection_id, "error", {"error": err})
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": err}),
        }

    send_progress(
        callback_url,
        connection_id,
        "done",
        {"has_final": bool(result.get("images", {}).get("final"))},
    )

    # Cost saved: if we used STANDARD when user did not specify tier, we saved vs PREMIUM
    cost_saved = False
    if not requested_tier and detected_tier == "STANDARD":
        cost_saved = True  # Would have defaulted to STANDARD anyway; metric tracks auto-STANDARD usage
    requested_weight = TIER_COST_WEIGHT.get(requested_tier, 1.0)
    used_weight = TIER_COST_WEIGHT.get(tier_for_invoke, 1.0)
    cost_reduction_pct = (
        max(0, (requested_weight - used_weight) / requested_weight * 100)
        if requested_tier
        else 0
    )

    meta = result.get("metadata", {}) or {}
    meta["detected_tier"] = detected_tier
    meta["requested_tier"] = requested_tier or None
    meta["cost_optimized"] = cost_saved
    meta["cost_reduction_pct"] = round(cost_reduction_pct, 1)
    meta.setdefault("original_prompt", user_prompt)
    meta.setdefault("enhanced_prompt", user_prompt)
    meta.setdefault("mode", body.get("mode", "REALISM"))
    result["metadata"] = meta

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(result),
    }

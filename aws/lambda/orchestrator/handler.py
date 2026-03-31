"""
PhotoGenius AI - Orchestrator Lambda (AWS only, no Modal).

Flow: Optional semantic enhance → SageMaker (two-pass or single-pass by quality tier) → return images.
Quality tiers: FAST (Turbo preview), STANDARD (single-pass Base), PREMIUM (two-pass Turbo + Base + Refiner).
"""

import json
import os
import time
import uuid
import boto3
from datetime import datetime
from typing import Dict, Any, Optional

# SageMaker runtime client
sagemaker_runtime = boto3.client("sagemaker-runtime")
lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb")

# ==================== Advanced Services Integration (All 75+ Services) ====================
# Use Service Registry to dynamically load ALL available services with graceful degradation
try:
    from services_registry import (
        registry,
        get_service,
        is_service_available,
        list_available_services,
        get_registry_stats
    )

    # Log registry stats
    stats = get_registry_stats()
    print(f"🚀 Service Registry Initialized:")
    print(f"   📦 Total Services: {stats['total_services']}")
    print(f"   ✅ Available: {stats['available']}")
    print(f"   ⚠️ Unavailable: {stats['unavailable']}")
    print(f"   📊 Availability: {stats['availability_rate']}")

    # Load critical services from registry
    SMART_PROMPT_ENGINE = None
    PROMPT_CLASSIFIER = None
    PHYSICS_ENGINE = None
    EXPERIENCE_MEMORY = None
    QUALITY_SCORER = None

    if is_service_available('smart_prompt_engine'):
        SmartPromptEngine = get_service('smart_prompt_engine')
        SMART_PROMPT_ENGINE = SmartPromptEngine()
        print("   ✅ Smart Prompt Engine")

    if is_service_available('universal_prompt_classifier'):
        UniversalPromptClassifier = get_service('universal_prompt_classifier')
        PROMPT_CLASSIFIER = UniversalPromptClassifier()
        print("   ✅ Universal Prompt Classifier")

    if is_service_available('physics_micro_simulation'):
        from physics_micro_simulation import EnvironmentalConditions
        PhysicsMicroSimulation = get_service('physics_micro_simulation')
        PHYSICS_ENGINE = PhysicsMicroSimulation()
        print("   ✅ Physics Micro-Simulation")

    if is_service_available('experience_memory'):
        ExperienceMemory = get_service('experience_memory')
        EXPERIENCE_MEMORY = ExperienceMemory(storage_path="/tmp/experience_memory")
        print("   ✅ Experience Memory")

    if is_service_available('quality_scorer'):
        QualityScorer = get_service('quality_scorer')
        QUALITY_SCORER = QualityScorer()
        print("   ✅ Quality Scorer")

    # All 75+ services are available via registry.get_service('service_name')
    available_list = list_available_services()
    preview = ', '.join(available_list[:8])
    if len(available_list) > 8:
        preview += f'... (+{len(available_list)-8} more)'
    print(f"   📋 Available: {preview}")

except Exception as e:
    print(f"⚠️ Service Registry failed: {e}")
    SMART_PROMPT_ENGINE = None
    PROMPT_CLASSIFIER = None
    PHYSICS_ENGINE = None
    EXPERIENCE_MEMORY = None
    QUALITY_SCORER = None
    registry = None

# Endpoint names from environment
TWO_PASS_ENDPOINT = os.environ.get(
    "SAGEMAKER_TWO_PASS_ENDPOINT", "photogenius-two-pass-dev"
)
FOUR_K_ENDPOINT = os.environ.get(
    "SAGEMAKER_4K_ENDPOINT", os.environ.get("SAGEMAKER_FOUR_K_ENDPOINT", "")
)
REALTIME_ENDPOINT = os.environ.get(
    "SAGEMAKER_REALTIME_ENDPOINT", os.environ.get("REALTIME_ENDPOINT", "")
)
SINGLE_PASS_ENDPOINT = os.environ.get(
    "SAGEMAKER_GENERATION_ENDPOINT",
    os.environ.get("SAGEMAKER_ENDPOINT", "photogenius-generation-dev"),
)
IDENTITY_V2_ENDPOINT = os.environ.get(
    "SAGEMAKER_IDENTITY_V2_ENDPOINT", os.environ.get("IDENTITY_V2_ENDPOINT", "")
)
IDENTITY_ENGINE_VERSION = os.environ.get("IDENTITY_ENGINE_VERSION", "v1")  # v1 | v2
IDENTITY_METHOD = os.environ.get(
    "IDENTITY_METHOD", "ensemble"
)  # instantid | faceadapter | photomaker | ensemble
S3_BUCKET = os.environ.get("S3_BUCKET", "photogenius-images-dev")
GENERATION_TABLE = os.environ.get("DYNAMODB_TABLE", "photogenius-generations")
PROMPT_ENHANCER = os.environ.get("PROMPT_ENHANCER_FUNCTION", "")
POST_PROCESSOR = os.environ.get("POST_PROCESSOR_FUNCTION", "")

# Auto-validation (95%+ first-try success target): pass-through from backend or optional validation Lambda
AUTO_VALIDATION_ENABLED = os.environ.get("AUTO_VALIDATION_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)
MAX_REFINEMENT_LOOPS = int(os.environ.get("MAX_REFINEMENT_LOOPS", "2"))
VALIDATION_LAMBDA_ARN = os.environ.get("VALIDATION_LAMBDA_ARN", "")

# Mode/style to negative prompt (align with generation handler)
NEGATIVE_BY_STYLE = {
    "realistic": "low quality, blurry, distorted, deformed, ugly, bad anatomy, artistic, painterly, stylized, cartoon",
    "cinematic": "low quality, blurry, distorted, amateur, snapshot, flat lighting",
    "fantasy": "low quality, blurry, flat, amateur, generic, boring, poorly drawn, bad composition, worst quality",
    "fantasy_art": "low quality, blurry, flat, amateur, generic, boring, poorly drawn, bad composition, worst quality",
    "concept_art": "low quality, blurry, flat, amateur, generic, boring, poorly drawn, bad composition, worst quality",
    "surrealism": "low quality, blurry, flat, amateur, generic, boring, photorealistic literal, worst quality",
    "surrealism_fine_art": "low quality, blurry, flat, amateur, generic, boring, photorealistic literal, worst quality",
    "REALISM": "low quality, blurry, cartoon, 3d render, anime, drawing, painting, disfigured, bad anatomy",
    "CREATIVE": "ugly, tiling, poorly drawn hands, blurry, bad art, bad anatomy, worst quality",
    "CINEMATIC": "flat, boring, amateur, low quality, blurry, cartoon, anime",
    "COOL_EDGY": "bright, cheerful, soft, pastel, cartoon, amateur, low quality",
}
# Object-coherence: avoid umbrella/handle misalignment, disconnected parts
COHERENCE_NEGATIVE = (
    "misaligned parts, disconnected handle, wrong perspective, impossible geometry, "
    "floating parts, broken structure, handle canopy mismatch, inconsistent angles, "
    "structurally impossible, ai generated look, fake looking, disjointed object"
)
# Anatomy & limb coherence: eliminate missing hands, phantom limbs, duplicate objects
ANATOMY_NEGATIVE_EXTRA = (
    "missing hands, amputated, hand cut off, invisible hand, phantom limb, hand absorbed, "
    "duplicate object, extra ball, floating duplicate, cloned object, poorly drawn hands, bad hands"
)
DEFAULT_NEGATIVE = (
    "low quality, blurry, distorted, deformed, ugly, bad anatomy, worst quality, "
    + COHERENCE_NEGATIVE
    + ", "
    + ANATOMY_NEGATIVE_EXTRA
)


def get_negative_prompt(style: str) -> str:
    s = style if isinstance(style, str) else "cinematic"
    return (
        NEGATIVE_BY_STYLE.get(s) or NEGATIVE_BY_STYLE.get(s.upper()) or DEFAULT_NEGATIVE
    )


# ==================== Advanced Prompt Enhancement ====================

def enhance_prompt_with_smart_engine(user_prompt: str, mode: str = "REALISM") -> Dict[str, Any]:
    """
    Use Smart Prompt Engine to enhance prompt with category-specific boosters.

    Returns dict with:
        - enhanced_prompt: Full enhanced prompt
        - category: Detected category (portrait, landscape, action, etc.)
        - quality_boosters: Applied quality keywords
        - negative_prompt: Category-specific negative prompt
    """
    if not SMART_PROMPT_ENGINE or not PROMPT_CLASSIFIER:
        return {
            "enhanced_prompt": user_prompt,
            "category": "unknown",
            "quality_boosters": [],
            "negative_prompt": get_negative_prompt(mode)
        }

    try:
        # Classify the prompt
        classification = PROMPT_CLASSIFIER.classify(user_prompt)

        # Build enhanced prompt with category-specific quality boosters
        positive_prompt, negative_prompt = SMART_PROMPT_ENGINE.build_prompts(
            base_prompt=user_prompt,
            classification=classification
        )

        print(f"✅ Smart Engine: category={classification.category}, confidence={classification.confidence:.2f}")

        return {
            "enhanced_prompt": positive_prompt,
            "category": classification.category,
            "quality_boosters": classification.keywords,
            "negative_prompt": negative_prompt
        }
    except Exception as e:
        print(f"⚠️ Smart enhancement failed: {e}")
        return {
            "enhanced_prompt": user_prompt,
            "category": "unknown",
            "quality_boosters": [],
            "negative_prompt": get_negative_prompt(mode)
        }


def validate_with_physics(prompt: str, scene_type: str = "general") -> Dict[str, Any]:
    """
    Use Physics Engine to validate scene coherence.

    Returns dict with:
        - is_coherent: Whether the scene makes physical sense
        - issues: List of detected issues
        - suggestions: Corrections to improve realism
    """
    if not PHYSICS_ENGINE:
        return {"is_coherent": True, "issues": [], "suggestions": []}

    try:
        # Create environmental conditions based on prompt keywords
        conditions = EnvironmentalConditions()

        # Check for weather indicators in prompt
        prompt_lower = prompt.lower()
        if any(w in prompt_lower for w in ["rain", "wet", "dripping"]):
            conditions.is_raining = True
            conditions.rain_intensity = 0.7
        if any(w in prompt_lower for w in ["sunny", "bright", "sunlight"]):
            conditions.light_intensity = 1.0
        if any(w in prompt_lower for w in ["wind", "windy", "breeze"]):
            conditions.wind_speed = 0.6

        # Simulate physics for common materials
        issues = []
        suggestions = []

        # Example: Check if umbrella physics makes sense in rain
        if conditions.is_raining and "umbrella" in prompt_lower:
            # Umbrella should show wetness
            if "dry" in prompt_lower:
                issues.append("Umbrella marked as dry in rain scene")
                suggestions.append("Add 'water droplets', 'wet surface', 'rain beading'")

        return {
            "is_coherent": len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions
        }
    except Exception as e:
        print(f"⚠️ Physics validation failed: {e}")
        return {"is_coherent": True, "issues": [], "suggestions": []}


def log_generation_experience(
    prompt: str,
    enhanced_prompt: str,
    category: str,
    quality_tier: str,
    result: Dict[str, Any],
    success: bool
) -> None:
    """
    Log generation to Experience Memory for learning.
    """
    if not EXPERIENCE_MEMORY:
        return

    try:
        # Create experience record
        experience = {
            "prompt": prompt,
            "enhanced_prompt": enhanced_prompt,
            "category": category,
            "quality_tier": quality_tier,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": result.get("metadata", {})
        }

        EXPERIENCE_MEMORY.add_experience(experience)
        print(f"✅ Logged to experience memory: {category}, success={success}")
    except Exception as e:
        print(f"⚠️ Failed to log experience: {e}")


# ==================== SageMaker invocation ====================


def invoke_sagemaker_endpoint(
    endpoint_name: str,
    payload: Dict[str, Any],
    timeout: int = 300,
) -> Dict[str, Any]:
    """
    Invoke SageMaker endpoint with error handling.

    Args:
        endpoint_name: SageMaker endpoint name
        payload: Request payload (JSON-serializable)
        timeout: Request timeout in seconds (SageMaker uses endpoint config)

    Returns:
        Parsed response dict from endpoint
    """
    try:
        print(f"Invoking endpoint: {endpoint_name}")

        # Transform to HuggingFace Inference Toolkit format
        # Strong negative prompt for photorealism
        default_negative = "ugly, tiling, poorly drawn hands, poorly drawn feet, poorly drawn face, out of frame, mutation, mutated, extra limbs, extra legs, extra arms, disfigured, deformed, cross-eye, body out of frame, blurry, bad art, bad anatomy, blurred, text, watermark, grainy, worst quality, low quality, jpeg artifacts, signature, username, artist name, deformed iris, deformed pupils, semi-realistic, cgi, 3d, render, sketch, cartoon, drawing, anime, duplicate, morbid, mutilated, extra fingers, mutated hands, poorly drawn eyes, cloned face, gross proportions, malformed limbs, missing arms, missing legs, fused fingers, too many fingers"

        hf_payload = {
            "inputs": payload.get("prompt", payload.get("inputs", "")),
            "parameters": {
                "num_inference_steps": payload.get("steps", payload.get("num_inference_steps", 50)),
                "guidance_scale": payload.get("guidance_scale", 8.5),
                "negative_prompt": payload.get("negative_prompt", default_negative),
                "width": payload.get("width", 1024),
                "height": payload.get("height", 1024),
            }
        }
        if payload.get("seed") is not None:
            hf_payload["parameters"]["seed"] = payload["seed"]
        if payload.get("return_preview"):
            hf_payload["parameters"]["return_preview"] = True

        body_str = json.dumps(hf_payload)
        print(f"Payload size: {len(body_str)} chars")

        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Body=body_str,
        )

        result_body = response["Body"].read().decode("utf-8")
        result = json.loads(result_body)
        print("✅ Endpoint invoked successfully")
        return result
    except Exception as e:
        print(f"❌ Endpoint invocation failed: {e}")
        raise


def _normalize_sagemaker_response(result: Any) -> Dict[str, Any]:
    """
    Normalize SageMaker response to consistent format.
    Handles: string, list of strings, dict responses from HuggingFace.
    """
    if isinstance(result, str):
        # Single base64 string
        return {"image_base64": result, "images": [result]}
    elif isinstance(result, list) and result:
        # List of base64 strings or dicts
        first_item = result[0]
        if isinstance(first_item, str):
            return {"image_base64": first_item, "images": result}
        elif isinstance(first_item, dict):
            img = first_item.get("image") or first_item.get("b64") or first_item.get("generated_image")
            return {"image_base64": img, "images": result}
    elif isinstance(result, dict):
        # Already a dict, just ensure we have image_base64
        if not result.get("image_base64"):
            # Try to extract from various fields
            result["image_base64"] = (
                result.get("final_base64") or
                result.get("preview_base64") or
                (result["images"][0] if isinstance(result.get("images"), list) and result["images"] else None)
            )
        return result
    return {"image_base64": None, "error": "Invalid response format"}

def _normalize_single_pass_result(result: Dict[str, Any]) -> Optional[str]:
    """Extract image_base64 from single-pass endpoint response (HF toolkit or custom)."""
    normalized = _normalize_sagemaker_response(result)
    if normalized.get("image_base64"):
        return normalized["image_base64"]
    if normalized.get("final_base64"):
        return normalized["final_base64"]
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("image") or first.get("b64")
    if isinstance(result, dict):
        for key in ("images", "generated_images", "generated_image"):
            if key in result:
                val = result[key]
                img = val[0] if isinstance(val, list) else val
                if isinstance(img, dict):
                    img = img.get("image") or img.get("b64")
                if img:
                    return img
        if result.get("image"):
            return result["image"]
    return None


# ==================== Quality tier routing ====================


def generate_with_quality_tier(
    prompt: str,
    quality_tier: str,
    identity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Route generation based on quality tier.

    Tiers:
    - FAST: Two-pass with preview only (Turbo ~5s); returns preview as main image.
    - STANDARD: Single-pass SDXL Base (~40s).
    - PREMIUM: Two-pass Turbo + Base + Refiner (~45s).

    Args:
        prompt: Enhanced prompt
        quality_tier: FAST | STANDARD | PREMIUM
        identity_id: Optional LoRA identity
        user_id: User ID for LoRA path
        **kwargs: negative_prompt, width, height, num_inference_steps, guidance_scale, seed, denoising_strength

    Returns:
        Dict with images (preview, final) and metadata (quality_tier, times).
    """
    # Use `or` for defaults since kwargs may contain explicit None values
    base_payload = {
        "prompt": prompt,
        "identity_id": identity_id,
        "user_id": user_id or "",
        "style_lora": kwargs.get("style_lora"),
        "negative_prompt": kwargs.get("negative_prompt") or "",
        "width": kwargs.get("width") or 1024,
        "height": kwargs.get("height") or 1024,
        "seed": kwargs.get("seed"),  # seed can be None (random)
    }

    tier = (quality_tier or "STANDARD").upper()

    if tier == "FAST":
        # Prefer realtime endpoint (LCM 8–10s) when set; else two-pass Turbo preview
        if REALTIME_ENDPOINT:
            print("🚀 FAST tier: Realtime (LCM) preview")
            payload = {
                "prompt": prompt,
                "negative_prompt": base_payload.get("negative_prompt", ""),
                "steps": 4,
                "guidance_scale": 1.0,
                "upscale_to": 1024,
                "seed": base_payload.get("seed"),
            }
            try:
                result = invoke_sagemaker_endpoint(REALTIME_ENDPOINT, payload)
                result = _normalize_sagemaker_response(result)
                preview_b64 = result.get("preview_base64") or result.get("image_base64")
                return {
                    "images": {"preview": preview_b64, "final": preview_b64},
                    "metadata": {
                        "quality_tier": "FAST",
                        "preview_time": result.get("preview_time", 0),
                        "final_time": 0,
                        "total_time": result.get("preview_time", 0),
                        "source": "realtime",
                    },
                    "error": result.get("error"),
                }
            except Exception as e:
                print(f"⚠️ Realtime endpoint failed, fallback to two-pass: {e}")
        print("🚀 FAST tier: Turbo preview only")
        payload = {
            **base_payload,
            "num_inference_steps": 4,
            "guidance_scale": 1.0,
            "return_preview": True,
        }
        result = invoke_sagemaker_endpoint(TWO_PASS_ENDPOINT, payload)
        result = _normalize_sagemaker_response(result)
        preview_b64 = result.get("preview_base64") or result.get("image_base64")
        return {
            "images": {"preview": preview_b64, "final": preview_b64},
            "metadata": {
                "quality_tier": "FAST",
                "preview_time": result.get("preview_time", 0),
                "final_time": 0,
                "total_time": result.get("preview_time", 0),
            },
            "error": result.get("error"),
        }

    if tier == "STANDARD":
        print("📊 STANDARD tier: Single-pass Base")
        # HuggingFace Inference Toolkit expects "inputs" (str) + "parameters" (dict)
        # Use `or` instead of kwargs.get() default because kwargs may contain explicit None values
        sm_payload = {
            "inputs": prompt,  # HF toolkit requires "inputs" as string
            "parameters": {
                "num_inference_steps": kwargs.get("num_inference_steps") or 30,
                "guidance_scale": kwargs.get("guidance_scale") or 8.5,
                "negative_prompt": kwargs.get("negative_prompt") or "",
                "width": kwargs.get("width") or 1024,
                "height": kwargs.get("height") or 1024,
            },
        }
        # Add optional parameters if provided
        if kwargs.get("seed") is not None:
            sm_payload["parameters"]["seed"] = kwargs["seed"]
        if identity_id and identity_id != "default":
            sm_payload["parameters"]["identity_id"] = identity_id
        if user_id:
            sm_payload["parameters"]["user_id"] = user_id
        result = invoke_sagemaker_endpoint(SINGLE_PASS_ENDPOINT, sm_payload)
        image_b64 = _normalize_single_pass_result(result)
        # Handle case where result is a string (raw base64) instead of dict
        if isinstance(result, dict):
            gen_time = (
                result.get("generation_time")
                or result.get("final_time")
                or result.get("inference_time")
                or 0
            )
            error = result.get("error")
        else:
            gen_time = 0
            error = None
        return {
            "images": {
                "preview": None,
                "final": image_b64,
            },
            "metadata": {
                "quality_tier": "STANDARD",
                "generation_time": gen_time,
                "total_time": gen_time,
            },
            "error": error,
        }

    if tier == "PREMIUM":
        # Native 4K: route to 4K endpoint when resolution=4k or width=3840
        resolution_4k = (
            (kwargs.get("resolution") or "").lower() == "4k"
            or kwargs.get("width") == 3840
            or kwargs.get("height") in (2160, 3840)
        )
        if resolution_4k and FOUR_K_ENDPOINT:
            print("⭐ PREMIUM tier: Native 4K generation")
            width_4k = kwargs.get("width") or 3840
            height_4k = kwargs.get("height") or 2160
            if height_4k not in (2160, 3840):
                height_4k = 2160 if width_4k == 3840 else 3840
            payload = {
                "prompt": prompt,
                "negative_prompt": base_payload.get("negative_prompt") or "",
                "width": width_4k,
                "height": height_4k,
                "steps": kwargs.get("num_inference_steps") or 40,
                "guidance_scale": kwargs.get("guidance_scale") or 7.5,
                "seed": base_payload.get("seed"),
                "method": kwargs.get("4k_method") or "latent",
            }
            try:
                result_4k = invoke_sagemaker_endpoint(FOUR_K_ENDPOINT, payload)
                image_b64 = result_4k.get("image_base64")
                gen_time = result_4k.get("inference_time", 0)
                return {
                    "images": {"preview": image_b64, "final": image_b64},
                    "metadata": {
                        "quality_tier": "PREMIUM",
                        "resolution": "4k",
                        "width": result_4k.get("width", width_4k),
                        "height": result_4k.get("height", height_4k),
                        "preview_time": 0,
                        "final_time": gen_time,
                        "total_time": gen_time,
                    },
                    "error": result_4k.get("error"),
                }
            except Exception as e:
                print(f"⚠️ 4K endpoint failed, fallback to two-pass: {e}")
        print("⭐ PREMIUM tier: Two-pass generation")
        payload = {
            **base_payload,
            "num_inference_steps": kwargs.get("num_inference_steps") or 50,
            "guidance_scale": kwargs.get("guidance_scale") or 8.5,
            "return_preview": True,
            "denoising_strength": kwargs.get("denoising_strength") or 0.3,
        }
        result = invoke_sagemaker_endpoint(TWO_PASS_ENDPOINT, payload)
        result = _normalize_sagemaker_response(result)

        preview_time = result.get("preview_time", 0)
        final_time = result.get("final_time", 0)
        return {
            "images": {
                "preview": result.get("preview_base64"),
                "final": result.get("final_base64") or result.get("image_base64"),
            },
            "metadata": {
                "quality_tier": "PREMIUM",
                "preview_time": preview_time,
                "final_time": final_time,
                "total_time": preview_time + final_time,
            },
            "error": result.get("error"),
        }

    raise ValueError(
        f"Invalid quality tier: {quality_tier}. Use FAST, STANDARD, or PREMIUM."
    )


# ==================== Identity Engine V2 (optional) ====================


def generate_with_identity_v2(
    prompt: str,
    face_image_base64: str,
    identity_method: Optional[str] = None,
    identity_embedding: Optional[list] = None,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    num_inference_steps: int = 45,
    guidance_scale: float = 7.5,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Invoke Identity V2 SageMaker endpoint for 99%+ face consistency.

    Args:
        prompt: Text prompt
        face_image_base64: Reference face image (base64)
        identity_method: instantid | faceadapter | photomaker | ensemble
        identity_embedding: Optional pre-computed embedding list
        **kwargs: negative_prompt, width, height, num_inference_steps, guidance_scale, seed

    Returns:
        Dict with images.final (base64), metadata (similarity, path, guaranteed, inference_time), error
    """
    # Use env only — do not hardcode endpoint name
    endpoint = os.getenv("SAGEMAKER_IDENTITY_V2_ENDPOINT", "")
    if not endpoint:
        return {
            "images": {"preview": None, "final": None},
            "metadata": {"identity_similarity": 0, "path": "", "guaranteed": False},
            "error": "Identity V2 endpoint not configured (SAGEMAKER_IDENTITY_V2_ENDPOINT)",
        }
    method = (identity_method or IDENTITY_METHOD or "ensemble").lower()
    if method not in ("instantid", "faceadapter", "photomaker", "ensemble"):
        method = "ensemble"
    payload = {
        "prompt": prompt,
        "face_image_base64": face_image_base64,
        "identity_method": method,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "seed": seed,
    }
    if identity_embedding is not None:
        payload["identity_embedding"] = identity_embedding
    try:
        print(f"Identity V2: invoking {endpoint} method={method}")
        result = invoke_sagemaker_endpoint(endpoint, payload)
        image_b64 = result.get("image_base64")
        return {
            "images": {"preview": image_b64, "final": image_b64},
            "metadata": {
                "identity_similarity": result.get("similarity", 0),
                "path": result.get("path", ""),
                "guaranteed": result.get("guaranteed", False),
                "inference_time": result.get("inference_time", 0),
                "quality_tier": "PREMIUM",
            },
            "error": result.get("error"),
        }
    except Exception as e:
        print(f"Identity V2 invocation failed: {e}")
        return {
            "images": {"preview": None, "final": None},
            "metadata": {"identity_similarity": 0, "path": "", "guaranteed": False},
            "error": str(e),
        }


# ==================== Auto-validation (metrics + optional Lambda) ====================


def ensure_validation_metadata(
    result: Dict[str, Any],
    prompt: str,
    quality_tier: str,
) -> None:
    """
    Ensure result.metadata has validation metrics (first_try_success, refinement_loops_used).
    If VALIDATION_LAMBDA_ARN is set and we have a final image, invoke it and merge metrics.
    Otherwise set defaults for monitoring. Log first_try_success for CloudWatch.
    """
    meta = result.get("metadata") or {}
    final_b64 = (result.get("images") or {}).get("final")
    first_try_success = meta.get("first_try_success", True)
    refinement_loops_used = meta.get("refinement_loops_used", 0)

    if AUTO_VALIDATION_ENABLED and VALIDATION_LAMBDA_ARN and final_b64:
        try:
            val_response = lambda_client.invoke(
                FunctionName=VALIDATION_LAMBDA_ARN,
                InvocationType="RequestResponse",
                Payload=json.dumps(
                    {
                        "image_base64": final_b64,
                        "prompt": prompt,
                        "max_retries": MAX_REFINEMENT_LOOPS,
                    }
                ),
            )
            val_payload = json.loads(val_response["Payload"].read())
            if val_payload.get("first_try_success") is not None:
                first_try_success = val_payload["first_try_success"]
            if val_payload.get("refinement_loops_used") is not None:
                refinement_loops_used = val_payload["refinement_loops_used"]
            if val_payload.get("image_base64"):
                result.setdefault("images", {})["final"] = val_payload["image_base64"]
        except Exception as e:
            print(f"Validation Lambda invocation failed: {e}")

    result.setdefault("metadata", {})["validation"] = {
        "first_try_success": first_try_success,
        "refinement_loops_used": refinement_loops_used,
    }
    result["metadata"]["first_try_success"] = first_try_success
    result["metadata"]["refinement_loops_used"] = refinement_loops_used
    # Log for CloudWatch / monitoring (target: 95%+ first-try success)
    print(
        f"auto_validation first_try_success={first_try_success} refinement_loops_used={refinement_loops_used} quality_tier={quality_tier}"
    )


# ==================== Main handler ====================


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main orchestrator handler.

    Routing:
        - No identity_engine_version=v2 → standard pipeline (FAST / STANDARD / PREMIUM).
        - identity_engine_version=v2 + face_image_base64 + SAGEMAKER_IDENTITY_V2_ENDPOINT set
          → Identity V2 SageMaker; on failure → fallback to standard pipeline.
    Do not hardcode endpoint names; use SAGEMAKER_IDENTITY_V2_ENDPOINT only.

    Input (body):
        prompt (required), quality_tier (FAST|STANDARD|PREMIUM), mode, identity_id, user_id,
        identity_engine_version ("v2" to use Identity V2), face_image_base64, identity_method,
        negative_prompt, width, height, num_inference_steps, guidance_scale, seed

    Output:
        statusCode, body: { images: { preview, final }, metadata: { ... } }
    """
    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

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

        quality_tier = body.get("quality_tier", "STANDARD")
        mode = body.get("mode", body.get("style", "REALISM"))
        identity_id = body.get("identity_id")
        user_id = body.get("user_id", "anonymous")
        style_lora = body.get("style_lora")
        identity_engine_version = (
            body.get("identity_engine_version") or IDENTITY_ENGINE_VERSION
        )
        identity_method = body.get("identity_method") or IDENTITY_METHOD
        face_image_base64 = body.get("face_image_base64") or body.get(
            "reference_face_base64"
        )

        print(
            f"Request: tier={quality_tier}, mode={mode}, identity_engine={identity_engine_version}, prompt={user_prompt[:50]}..."
        )

        # 1. Advanced prompt enhancement with Smart Engine + Semantic enhancer
        enhanced_prompt = user_prompt
        detected_category = "unknown"
        smart_negative = ""
        is_fantasy_concept = False
        is_surrealism_fine_art = False
        is_cosmic_surreal_art = False

        # First, use Smart Prompt Engine for category-specific enhancement
        smart_result = enhance_prompt_with_smart_engine(user_prompt, mode)
        enhanced_prompt = smart_result["enhanced_prompt"]
        detected_category = smart_result["category"]
        smart_negative = smart_result["negative_prompt"]
        print(f"✅ Smart Engine enhanced: category={detected_category}")

        # Then, apply semantic enhancement on top for mode-specific styling
        try:
            from semantic_prompt_enhancer import (
                SemanticPromptEnhancer,
                suggest_style_lora,
                FANTASY_KEYWORDS,
                SURREALISM_KEYWORDS,
                COSMIC_SURREAL_KEYWORDS,
            )

            enhancer = SemanticPromptEnhancer()
            enhanced_prompt = enhancer.enhance(enhanced_prompt, mode)
            is_fantasy_concept = any(
                kw in enhanced_prompt.lower() for kw in FANTASY_KEYWORDS
            )
            is_surrealism_fine_art = any(
                kw in enhanced_prompt.lower() for kw in SURREALISM_KEYWORDS
            )
            is_cosmic_surreal_art = any(
                kw in enhanced_prompt.lower() for kw in COSMIC_SURREAL_KEYWORDS
            )
            if not style_lora:
                suggested = suggest_style_lora(enhanced_prompt)
                if suggested:
                    style_lora = suggested
                    print(f"✅ Style LoRA auto-applied from prompt: {style_lora}")
            print(
                f"✅ Prompt enhanced: {len(enhanced_prompt)} chars"
                + (" (fantasy/concept art)" if is_fantasy_concept else "")
                + (" (surrealism/fine art)" if is_surrealism_fine_art else "")
                + (" (cosmic/surreal art)" if is_cosmic_surreal_art else "")
            )
        except Exception as e:
            print(f"⚠️ Semantic enhancement skipped: {e}")
            is_fantasy_concept = any(
                kw in user_prompt.lower()
                for kw in [
                    "flying",
                    "turtle",
                    "tortoise",
                    "dragon",
                    "creature",
                    "city on back",
                    "steampunk",
                    "airship",
                    "concept art",
                    "fantasy",
                ]
            )
            is_surrealism_fine_art = any(
                kw in user_prompt.lower()
                for kw in [
                    "melting",
                    "clock",
                    "watch",
                    "dali",
                    "dalí",
                    "van gogh",
                    "starry night",
                    "surrealism",
                    "dreamscape",
                    "impasto",
                ]
            )
            is_cosmic_surreal_art = any(
                kw in user_prompt.lower()
                for kw in [
                    "cosmic",
                    "surrealist",
                    "nebulae",
                    "star clusters",
                    "slam dunk",
                    "basketball",
                    "jersey",
                    "deep space",
                    "galaxies",
                    "mid-air",
                ]
            )

        # 2. Legacy: rule-based enhancer Lambda (if no quality_tier path or we want both)
        if not body.get("quality_tier") and PROMPT_ENHANCER:
            try:
                enhance_response = lambda_client.invoke(
                    FunctionName=PROMPT_ENHANCER,
                    InvocationType="RequestResponse",
                    Payload=json.dumps(
                        {"body": json.dumps({"prompt": user_prompt, "style": mode})}
                    ),
                )
                enhance_result = json.loads(enhance_response["Payload"].read())
                if enhance_result.get("statusCode") == 200:
                    enhance_body = json.loads(enhance_result.get("body", "{}"))
                    enhanced_prompt = enhance_body.get("enhanced", enhanced_prompt)
            except Exception:
                pass

        # 3. Routing: Identity V2 only when explicitly requested; else default flow (FAST/STANDARD/PREMIUM)
        # Do not hardcode endpoint names — use env SAGEMAKER_IDENTITY_V2_ENDPOINT only.
        use_identity_v2 = (
            body.get("identity_engine_version") == "v2"
            and face_image_base64
            and os.getenv("SAGEMAKER_IDENTITY_V2_ENDPOINT")
        )
        if use_identity_v2:
            result = generate_with_identity_v2(
                prompt=enhanced_prompt,
                face_image_base64=face_image_base64,
                identity_method=identity_method,
                identity_embedding=body.get("identity_embedding"),
                negative_prompt=body.get("negative_prompt")
                or get_negative_prompt(mode),
                width=body.get("width", 1024),
                height=body.get("height", 1024),
                num_inference_steps=body.get("num_inference_steps", 45),
                guidance_scale=body.get("guidance_scale", 7.5),
                seed=body.get("seed"),
            )
            if result.get("error") or not result.get("images", {}).get("final"):
                print(
                    "Identity V2 failed or no image; falling back to standard pipeline"
                )
                result = generate_with_quality_tier(
                    prompt=enhanced_prompt,
                    quality_tier=quality_tier,
                    identity_id=identity_id,
                    user_id=user_id,
                    style_lora=style_lora,
                    resolution=body.get("resolution"),
                    negative_prompt=body.get("negative_prompt")
                    or get_negative_prompt(mode),
                    width=body.get("width"),
                    height=body.get("height"),
                    num_inference_steps=body.get("num_inference_steps"),
                    guidance_scale=body.get("guidance_scale"),
                    seed=body.get("seed"),
                    denoising_strength=body.get("denoising_strength"),
                    **(
                        {"4k_method": body.get("4k_method")}
                        if body.get("4k_method")
                        else {}
                    ),
                )
        else:
            # Use smart negative from category detection, with fallback to style-specific negative
            neg_prompt = body.get("negative_prompt") or smart_negative or (
                get_negative_prompt("fantasy")
                if is_fantasy_concept
                else (
                    get_negative_prompt("surrealism")
                    if is_surrealism_fine_art
                    else (
                        get_negative_prompt("CREATIVE")
                        if is_cosmic_surreal_art
                        else get_negative_prompt(mode)
                    )
                )
            )
            kwargs_tier = {
                "resolution": body.get("resolution"),
                "negative_prompt": neg_prompt,
                "width": body.get("width"),
                "height": body.get("height"),
                "num_inference_steps": body.get("num_inference_steps"),
                "guidance_scale": body.get("guidance_scale"),
                "seed": body.get("seed"),
                "denoising_strength": body.get("denoising_strength"),
            }
            if body.get("4k_method"):
                kwargs_tier["4k_method"] = body.get("4k_method")
            # Next-level: fantasy, surrealism, or cosmic/surreal art on PREMIUM gets higher steps
            if (
                (is_fantasy_concept or is_surrealism_fine_art or is_cosmic_surreal_art)
                and (quality_tier or "").upper() == "PREMIUM"
                and not body.get("num_inference_steps")
            ):
                kwargs_tier["num_inference_steps"] = 55
            result = generate_with_quality_tier(
                prompt=enhanced_prompt,
                quality_tier=quality_tier,
                identity_id=identity_id,
                user_id=user_id,
                style_lora=style_lora,
                **kwargs_tier,
            )

        # 4. Physics validation (check scene coherence)
        physics_check = validate_with_physics(enhanced_prompt, mode)
        if not physics_check["is_coherent"]:
            print(f"⚠️ Physics issues detected: {physics_check['issues']}")
            result["metadata"]["physics_warnings"] = physics_check["issues"]
            result["metadata"]["physics_suggestions"] = physics_check["suggestions"]

        # 5. Validation metrics (first_try_success, refinement_loops_used) + optional validation Lambda
        ensure_validation_metadata(result, enhanced_prompt, quality_tier)

        # 6. Log generation experience for learning
        generation_success = result.get("images", {}).get("final") is not None and not result.get("error")
        log_generation_experience(
            prompt=user_prompt,
            enhanced_prompt=enhanced_prompt,
            category=detected_category,
            quality_tier=quality_tier,
            result=result,
            success=generation_success
        )

        # 7. Enrich metadata
        result["metadata"]["original_prompt"] = user_prompt
        result["metadata"]["enhanced_prompt"] = enhanced_prompt
        result["metadata"]["mode"] = mode
        result["metadata"]["detected_category"] = detected_category
        if (
            use_identity_v2
            and result.get("metadata", {}).get("identity_similarity") is not None
        ):
            result["metadata"]["identity_engine_version"] = "v2"
            result["metadata"]["identity_method"] = identity_method

        # 6. Optional: post-process and DynamoDB (when final image present)
        final_b64 = result.get("images", {}).get("final")
        generation_id = str(uuid.uuid4())
        if final_b64 and S3_BUCKET:
            try:
                import base64

                s3 = boto3.client("s3")
                key = f"generations/{generation_id}.png"
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=key,
                    Body=base64.b64decode(final_b64),
                    ContentType="image/png",
                )
                region = os.environ.get("AWS_REGION", "us-east-1")
                result["metadata"][
                    "image_url"
                ] = f"https://{S3_BUCKET}.s3.{region}.amazonaws.com/{key}"
            except Exception as e:
                print(f"⚠️ S3 upload failed: {e}")
        result["metadata"]["generation_id"] = generation_id

        if GENERATION_TABLE and final_b64:
            try:
                table = dynamodb.Table(GENERATION_TABLE)
                table.put_item(
                    Item={
                        "generation_id": generation_id,
                        "user_id": user_id,
                        "original_prompt": user_prompt,
                        "enhanced_prompt": enhanced_prompt,
                        "style": mode,
                        "quality_tier": quality_tier,
                        "image_url": result["metadata"].get("image_url", ""),
                        "created_at": int(datetime.utcnow().timestamp()),
                        "ttl": int(datetime.utcnow().timestamp()) + (30 * 24 * 60 * 60),
                    }
                )
            except Exception:
                pass

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(result),
        }
    except Exception as e:
        import traceback

        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"❌ Handler error: {error_msg}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": error_msg}),
        }

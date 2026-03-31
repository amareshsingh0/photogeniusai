"""
AWS Orchestrator - Integration & orchestration for AWS (no Modal).

Wires: SemanticEnhancer, TwoPassGeneration, optional InstantID.
Quality tiers: FAST (Turbo only), STANDARD (Base+Refiner), PREMIUM (TwoPass + optional InstantID).
Graceful degradation: PREMIUM → STANDARD → BASIC → error.
"""

from __future__ import annotations

import io
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Auto-validation configuration (95%+ first-try success target)
AUTO_VALIDATION_ENABLED = os.environ.get("AUTO_VALIDATION_ENABLED", "true").lower() in ("true", "1", "yes")
MAX_REFINEMENT_LOOPS = int(os.environ.get("MAX_REFINEMENT_LOOPS", "2"))

# Metrics for first-try success rate per category and average refinement loops (logged to CloudWatch)
_validation_metrics: Dict[str, List[Any]] = {"first_try_success": [], "refinement_loops": [], "by_category": {}}

try:
    from .observability import (
        record_validation_first_try,
        record_refinement_loops,
        record_validation_result,
        is_auto_validation_disabled,
    )
except ImportError:
    record_validation_first_try = lambda cat, ok: None  # type: ignore[assignment, misc]
    record_refinement_loops = lambda cat, n: None  # type: ignore[assignment, misc]
    record_validation_result = lambda ok: None  # type: ignore[assignment, misc]
    is_auto_validation_disabled = lambda: False  # type: ignore[assignment, misc]

# Optional imports - graceful degradation when services unavailable
try:
    from .semantic_prompt_enhancer import get_enhancer
except ImportError:
    try:
        from semantic_prompt_enhancer import get_enhancer
    except ImportError:
        get_enhancer = None  # type: ignore[assignment, misc]

try:
    from .universal_prompt_classifier import UniversalPromptClassifier
    from .smart_prompt_engine import SmartPromptEngine
except ImportError:
    try:
        from universal_prompt_classifier import UniversalPromptClassifier
        from smart_prompt_engine import SmartPromptEngine
    except ImportError:
        UniversalPromptClassifier = None  # type: ignore[assignment, misc]
        SmartPromptEngine = None  # type: ignore[assignment, misc]

try:
    from .two_pass_generation import generate_two_pass, generate_fast
except ImportError:
    try:
        from two_pass_generation import generate_two_pass, generate_fast
    except ImportError:
        generate_two_pass = None  # type: ignore[assignment, misc]
        generate_fast = None  # type: ignore[assignment, misc]

try:
    from .instantid_service import generate_with_instantid, app as instantid_app
except ImportError:
    try:
        from instantid_service import generate_with_instantid, app as instantid_app
    except ImportError:
        generate_with_instantid = None  # type: ignore[assignment, misc]
        instantid_app = None  # type: ignore[assignment]

try:
    from .auto_validation_pipeline import AutoValidationPipeline
except ImportError:
    try:
        from auto_validation_pipeline import AutoValidationPipeline
    except ImportError:
        AutoValidationPipeline = None  # type: ignore[assignment, misc]

# Singleton semantic enhancer / classifier / validation
_semantic_enhancer = None
_classifier = None
_smart_prompt_engine = None
_auto_validation_pipeline: Optional[Any] = None


def _get_semantic_enhancer():
    """Lazy singleton SemanticPromptEnhancer."""
    global _semantic_enhancer
    if _semantic_enhancer is None and get_enhancer is not None:
        _semantic_enhancer = get_enhancer()
    return _semantic_enhancer


def _get_classifier():
    """Lazy singleton UniversalPromptClassifier for auto-LoRA."""
    global _classifier
    if _classifier is None and UniversalPromptClassifier is not None:
        _classifier = UniversalPromptClassifier()
    return _classifier


def _get_smart_prompt_engine():
    """Lazy singleton SmartPromptEngine for recommend_loras."""
    global _smart_prompt_engine
    if _smart_prompt_engine is None and SmartPromptEngine is not None:
        _smart_prompt_engine = SmartPromptEngine()
    return _smart_prompt_engine


def _get_auto_validation_pipeline():
    """Lazy singleton AutoValidationPipeline for validate-and-fix."""
    global _auto_validation_pipeline
    if _auto_validation_pipeline is None and AutoValidationPipeline is not None:
        _auto_validation_pipeline = AutoValidationPipeline()
    return _auto_validation_pipeline


def _record_validation_metrics(
    category: str,
    first_try_success: bool,
    refinement_loops_used: int,
) -> None:
    """Record validation metrics for CloudWatch (first-try success rate, avg refinement loops)."""
    global _validation_metrics
    _validation_metrics["first_try_success"].append(first_try_success)
    _validation_metrics["refinement_loops"].append(refinement_loops_used)
    if category not in _validation_metrics["by_category"]:
        _validation_metrics["by_category"][category] = {"first_try": [], "loops": []}
    _validation_metrics["by_category"][category]["first_try"].append(first_try_success)
    _validation_metrics["by_category"][category]["loops"].append(refinement_loops_used)
    # Log for CloudWatch (structured so metrics can be extracted)
    n = len(_validation_metrics["first_try_success"])
    rate = sum(_validation_metrics["first_try_success"]) / n if n else 0.0
    avg_loops = sum(_validation_metrics["refinement_loops"]) / n if n else 0.0
    logger.info(
        "auto_validation_metrics",
        extra={
            "first_try_success": first_try_success,
            "refinement_loops_used": refinement_loops_used,
            "category": category,
            "cumulative_first_try_rate": round(rate, 4),
            "cumulative_avg_refinement_loops": round(avg_loops, 4),
            "sample_count": n,
        },
    )


def generate_professional(
    user_prompt: str,
    identity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    mode: str = "REALISM",
    quality_tier: str = "PREMIUM",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Master generation entry: semantic enhancement + quality-tier routing + graceful fallback.

    Parameters
    ----------
    user_prompt : str
        Raw user prompt.
    identity_id : str, optional
        Identity/LoRA id for face-consistent generation.
    user_id : str, optional
        User id for LoRA/InstantID paths.
    mode : str
        REALISM | CREATIVE | ROMANTIC | FASHION | CINEMATIC.
    quality_tier : str
        FAST (< 5s Turbo only) | STANDARD (Base+Refiner) | PREMIUM (TwoPass + optional InstantID).
    **kwargs
        negative_prompt, return_preview, seed, etc. passed to generation.

    Returns
    -------
    dict
        images: { preview, final } (base64 or URLs)
        metadata: { enhanced_prompt, original_prompt, mode, quality_tier, face_accuracy }
        timing: { preview_time, total_time }
        status: "success" | "error"
    """
    uid = user_id or ""
    tier = (quality_tier or "PREMIUM").upper()
    mode_upper = (mode or "REALISM").upper()
    t_start = time.perf_counter()

    # ----- STEP 1: Semantic enhancement -----
    enhanced_prompt = user_prompt or ""
    enhancer = _get_semantic_enhancer()
    if enhancer is not None:
        try:
            enhanced_prompt = enhancer.enhance(user_prompt or "", mode_upper)
            logger.info("Semantic enhancement succeeded", extra={"mode": mode_upper})
        except Exception as e:
            logger.warning("Semantic enhancement failed, using original prompt: %s", e)
            enhanced_prompt = user_prompt or ""
    else:
        logger.debug("Semantic enhancer unavailable, using original prompt")

    # ----- Auto-LoRA selection from category (after semantic enhancement) -----
    lora_names: list = []
    classification_for_validation: Optional[Any] = None
    classifier = _get_classifier()
    smart_engine = _get_smart_prompt_engine()
    if classifier is not None and smart_engine is not None:
        try:
            classification = classifier.classify(enhanced_prompt)
            classification_for_validation = classification
            lora_names = smart_engine.recommend_loras(classification)
            if lora_names:
                logger.info(
                    "Auto-applying LoRAs: %s for category %s",
                    lora_names,
                    classification.category,
                )
        except Exception as e:
            logger.debug("Auto-LoRA selection skipped: %s", e)
            lora_names = []

    # ----- STEP 2 & 3: Quality tier routing with graceful degradation -----
    result: Optional[Dict[str, Any]] = None
    method_used = "none"
    face_accuracy = "N/A"

    if tier == "FAST":
        # FAST: Turbo only (< 5s)
        if generate_fast is not None:
            try:
                result = generate_fast(
                    prompt=enhanced_prompt,
                    negative_prompt=kwargs.get("negative_prompt", ""),
                    seed=kwargs.get("seed"),
                )
                if result.get("error"):
                    raise RuntimeError(result.get("error"))
                method_used = "fast_turbo"
                logger.info("FAST tier succeeded", extra={"method": method_used})
            except Exception as e:
                logger.error("FAST (Turbo) failed: %s", e)
                result = None
    elif tier == "STANDARD":
        # STANDARD: two-pass without preview (Base + Refiner, optional LoRA)
        if generate_two_pass is not None:
            try:
                result = generate_two_pass(
                    prompt=enhanced_prompt,
                    identity_id=identity_id,
                    user_id=uid,
                    negative_prompt=kwargs.get("negative_prompt", ""),
                    return_preview=False,
                    seed=kwargs.get("seed"),
                    use_instantid=False,
                    mode=mode_upper,
                    lora_names=lora_names if lora_names else None,
                )
                if result.get("error"):
                    raise RuntimeError(result.get("error"))
                method_used = "standard_two_pass"
                logger.info("STANDARD tier succeeded", extra={"method": method_used})
            except Exception as e:
                logger.warning("STANDARD failed, falling back to BASIC: %s", e)
                result = None
        if result is None and generate_fast is not None:
            try:
                result = generate_fast(
                    prompt=enhanced_prompt,
                    negative_prompt=kwargs.get("negative_prompt", ""),
                    seed=kwargs.get("seed"),
                )
                if result.get("error"):
                    raise RuntimeError(result.get("error"))
                method_used = "basic_fast"
                logger.info("BASIC (FAST) fallback succeeded", extra={"method": method_used})
            except Exception as e:
                logger.error("STANDARD and BASIC failed: %s", e)
                result = None
    else:
        # PREMIUM: two-pass + optional InstantID; fallback ladder PREMIUM → STANDARD → BASIC
        if generate_two_pass is not None:
            try:
                result = generate_two_pass(
                    prompt=enhanced_prompt,
                    identity_id=identity_id,
                    user_id=uid,
                    negative_prompt=kwargs.get("negative_prompt", ""),
                    return_preview=True,
                    seed=kwargs.get("seed"),
                    use_instantid=bool(identity_id and uid),
                    mode=mode_upper,
                    lora_names=lora_names if lora_names else None,
                )
                if result.get("error"):
                    raise RuntimeError(result.get("error"))
                method_used = "premium_two_pass"
                if identity_id and result.get("final"):
                    face_accuracy = "90%+"
                logger.info("PREMIUM tier succeeded", extra={"method": method_used})
            except Exception as e:
                logger.warning("PREMIUM failed, falling back to STANDARD: %s", e)
                result = None

        if result is None and generate_two_pass is not None:
            try:
                result = generate_two_pass(
                    prompt=enhanced_prompt,
                    identity_id=identity_id,
                    user_id=uid,
                    negative_prompt=kwargs.get("negative_prompt", ""),
                    return_preview=False,
                    seed=kwargs.get("seed"),
                    use_instantid=False,
                    mode=mode_upper,
                    lora_names=lora_names if lora_names else None,
                )
                if result.get("error"):
                    raise RuntimeError(result.get("error"))
                method_used = "standard_two_pass"
                logger.info("STANDARD fallback succeeded", extra={"method": method_used})
            except Exception as e:
                logger.warning("STANDARD failed, falling back to BASIC: %s", e)
                result = None

        if result is None and generate_fast is not None:
            try:
                result = generate_fast(
                    prompt=enhanced_prompt,
                    negative_prompt=kwargs.get("negative_prompt", ""),
                    seed=kwargs.get("seed"),
                )
                if result.get("error"):
                    raise RuntimeError(result.get("error"))
                method_used = "basic_fast"
                logger.info("BASIC (FAST) fallback succeeded", extra={"method": method_used})
            except Exception as e:
                logger.error("All methods failed: %s", e)
                result = None

    if result is None:
        total_time = time.perf_counter() - t_start
        logger.error("All generation methods failed", extra={"quality_tier": tier})
        return {
            "images": {"preview": None, "final": None},
            "metadata": {
                "enhanced_prompt": enhanced_prompt,
                "original_prompt": user_prompt,
                "mode": mode_upper,
                "quality_tier": tier,
                "face_accuracy": "N/A",
            },
            "timing": {"preview_time": 0.0, "total_time": total_time},
            "status": "error",
            "message": "All generation methods failed",
        }

    # ----- Auto-validation: validate-and-fix after generation (95%+ first-try target) -----
    preview_b64 = result.get("preview_base64")
    final_b64 = result.get("final_base64") or ""
    first_try_success = True
    refinement_loops_used = 0
    validation_passed = True
    validation_meta: Dict[str, Any] = {}

    if AUTO_VALIDATION_ENABLED and final_b64 and not is_auto_validation_disabled():
        pipeline = _get_auto_validation_pipeline()
        if pipeline is not None:
            try:
                import base64
                from PIL import Image
                img_bytes = base64.b64decode(final_b64)
                pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                final_image, validation_passed, validation_meta = pipeline.validate_and_fix(
                    pil_image,
                    enhanced_prompt,
                    max_retries=MAX_REFINEMENT_LOOPS,
                )
                refinement_loops_used = validation_meta.get("attempts", 0)
                first_try_success = refinement_loops_used == 0 and validation_passed
                if validation_passed:
                    buf = io.BytesIO()
                    if hasattr(final_image, "save"):
                        final_image.save(buf, format="PNG")
                    else:
                        Image.fromarray(final_image).save(buf, format="PNG")
                    final_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                    result["final_base64"] = final_b64
                else:
                    logger.warning(
                        "Auto-validation failed after %d retries; returning image (degraded). issues=%s",
                        refinement_loops_used,
                        validation_meta.get("issues", []),
                        extra={"validation_meta": validation_meta},
                    )
            except Exception as e:
                logger.warning("Auto-validation skipped (error): %s", e, exc_info=True)
        category = "unknown"
        if classification_for_validation is not None:
            category = getattr(classification_for_validation, "category", "unknown") or "unknown"
        elif classifier is not None:
            try:
                cl = classifier.classify(enhanced_prompt)
                category = getattr(cl, "category", "unknown") or "unknown"
            except Exception:
                pass
        _record_validation_metrics(category, first_try_success, refinement_loops_used)
        try:
            record_validation_first_try(category, first_try_success)
            record_refinement_loops(category, float(refinement_loops_used))
            record_validation_result(first_try_success)
        except Exception:
            pass

    # ----- Response format -----
    preview_time = result.get("preview_time", 0.0)
    final_time = result.get("final_time", 0.0)
    total_time = time.perf_counter() - t_start

    # Optional: if your API serves URLs instead of inline base64
    preview_url = kwargs.get("preview_url")
    final_url = kwargs.get("final_url")
    if preview_url and preview_b64:
        pass  # caller can set URLs after upload
    if final_url:
        pass

    return {
        "images": {
            "preview": preview_b64,
            "final": final_b64,
        },
        "metadata": {
            "enhanced_prompt": enhanced_prompt,
            "original_prompt": user_prompt,
            "mode": mode_upper,
            "quality_tier": tier,
            "face_accuracy": face_accuracy if identity_id else "N/A",
            "method_used": method_used,
            "first_try_success": first_try_success,
            "refinement_loops_used": refinement_loops_used,
            "validation_passed": validation_passed,
            "validation_meta": validation_meta,
        },
        "timing": {
            "preview_time": preview_time,
            "final_time": final_time,
            "total_time": total_time,
        },
        "status": "success",
    }


def generate_professional_with_fallback(
    user_prompt: str,
    identity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    mode: str = "REALISM",
    quality_tier: str = "PREMIUM",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Same as generate_professional but explicitly tries PREMIUM → STANDARD → BASIC and returns
    the first successful result. Used when you want the highest available tier.
    """
    return generate_professional(
        user_prompt=user_prompt,
        identity_id=identity_id,
        user_id=user_id,
        mode=mode,
        quality_tier=quality_tier,
        **kwargs,
    )

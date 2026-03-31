"""
API v2 – Unified prompt enhancement.

Single endpoint /enhance: style classify → multi-variant → model optimizer.
Feedback /feedback, analytics /analytics, health /health, models /models.
Requires ai-pipeline on PYTHONPATH.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v2-enhancement"])

_repo_root = Path(__file__).resolve().parents[6]
_ai_pipeline = _repo_root / "ai-pipeline"
if _ai_pipeline.exists() and str(_ai_pipeline) not in sys.path:
    sys.path.insert(0, str(_ai_pipeline))

# Lazy-loaded services
_variant_generator = None
_model_optimizer = None
_preference_analyzer = None
_improvement_engine = None


def _get_services():
    """Load ai-pipeline services (singleton)."""
    global _variant_generator, _model_optimizer, _preference_analyzer, _improvement_engine
    if _variant_generator is not None:
        return _variant_generator, _model_optimizer, _preference_analyzer, _improvement_engine
    try:
        from services.user_preference_analyzer import get_default_preference_analyzer
        from services.self_improvement_engine import get_default_self_improvement_engine
        from services.multi_variant_generator import MultiVariantGenerator
        from services.model_optimizer import ModelOptimizer, AIModel

        _preference_analyzer = get_default_preference_analyzer()
        _improvement_engine = get_default_self_improvement_engine()
        _improvement_engine.preference_analyzer = _preference_analyzer
        _variant_generator = MultiVariantGenerator(preference_analyzer=_preference_analyzer)
        _model_optimizer = ModelOptimizer()
        return _variant_generator, _model_optimizer, _preference_analyzer, _improvement_engine
    except Exception as e:
        logger.warning("API v2 services not available: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Enhancement service unavailable: {e}. Ensure ai-pipeline is on PYTHONPATH.",
        )


# ==================== Request/Response ====================


class EnhanceRequest(BaseModel):
    """Request to enhance prompt and get all variants."""

    prompt: str = Field(..., description="Original user prompt", min_length=1, max_length=2000)
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    include_personalized: bool = Field(True, description="Include personalized variant")
    target_models: Optional[List[str]] = Field(
        None,
        description="Target models (midjourney_v7, flux, dalle3, stable_diffusion)",
        example=["midjourney_v7", "flux", "dalle3", "stable_diffusion"],
    )


class VariantResponse(BaseModel):
    """Single variant with model-optimized prompts."""

    variant_type: str
    variant_index: int
    enhanced_prompt: str
    negative_prompt: Optional[str] = None
    detail_score: float
    cinematic_fit: float
    surprise_factor: float
    wow_factor: float
    overall_score: float
    is_recommended: bool = False
    is_personalized: bool = False
    model_prompts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    remix_suggestions: List[str] = Field(default_factory=list)


class EnhanceResponse(BaseModel):
    """Response with all variants and metadata."""

    request_id: str
    original_prompt: str
    variants: List[VariantResponse]
    recommended_index: int
    personalized_index: Optional[int] = None
    detected_style: str
    detected_surprise: str
    detected_lighting: str
    detected_emotion: str
    processing_time_ms: float
    timestamp: str


class FeedbackRequest(BaseModel):
    """Feedback submission for learning."""

    request_id: str = Field(..., description="Request ID from enhance response")
    user_id: str = Field(..., description="User ID")
    variant_selected: int = Field(..., ge=0, le=5, description="Variant index chosen")
    action_type: str = Field(
        ...,
        description="select, download, share, rate, regenerate",
        min_length=1,
        max_length=50,
    )
    rating: Optional[int] = Field(None, ge=1, le=5)
    model_used: Optional[str] = None
    original_prompt: Optional[str] = Field(None, description="Original prompt (for learning)")
    variant_type: Optional[str] = Field(None, description="Variant type chosen (e.g. cinematic)")
    enhanced_prompt: Optional[str] = Field(None, description="Enhanced prompt of chosen variant")


class AnalyticsResponse(BaseModel):
    """Analytics and insights."""

    total_requests: int
    total_feedback: int
    variant_performance: Dict[str, Dict[str, Any]]
    failure_patterns: List[Dict[str, Any]]
    improvement_suggestions: List[Dict[str, Any]]
    active_ab_tests: List[Dict[str, Any]]


# ==================== Endpoints ====================


@router.post(
    "/enhance",
    response_model=EnhanceResponse,
    summary="Enhance prompt and get all variants",
    description="Runs full pipeline: style classify → 6 variants → model-optimized prompts for MJ/Flux/DALL-E/SD.",
)
def enhance_prompt(request: EnhanceRequest) -> EnhanceResponse:
    """Single endpoint: enhance prompt and return all 6 variants with model-specific copy-ready prompts."""
    t0 = time.perf_counter()
    request_id = f"req_{uuid.uuid4().hex[:16]}"

    try:
        gen, optimizer, _, _ = _get_services()
    except HTTPException:
        raise

    try:
        from services.model_optimizer import AIModel
    except ImportError:
        raise HTTPException(status_code=503, detail="model_optimizer not available")

    target_models = request.target_models or [
        "midjourney_v7",
        "flux",
        "dalle3",
        "stable_diffusion",
    ]

    result = gen.generate_variants(
        prompt=request.prompt,
        user_id=request.user_id,
        include_personalized=request.include_personalized,
    )

    variant_responses: List[VariantResponse] = []
    for i, variant in enumerate(result.variants):
        model_prompts: Dict[str, Dict[str, Any]] = {}
        for model_name in target_models:
            try:
                model_enum = AIModel(model_name)
            except ValueError:
                logger.warning("Unknown model: %s", model_name)
                continue
            optimized = optimizer.optimize_for_model(
                prompt=variant.enhanced_prompt,
                negative_prompt=variant.negative_prompt,
                model=model_enum,
                model_params=variant.model_params if model_enum.value == "midjourney_v7" else None,
            )
            model_prompts[model_name] = {
                "prompt": optimized.optimized_prompt,
                "negative": optimized.negative_prompt,
                "parameters": optimized.parameters,
                "copy_ready": optimized.copy_ready or optimized.optimized_prompt,
            }
        variant_responses.append(
            VariantResponse(
                variant_type=variant.variant_type.value,
                variant_index=i,
                enhanced_prompt=variant.enhanced_prompt,
                negative_prompt=variant.negative_prompt,
                detail_score=variant.scores.detail_score,
                cinematic_fit=variant.scores.cinematic_fit,
                surprise_factor=variant.scores.surprise_factor,
                wow_factor=variant.scores.wow_factor,
                overall_score=round(variant.scores.overall_score(), 2),
                is_recommended=variant.is_recommended,
                is_personalized=variant.is_personalized,
                model_prompts=model_prompts,
                remix_suggestions=variant.remix_suggestions or [],
            )
        )

    processing_time_ms = (time.perf_counter() - t0) * 1000
    now = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Enhancement complete",
        request_id=request_id,
        variants_count=len(variant_responses),
        processing_time_ms=round(processing_time_ms, 2),
    )

    return EnhanceResponse(
        request_id=request_id,
        original_prompt=request.prompt,
        variants=variant_responses,
        recommended_index=result.recommended_index,
        personalized_index=result.personalized_index,
        detected_style=result.detected_style.value,
        detected_surprise=result.detected_surprise.value,
        detected_lighting=result.detected_lighting.value,
        detected_emotion=result.detected_emotion.value,
        processing_time_ms=round(processing_time_ms, 2),
        timestamp=now,
    )


@router.post(
    "/feedback",
    summary="Submit feedback for learning",
    description="Track variant selection/rating. Send original_prompt, variant_type, enhanced_prompt from enhance response for best learning.",
)
def submit_feedback(feedback: FeedbackRequest) -> Dict[str, str]:
    """Record user feedback for self-improvement."""
    try:
        _, _, _, engine = _get_services()
    except HTTPException:
        raise

    original_prompt = feedback.original_prompt or "[unknown]"
    variant_type = feedback.variant_type or "unknown"
    enhanced_prompt = feedback.enhanced_prompt or original_prompt

    engine.collect_feedback(
        user_id=feedback.user_id,
        original_prompt=original_prompt,
        variant_selected=feedback.variant_selected,
        variant_type=variant_type,
        enhanced_prompt=enhanced_prompt,
        action_type=feedback.action_type,
        rating=feedback.rating,
        context={"model_used": feedback.model_used} if feedback.model_used else None,
    )

    logger.info(
        "Feedback submitted",
        request_id=feedback.request_id,
        user_id=feedback.user_id,
        variant=feedback.variant_selected,
        action=feedback.action_type,
    )
    return {"status": "success", "message": "Feedback recorded"}


@router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    summary="Get analytics and insights (admin)",
    description="Variant performance, failure patterns, improvement suggestions, active A/B tests.",
)
def get_analytics() -> AnalyticsResponse:
    """Return system analytics from self-improvement engine."""
    try:
        _, _, _, engine = _get_services()
    except HTTPException:
        raise

    pattern_analysis = engine.analyze_success_patterns()
    failures = engine.detect_failure_patterns()
    suggestions = engine.generate_improvement_suggestions()
    active_tests = [
        {
            "test_id": test_id,
            "name": test["name"],
            "variant_a": test["variant_a"],
            "variant_b": test["variant_b"],
            "traffic_split": test["traffic_split"],
        }
        for test_id, test in engine.active_tests.items()
    ]
    suggestion_dicts = [
        {
            "category": s.category,
            "current": s.current_approach,
            "suggested": s.suggested_approach,
            "reason": s.reason,
            "confidence": s.confidence,
        }
        for s in suggestions
    ]

    return AnalyticsResponse(
        total_requests=len(engine.feedback_history),
        total_feedback=len(engine.feedback_history),
        variant_performance=pattern_analysis,
        failure_patterns=failures,
        improvement_suggestions=suggestion_dicts,
        active_ab_tests=active_tests,
    )


@router.get(
    "/health",
    summary="Health check (v2)",
)
def health_v2() -> Dict[str, Any]:
    """Health check for v2 enhancement service."""
    try:
        _get_services()
        services_ok = True
    except Exception:
        services_ok = False
    return {
        "status": "healthy" if services_ok else "degraded",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": "ok" if services_ok else "ai-pipeline unavailable",
    }


@router.get(
    "/models",
    summary="List supported AI models",
)
def list_models() -> Dict[str, Any]:
    """List supported models and capabilities."""
    try:
        from services.model_optimizer import AIModel
    except ImportError:
        raise HTTPException(status_code=503, detail="model_optimizer not available")
    return {
        "models": [
            {
                "id": m.value,
                "name": m.value.replace("_", " ").title(),
                "supports_parameters": m.value == "midjourney_v7",
                "supports_negatives": m.value in ("midjourney_v7", "stable_diffusion"),
            }
            for m in AIModel
        ]
    }

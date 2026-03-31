"""
Variants API: POST /variants – generate 6 styled variants from a single prompt.

Uses MultiVariantGenerator + optional ModelOptimizer for copy-ready MJ/Flux/DALL-E/SD.
Requires ai-pipeline on PYTHONPATH for services.multi_variant_generator and model_optimizer.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

_repo_root = Path(__file__).resolve().parents[6]
_ai_pipeline = _repo_root / "ai-pipeline"
if _ai_pipeline.exists() and str(_ai_pipeline) not in sys.path:
    sys.path.insert(0, str(_ai_pipeline))

_multi_variant_generator = None
_model_optimizer = None


def _get_multi_variant_generator():
    global _multi_variant_generator
    if _multi_variant_generator is not None:
        return _multi_variant_generator
    try:
        from services.multi_variant_generator import MultiVariantGenerator
        from services.user_preference_analyzer import get_default_preference_analyzer
        _multi_variant_generator = MultiVariantGenerator(
            preference_analyzer=get_default_preference_analyzer(),
        )
        return _multi_variant_generator
    except Exception as e:
        logger.warning("MultiVariantGenerator not available: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Variants service unavailable: {e}. Ensure ai-pipeline is on PYTHONPATH.",
        )


def _get_model_optimizer():
    global _model_optimizer
    if _model_optimizer is not None:
        return _model_optimizer
    try:
        from services.model_optimizer import ModelOptimizer
        _model_optimizer = ModelOptimizer()
        return _model_optimizer
    except Exception as e:
        logger.warning("ModelOptimizer not available: %s", e)
        return None


# ==================== Request/Response ====================


class VariantsRequest(BaseModel):
    """Request to generate 6 variants."""

    prompt: str = Field(
        ...,
        description="User prompt",
        min_length=1,
        max_length=1000,
        example="young woman in enchanted forest",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for personalized variant (6th variant)",
    )
    include_personalized: bool = Field(
        default=True,
        description="Include personalized variant when user_id provided",
    )
    include_model_optimized: bool = Field(
        default=True,
        description="Include copy-ready prompts for MJ/Flux/DALL-E/SD per variant",
    )


class VariantScoreOut(BaseModel):
    detail_score: float
    cinematic_fit: float
    surprise_factor: float
    wow_factor: float
    overall_score: float


class VariantOut(BaseModel):
    variant_type: str
    enhanced_prompt: str
    negative_prompt: str
    model_params: Dict[str, Any]
    scores: VariantScoreOut
    is_recommended: bool = False
    is_personalized: bool = False
    remix_suggestions: List[str] = Field(default_factory=list)
    escalate_options: Dict[str, str] = Field(default_factory=dict)
    model_optimized: Optional[Dict[str, Any]] = None


class VariantsResponse(BaseModel):
    """Response with 6 variants and optional model-optimized copy-ready prompts."""

    original_prompt: str
    variants: List[VariantOut]
    recommended_index: int
    personalized_index: Optional[int] = None
    detected_style: str
    detected_surprise: str
    detected_lighting: str
    detected_emotion: str


@router.post(
    "/",
    response_model=VariantsResponse,
    summary="Generate 6 styled variants",
    description="Generate Realistic, Cinematic (recommended), Cool/Edgy, Artistic, Max Surprise, and optionally Personalized variants with scores and model-optimized copy-ready prompts.",
)
def generate_variants(req: VariantsRequest) -> VariantsResponse:
    """Generate 6 variants from a single prompt; optionally include model-optimized copy-ready text."""
    gen = _get_multi_variant_generator()
    result = gen.generate_variants(
        prompt=req.prompt,
        user_id=req.user_id,
        include_personalized=req.include_personalized,
    )

    optimizer = _get_model_optimizer() if req.include_model_optimized else None
    variant_outs: List[VariantOut] = []

    for v in result.variants:
        scores_out = VariantScoreOut(
            detail_score=v.scores.detail_score,
            cinematic_fit=v.scores.cinematic_fit,
            surprise_factor=v.scores.surprise_factor,
            wow_factor=v.scores.wow_factor,
            overall_score=round(v.scores.overall_score(), 2),
        )
        model_optimized: Optional[Dict[str, Any]] = None
        if optimizer is not None:
            try:
                from services.model_optimizer import AIModel
                optimized = optimizer.optimize_for_model(
                    prompt=v.enhanced_prompt,
                    negative_prompt=v.negative_prompt,
                    model=AIModel.MIDJOURNEY_V7,
                    model_params=v.model_params,
                )
                model_optimized = {
                    "midjourney_v7": optimized.copy_ready or optimized.optimized_prompt,
                }
                for aimodel in (AIModel.FLUX, AIModel.DALLE3, AIModel.STABLE_DIFFUSION):
                    o = optimizer.optimize_for_model(
                        v.enhanced_prompt,
                        v.negative_prompt,
                        aimodel,
                        None,
                    )
                    key = aimodel.value
                    if aimodel == AIModel.STABLE_DIFFUSION and o.negative_prompt:
                        model_optimized[key] = {
                            "prompt": o.copy_ready or o.optimized_prompt,
                            "negative_prompt": o.negative_prompt,
                        }
                    else:
                        model_optimized[key] = o.copy_ready or o.optimized_prompt
            except Exception as e:
                logger.debug("Model optimizer per variant skipped: %s", e)

        variant_outs.append(
            VariantOut(
                variant_type=v.variant_type.value,
                enhanced_prompt=v.enhanced_prompt,
                negative_prompt=v.negative_prompt,
                model_params=v.model_params,
                scores=scores_out,
                is_recommended=v.is_recommended,
                is_personalized=v.is_personalized,
                remix_suggestions=v.remix_suggestions,
                escalate_options=v.escalate_options,
                model_optimized=model_optimized,
            )
        )

    return VariantsResponse(
        original_prompt=result.original_prompt,
        variants=variant_outs,
        recommended_index=result.recommended_index,
        personalized_index=result.personalized_index,
        detected_style=result.detected_style.value,
        detected_surprise=result.detected_surprise.value,
        detected_lighting=result.detected_lighting.value,
        detected_emotion=result.detected_emotion.value,
    )

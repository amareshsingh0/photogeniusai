"""
Learning Engine API Endpoints

Endpoints:
- POST /api/v1/learning/log - Log generation with feedback
- GET /api/v1/learning/recommend - Get learned recommendations
- GET /api/v1/learning/analytics - Get analytics dashboard data
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.smart.learning_engine import (
    log_generation_async,
    get_recommendation_async,
    get_analytics_async,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])


# ══════════════════════════════════════════════════════════════════════════════
# Request/Response Models
# ══════════════════════════════════════════════════════════════════════════════

class LogGenerationRequest(BaseModel):
    """Request to log a generation cycle."""
    brief: Dict = Field(..., description="Full design brief from design_agent_chain")
    quality_result: Dict = Field(..., description="Quality Critic output")
    generation_time_ms: int = Field(..., description="Total generation time in milliseconds")
    cost_usd: float = Field(default=0.0, description="API cost in USD")
    user_feedback: Optional[str] = Field(
        default=None,
        description="User feedback: thumbs_up | thumbs_down | neutral"
    )


class RecommendationRequest(BaseModel):
    """Request for learned recommendations."""
    bucket: str = Field(..., description="Industry/category (tech, fashion, food, etc.)")
    platform: str = Field(..., description="Platform (instagram, tiktok, linkedin, etc.)")
    aesthetic: Optional[str] = Field(
        default=None,
        description="Aesthetic code (ai_native, quiet_luxury_loud, etc.)"
    )


class AnalyticsRequest(BaseModel):
    """Request for analytics data."""
    days: int = Field(default=30, ge=1, le=365, description="Number of days to analyze")


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/log")
async def log_generation(req: LogGenerationRequest):
    """
    Log a generation cycle with quality scores and optional user feedback.

    This endpoint is called AFTER generation completes to store:
    - Input context (prompt, bucket, platform, aesthetic)
    - Agent decisions (creative concept, layout variant, model used)
    - Quality metrics (12 dimensions, Beast gates, overall score)
    - Performance (time, cost, revision cycles)
    - User feedback (thumbs up/down if available)

    Returns:
        {"success": true, "message": "Logged successfully"}
    """
    try:
        success = await log_generation_async(
            brief=req.brief,
            quality_result=req.quality_result,
            generation_time_ms=req.generation_time_ms,
            cost_usd=req.cost_usd,
            user_feedback=req.user_feedback,
        )

        if success:
            return {
                "success": True,
                "message": "Generation logged successfully",
            }
        else:
            return {
                "success": False,
                "message": "Learning engine disabled or failed to log",
            }

    except Exception as e:
        logger.exception(f"[learning/log] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend")
async def get_recommendation(req: RecommendationRequest):
    """
    Get learned recommendations for a specific context.

    Based on historical data, returns:
    - Recommended aesthetic code (if not provided)
    - Preferred model (highest avg quality for this context)
    - Preferred layout variant (safe/bold/disruptive)
    - Expected quality score
    - Confidence level (based on sample count)

    Example response:
    {
        "aesthetic_recommendation": "ai_native",
        "confidence": 0.87,
        "rationale": "Tech + Instagram: ai_native has 9.2 avg quality (2.3k samples)",
        "model_preference": "flux_2_pro",
        "expected_quality": 8.9,
        "layout_variant_preference": "bold",
        "sample_count": 2300
    }
    """
    try:
        recommendation = await get_recommendation_async(
            bucket=req.bucket,
            platform=req.platform,
            aesthetic=req.aesthetic,
        )

        return recommendation

    except Exception as e:
        logger.exception(f"[learning/recommend] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def get_analytics(days: int = 30):
    """
    Get learning analytics for the past N days.

    Returns comprehensive statistics:
    - Total generations
    - Average quality score
    - Beast gates pass rate
    - Top aesthetics (by count and avg quality)
    - Top models (by count and avg quality)
    - Layout variant distribution
    - Quality trend (improving/stable/declining)

    Example response:
    {
        "total_generations": 15420,
        "avg_quality_score": 8.3,
        "avg_beast_gates_passed": 8.7,
        "beast_gates_pass_rate": 0.87,
        "top_aesthetics": [
            {"code": "ai_native", "count": 3200, "avg_quality": 8.9},
            {"code": "quiet_luxury_loud", "count": 2800, "avg_quality": 8.7}
        ],
        "top_models": [
            {"model": "flux_2_pro", "count": 7200, "avg_quality": 8.8}
        ],
        "layout_variant_distribution": {
            "safe": 8200,
            "bold": 5100,
            "disruptive": 2120
        },
        "quality_trend": "improving"
    }
    """
    try:
        analytics = await get_analytics_async(days=days)
        return analytics

    except Exception as e:
        logger.exception(f"[learning/analytics] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

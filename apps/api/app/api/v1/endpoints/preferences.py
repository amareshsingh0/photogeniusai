"""
Preferences API: POST /preferences/track – track variant selection for personalization.

Uses UserPreferenceAnalyzer to learn from user selections/ratings.
Requires ai-pipeline on PYTHONPATH for services.user_preference_analyzer.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import CurrentUserId, DbSession
from app.core.security import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()

_repo_root = Path(__file__).resolve().parents[6]
_ai_pipeline = _repo_root / "ai-pipeline"
if _ai_pipeline.exists() and str(_ai_pipeline) not in sys.path:
    sys.path.insert(0, str(_ai_pipeline))

_preference_analyzer = None
_self_improvement_engine = None


def _get_preference_analyzer():
    global _preference_analyzer
    if _preference_analyzer is not None:
        return _preference_analyzer
    try:
        from services.user_preference_analyzer import get_default_preference_analyzer
        _preference_analyzer = get_default_preference_analyzer()
        return _preference_analyzer
    except Exception as e:
        logger.warning("UserPreferenceAnalyzer not available: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Preferences service unavailable: {e}. Ensure ai-pipeline is on PYTHONPATH.",
        )


# ==================== Request/Response ====================


class TrackRequest(BaseModel):
    """Request to track a variant selection/rating."""

    user_id: str = Field(
        ...,
        description="User ID (e.g. Clerk user_xxx or DB user UUID)",
        min_length=1,
        max_length=255,
    )
    action_type: str = Field(
        ...,
        description="Action: select, rate, regenerate, download, share",
        min_length=1,
        max_length=50,
        example="select",
    )
    prompt: str = Field(
        ...,
        description="Original prompt that was used",
        min_length=1,
        max_length=2000,
    )
    variant_index: int = Field(
        ...,
        description="Which variant was chosen (0-5)",
        ge=0,
        le=5,
    )
    variant_style: str = Field(
        ...,
        description="Style of chosen variant (e.g. cinematic, cool_edgy)",
        min_length=1,
        max_length=50,
        example="cinematic",
    )
    rating: Optional[int] = Field(
        default=None,
        description="Optional 1-5 star rating",
        ge=1,
        le=5,
    )
    style_analysis: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional: visual_style, surprise_level, lighting, emotion (string values)",
    )
    enhanced_prompt: Optional[str] = Field(
        default=None,
        description="Enhanced prompt of chosen variant (for self-improvement)",
        max_length=5000,
    )


class TrackResponse(BaseModel):
    """Response after tracking."""

    success: bool = True
    message: str = "Interaction tracked"


@router.post(
    "/track",
    response_model=TrackResponse,
    summary="Track variant selection",
    description="Record user selection/rating for personalization. Call when user picks a variant or rates an image.",
)
def track_preference(req: TrackRequest) -> TrackResponse:
    """Track user interaction (variant selection, rating, download, share)."""
    analyzer = _get_preference_analyzer()
    style_analysis = req.style_analysis
    analyzer.track_interaction(
        user_id=req.user_id,
        action_type=req.action_type,
        prompt=req.prompt,
        variant_index=req.variant_index,
        variant_style=req.variant_style,
        rating=req.rating,
        style_analysis=style_analysis,
    )
    engine = _get_self_improvement_engine()
    if engine is not None:
        try:
            context = {}
            if style_analysis:
                context["detected_style"] = style_analysis.get("visual_style")
                context["detected_surprise"] = style_analysis.get("surprise_level")
            engine.collect_feedback(
                user_id=req.user_id,
                original_prompt=req.prompt,
                variant_selected=req.variant_index,
                variant_type=req.variant_style,
                enhanced_prompt=req.enhanced_prompt or req.prompt,
                action_type=req.action_type,
                rating=req.rating,
                context=context,
            )
        except Exception as e:
            logger.debug("Self-improvement collect_feedback skipped: %s", e)
    return TrackResponse(success=True, message="Interaction tracked")


# ==================== Style DNA Feedback ====================

class FeedbackRequest(BaseModel):
    generation_id: str = Field(..., description="Generation UUID to rate")
    liked: bool = Field(..., description="True = thumbs up, False = thumbs down")
    style: str = Field(default="Auto", description="Style used for this generation")
    bucket: str = Field(default="photorealism", description="Capability bucket used")
    tier: str = Field(default="balanced", description="Quality tier used")


class FeedbackResponse(BaseModel):
    success: bool = True
    message: str = "Feedback saved"
    style_dna: dict = {}


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Thumbs up/down feedback",
    description="Record like/dislike on a generated image. Updates userRating and Style DNA.",
)
async def record_feedback(
    req: FeedbackRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> FeedbackResponse:
    """Save thumbs up/down → Generation.userRating + User.preferences.style_dna."""
    require_auth(user_id)

    rating = 5 if req.liked else 1

    # 1. Update Generation.userRating
    try:
        await db.generation.update_many(
            where={"id": req.generation_id, "userId": user_id},
            data={"userRating": rating},
        )
    except Exception as e:
        logger.warning("Failed to update userRating: %s", e)

    # 2. Read current User.preferences, update style_dna
    try:
        user = await db.user.find_first(where={"id": user_id})
        prefs: dict = (user.preferences or {}) if user else {}
        dna: dict = prefs.get("style_dna", {
            "styles": {}, "buckets": {}, "tiers": {},
            "liked": 0, "disliked": 0,
        })

        weight = 1 if req.liked else -1

        # styles
        dna["styles"][req.style] = dna["styles"].get(req.style, 0) + weight
        # buckets
        dna["buckets"][req.bucket] = dna["buckets"].get(req.bucket, 0) + weight
        # tiers
        dna["tiers"][req.tier] = dna["tiers"].get(req.tier, 0) + (1 if req.liked else 0)
        # counters
        if req.liked:
            dna["liked"] = dna.get("liked", 0) + 1
        else:
            dna["disliked"] = dna.get("disliked", 0) + 1
        dna["last_updated"] = datetime.now(timezone.utc).isoformat()

        prefs["style_dna"] = dna
        await db.user.update(
            where={"id": user_id},
            data={"preferences": prefs},
        )
        return FeedbackResponse(success=True, message="Feedback saved", style_dna=dna)

    except Exception as e:
        logger.warning("Failed to update style_dna: %s", e)
        return FeedbackResponse(success=True, message="Rating saved, DNA update skipped")


# ==================== Brand Kit ====================

class BrandKitRequest(BaseModel):
    primary_color:   str  = Field(default="#6366F1", description="Primary brand hex color")
    secondary_color: str  = Field(default="#8B5CF6", description="Secondary brand hex color")
    accent_color:    str  = Field(default="#F59E0B", description="CTA/accent hex color")
    bg_color:        str  = Field(default="#0A0A1A", description="Preferred background hex color")
    font_style:      str  = Field(default="modern_sans", description="Font style key")
    brand_tone:      str  = Field(default="professional", description="Brand voice tone")
    brand_name:      str  = Field(default="", description="Brand / company name")
    logo_url:        str  = Field(default="", description="Logo image URL")
    industry:        str  = Field(default="", description="Industry category")


class BrandKitResponse(BaseModel):
    success:   bool = True
    brand_kit: dict = {}


@router.get(
    "/brand-kit",
    response_model=BrandKitResponse,
    summary="Get brand kit",
)
async def get_brand_kit(user_id: CurrentUserId, db: DbSession) -> BrandKitResponse:
    """Return the user's saved brand kit from User.preferences.brand_kit."""
    require_auth(user_id)
    try:
        user = await db.user.find_first(where={"id": user_id})
        prefs: dict = (user.preferences or {}) if user else {}
        return BrandKitResponse(success=True, brand_kit=prefs.get("brand_kit", {}))
    except Exception as e:
        logger.warning("get_brand_kit error: %s", e)
        return BrandKitResponse(success=True, brand_kit={})


@router.post(
    "/brand-kit",
    response_model=BrandKitResponse,
    summary="Save brand kit",
)
async def save_brand_kit(
    req: BrandKitRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> BrandKitResponse:
    """Persist brand kit to User.preferences.brand_kit."""
    require_auth(user_id)
    try:
        user = await db.user.find_first(where={"id": user_id})
        prefs: dict = (user.preferences or {}) if user else {}
        prefs["brand_kit"] = req.model_dump()
        await db.user.update(where={"id": user_id}, data={"preferences": prefs})
        return BrandKitResponse(success=True, brand_kit=req.model_dump())
    except Exception as e:
        logger.error("save_brand_kit error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Prompt DNA extraction ─────────────────────────────────────────────────────

class DnaExtractRequest(BaseModel):
    prompt:           str  = Field(..., description="Original or enhanced prompt")
    bucket:           str  = Field(default="photorealism", description="Capability bucket")
    liked:            bool = Field(..., description="True = thumbs up, False = thumbs down")
    enhanced_prompt:  str  = Field(default="", description="Full Flux/Ideogram prompt used")
    user_id:          str  = Field(default="", description="DB user ID (passed from Next.js layer)")


@router.post(
    "/extract-prompt-dna",
    summary="Extract Prompt DNA keywords from a prompt using Gemini",
)
async def extract_prompt_dna(
    req: DnaExtractRequest,
    db: DbSession,
) -> dict:
    # Accept user_id from body (internal call from Next.js thumbs route)
    user_id = req.user_id.strip() if req.user_id else None
    """
    Phase 4 / Reflexion: use Gemini to extract winning/failing style keywords
    from the prompt, then accumulate them in User.preferences.prompt_dna[bucket].

    After run_count >= 5, the design_agent_chain uses these keywords as a
    self-improving memory prefix in the image prompter.
    """
    if not user_id:
        return {"success": False, "error": "user_id required"}

    import os, json as _json
    from datetime import date

    # ── Gemini extraction ──────────────────────────────────────────────────────
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY", "")
    keywords: list = []
    patterns: list = []

    if gemini_key:
        try:
            from google import genai
            from google.genai import types as gtypes

            source = req.enhanced_prompt.strip() or req.prompt.strip()
            action = "liked" if req.liked else "disliked"
            system = (
                "You are a prompt analyst. Extract the key style/visual descriptors "
                f"from this image prompt that the user {action}.\n"
                "Return ONLY valid JSON:\n"
                '{"keywords":["3-7 short descriptors that define the visual style"],'
                '"patterns":["1-3 phrases that describe what works or fails"]}'
            )
            client = genai.Client(api_key=gemini_key)
            resp = await client.aio.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[{"role": "user", "parts": [{"text": source[:500]}]}],
                config=gtypes.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.2,
                    max_output_tokens=150,
                ),
            )
            import re as _re
            raw = (resp.text or "{}").strip()
            raw = _re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
            extracted = _json.loads(raw)
            keywords = extracted.get("keywords") or []
            patterns = extracted.get("patterns") or []
        except Exception as e:
            logger.warning("[dna_extract] Gemini failed: %s", e)

    # ── Accumulate in User.preferences.prompt_dna ────────────────────────────
    try:
        user = await db.user.find_first(where={"id": user_id})
        prefs: dict = (user.preferences or {}) if user else {}
        dna_all: dict = prefs.get("prompt_dna", {})
        bucket_dna: dict = dna_all.get(req.bucket, {
            "winning_keywords": [], "failing_patterns": [],
            "run_count": 0, "last_updated": "",
        })

        if req.liked:
            existing = set(bucket_dna.get("winning_keywords", []))
            for kw in keywords:
                if kw and kw not in existing:
                    existing.add(kw)
            # Keep last 30 winning keywords
            bucket_dna["winning_keywords"] = list(existing)[-30:]
        else:
            existing_fail = set(bucket_dna.get("failing_patterns", []))
            for p in patterns:
                if p and p not in existing_fail:
                    existing_fail.add(p)
            bucket_dna["failing_patterns"] = list(existing_fail)[-15:]

        bucket_dna["run_count"] = bucket_dna.get("run_count", 0) + 1
        bucket_dna["last_updated"] = date.today().isoformat()
        dna_all[req.bucket] = bucket_dna
        prefs["prompt_dna"] = dna_all

        await db.user.update(where={"id": user_id}, data={"preferences": prefs})
        return {"success": True, "bucket": req.bucket, "dna": bucket_dna}
    except Exception as e:
        logger.warning("[dna_extract] DB update failed: %s", e)
        return {"success": False, "error": str(e)}


# ── Brand Research Agent ───────────────────────────────────────────────────────

class BrandResearchRequest(BaseModel):
    url: str = Field(..., description="Website URL to scrape for brand identity")


@router.post(
    "/brand-kit/research",
    summary="Extract brand identity from website URL",
)
async def research_brand_from_url(req: BrandResearchRequest):
    """
    Scrape a website and extract brand signals (name, colors, fonts, tone).
    Used by Brand Kit settings page — "Import from Website" button.
    """
    try:
        from app.services.agents.research_agent import research_brand
        result = await research_brand(req.url)
        return result
    except Exception as e:
        logger.error("brand research error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Integrations (Instagram / LinkedIn tokens) ──────────────────────────���─────

@router.get("/integrations", summary="Get connected social integrations")
async def get_integrations(user_id: CurrentUserId, db: DbSession):
    """Return masked view of connected integrations (no raw tokens)."""
    require_auth(user_id)
    try:
        user = await db.user.find_first(where={"id": user_id})
        prefs = (user.preferences or {}) if user else {}
        integrations = prefs.get("integrations", {})

        result: dict = {}
        for platform in ("instagram", "linkedin"):
            creds = integrations.get(platform, {})
            if creds.get("access_token"):
                result[platform] = {
                    "connected":    True,
                    "account_name": creds.get("account_name", ""),
                    "expires_at":   creds.get("expires_at"),
                }
        return result
    except Exception as e:
        logger.warning("get_integrations error: %s", e)
        return {}


@router.delete("/integrations/{platform}", summary="Disconnect a social integration")
async def disconnect_integration(
    platform: str,
    user_id: CurrentUserId,
    db: DbSession,
):
    """Remove stored credentials for a platform."""
    require_auth(user_id)
    if platform not in ("instagram", "linkedin"):
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
    try:
        user = await db.user.find_first(where={"id": user_id})
        prefs = (user.preferences or {}) if user else {}
        integrations = prefs.get("integrations", {})
        integrations.pop(platform, None)
        prefs["integrations"] = integrations
        await db.user.update(where={"id": user_id}, data={"preferences": prefs})
        return {"success": True, "platform": platform}
    except Exception as e:
        logger.error("disconnect_integration error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

"""
PhotoGenius Unified Generation — POST /api/v1/generate

Creative OS Pipeline:
  STAGE -1: Intent & Platform Analyzer → creative_type, platform, goal
  STAGE 0:  Text overlay detection
  STAGE 0.5: Creative Director → theme, objects, colors, atmosphere
  STAGE 1:  Creative Graph Builder → node-based layout graph
  STAGE 2:  Layout Planner → design plan with rule-of-thirds math
  STAGE 3:  GPU1 (photogenius-generation-dev): Best-of-N + CLIP jury
  STAGE 4:  Text overlay + Design effects (PIL)
  STAGE 5:  Poster Jury → readability/balance/harmony scoring
  STAGE 6:  CTR Predictor → engagement potential (heuristic)
  STAGE 7:  [PREMIUM] GPU2 post-processing

Timeouts:
  FAST     ~60s    (8 steps, 1 candidate, GPU1 only)
  STANDARD ~130s   (22 steps, 1 candidate, GPU1 only)
  PREMIUM  ~390s   (20 steps × 6 candidates, GPU1 → GPU2 refine)
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.smart.text_overlay import text_overlay, TEXT_NEGATIVE_PROMPT
from app.services.smart.layout_planner import layout_planner
from app.services.smart.creative_director import creative_director
from app.services.smart.design_effects import design_effects
from app.services.smart.intent_analyzer import intent_analyzer
from app.services.smart.creative_graph import creative_graph
from app.services.smart.poster_jury import poster_jury
from app.services.smart.ctr_predictor import ctr_predictor
from app.services.smart.brand_checker import brand_checker
from app.services.smart.variant_generator import variant_generator

logger = logging.getLogger(__name__)
router = APIRouter(tags=["unified-generation"])


def _round64(n: int) -> int:
    """Round n to the nearest multiple of 64 (required by diffusion models)."""
    return max(64, (n + 32) // 64 * 64)

# ── ai-pipeline on sys.path so services.* imports work ──────────────────────
_repo_root = Path(__file__).resolve().parents[6]
_ai_pipeline = _repo_root / "ai-pipeline"
if _ai_pipeline.exists() and str(_ai_pipeline) not in sys.path:
    sys.path.insert(0, str(_ai_pipeline))


# ============================================================
# Request / Response models
# ============================================================

class GenerateRequest(BaseModel):
    prompt: str = Field(
        ..., min_length=3, max_length=2000,
        example="beautiful woman at golden hour beach",
    )
    quality: Optional[str] = Field(
        default="balanced",
        description="fast | balanced | quality | ultra",
    )
    style: Optional[str] = Field(
        default=None,
        description="Auto | Realistic | Cinematic | Anime | Fantasy | Art | Fashion | ...",
    )
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    wow_intensity: float = Field(default=0.85, ge=0.0, le=1.0)
    # kept for API compat — not used (GPU1 handles quality internally)
    skip_quality_check: bool = Field(default=False)
    async_mode: bool = Field(default=False)
    reference_image: Optional[str] = Field(default=None)
    negative_prompt: Optional[str] = Field(default=None)
    # P3: Style DNA — passed by Next.js route from DB (optional, silent if absent)
    user_preferences: Optional[Dict] = Field(default=None)


class GenerateResponse(BaseModel):
    success: bool = True
    image_url: str
    enhanced_prompt: str
    original_prompt: str
    domain: str = "portrait"
    model_used: str = ""
    quality_score: Optional[float] = None
    total_time: float = 0.0
    alternative_urls: List[str] = Field(default_factory=list)
    # legacy fields kept for frontend compat
    attempts_made: int = 1
    job_id: Optional[str] = None
    # ── Creative OS response fields ─────────────────────────────────────
    creative_os: Optional[Dict] = Field(
        default=None,
        description="Creative OS pipeline metadata (intent, graph, jury, ctr)",
    )


# ============================================================
# Quality / style mappings
# ============================================================

# web quality string → GPU1 quality_tier (passed to GPU2 for context-aware enhancement)
# NOTE: actual GPU1 tier is determined in flux_finish.py _quality_map.
_TO_GPU1_TIER: dict[str, str] = {
    "fast":     "FAST",
    "balanced": "STANDARD",
    "quality":  "PREMIUM",
    "ultra":    "PREMIUM",
}

# web style → GPU2 mode
_TO_GPU2_MODE: dict[str, str] = {
    "Realistic":    "REALISM",
    "Cinematic":    "CINEMATIC",
    "Anime":        "ANIME",
    "Fantasy":      "CREATIVE",
    "Art":          "ART",
    "Fashion":      "FASHION",
    "Digital Art":  "CREATIVE",
    "Product":      "REALISM",
    "Architecture": "REALISM",
    "Nature":       "REALISM",
    "Cyberpunk":    "CINEMATIC",
    "Vintage":      "ART",
    "Design":       "CREATIVE",
    "Creative":     "CREATIVE",
    "Scientific":   "REALISM",
    "Geometric":    "CREATIVE",
}

# Cached FluxFinish instance (avoid rebuilding SmartConfigBuilder on every request)
_flux_finish = None


def _get_flux():
    global _flux_finish
    if _flux_finish is None:
        from services.finish.flux_finish import FluxFinish
        _flux_finish = FluxFinish()
    return _flux_finish


# ============================================================
# Main endpoint
# ============================================================

@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Generate image (GPU2 cinematic enhance → GPU1 Best-of-N)",
    description=(
        "Stage 1: GPU2 Qwen2+Llama creates a cinematic photography-director prompt. "
        "Stage 2: GPU1 runs Best-of-N generation with CLIP jury + micro-polish."
    ),
)
async def generate_image(request: GenerateRequest):
    start_time = time.time()

    quality = (request.quality or "balanced").lower()
    if quality not in _TO_GPU1_TIER:
        quality = "balanced"

    mode = _TO_GPU2_MODE.get(request.style or "", "REALISM")

    logger.info(
        "[GEN] prompt=%r quality=%s style=%s(%s) dims=%dx%d",
        request.prompt[:60], quality, request.style, mode,
        request.width, request.height,
    )

    # ══════════════════════════════════════════════════════════════════════
    # CREATIVE OS PIPELINE
    # ══════════════════════════════════════════════════════════════════════

    # ── STAGE -1: Intent & Platform Analyzer ──────────────────────────────
    #    Classify: creative_type, platform, goal, audience_tone, cta_strength
    intent = intent_analyzer.analyze(request.prompt, request.width, request.height)

    # ── STAGE 0: Text overlay detection ───────────────────────────────────
    text_info = text_overlay.detect(request.prompt)
    generation_prompt = text_info["cleaned_prompt"] if text_info["has_text"] else request.prompt

    # ── STAGE 0.5: Creative Director — structured concept extraction ──────
    creative_brief = creative_director.direct(generation_prompt)
    logger.info(
        "[GEN] Creative brief: theme=%s objects=%s",
        creative_brief["theme"], creative_brief["objects"][:3],
    )

    # ── STAGE 1: Creative Graph — node-based layout for ads/posters ───────
    graph = creative_graph.build(
        creative_type=intent["creative_type"],
        is_ad=intent["is_ad"],
        text_heavy=intent["text_heavy"],
        has_text_overlay=text_info["has_text"],
        aspect_ratio=request.width / max(request.height, 1),
        cta_strength=intent["cta_strength"],
        goal=intent["goal"],
    )

    # ── STAGE 1.5: Variant Generator — auto-generate layout/color variants ─
    variant_set = None
    if intent["is_ad"] or intent["creative_type"] in ("ad", "poster", "banner"):
        try:
            variant_set = variant_generator.generate(
                creative_type=intent["creative_type"],
                is_ad=intent["is_ad"],
                template=graph.get("template", "poster_standard"),
                style="poster",  # variant gen only runs for ads/posters
                goal=intent["goal"],
                aspect_ratio=request.width / max(request.height, 1),
                theme_label=creative_brief.get("theme", ""),
            )
            logger.info(
                "[GEN] Variants: %d generated, primary=%s",
                len(variant_set["variants"]), variant_set["primary_variant"],
            )
        except Exception as e:
            logger.warning("[GEN] Variant generation failed (%s), skipping", e)

    # ── STAGE 2: Layout Planner — design plan with rule-of-thirds math ────
    text_positions = [t.get("position", "bottom") for t in text_info["texts"]] if text_info["has_text"] else None
    design_plan = layout_planner.plan(
        prompt=generation_prompt,
        quality=_TO_GPU1_TIER.get(quality, "STANDARD"),
        width=request.width,
        height=request.height,
        has_text_overlay=text_info["has_text"],
        text_positions=text_positions,
    )

    # Assemble enhanced prompt: layout plan + creative director concept + intent hints
    enhanced_prompt: str = design_plan["enhanced_prompt"]
    if creative_brief["concept_prompt"]:
        enhanced_prompt = f"{enhanced_prompt}, {creative_brief['concept_prompt']}"
    # Inject intent-based hints (composition, lighting, framing)
    for hint_key in ("composition", "lighting", "framing"):
        hint_val = intent["prompt_hints"].get(hint_key)
        if hint_val:
            enhanced_prompt = f"{enhanced_prompt}, {hint_val}"

    negative_prompt: str = design_plan["negative_prompt"]
    # Append user-specified negative prompt if provided
    if request.negative_prompt:
        negative_prompt = f"{negative_prompt}, {request.negative_prompt.strip()}"
    domain: str = design_plan.get("style", "photo")

    logger.info(
        "[GEN] Layout: style=%s intent=%s subj=(%.2f,%.2f) bal=%.2f | prompt=%r",
        design_plan["style"], design_plan["design_intent"],
        design_plan.get("subject_x", 0.5), design_plan.get("subject_y", 0.5),
        design_plan.get("visual_balance", 0.5), enhanced_prompt[:80],
    )

    # ── STAGE 3: Smart Router (fal.ai / Ideogram) with GPU1 fallback ────────
    try:
        from app.services.smart.generation_router import smart_router

        t1 = time.time()

        # Pass Creative OS context to enrich Gemini's brief
        _creative_context = (
            f"creative_type={intent['creative_type']}, "
            f"goal={intent['goal']}, "
            f"audience={intent['audience_tone']}, "
            f"theme={creative_brief.get('theme', '')}"
        )

        gen_result = await smart_router.generate(
            prompt=request.prompt,
            tier=quality,
            style=request.style or "photo",
            creative_type=intent["creative_type"],
            width=_round64(request.width),
            height=_round64(request.height),
            reference_image_url=request.reference_image,
            extra_context=_creative_context,
            user_preferences=request.user_preferences,
        )
        gen_time = time.time() - t1

        if gen_result["success"]:
            logger.info(
                "[GEN] Smart router OK %.1fs bucket=%s model=%s engine=%s",
                gen_time, gen_result["capability_bucket"],
                gen_result["model_used"], gen_result["prompt_engine"],
            )
            # Use smart router's enhanced prompt for downstream stages
            enhanced_prompt = gen_result["enhanced_prompt"]
            final_image_url = gen_result["image_url"]

            # Wrap result to match finish_result interface used in stages 4-6
            class _FakeFinish:
                image_url = final_image_url
                model_used = gen_result["model_used"]
                alternative_urls = gen_result.get("all_urls", [])[1:]  # rest are alternatives
            finish_result = _FakeFinish()

        else:
            # Smart router failed — raise clean error (SageMaker not active in API mode)
            err_detail = gen_result.get("metadata", {}).get("error", "unknown error")
            logger.error("[GEN] Smart router failed: %s", err_detail)
            raise HTTPException(
                status_code=503,
                detail=f"Generation service unavailable: {err_detail}",
            )

        logger.info("[GEN] Generation OK %.1fs", gen_time)

        # ── STAGE 4: Text overlay (if detected) ──────────────────────────
        final_image_url = finish_result.image_url
        if text_info["has_text"]:
            try:
                final_image_url = text_overlay.apply_to_data_url(
                    final_image_url, text_info["texts"], style=domain
                )
                logger.info(
                    "[GEN] Text overlay applied: %s",
                    [t["text"] for t in text_info["texts"]],
                )
            except Exception as e:
                logger.warning("[GEN] Text overlay failed (%s), returning image without text", e)

        # ── STAGE 4b: Design Effects — professional polish ────────────────
        try:
            final_image_url = design_effects.apply_to_data_url(
                final_image_url, style=domain
            )
            logger.info("[GEN] Design effects applied: style=%s", domain)
        except Exception as e:
            logger.warning("[GEN] Design effects failed (%s), returning without effects", e)

        # ── STAGE 5a: Brand Checker — brand guideline compliance ─────────
        brand_verdict = None
        if intent["is_ad"] or text_info["has_text"]:
            try:
                brand_verdict = brand_checker.check(
                    image_b64=final_image_url if final_image_url.startswith("data:") else None,
                    prompt=request.prompt,
                    has_text=text_info["has_text"],
                    creative_tone=intent.get("audience_tone", ""),
                )
            except Exception as e:
                logger.warning("[GEN] Brand checker failed (%s), skipping", e)

        # ── STAGE 5b: Poster Jury v2 — quality scoring (8 signals) ─────
        jury_verdict = None
        if intent["is_ad"] or text_info["has_text"]:
            try:
                jury_verdict = poster_jury.evaluate(
                    image_b64=final_image_url if final_image_url.startswith("data:") else None,
                    visual_balance=graph["visual_balance"],
                    total_text_area=graph["total_text_area"],
                    has_text=text_info["has_text"],
                    is_ad=intent["is_ad"],
                    subject_x=design_plan.get("subject_x", 0.5),
                    subject_y=design_plan.get("subject_y", 0.5),
                    brand_verdict=brand_verdict,
                )
            except Exception as e:
                logger.warning("[GEN] Poster jury failed (%s), skipping", e)

        # ── STAGE 6: CTR Predictor — engagement potential ─────────────────
        ctr_prediction = None
        if intent["is_ad"]:
            try:
                ctr_prediction = ctr_predictor.predict(
                    creative_type=intent["creative_type"],
                    is_ad=intent["is_ad"],
                    visual_balance=graph["visual_balance"],
                    total_text_area=graph["total_text_area"],
                    cta_strength=intent["cta_strength"],
                    has_text=text_info["has_text"],
                    quality_score=None,  # filled by GPU1 if available
                    goal=intent["goal"],
                )
            except Exception as e:
                logger.warning("[GEN] CTR predictor failed (%s), skipping", e)

        # ── Build Creative OS metadata ────────────────────────────────────
        creative_os_data = {
            "intent": {
                "creative_type": intent["creative_type"],
                "platform": intent["platform"]["name"],
                "goal": intent["goal"],
                "audience_tone": intent["audience_tone"],
                "cta_strength": intent["cta_strength"],
                "is_ad": intent["is_ad"],
            },
            "graph": {
                "reading_flow": graph["reading_flow"],
                "visual_balance": graph["visual_balance"],
                "total_text_area": graph["total_text_area"],
                "dominant_quadrant": graph["dominant_quadrant"],
                "node_count": len(graph["nodes"]),
            },
            "layout": {
                "subject_x": design_plan.get("subject_x", 0.5),
                "subject_y": design_plan.get("subject_y", 0.5),
                "visual_balance": design_plan.get("visual_balance", 0.5),
                "copy_space": design_plan["copy_space"],
                "design_intent": design_plan["design_intent"],
            },
        }
        if jury_verdict:
            creative_os_data["jury"] = {
                "overall_score": jury_verdict["overall_score"],
                "grade": jury_verdict.get("grade", ""),
                "readability": jury_verdict["readability"],
                "balance": jury_verdict["balance"],
                "color_harmony": jury_verdict["color_harmony"],
                "ocr_quality": jury_verdict.get("ocr_quality", 0),
                "composition": jury_verdict.get("composition", 0),
                "wcag_contrast": jury_verdict.get("wcag_contrast", 0),
                "brand_score": jury_verdict.get("brand_score", 0),
                "passed": jury_verdict["passed"],
                "issues": jury_verdict["issues"],
            }
        if brand_verdict:
            creative_os_data["brand"] = {
                "compliant": brand_verdict["compliant"],
                "score": brand_verdict["score"],
                "color_match": brand_verdict["color_match"],
                "tone_match": brand_verdict["tone_match"],
                "contrast_ok": brand_verdict["contrast_ok"],
                "issues": brand_verdict["issues"],
            }
        if variant_set and variant_set["variants"]:
            creative_os_data["variants"] = {
                "count": len(variant_set["variants"]),
                "primary": variant_set["primary_variant"],
                "strategy": variant_set["generation_strategy"],
                "options": [
                    {
                        "id": v["variant_id"],
                        "label": v["label"],
                        "type": v["variant_type"],
                        "template": v["template"],
                        "style": v["style"],
                        "colors": v["color_palette"],
                        "text_position": v["text_position"],
                    }
                    for v in variant_set["variants"]
                ],
            }
        if ctr_prediction:
            creative_os_data["ctr"] = {
                "engagement_score": ctr_prediction["engagement_score"],
                "confidence": ctr_prediction["confidence"],
                "method": ctr_prediction["method"],
                "suggestions": ctr_prediction["suggestions"],
            }

        # Add smart router info to creative_os metadata
        creative_os_data["generation"] = {
            "backend":          gen_result.get("backend", "unknown"),
            "model":            gen_result.get("model_used", "unknown"),
            "capability_bucket": gen_result.get("capability_bucket", domain),
            "prompt_engine":    gen_result.get("prompt_engine", "heuristic"),
            "generation_time":  gen_result.get("generation_time", 0),
            "flags":            gen_result.get("flags", {}),
        }

        return GenerateResponse(
            success=True,
            image_url=final_image_url,
            enhanced_prompt=enhanced_prompt,
            original_prompt=request.prompt,
            domain=gen_result.get("capability_bucket", domain),
            model_used=gen_result.get("model_used") or finish_result.model_used or "photogenius",
            total_time=time.time() - start_time,
            alternative_urls=finish_result.alternative_urls or [],
            creative_os=creative_os_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[GEN] GPU1 failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {type(e).__name__}: {e}",
        )

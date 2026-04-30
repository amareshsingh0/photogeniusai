"""
SSE Streaming Generation — POST /api/v1/generate/stream

Events emitted (in order):
  intent_ready   — after Stage -1 Intent Analyzer (<0.2s)
  brief_ready    — after Gemini Creative Brief (1-3s)
  generating     — when fal.ai call starts (immediately after brief)
  compositing    — when PIL compositor starts (typography only)
  final_ready    — when image arrives (~8-60s)
  error          — on failure at any stage
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from typing import Any, AsyncIterator, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from app.services.smart.model_config import QualityTier, normalize_quality_tier

logger = logging.getLogger(__name__)
router = APIRouter(tags=["streaming"])

# ── Module-level HTTP client (connection-pooled, reused across requests) ─────
_http_client: Optional[httpx.AsyncClient] = None

# ── Smart Cache (Semantic + Exact Match Caching) ─────────────────────────────
try:
    from app.services.smart.smart_cache import SmartCache
    _smart_cache = SmartCache()
    _CACHE_ENABLED = os.getenv("USE_SMART_CACHE", "true").lower() != "false"
except Exception as e:
    logger.warning("[cache] SmartCache init failed: %s - caching disabled", e)
    _smart_cache = None
    _CACHE_ENABLED = False


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    return _http_client


_MODEL_LABELS = {
    "flux_2_flex":       "Flux 2 Flex",
    "flux_2_pro":        "Flux 2 Pro",
    "flux_2_dev":        "Flux 2 Dev",
    "flux_2_turbo":      "Flux 2 Turbo",
    "flux_2_max":        "Flux 2 Max",
    "flux_pro":          "Flux 2 Pro",
    "flux_schnell":      "Flux Schnell",
    "flux_dev":          "Flux 2 Dev",
    "flux_redux":        "Flux Redux",
    "flux_fill":         "Flux Fill",
    "gemini_3_imagen":   "Gemini 3 Imagen",
    "gemini_3_1_imagen": "Gemini 3.1 Imagen",
    "imagen_4_base":     "Imagen 4 Base",
    "imagen_4_fast":     "Imagen 4 Fast",
    "imagen_4_ultra":    "Imagen 4 Ultra",
    "grok_2_imagine":    "Grok 2 Imagine",
    "ideogram_v3":       "Ideogram v3",
    "recraft_v4_pro":    "Recraft v4 Pro",
    "seedream_4_5":      "Seedream 4.5",
    "wan_2_7":           "Wan 2.7",
    "ideogram_turbo":    "Ideogram v3 Turbo",
    "ideogram_quality":  "Ideogram v3 Quality",
    "recraft_v4":        "Recraft v4",
    "recraft_v4_svg":    "Recraft v4 SVG",
    "hunyuan_image":     "Hunyuan Image",
    "flux_kontext":      "Flux Kontext",
    "flux_kontext_max":  "Flux Kontext Max",
    "gpt_image_2":       "GPT Image 2",
}

_MODEL_ALIASES = {
    "flux_pro": "flux_2_pro",
    "flux_dev": "flux_2_dev",
    "flux_schnell_fal": "flux_schnell",
    "flux_schnell_pixazo": "flux_schnell",
    "imagen_4_standard": "imagen_4_base",
    "gemini_flash_image": "gemini_3_imagen",
    "fal_ai_flux_2_flex": "flux_2_flex",
    "gemini_3_0_imagen": "gemini_3_imagen",
    "hunyuan_image_v1": "hunyuan_image",
    "fal_ai_bytedance_seedream_v4_5_text_to_image": "seedream_4_5",
    "fal_ai_wan_v2_7_text_to_image": "wan_2_7",
    "xai_grok_imagine_image": "grok_2_imagine",
    "fal_ai_recraft_v4_pro_text_to_image": "recraft_v4_pro",
}

_QUALITY_SECONDS = {
    QualityTier.RES_1K.value: 10,
    QualityTier.RES_2K.value: 30,
    QualityTier.RES_4K.value: 60,
}

# Per-tier inference steps
_QUALITY_STEPS = {
    QualityTier.RES_1K.value: 12,
    QualityTier.RES_2K.value: 25,
    QualityTier.RES_4K.value: 50,
}

# guidance_scale per model family
_MODEL_GUIDANCE = {
    "ideogram_v3":      3.0,
    "ideogram_turbo":   3.0,
    "ideogram_quality": 3.0,
    "recraft_v4_pro":   4.0,
    "recraft_v4":       4.0,
    "recraft_v4_svg":   4.0,
    "hunyuan_image":    4.0,
    "wan_2_7":          4.0,
}
_DEFAULT_GUIDANCE = 3.5


# ─────────────────────────────────────────────────────────────────────────────
# Quality-aware retry (Priority 3 Phase B)
# ─────────────────────────────────────────────────────────────────────────────
# When critic returns REVISE, we already generate a 2nd image as a tie-breaker.
# Phase B upgrades the mutation prompt from generic "— IMPROVE: <notes>" to a
# failure-reason-classified targeted rewrite — strengthen anti-collage anchor
# for grid output, add anatomy cues for bad hands, etc.
def _classify_failure_reason(critique: Dict[str, Any]) -> str:
    """Derive a single dominant failure label from the critic result.

    Returns one of: 'collage_detected', 'anatomy_failure', 'text_failure',
    'composition_failure', 'low_quality', or '' when nothing classifies.
    """
    dims = critique.get("dimensions", {}) or {}
    gates = critique.get("beast_gates", {}) or {}
    score = float(critique.get("overall_score", 10.0))

    failed_gate_text = " ".join(
        str(g.get("name", "")).lower()
        for g in gates.values()
        if isinstance(g, dict) and not g.get("pass", True)
    )

    # Multi-panel / collage / split detection — highest priority because
    # the affirmative anchor in the retry prompt is an exact known fix.
    if any(k in failed_gate_text for k in ("collage", "panel", "split", "grid", "single image", "single subject")):
        return "collage_detected"

    # Anatomy issues
    if any(k in failed_gate_text for k in ("anatomy", "hand", "finger", "face symmetry", "limb")):
        return "anatomy_failure"

    # Typography / text issues
    if (
        dims.get("text_legibility", {}).get("below_floor")
        or dims.get("typography", {}).get("below_floor")
        or any(k in failed_gate_text for k in ("text legibility", "typography", "garbled", "illegible"))
    ):
        return "text_failure"

    # Composition / polish below floor
    if dims.get("composition", {}).get("below_floor") or dims.get("polish", {}).get("below_floor"):
        return "composition_failure"

    # Generic low-quality fallback
    if score < 6.0:
        return "low_quality"

    return ""


def _build_targeted_retry_prompt(
    base_prompt: str,
    failure_reason: str,
    revision_notes: str,
    base_negative: str,
) -> Tuple[str, str]:
    """Return (mutated_prompt, mutated_negative) for a quality-aware retry.

    Each branch is a tested fix for a specific failure mode. Falls back to the
    legacy generic "— IMPROVE: <notes>" suffix when the reason is unclassified.
    """
    base = base_prompt.rstrip()
    if failure_reason == "collage_detected":
        # Stronger affirmative anchor — research shows pure-positive phrasing
        # outperforms negative chains in diffusion cross-attention.
        prefix = (
            "A single continuous photograph spanning the entire canvas as one "
            "unbroken scene, one cohesive composition rendered as one committed "
            "final design. "
        )
        return (prefix + base, base_negative)
    if failure_reason == "anatomy_failure":
        suffix = (
            ", anatomically correct human figure with natural pose, "
            "well-formed hands with five distinct fingers, symmetric facial "
            "features, realistic proportions"
        )
        neg_extras = "extra fingers, deformed hands, asymmetric face, bad anatomy"
        merged_neg = f"{base_negative}, {neg_extras}" if base_negative else neg_extras
        return (base + suffix, merged_neg)
    if failure_reason == "text_failure":
        suffix = (
            ", crisp legible typography with clear consistent character shapes, "
            "all on-image text rendered cleanly, professional letterforms"
        )
        neg_extras = "distorted text, garbled letters, misspelled words, extra characters"
        merged_neg = f"{base_negative}, {neg_extras}" if base_negative else neg_extras
        return (base + suffix, merged_neg)
    if failure_reason == "composition_failure":
        suffix = (
            ", professional composition with clear focal point at rule-of-thirds "
            "intersection, generous negative space, balanced visual hierarchy, "
            "tack-sharp hero with intentional bokeh"
        )
        return (base + suffix, base_negative)
    if failure_reason == "low_quality":
        suffix = (
            ", professional photography polish, tack-sharp focus, "
            "high-quality finish, editorial-grade detail"
        )
        neg_extras = "low-quality, blurry, jpeg artifacts, oversaturated"
        merged_neg = f"{base_negative}, {neg_extras}" if base_negative else neg_extras
        return (base + suffix, merged_neg)
    # Fallback: legacy behavior — append revision notes as a generic hint
    return (f"{base} — IMPROVE: {revision_notes}"[:500], base_negative)

# Models that actually honor `reference_image_url` end-to-end. Either:
#  (a) Native: standard Flux + Kontext payloads include `image_url`
#  (b) Endpoint swap: `_FAL_I2I_ENDPOINT_MAP` rewrites t2i URL → edit/remix URL
#      when a reference is present (Seedream → /v4/edit, Ideogram → /v3/remix)
# Everything else silently drops the reference, so the router falls back to
# Flux Kontext for those.
_IMG2IMG_CAPABLE_MODELS = {
    # Native fal Flux family
    "flux_kontext",
    "flux_kontext_max",
    "flux_2_flex",
    "flux_2_pro",
    "flux_2_dev",
    "flux_2_turbo",
    "flux_2_max",
    # Endpoint-swap models (typography heavyweights — text rendering kings)
    "seedream_4_5",   # → fal-ai/bytedance/seedream/v4/edit
    "ideogram_v3",    # → fal-ai/ideogram/v3/remix
}


def _pick_img2img_model(quality: str) -> str:
    """Choose the best reference-aware model for a given quality tier.

    Kontext is purpose-built for instruction/guided edits and is the only
    model across our 3 providers with verified reference-image plumbing.
    """
    if quality in (QualityTier.RES_2K.value, QualityTier.RES_4K.value):
        return "flux_kontext_max"
    return "flux_kontext"


def _parse_bool_env(name: str, default: bool = True) -> bool:
    """Parse env flag: false/0/no/off → False, anything else → True."""
    val = os.getenv(name, "").strip().lower()
    if not val:
        return default
    return val not in ("false", "0", "no", "off")


class StreamRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)
    quality: Optional[str] = Field(default=QualityTier.RES_1K.value)
    style: Optional[str] = Field(default=None)
    width: int = Field(default=1024, ge=256, le=4096)
    height: int = Field(default=1024, ge=256, le=4096)
    reference_image_url: Optional[str] = Field(default=None)
    negative_prompt: Optional[str] = Field(default=None)
    brand_kit: Optional[dict] = Field(default=None)
    prompt_dna: Optional[dict] = Field(default=None)   # User.preferences.prompt_dna from Next.js
    testing_mode: Optional[bool] = Field(default=False)  # Admin testing mode (parallel models)
    model_key: Optional[str] = Field(default=None)      # Force a specific model (bypasses bucket routing)

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: Optional[str]) -> str:
        return normalize_quality_tier(v)

    @field_validator("width", "height")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        # Snap to nearest 64
        return max(256, min(4096, round(v / 64) * 64))


def _sse(event: str, data: dict) -> str:
    # Use compact JSON to avoid literal newlines breaking SSE protocol
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _sse_keepalive() -> str:
    return ": keepalive\n\n"


def _pick_image_size(width: int, height: int) -> str:
    if width == height:
        return "square_hd"
    if width > height:
        ratio = width / height
        if ratio >= 1.6:
            return "landscape_16_9"
        return "landscape_4_3"
    ratio = height / width
    if ratio >= 1.6:
        return "portrait_9_16"
    return "portrait_4_3"


def _canonical_model_key(model_key: Optional[str], default: str = "flux_2_pro") -> str:
    normalized = (
        (model_key or "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace(".", "_")
        .replace("-", "_")
        .replace("/", "_")
    )
    if not normalized:
        return default
    return _MODEL_ALIASES.get(normalized, normalized)


def _build_design_brief(
    brief: dict,
    ad_copy: dict,
    poster_design: Optional[dict],
    raw_hero_url: str,
) -> dict:
    """Build canvas-editor design_brief from agent/Gemini brief. Separate from stream logic."""
    pd = poster_design or {}
    result = {
        "ad_copy":       ad_copy,
        "poster_design": pd,
        "hero_url":      raw_hero_url,
        "brand_colors": {
            "accent":         pd.get("accent_color", "#F59E0B"),
            "bg":             pd.get("bg_color", "#0F172A"),
            "primary":        pd.get("accent_color", "#2563EB"),
            "text_primary":   "#FFFFFF",
            "text_secondary": "#CBD5E1",
        },
        "layout_archetype": pd.get("layout", "hero_top_features_bottom"),
        "font_style":        pd.get("font_style", "bold_tech"),
    }
    if brief.get("_source") == "agent_chain":
        result.update({
            "triage":   brief.get("triage", {}),
            "brand":    brief.get("brand", {}),
            "creative": brief.get("creative", {}),
            "elements": brief.get("elements", []),
        })
    return result


async def _stream_pipeline(req: StreamRequest, trace_id: str) -> AsyncIterator[str]:
    start = time.time()
    quality = req.quality  # already validated by Pydantic

    # ── Stage -2: Smart Cache Check ────────────────────────────────────────
    cache_result = None
    if _CACHE_ENABLED and _smart_cache:
        try:
            cache_result = await asyncio.to_thread(
                _smart_cache.check_cache,
                prompt=req.prompt,
                mode=f"w{req.width}h{req.height}",
                identity_id=None,  # Add user_id when auth implemented
                quality_tier=quality,
                style=req.style,
            )
            if cache_result:
                cache_type = cache_result.get("type", "unknown")
                logger.info("[stream][%s] Cache %s hit!", trace_id, cache_type)

                # Return cached result via SSE
                yield _sse("cache_hit", {
                    "type": cache_type,
                    "similarity": cache_result.get("similarity", 1.0),
                    "trace_id": trace_id,
                })

                # Extract cached data
                images = cache_result.get("images", [])
                if images and len(images) > 0:
                    first_img = images[0]
                    yield _sse("final_ready", {
                        "image_url": first_img.get("image_url", ""),
                        "seed": first_img.get("seed"),
                        "composite_status": "cached",
                        "model_used": first_img.get("model_used", "cached"),
                        "elapsed_seconds": time.time() - start,
                        "trace_id": trace_id,
                        "cached": True,
                        "cache_type": cache_type,
                    })
                    return
        except Exception as cache_err:
            logger.warning("[stream][%s] Cache check failed: %s", trace_id, cache_err)

    try:
        # ── Stage -2: PRE-SANITIZE USER INPUT ──────────────────────────────
        # Users often paste full marketing briefs as the prompt — markdown
        # asterisks, '[Brand]' placeholder brackets, '**Caption Prompt:**'
        # section labels, '**Visual Suggestion:**', '**CTA:**', etc.
        # If we forward this raw to the engine, the image model renders all
        # of it as text on the image. Strip it BEFORE anything sees it.
        from app.services.smart.simple_prompt_engine import _sanitize_prompt as _strip_leaks
        _raw_user_prompt = req.prompt
        _cleaned = _strip_leaks(_raw_user_prompt)
        # Also strip markdown asterisks / list bullets that the output sanitizer
        # already handles but applied here defensively for input.
        import re as _re
        _cleaned = _re.sub(r"^\s*[\*\-•]\s+", "", _cleaned, flags=_re.MULTILINE)  # bullet markers
        _cleaned = _re.sub(r"\*{1,3}([^\*\n]+)\*{1,3}", r"\1", _cleaned)         # **bold**, *italic*
        _cleaned = _re.sub(r"\s{2,}", " ", _cleaned).strip()
        if _cleaned and _cleaned != _raw_user_prompt:
            logger.info(
                "[stream][%s] PRE-SANITIZED user input %d→%d chars",
                trace_id, len(_raw_user_prompt), len(_cleaned),
            )
            req.prompt = _cleaned

        # ── Stage -1: Intent ───────────────────────────────────────────────
        from app.services.smart.intent_analyzer import intent_analyzer

        intent = await asyncio.to_thread(intent_analyzer.analyze, req.prompt, req.width, req.height)

        if not isinstance(intent, dict):
            yield _sse("error", {"message": "Intent analyzer returned invalid result", "stage": "intent", "trace_id": trace_id})
            return

        yield _sse("intent_ready", {
            "creative_type": intent.get("creative_type", "photorealism"),
            "is_ad":         intent.get("is_ad", False),
            "goal":          intent.get("goal", ""),
            "audience_tone": intent.get("audience_tone", ""),
            "trace_id":      trace_id,
        })

        # ── Capability routing ─────────────────────────────────────────────
        from app.services.smart.config import detect_capability_bucket
        from app.services.smart.model_config import (
            get_model_for_request, get_model_supported_tiers,
            normalize_quality_tier, MODEL_REGISTRY,
        )

        bucket = detect_capability_bucket(req.prompt)
        norm_tier = normalize_quality_tier(quality)
        db_bucket = bucket.split("_")[0] if "_" in bucket else bucket
        model_cfg = None

        # ── model_key override — bypasses bucket routing entirely ──────────
        if req.model_key:
            _mk = _canonical_model_key(req.model_key, default="")
            if _mk and _mk in MODEL_REGISTRY:
                _spec = MODEL_REGISTRY[_mk]
                model_cfg = {
                    "model_key": _mk,
                    "model":     _spec["endpoint"],
                    "provider":  _spec["provider"].value,
                    "display_name": _spec["display_name"],
                    "tier_used": norm_tier,
                    "cost_per_image": _spec["cost_per_image"],
                    "num_images": 1,
                }
                logger.info("[stream][%s] model_key override → %s", trace_id, _mk)
            else:
                logger.warning("[stream][%s] model_key=%s not in registry, using bucket routing", trace_id, req.model_key)

        # ── DB-driven model picker (only if no model_key override) ────────
        if not model_cfg:
            try:
                from prisma import Prisma
                _prisma = Prisma()
                await _prisma.connect()
                _db_models = await _prisma.modelconfig.find_many(where={"isActive": True})
                await _prisma.disconnect()
                _candidates = [
                    m for m in _db_models
                    if (bucket in (m.buckets or []) or db_bucket in (m.buckets or []))
                    and norm_tier in get_model_supported_tiers(m.modelId)
                    and _canonical_model_key(m.modelId, default="") in MODEL_REGISTRY
                ]
                if _candidates:
                    _candidates.sort(key=lambda m: m.costPerImage or 0)
                    _chosen_key = _canonical_model_key(_candidates[0].modelId, default="")
                    _spec = MODEL_REGISTRY[_chosen_key]
                    model_cfg = {
                        "model_key": _chosen_key,
                        "model":     _spec["endpoint"],
                        "provider":  _spec["provider"].value,
                        "display_name": _spec["display_name"],
                        "tier_used": norm_tier,
                        "cost_per_image": _spec["cost_per_image"],
                        "num_images": 1,
                    }
                    logger.info("[stream][%s] DB-picker chose %s for bucket=%s tier=%s (from %d candidates)",
                                trace_id, _chosen_key, bucket, norm_tier, len(_candidates))
            except Exception as _e:
                logger.warning("[stream][%s] DB-picker failed, falling back to static map: %s", trace_id, _e)

        # ── Fallback: static BUCKET_MODEL_MAP ─────────────────────────────
        if not model_cfg:
            model_cfg = get_model_for_request(bucket, quality)
            logger.info("[stream][%s] Static-map picked %s for bucket=%s tier=%s",
                        trace_id, model_cfg.get("model_key"), bucket, norm_tier)

        fal_model_key = _canonical_model_key(
            model_cfg.get("model_key") or model_cfg.get("model"),
            default="flux_2_pro",
        )
        if not model_cfg.get("model"):
            fal_model_key = "flux_2_pro"
            logger.warning("[stream][%s] model_cfg missing 'model' key, falling back to flux_2_pro", trace_id)

        # ── Img2Img override ───────────────────────────────────────────────
        # If a reference image was uploaded, the selected text-to-image model
        # will silently drop it (Seedream/Ideogram/Recraft/Wan/Grok payloads
        # don't wire `image_url`, and Google/WaveSpeed providers don't accept
        # references at all). Force Flux Kontext, which is purpose-built for
        # reference-guided editing, so the upload actually influences output.
        if req.reference_image_url and fal_model_key not in _IMG2IMG_CAPABLE_MODELS:
            _prev_model = fal_model_key
            fal_model_key = _pick_img2img_model(quality)
            logger.info(
                "[stream][%s] Img2Img override: %s → %s (reference image provided)",
                trace_id, _prev_model, fal_model_key,
            )

        model_label = _MODEL_LABELS.get(fal_model_key, fal_model_key)
        num_images = model_cfg.get("num_images", 1)

        # ── Stage A: Creative Brief ────────────────────────────────────────
        # Simple engine path — single Haiku call, skips agent chain + Stage A/B engine.
        # Toggle: USE_SIMPLE_ENGINE=true. When on, bypass everything else.
        # HARD ENV OVERRIDE — simple flow: prompt → Haiku → describe → image model.
        # Only OFF when explicitly USE_SIMPLE_ENGINE=false. Missing var, blank,
        # or any other value defaults to ON. Prevents stale .env from silently
        # falling back to the 4-agent chain that produces option/panel layouts.
        _simple_env = os.getenv("USE_SIMPLE_ENGINE", "").strip().lower()
        use_simple = (_simple_env != "false")
        # Loud stdout marker — visible in pm2 logs (logger.info isn't captured).
        print(f"[ENGINE-PICK] use_simple={use_simple} env_value={_simple_env!r} bucket={bucket} tier={quality} prompt_len={len(req.prompt)}", flush=True)
        # Import prompt engine based on env flag
        use_claude = os.getenv("USE_CLAUDE_ENGINE", "true").lower() != "false"
        if use_claude:
            from app.services.smart.claude_prompt_engine_v2 import claude_prompt_engine as prompt_engine
        else:
            from app.services.smart.gemini_prompt_engine import gemini_prompt_engine as prompt_engine
        brief: dict

        if use_simple:
            from app.services.smart.simple_prompt_engine import simple_engine

            # Priority 6 — Style consistency: when user uploads a reference image
            # AND has not specified an explicit style keyword, extract a 2-3
            # sentence visual style summary via Gemini Vision and feed it to
            # Haiku as a hard aesthetic anchor. Cached per reference URL — same
            # reference reused across N generations costs 1 Vision call total.
            style_reference_description = ""
            if req.reference_image_url and not (req.style or "").strip():
                try:
                    from app.services.smart.style_extractor import extract_style_description
                    style_reference_description = await extract_style_description(req.reference_image_url)
                    if style_reference_description:
                        logger.info(
                            "[stream][%s] style-extractor produced %d chars",
                            trace_id, len(style_reference_description),
                        )
                except Exception as _se_err:
                    logger.warning("[stream][%s] style-extractor failed (non-fatal): %s",
                                   trace_id, _se_err)

            simple_out = await simple_engine.enrich(
                user_prompt=req.prompt,
                bucket=bucket,
                tier=quality,
                width=req.width,
                height=req.height,
                style=req.style,
                brand_kit=req.brand_kit,
                style_reference_description=style_reference_description or None,
            )
            logger.info(
                "[stream][%s] SimpleEngine done in %.2fs intent=%s aspect=%s",
                trace_id, simple_out.get("_elapsed", 0),
                simple_out.get("intent"), simple_out.get("aspect_hint"),
            )
            # Synthesize a brief shape compatible with downstream code.
            brief = {
                "_source":          simple_out.get("_source", "simple_engine"),
                "_elapsed":         simple_out.get("_elapsed", 0),
                "visual_concept":   simple_out["prompt"][:200],
                "subject":          simple_out.get("intent", "general"),
                "lighting":         "",
                "camera":           "",
                "mood":             "",
                "color_palette":    "",
                "style_refs":       [],
                "ad_copy":          simple_out.get("ad_copy"),
                "poster_design":    None,
                "_simple_payload":  simple_out,   # consumed below to skip Stage B
            }
        elif bucket == "typography":
            try:
                from app.services.smart.design_agent_chain import design_agent_chain
                # design_agent_chain.arun() is fully async now
                brief = await design_agent_chain.arun(
                    prompt=req.prompt,
                    brand_kit=req.brand_kit,
                    width=req.width,
                    height=req.height,
                    prompt_dna=req.prompt_dna,
                )
                if brief.get("_error"):
                    raise RuntimeError(f"DesignAgentChain: {brief['_error']}")
                logger.info("[stream][%s] DesignAgentChain done in %.2fs", trace_id, brief.get("_elapsed", 0))
            except Exception as _chain_err:
                logger.warning("[stream][%s] DesignAgentChain failed (%s), falling back to Gemini", trace_id, _chain_err)
                brief = await prompt_engine.create_brief(
                    req.prompt,
                    creative_type=intent.get("creative_type", "typography"),
                    style=req.style or "photo",
                    extra_context=f"creative_type={intent.get('creative_type')}, goal={intent.get('goal')}",
                    bucket=bucket,
                    tier=quality,
                )
                brief["_source"] = "gemini_fallback"
        else:
            _ctx = (
                f"creative_type={intent.get('creative_type')}, "
                f"goal={intent.get('goal')}, "
                f"audience={intent.get('audience_tone')}"
            )
            brief = await prompt_engine.create_brief(
                req.prompt,
                creative_type=intent.get("creative_type", "photorealism"),
                style=req.style or "photo",
                extra_context=_ctx,
                bucket=bucket,
                tier=quality,
            )

        # Normalize brief shape (both paths produce compatible dict)
        brief.setdefault("_source", "gemini")
        brief.setdefault("ad_copy", None)
        brief.setdefault("poster_design", None)
        effective_width = req.width
        effective_height = req.height
        # Simple engine: use aspect_hint to pick canvas when caller left default 1024².
        _simple_payload = brief.get("_simple_payload")
        if _simple_payload and req.width == 1024 and req.height == 1024:
            _ASPECT_DIMS = {
                "square_hd":      (1024, 1024),
                "portrait_4_3":   (832, 1216),
                "landscape_4_3":  (1216, 832),
                "portrait_9_16":  (768, 1344),
                "landscape_16_9": (1344, 768),
            }
            _w, _h = _ASPECT_DIMS.get(_simple_payload.get("aspect_hint", "square_hd"), (1024, 1024))
            effective_width, effective_height = _w, _h
        elif req.width == 1024 and req.height == 1024:
            effective_width = int(brief.get("resolved_width") or brief.get("recommended_width") or req.width)
            effective_height = int(brief.get("resolved_height") or brief.get("recommended_height") or req.height)

        yield _sse("brief_ready", {
            "visual_concept": brief.get("visual_concept", ""),
            "subject":        brief.get("subject", ""),
            "lighting":       brief.get("lighting", ""),
            "camera":         brief.get("camera", ""),
            "mood":           brief.get("mood", ""),
            "color_palette":  brief.get("color_palette", ""),
            "style_refs":     brief.get("style_refs", []),
            "source":         brief.get("_source", "heuristic"),
            "ad_copy":        brief.get("ad_copy"),
            "trace_id":       trace_id,
        })

        # ── Stage B: CDI — Creative Director Integration ──────────────────
        # Simple engine path: skip Stage B; the enriched prompt IS the final prompt.
        if _simple_payload:
            params = {
                "prompt":          _simple_payload["prompt"],
                "negative_prompt": _simple_payload.get("negative_prompt", ""),
                "parameters":      {},
                "style_notes":     _simple_payload.get("intent", "")[:80],
                "recommendation_reason": "simple_engine: single-call enrichment",
            }
        else:
            params = await prompt_engine.build_params(brief, model_label, bucket)
        enhanced_prompt = params.get("prompt") or req.prompt
        negative_prompt = params.get("negative_prompt", "")
        if req.negative_prompt is not None:
            negative_prompt = f"{req.negative_prompt}, {negative_prompt}" if negative_prompt else req.negative_prompt

        # Universal leak sanitizer + anti-collage negatives + hard cap + single-image anchor
        # — applies to ALL engine paths (simple_engine / claude_v2 / 4-agent chain).
        # This is defense-in-depth: LLMs sometimes output pitch-deck structure even when
        # told not to, and long walls of copy get rendered verbatim by image models.
        from app.services.smart.simple_prompt_engine import (
            _sanitize_prompt,
            _ANTI_COLLAGE_NEGATIVES,
            _AFFIRMATIVE_SINGLE_IMAGE_ANCHOR,
        )

        # 1) Strip Option 1/2/3, [Placeholder], brief-doc labels, collage words.
        enhanced_prompt = _sanitize_prompt(enhanced_prompt)

        # 2) Sentence-aware safety cap — only kicks in for genuinely runaway prompts.
        #    The earlier 35-word cap chopped Haiku's curated 192-word briefs in
        #    mid-sentence (literally ending at "metallic gold cap,"), destroying
        #    headline/palette/CTA context the image model needs.
        #    simple_engine output is already curated by Haiku → trust it (no cap).
        #    For other engines, cap at 220 words, cutting at the nearest sentence
        #    boundary so we never end mid-clause.
        _engine_source = (params.get("_source") or "").lower()
        if _engine_source != "simple_engine":
            _words = enhanced_prompt.split()
            if len(_words) > 220:
                _truncated = " ".join(_words[:220])
                # Cut at the last sentence terminator inside the kept window so
                # the prompt never ends mid-clause.
                _last_terminator = max(
                    _truncated.rfind("."), _truncated.rfind("!"), _truncated.rfind("?")
                )
                if _last_terminator > 200:  # only honor terminator if we keep most of the prompt
                    _truncated = _truncated[: _last_terminator + 1]
                enhanced_prompt = _truncated
                logger.info("[stream][%s] prompt truncated %d→%d words at sentence boundary",
                            trace_id, len(_words), len(enhanced_prompt.split()))

        # 3) Single-image anchor — universal short affirmative imperative so the
        #    image model interprets the prompt as ONE composition. Constant lives
        #    in simple_prompt_engine for single-source-of-truth across providers.
        enhanced_prompt = _AFFIRMATIVE_SINGLE_IMAGE_ANCHOR + enhanced_prompt

        # 4) Strong anti-collage negative prompt — Seedream/Imagen respect negatives.
        #    simple_engine.enrich() already merges _ANTI_COLLAGE_NEGATIVES into its
        #    own neg output, so check before appending or we double the payload.
        if not negative_prompt:
            negative_prompt = _ANTI_COLLAGE_NEGATIVES
        elif "design sheet, pitch deck" not in negative_prompt:
            negative_prompt = f"{negative_prompt}, {_ANTI_COLLAGE_NEGATIVES}"

        # ── DEBUG: dump exact prompt + engine source going to model ──────
        # When users report bad output, this is the SINGLE log line to check.
        # Tag = [FINAL-PROMPT] for easy grep.
        logger.info(
            "[FINAL-PROMPT][%s] engine=%s model=%s bucket=%s tier=%s\n  prompt: %s\n  negative: %s",
            trace_id,
            "simple_engine" if _simple_payload else (params.get("_source") or "unknown"),
            fal_model_key,
            bucket,
            quality,
            enhanced_prompt[:600],
            (negative_prompt or "")[:300],
        )

        # Typography bucket — use model from model_config.py BUCKET_MODEL_MAP (no hardcoded override)
        if bucket == "typography":
            logger.info("[stream][%s] Typography bucket → using config model: %s", trace_id, fal_model_key)

        # CDI model override — AI picks better model than router when context warrants it
        _cdi_recommended = _canonical_model_key(params.get("recommended_model"), default="")
        if _cdi_recommended and _cdi_recommended in _MODEL_LABELS:
            if _cdi_recommended != fal_model_key:
                logger.info(
                    "[stream][%s] CDI model override: %s → %s (%s)",
                    trace_id, fal_model_key, _cdi_recommended,
                    params.get("recommendation_reason", "")[:80],
                )
            fal_model_key = _cdi_recommended
            model_label = _MODEL_LABELS.get(fal_model_key, fal_model_key)

        # CDI steps/guidance override — AI knows scene complexity better than static tables
        _cdi_p = params.get("parameters") or {}
        inference_steps = int(_cdi_p.get("steps") or _QUALITY_STEPS.get(quality, 20))
        guidance_scale = float(_cdi_p.get("guidance") or _MODEL_GUIDANCE.get(fal_model_key, _DEFAULT_GUIDANCE))

        # Store draft variant for potential quick preview use
        _draft_variant = params.get("draft_variant")
        _ideogram_variant = params.get("ideogram_variant")

        yield _sse("generating", {
            "model":                   model_label,
            "bucket":                  bucket,
            "estimated_seconds":       _QUALITY_SECONDS.get(quality, 25),
            "enhanced_prompt_preview": enhanced_prompt[:120],
            "cdi_emotion":             params.get("style_notes", "")[:80],
            "recommendation_reason":   params.get("recommendation_reason", "")[:100],
            "trace_id":                trace_id,
        })

        # ── Generation via multi-provider client (with keepalives) ─────────
        from app.services.external.multi_provider_client import multi_client

        # Dual Variant (Phase 6): DISABLED — one model, one image.
        # Earlier this fired a safe + experimental pair for 2k/4k with creative_bible.
        # User requested single-image-per-model. If you need to re-enable, flip
        # this back to the original condition.
        _creative_bible = brief.get("creative_bible") or {}
        _run_dual = False
        _experimental_prompt: Optional[str] = None
        if _run_dual:
            _metaphors = [m for m in _creative_bible.get("visual_metaphors", []) if m]
            if _metaphors:
                _experimental_prompt = (
                    f"{enhanced_prompt} — experimental: {_metaphors[-1]}, "
                    f"unexpected juxtaposition, push creative boundaries"
                )[:500]

        # Run generation in thread, emit keepalives every 15s so proxies don't drop
        _gen_kwargs = dict(
            model_key=fal_model_key,
            prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
            num_images=num_images,
            image_size=_pick_image_size(effective_width, effective_height),
            num_inference_steps=inference_steps,
            guidance_scale=guidance_scale,
            reference_image_url=req.reference_image_url,
            rendering_speed=model_cfg.get("rendering_speed", "BALANCED"),
        )
        gen_task = asyncio.create_task(multi_client.generate(**_gen_kwargs))

        # Experimental variant fires concurrently (dual variant — phase 6)
        exp_task: Optional[asyncio.Task] = None
        if _experimental_prompt:
            _exp_kwargs = dict(_gen_kwargs, prompt=_experimental_prompt, num_images=1)
            exp_task = asyncio.create_task(multi_client.generate(**_exp_kwargs))

        # Wait for main gen with keepalives
        while not gen_task.done():
            try:
                gen = await asyncio.wait_for(asyncio.shield(gen_task), timeout=15.0)
                break
            except asyncio.TimeoutError:
                yield _sse_keepalive()
        else:
            gen = gen_task.result()

        generation_time = time.time() - start

        # Collect experimental result (already running, just await — should be done or close)
        gen_experimental: Optional[dict] = None
        if exp_task is not None:
            try:
                gen_experimental = await asyncio.wait_for(exp_task, timeout=30.0)
            except Exception as _exp_err:
                logger.warning("[stream][%s] experimental variant failed: %s", trace_id, _exp_err)

        if not gen.get("success"):
            yield _sse("error", {
                "message": gen.get("error") or gen.get("metadata", {}).get("error", "Generation failed"),
                "stage":   "generation",
                "elapsed": generation_time,
                "trace_id": trace_id,
            })
            return

        # Validate required keys on success
        raw_hero_url = gen.get("image_url")
        if not raw_hero_url:
            yield _sse("error", {
                "message": "Provider returned success=True but no image_url",
                "stage":   "generation",
                "elapsed": generation_time,
                "trace_id": trace_id,
            })
            return

        final_image_url = raw_hero_url
        ad_copy         = brief.get("ad_copy")
        poster_design   = brief.get("poster_design") or {}
        composite_status = "skipped"

        # ── Stage C: Poster compositor (PERMANENTLY DISABLED — AI generates text natively) ────
        # PIL compositor removed - Ideogram/Flux handles text rendering directly in image generation
        composite_status = "skipped"

        # Build design_brief for typography bucket (without compositor)
        _design_brief = None
        if bucket == "typography" and isinstance(ad_copy, dict):
            _design_brief = _build_design_brief(brief, ad_copy, poster_design, raw_hero_url)

# Clean Quality Gate Section (lines 460-720)
# Replace this in generate_stream.py

        # ── Stage D: Beast Quality Critic (Max 2 Images) ──
        quality_gate_result = None
        creative_bible = brief.get("creative_bible") or {}
        _run_quality_gate = (
            quality != QualityTier.RES_1K.value
            and bool(creative_bible.get("emotional_territory"))
        )

        # Simple rule: Max 2 images total
        max_images_total = 2
        images_generated = 1  # We already have Gen 1 (raw_hero_url)

        if _run_quality_gate:
            yield _sse("quality_checking", {
                "message": f"Quality review: Image 1/{max_images_total}",
                "trace_id": trace_id,
                "images_generated": images_generated,
            })

            try:
                from app.services.smart.quality_critic import QualityCritic

                # Preserve legacy critic thresholds: middle tier uses standard, top tier uses ultra.
                critic_tier = "standard" if quality == QualityTier.RES_2K.value else "ultra"
                critic = QualityCritic(tier=critic_tier)

                # Build design_brief for critic context
                design_brief_for_critic = {
                    "user_prompt": req.prompt,
                    "enhanced_prompt": enhanced_prompt,
                    "background_prompt": brief.get("background_prompt", brief.get("visual_concept", "")),
                    "bucket": bucket,
                    "ad_copy": ad_copy if isinstance(ad_copy, dict) else {},
                    "poster_design": poster_design if isinstance(poster_design, dict) else {},
                }

                # ━━━ CHECK IMAGE 1 ━━━
                critique_1 = await critic.critique(
                    image_url=raw_hero_url,
                    creative_bible=creative_bible,
                    design_brief=design_brief_for_critic,
                    platform=getattr(req, 'platform', 'instagram'),
                    revision_cycle=0,
                )

                quality_gate_result = critique_1

                # Yield quality_scored event for image 1
                yield _sse("quality_scored", {
                    "overall_score": critique_1.get("overall_score", 7.0),
                    "verdict": critique_1.get("verdict", "APPROVED"),
                    "dimensions": critique_1.get("dimensions", {}),
                    "beast_gates_passed": critique_1.get("gates_passed", 0),
                    "beast_gates_total": 10,
                    "image_number": 1,
                    "trace_id": trace_id,
                })

                verdict_1 = critique_1.get("verdict", "APPROVED")
                score_1 = critique_1.get("overall_score", 7.0)

                logger.info("[stream][%s] Image 1: score=%.2f, verdict=%s, gates=%d/%d",
                          trace_id, score_1, verdict_1,
                          critique_1.get("gates_passed", 0), 10)

                # ━━━ DECISION LOGIC ━━━
                if verdict_1 == "APPROVED":
                    # Image 1 is good enough - use it!
                    logger.info("[stream][%s] Image 1 APPROVED - no need for Image 2", trace_id)

                elif verdict_1 == "ESCALATE":
                    # Fundamental issues - use Image 1 with warning
                    logger.warning("[stream][%s] Image 1 ESCALATED (fundamental issues)", trace_id)
                    quality_gate_result["escalated"] = True

                elif verdict_1 == "REVISE" and images_generated < max_images_total:
                    # Generate Image 2 with targeted improvements
                    revision_notes = critique_1.get("revision_notes", "")
                    route_to = critique_1.get("revision_route_to", "")
                    weak_dims = [
                        dim_name for dim_name, dim_data in critique_1["dimensions"].items()
                        if dim_data.get("score", 10) < dim_data.get("floor", 7.0)
                    ]

                    # Phase B — classify the failure type for a targeted rewrite
                    failure_reason = _classify_failure_reason(critique_1)
                    mutation_prompt, mutation_neg = _build_targeted_retry_prompt(
                        base_prompt=enhanced_prompt,
                        failure_reason=failure_reason,
                        revision_notes=revision_notes,
                        base_negative=negative_prompt or "",
                    )
                    mutation_prompt = mutation_prompt[:1000]  # safety cap (P7 truncates further)

                    logger.info(
                        "[stream][%s] Image 1 REVISE — generating Image 2 (weak: %s, reason: %s)",
                        trace_id, weak_dims, failure_reason or "unclassified",
                    )
                    print(
                        f"[QUALITY-RETRY] reason={failure_reason or 'unclassified'} "
                        f"cycle=1 mutation_chars={len(mutation_prompt)}",
                        flush=True,
                    )

                    yield _sse("revision_triggered", {
                        "image_number": 2,
                        "route_to": route_to,
                        "notes": revision_notes,
                        "weak_dimensions": weak_dims,
                        "failure_reason": failure_reason,
                        "trace_id": trace_id,
                    })

                    # ━━━ GENERATE IMAGE 2 ━━━
                    gen_2 = await multi_client.generate(
                        model_key=fal_model_key,
                        prompt=mutation_prompt,
                        negative_prompt=mutation_neg,
                        num_images=1,
                        image_size=_pick_image_size(effective_width, effective_height),
                        num_inference_steps=inference_steps,
                        guidance_scale=guidance_scale,
                        reference_image_url=req.reference_image_url,
                        rendering_speed=model_cfg.get("rendering_speed", "BALANCED"),
                    )

                    if gen_2.get("success") and gen_2.get("image_url"):
                        images_generated += 1
                        image_2_url = gen_2["image_url"]

                        # ━━━ CHECK IMAGE 2 ━━━
                        yield _sse("quality_checking", {
                            "message": f"Quality review: Image 2/{max_images_total}",
                            "trace_id": trace_id,
                            "images_generated": images_generated,
                        })

                        critique_2 = await critic.critique(
                            image_url=image_2_url,
                            creative_bible=creative_bible,
                            design_brief=design_brief_for_critic,
                            platform=getattr(req, 'platform', 'instagram'),
                            revision_cycle=1,
                        )

                        # Yield quality_scored event for image 2
                        yield _sse("quality_scored", {
                            "overall_score": critique_2.get("overall_score", 7.0),
                            "verdict": critique_2.get("verdict", "APPROVED"),
                            "dimensions": critique_2.get("dimensions", {}),
                            "beast_gates_passed": critique_2.get("gates_passed", 0),
                            "beast_gates_total": 10,
                            "image_number": 2,
                            "trace_id": trace_id,
                        })

                        score_2 = critique_2.get("overall_score", 7.0)

                        logger.info("[stream][%s] Image 2: score=%.2f, verdict=%s",
                                  trace_id, score_2, critique_2.get("verdict", "APPROVED"))

                        # ━━━ PICK BEST OF 2 ━━━
                        if score_2 > score_1:
                            logger.info("[stream][%s] Image 2 better (%.2f > %.2f) - using Image 2",
                                      trace_id, score_2, score_1)
                            raw_hero_url = image_2_url
                            final_image_url = raw_hero_url
                            quality_gate_result = critique_2
                            quality_gate_result["image_selected"] = 2
                        else:
                            logger.info("[stream][%s] Image 1 better (%.2f >= %.2f) - using Image 1",
                                      trace_id, score_1, score_2)
                            # raw_hero_url stays as Image 1
                            quality_gate_result = critique_1
                            quality_gate_result["image_selected"] = 1

                        quality_gate_result["images_generated"] = 2

                        # NATIVE TEXT RENDERING ONLY (Apr 8, 2026)
                        # - ALL typography bucket prompts use Ideogram v3 native text rendering
                        # - Text is included in image generation prompt (not compositor overlay)
                        # - Agent decides text content, position, style, thickness during prompt creation
                        # - No PIL compositor needed - Ideogram renders complete poster with text
                        logger.info("[stream][%s] Typography bucket → Ideogram native text rendering (no compositor)", trace_id)
                    else:
                        # Image 2 generation failed - use Image 1
                        logger.warning("[stream][%s] Image 2 generation failed - using Image 1", trace_id)
                        quality_gate_result["image_2_gen_failed"] = True
                        quality_gate_result["images_generated"] = 1

            except Exception as _qg_err:
                logger.warning("[stream][%s] Quality Critic failed (non-fatal): %s", trace_id, _qg_err)
                quality_gate_result = None

        total_time = time.time() - start

        # Safe extraction of gen fields
        all_urls = gen.get("all_urls") or ([raw_hero_url] if raw_hero_url else [])

        # ── Store in Smart Cache ─────────────────────────────────────────
        if _CACHE_ENABLED and _smart_cache and not cache_result:
            try:
                await asyncio.to_thread(
                    _smart_cache.store_result,
                    prompt=req.prompt,
                    mode=f"w{req.width}h{req.height}",
                    identity_id=None,  # Add user_id when auth implemented
                    images=[{
                        "image_url": final_image_url,
                        "seed": gen.get("seed"),
                        "model_used": _MODEL_LABELS.get(gen.get("model_key", fal_model_key), gen.get("model_key", fal_model_key)),
                        "backend": gen.get("backend", "fal.ai"),
                        "quality_score": quality_gate_result.get("total") if quality_gate_result else None,
                    }],
                    parsed_prompt=brief,
                    execution_plan={"bucket": bucket, "model": fal_model_key},
                    quality_tier=quality,
                    style=req.style,
                )
                logger.info("[stream][%s] Result cached successfully", trace_id)
            except Exception as store_err:
                logger.warning("[stream][%s] Cache store failed (non-fatal): %s", trace_id, store_err)

        yield _sse("final_ready", {
            "success":           True,
            "image_url":         final_image_url,
            "all_urls":          all_urls,
            "enhanced_prompt":   enhanced_prompt,
            "original_prompt":   req.prompt,
            "model_used":        _MODEL_LABELS.get(gen.get("model_key", fal_model_key), gen.get("model_key", fal_model_key)),
            "backend":           gen.get("backend", "fal.ai"),
            "capability_bucket": bucket,
            "prompt_engine":     brief.get("_source", "heuristic"),
            "generation_time":   gen.get("generation_time", generation_time),
            "total_time":        total_time,
            "quality_score":          quality_gate_result.get("total") if quality_gate_result else None,
            "quality_gate":           quality_gate_result,
            "image_url_experimental": gen_experimental.get("image_url") if gen_experimental and gen_experimental.get("success") else None,
            "poster_composite_status": composite_status,
            # Poster / inline editor fields
            "ad_copy":      ad_copy,
            "poster_design": poster_design,
            "hero_url":     raw_hero_url,
            "design_brief": _design_brief,
            # Brief summary
            "brief": {
                "visual_concept": brief.get("visual_concept", ""),
                "mood":           brief.get("mood", ""),
                "lighting":       brief.get("lighting", ""),
                "camera":         brief.get("camera", ""),
            },
            # Creative OS
            "creative_os": {
                "intent": {
                    "creative_type": intent.get("creative_type", ""),
                    "platform":      intent.get("platform", {}).get("name", "unknown"),
                    "goal":          intent.get("goal", ""),
                    "is_ad":         intent.get("is_ad", False),
                },
                "generation": {
                    "backend":           gen.get("backend", "fal.ai"),
                    "model":             gen.get("model_key", fal_model_key),
                    "capability_bucket": bucket,
                    "prompt_engine":     brief.get("_source", "heuristic"),
                    "generation_time":   gen.get("generation_time", generation_time),
                },
            },
            "trace_id": trace_id,
        })

        # ── Learning Engine: Log generation for continuous improvement ────────
        try:
            from app.services.smart.learning_engine import LearningEngine

            learning = LearningEngine()
            await learning.log_generation(
                brief=brief,
                quality_result=quality_gate_result or {},
                generation_time_ms=int(total_time * 1000),
                cost_usd=0.0,  # TODO: Calculate from fal.ai pricing
                user_feedback=None,  # Will be updated via separate API when user gives thumbs up/down
            )
            logger.info("[stream][%s] generation logged to learning engine", trace_id)
        except Exception as _le_err:
            logger.warning("[stream][%s] learning engine logging failed (non-fatal): %s", trace_id, _le_err)

    except asyncio.CancelledError:
        logger.info("[stream][%s] client disconnected, aborting pipeline", trace_id)
        raise

    except Exception as exc:
        logger.exception("[stream][%s] pipeline error: %s", trace_id, exc)
        yield _sse("error", {
            "message":  f"{type(exc).__name__}: {exc}",
            "stage":    "unknown",
            "elapsed":  time.time() - start,
            "trace_id": trace_id,
        })


async def _parallel_model_stream(req: StreamRequest, trace_id: str) -> AsyncIterator[str]:
    """
    Parallel multi-model generation for admin testing.

    Flow:
    1. Detect bucket from prompt
    2. Fetch DB models: isActive=True, isTestingEnabled=True, bucket in model.buckets
    3. For each model, get all tiers it supports from MODEL_SUPPORTED_TIERS
    4. Generate (model, tier) pair in parallel — each at all tiers it supports
    """
    try:
        from prisma import Prisma
        from app.services.smart.config import detect_capability_bucket
        from app.services.smart.model_config import get_model_supported_tiers

        # Detect bucket from prompt
        bucket = detect_capability_bucket(req.prompt)
        # Normalize sub-bucket for DB lookup (photorealism_landscape → photorealism)
        db_bucket = bucket.split("_")[0] if "_" in bucket else bucket

        yield _sse("intent_ready", {
            "bucket": bucket,
            "trace_id": trace_id,
            "testing_mode": True,
        })

        # Fetch active testing-enabled models from DB, filtered by bucket
        prisma = Prisma()
        await prisma.connect()
        all_models = await prisma.modelconfig.find_many(
            where={"isActive": True, "isTestingEnabled": True}
        )
        await prisma.disconnect()

        # Filter: keep models whose buckets list includes this bucket
        bucket_models = [
            m for m in all_models
            if bucket in (m.buckets or []) or db_bucket in (m.buckets or [])
        ]

        if not bucket_models:
            yield _sse("error", {"message": f"No testing-enabled models found for bucket: {bucket}"})
            return

        # Img2Img filter — when a reference image is provided, only run models
        # that actually wire `image_url` through to the provider. Everything
        # else would silently drop the reference (Seedream/Ideogram/Recraft/
        # Wan/Grok payloads + Google + WaveSpeed). For typography this means
        # showing parallel results from Flux family models that respect the ref.
        if req.reference_image_url:
            before = len(bucket_models)
            bucket_models = [
                m for m in bucket_models
                if _canonical_model_key(m.modelId, default=m.modelId) in _IMG2IMG_CAPABLE_MODELS
            ]
            logger.info(
                "[parallel][%s] Img2Img filter: %d → %d capable models for bucket=%s",
                trace_id, before, len(bucket_models), bucket,
            )
            if not bucket_models:
                # No capable models in admin DB — fall back to single Kontext
                # variant rather than failing the request.
                fallback_key = _pick_img2img_model(req.quality)
                logger.warning(
                    "[parallel][%s] No img2img-capable models in DB for bucket=%s — "
                    "falling back to single %s",
                    trace_id, bucket, fallback_key,
                )
                yield _sse("testing_started", {
                    "bucket": bucket, "total": 1, "models": [fallback_key],
                    "trace_id": trace_id, "img2img_fallback": True,
                })
                result = await _generate_with_model(req, fallback_key, trace_id, quality_override=req.quality)
                if result:
                    yield _sse("model_result", {
                        "generationId": result.get("generation_id"),
                        "imageUrl":     result.get("image_url"),
                        "modelId":      result.get("model_id"),
                        "tier":         result.get("tier"),
                        "latency":      result.get("latency"),
                        "cost":         result.get("cost"),
                        "completed":    1,
                        "total":        1,
                        "trace_id":     trace_id,
                    })
                yield _sse("testing_complete", {
                    "total": 1, "completed": 1 if result else 0,
                    "bucket": bucket, "trace_id": trace_id,
                })
                return

        # Build (model_key, tier) pairs — STRICT tier match. Only models that
        # support the user's selected tier are included. 1k-only models are
        # skipped when user picks 2k/4k; 1k+2k models are skipped when user
        # picks 4k. One generation per capable model at exactly the user's tier.
        _VALID_TIERS = {"1k", "2k", "4k"}
        requested_tier = req.quality if req.quality in _VALID_TIERS else "1k"

        test_pairs = []
        seen = set()
        skipped = []
        for m in bucket_models:
            model_key = _canonical_model_key(m.modelId, default=m.modelId)
            supported = get_model_supported_tiers(model_key)
            if requested_tier not in supported:
                skipped.append(model_key)
                continue
            pair = (model_key, requested_tier)
            if pair not in seen:
                seen.add(pair)
                test_pairs.append(pair)

        if skipped:
            logger.info(
                "[parallel][%s] tier=%s — skipped %d non-capable models: %s",
                trace_id, requested_tier, len(skipped), skipped,
            )

        logger.info(
            "[parallel][%s] bucket=%s — %d models × tiers = %d generations: %s",
            trace_id, bucket, len(bucket_models), len(test_pairs), test_pairs,
        )

        yield _sse("testing_started", {
            "bucket":       bucket,
            "total":        len(test_pairs),
            "models":       list({m for m, _ in test_pairs}),
            "trace_id":     trace_id,
        })

        # Enrich the raw prompt ONCE before dispatching to all models. Without
        # this, vague prompts ("ek artist ka song launch poster") cause models
        # to render placeholder text like [ARTIST'S NAME], invent fake names,
        # or use wrong date formats. Same enriched prompt → same input for all
        # models → comparison stays fair.
        # Preserve the raw user prompt — it gets stored as originalPrompt in
        # the DB (VarChar(1000)) and is what the admin UI displays. The long
        # enriched version goes to the image models via req.prompt.
        raw_user_prompt = req.prompt
        try:
            from app.services.smart.simple_prompt_engine import simple_engine
            enrich = await simple_engine.enrich(
                user_prompt=req.prompt,
                bucket=db_bucket,
                tier=requested_tier,
                width=req.width,
                height=req.height,
                style=req.style,
            )
            enriched_prompt = enrich.get("prompt") or req.prompt
            enriched_neg = enrich.get("negative_prompt") or (req.negative_prompt or "")
            logger.info(
                "[parallel][%s] enriched prompt via simple_engine (raw=%d chars, enriched=%d chars)",
                trace_id, len(req.prompt), len(enriched_prompt),
            )
            req.prompt = enriched_prompt
            if not req.negative_prompt:
                req.negative_prompt = enriched_neg
        except Exception as exc:
            logger.warning("[parallel][%s] simple_engine enrich failed, using raw prompt: %s", trace_id, exc)
        # Stash raw prompt on req so _generate_with_model can use it for
        # originalPrompt at DB save time (VarChar(1000) limit).
        setattr(req, "_raw_user_prompt", raw_user_prompt)

        # Launch all (model, tier) pairs in parallel — wrap as Tasks so we can
        # interleave heartbeat events while waiting. Heartbeats (every ~15s)
        # keep the nginx/Cloudflare SSE proxy connection alive during long
        # (80–120s) gens like Hunyuan. Without them the proxy idle-timeouts
        # and the client never receives the final model_result.
        tasks = [
            asyncio.create_task(
                _generate_with_model(req, model_id, trace_id, quality_override=tier)
            )
            for model_id, tier in test_pairs
        ]

        completed = 0
        pending = set(tasks)
        heartbeat_interval = 15  # seconds
        parallel_started_at = time.time()

        while pending:
            done, pending = await asyncio.wait(
                pending,
                timeout=heartbeat_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if not done:
                # Nothing finished in this window — emit a heartbeat so the
                # SSE connection doesn't sit silent long enough for nginx
                # (default proxy_read_timeout=60s) to drop it.
                yield _sse("heartbeat", {
                    "t":         int(time.time()),
                    "elapsed":   int(time.time() - parallel_started_at),
                    "completed": completed,
                    "total":     len(tasks),
                    "trace_id":  trace_id,
                })
                continue

            for task in done:
                try:
                    result = task.result()
                except Exception as e:
                    logger.error("[parallel][%s] task failed: %s", trace_id, e, exc_info=True)
                    result = None
                completed += 1
                if result:
                    yield _sse("model_result", {
                        "generationId": result.get("generation_id"),
                        "imageUrl":     result.get("image_url"),
                        "modelId":      result.get("model_id"),
                        "tier":         result.get("tier"),
                        "latency":      result.get("latency"),
                        "cost":         result.get("cost"),
                        "completed":    completed,
                        "total":        len(tasks),
                        "trace_id":     trace_id,
                    })

        yield _sse("testing_complete", {
            "total":     len(test_pairs),
            "completed": completed,
            "bucket":    bucket,
            "trace_id":  trace_id,
        })

    except Exception as e:
        logger.error(f"[parallel][{trace_id}] Error: {e}", exc_info=True)
        yield _sse("error", {"message": str(e)})


async def _generate_with_model(
    req: StreamRequest,
    model_id: str,
    trace_id: str,
    quality_override: Optional[str] = None,
) -> dict:
    """
    Generate with a specific model.

    Args:
        quality_override: If set, use this tier instead of req.quality.
                          Used in testing mode so each model generates at its own max resolution.

    Returns:
        {
            "generation_id": str,
            "image_url": str,
            "model_id": str,
            "latency": float,
            "cost": float,
        }
    """
    start = time.time()
    requested_model_id = model_id
    model_id = _canonical_model_key(model_id, default=model_id)
    effective_quality = quality_override or req.quality

    try:
        from app.services.external.multi_provider_client import multi_client
        from prisma import Prisma

        # Generate image
        result = await multi_client.generate(
            prompt=req.prompt,
            model_key=model_id,
            image_size=_pick_image_size(req.width, req.height),
            num_images=1,
            num_inference_steps=_QUALITY_STEPS.get(effective_quality, 20),
            guidance_scale=_MODEL_GUIDANCE.get(model_id, _DEFAULT_GUIDANCE),
            negative_prompt=req.negative_prompt or "",
            reference_image_url=req.reference_image_url,
        )

        latency = time.time() - start

        if not result.get("success"):
            logger.warning(
                f"[parallel][{trace_id}][{requested_model_id}->{model_id}] "
                f"Generation failed: {result.get('error')}"
            )
            return None

        # Save to database (Generation model)
        generation = None
        model_config = None
        try:
            prisma = Prisma()
            await prisma.connect()

            from app.services.smart.config import detect_capability_bucket
            bucket = detect_capability_bucket(req.prompt)

            # originalPrompt is VarChar(1000); enhancedPrompt is Text (unlimited).
            # Use the raw user prompt for originalPrompt (what admin UI shows)
            # and the long enriched prompt for enhancedPrompt.
            raw_prompt = getattr(req, "_raw_user_prompt", req.prompt) or req.prompt
            original_prompt = raw_prompt[:1000]

            generation = await prisma.generation.create(
                data={
                    "userId": "ee10a6d4-a124-4fea-ac1f-395d4f3adb6c",  # DEV_USER UUID
                    "mode": "REALISM",  # Default mode
                    "originalPrompt": original_prompt,
                    "enhancedPrompt": req.prompt,
                    "numInferenceSteps": _QUALITY_STEPS.get(effective_quality, 20),
                    "guidanceScale": _MODEL_GUIDANCE.get(model_id, _DEFAULT_GUIDANCE),
                    "width": req.width,
                    "height": req.height,
                    "outputUrls": json.dumps([result.get("image_url")]),  # JSON string
                    "selectedOutputUrl": result.get("image_url"),
                    "creditsUsed": 0,  # Testing mode = free
                    "qualityTierUsed": effective_quality,
                    "modelUsed": model_id,
                    "bucket": bucket,
                    "generationTimeSeconds": latency,
                }
            )

            # Get model cost
            model_config = await prisma.modelconfig.find_unique(
                where={"modelId": model_id}
            )
            if not model_config and requested_model_id != model_id:
                model_config = await prisma.modelconfig.find_unique(
                    where={"modelId": requested_model_id}
                )

            await prisma.disconnect()

        except Exception as db_error:
            logger.warning(f"[parallel][{trace_id}][{model_id}] DB save failed: {db_error}")
            generation_id = None
        
        return {
            "generation_id": generation.id if generation else None,
            "image_url": result.get("image_url"),
            "model_id": model_id,
            "tier": effective_quality,
            "latency": latency,
            "cost": model_config.costPerImage if model_config and hasattr(model_config, "costPerImage") else 0.0,
        }

    except Exception as e:
        logger.error(f"[parallel][{trace_id}][{model_id}] Error: {e}", exc_info=True)
        return None


@router.post("/generate/stream")
async def stream_generate(req: StreamRequest, request: Request):
    """
    Generate image(s) with SSE streaming.

    Args:
        req: Generation parameters (includes testing_mode for admin)
        request: FastAPI request object
    """
    trace_id = str(uuid.uuid4())[:8]

    # Check if testing mode is enabled (from request body or system config)
    testing_enabled = req.testing_mode or _parse_bool_env("TESTING_MODE_ENABLED", False)

    # Img2Img routing: when a reference image is supplied, only typography
    # benefits from admin parallel mode (multiple text-rendering models compared
    # head-to-head). Non-typography img2img always uses the single-model Flux
    # Kontext path — running Imagen / WaveSpeed in parallel would just produce
    # reference-blind text-to-image variants.
    use_parallel = testing_enabled
    if testing_enabled and req.reference_image_url:
        from app.services.smart.config import detect_capability_bucket
        _bucket_for_dispatch = detect_capability_bucket(req.prompt)
        if _bucket_for_dispatch != "typography":
            use_parallel = False
            logger.info(
                "[stream][%s] Img2Img + non-typography (%s) → single-model Kontext path (skip admin parallel)",
                trace_id, _bucket_for_dispatch,
            )

    async def _guarded() -> AsyncIterator[str]:
        if use_parallel:
            # PARALLEL TESTING MODE - generate from multiple models
            async for chunk in _parallel_model_stream(req, trace_id):
                if await request.is_disconnected():
                    logger.info("[stream][%s] client disconnected mid-stream", trace_id)
                    return
                yield chunk
        else:
            # NORMAL MODE - single model generation
            async for chunk in _stream_pipeline(req, trace_id):
                if await request.is_disconnected():
                    logger.info("[stream][%s] client disconnected mid-stream", trace_id)
                    return
                yield chunk

    return StreamingResponse(
        _guarded(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

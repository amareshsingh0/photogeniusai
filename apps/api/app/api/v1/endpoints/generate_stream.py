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
from typing import AsyncIterator, Optional

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)
router = APIRouter(tags=["streaming"])

# ── Module-level HTTP client (connection-pooled, reused across requests) ─────
_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    return _http_client


_MODEL_LABELS = {
    "flux_2_pro":        "Flux 2 Pro",
    "flux_2_dev":        "Flux 2 Dev",
    "flux_2_turbo":      "Flux 2 Turbo",
    "flux_2_max":        "Flux 2 Max",
    "flux_pro":          "Flux 2 Pro",
    "flux_schnell":      "Flux Schnell",
    "flux_dev":          "Flux 2 Dev",
    "flux_redux":        "Flux Redux",
    "flux_fill":         "Flux Fill",
    "ideogram_turbo":    "Ideogram v3 Turbo",
    "ideogram_quality":  "Ideogram v3 Quality",
    "recraft_v4":        "Recraft v4",
    "recraft_v4_svg":    "Recraft v4 SVG",
    "hunyuan_image":     "Hunyuan Image",
    "flux_kontext":      "Flux Kontext",
    "flux_kontext_max":  "Flux Kontext Max",
}

_MODEL_ALIASES = {
    "flux_pro": "flux_2_pro",
    "flux_dev": "flux_2_dev",
    "flux_schnell_fal": "flux_schnell",
    "flux_schnell_pixazo": "flux_schnell",
}

_QUALITY_SECONDS = {
    "fast":     8,
    "balanced": 25,
    "quality":  45,
    "ultra":    60,
}

# Per-quality inference steps (honoring all 4 tiers)
_QUALITY_STEPS = {
    "fast":     8,
    "balanced": 20,
    "quality":  35,
    "ultra":    50,
}

# guidance_scale per model family
_MODEL_GUIDANCE = {
    "ideogram_turbo":   3.0,
    "ideogram_quality": 3.0,
    "recraft_v4":       4.0,
    "recraft_v4_svg":   4.0,
    "hunyuan_image":    4.0,
}
_DEFAULT_GUIDANCE = 3.5


def _parse_bool_env(name: str, default: bool = True) -> bool:
    """Parse env flag: false/0/no/off → False, anything else → True."""
    val = os.getenv(name, "").strip().lower()
    if not val:
        return default
    return val not in ("false", "0", "no", "off")


class StreamRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)
    quality: Optional[str] = Field(default="balanced")
    style: Optional[str] = Field(default=None)
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    reference_image_url: Optional[str] = Field(default=None)
    negative_prompt: Optional[str] = Field(default=None)
    brand_kit: Optional[dict] = Field(default=None)
    prompt_dna: Optional[dict] = Field(default=None)   # User.preferences.prompt_dna from Next.js

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: Optional[str]) -> str:
        allowed = ("fast", "balanced", "quality", "ultra")
        if not v or v.lower() not in allowed:
            return "balanced"
        return v.lower()

    @field_validator("width", "height")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        # Snap to nearest 64
        return max(256, min(2048, round(v / 64) * 64))


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
    normalized = (model_key or "").strip().lower().replace(" ", "_").replace(".", "_").replace("-", "_")
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

    try:
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
        from app.services.smart.config import detect_capability_bucket, get_model_config

        bucket = detect_capability_bucket(req.prompt)
        model_cfg = get_model_config(bucket, quality)

        fal_model_key = _canonical_model_key(model_cfg.get("model"), default="flux_2_pro")
        if not model_cfg.get("model"):
            fal_model_key = "flux_2_pro"
            logger.warning("[stream][%s] model_cfg missing 'model' key for bucket=%s quality=%s, falling back to flux_2_pro", trace_id, bucket, quality)

        # Ideogram fallback
        use_ideogram = _parse_bool_env("USE_IDEOGRAM", default=True)
        if not use_ideogram and fal_model_key in ("ideogram_turbo", "ideogram_quality"):
            fal_model_key = "flux_2_pro"
            logger.info("[stream][%s] Ideogram disabled (USE_IDEOGRAM=false), using flux_2_pro", trace_id)

        model_label = _MODEL_LABELS.get(fal_model_key, fal_model_key)
        num_images = model_cfg.get("num_images", 1)

        # ── Stage A: Creative Brief ────────────────────────────────────────
        from app.services.smart.gemini_prompt_engine import gemini_prompt_engine
        brief: dict

        if bucket == "typography":
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
                brief = await gemini_prompt_engine.create_brief(
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
            brief = await gemini_prompt_engine.create_brief(
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
        if req.width == 1024 and req.height == 1024:
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
        params = await gemini_prompt_engine.build_params(brief, model_label, bucket)
        enhanced_prompt = params.get("prompt") or req.prompt
        negative_prompt = params.get("negative_prompt", "")
        if req.negative_prompt is not None:
            negative_prompt = f"{req.negative_prompt}, {negative_prompt}" if negative_prompt else req.negative_prompt

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

        # Dual Variant (Phase 6): premium/ultra + creative_bible → Safe + Experimental in parallel
        _creative_bible = brief.get("creative_bible") or {}
        _run_dual = (
            quality in ("quality", "ultra")
            and bool(_creative_bible.get("visual_metaphors"))
        )
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

        # ── Stage C: Poster compositor (RE-ENABLED for ad text overlay) ────
        if bucket == "typography" and isinstance(ad_copy, dict) and ad_copy.get("headline"):
            yield _sse("compositing", {
                "message":  "Applying text layout",
                "trace_id": trace_id,
            })
            try:
                from app.services.smart.poster_compositor import poster_compositor

                http = _get_http_client()
                img_resp = await http.get(raw_hero_url)
                img_resp.raise_for_status()
                img_b64 = base64.b64encode(img_resp.content).decode("ascii")

                composed_b64 = await asyncio.to_thread(
                    poster_compositor.composite,
                    hero_b64=img_b64,
                    ad_copy=ad_copy,
                    poster_design=poster_design,
                    elements=brief.get("elements", []),
                    target_width=effective_width,
                    target_height=min(int(effective_height * 1.5), 3072),
                )
                final_image_url = f"data:image/jpeg;base64,{composed_b64}"
                composite_status = "success"
                logger.info("[stream][%s] PosterCompositor applied: headline=%s features=%d",
                            trace_id,
                            ad_copy.get("headline", ""),
                            len(ad_copy.get("features") or []))

            except Exception as _ov_err:
                logger.warning("[stream][%s] PosterCompositor failed (%s), using raw image", trace_id, _ov_err)
                composite_status = "failed"

        # Build design_brief — only when compositor succeeded
        _design_brief = None
        if bucket == "typography" and isinstance(ad_copy, dict) and composite_status in ("success", "skipped"):
            _design_brief = _build_design_brief(brief, ad_copy, poster_design, raw_hero_url)

# Clean Quality Gate Section (lines 460-720)
# Replace this in generate_stream.py

        # ── Stage D: Beast Quality Critic (Max 2 Images) ──
        quality_gate_result = None
        creative_bible = brief.get("creative_bible") or {}
        _run_quality_gate = (
            quality != "fast"
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

                # Map quality tier to critic tier
                critic_tier = "standard" if quality == "quality" else quality
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
                    "overall_score": critique_1["overall_score"],
                    "verdict": critique_1["verdict"],
                    "dimensions": critique_1["dimensions"],
                    "beast_gates_passed": critique_1["beast_gates_passed"],
                    "beast_gates_total": critique_1["beast_gates_total"],
                    "image_number": 1,
                    "trace_id": trace_id,
                })

                verdict_1 = critique_1["verdict"]
                score_1 = critique_1["overall_score"]

                logger.info("[stream][%s] Image 1: score=%.2f, verdict=%s, gates=%d/%d",
                          trace_id, score_1, verdict_1,
                          critique_1["beast_gates_passed"], critique_1["beast_gates_total"])

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

                    logger.info("[stream][%s] Image 1 REVISE - generating Image 2 (weak: %s)",
                              trace_id, weak_dims)

                    yield _sse("revision_triggered", {
                        "image_number": 2,
                        "route_to": route_to,
                        "notes": revision_notes,
                        "weak_dimensions": weak_dims,
                        "trace_id": trace_id,
                    })

                    # Build targeted prompt with specific fixes
                    mutation_prompt = f"{enhanced_prompt} — IMPROVE: {revision_notes}"[:500]

                    # ━━━ GENERATE IMAGE 2 ━━━
                    gen_2 = await multi_client.generate(
                        model_key=fal_model_key,
                        prompt=mutation_prompt,
                        negative_prompt=negative_prompt,
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
                            "overall_score": critique_2["overall_score"],
                            "verdict": critique_2["verdict"],
                            "dimensions": critique_2["dimensions"],
                            "beast_gates_passed": critique_2["beast_gates_passed"],
                            "beast_gates_total": critique_2["beast_gates_total"],
                            "image_number": 2,
                            "trace_id": trace_id,
                        })

                        score_2 = critique_2["overall_score"]

                        logger.info("[stream][%s] Image 2: score=%.2f, verdict=%s",
                                  trace_id, score_2, critique_2["verdict"])

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

                        # Re-composite if typography bucket
                        if bucket == "typography" and isinstance(ad_copy, dict) and ad_copy.get("headline"):
                            try:
                                from app.services.smart.poster_compositor import poster_compositor as _pc
                                http = _get_http_client()
                                img_resp2 = await http.get(raw_hero_url)
                                img_resp2.raise_for_status()
                                img_b64_retry = base64.b64encode(img_resp2.content).decode("ascii")
                                composed_b64_retry = await asyncio.to_thread(
                                    _pc.composite,
                                    hero_b64=img_b64_retry,
                                    ad_copy=ad_copy,
                                    poster_design=poster_design,
                                    elements=brief.get("elements", []),
                                    target_width=effective_width,
                                    target_height=min(int(effective_height * 1.5), 3072),
                                )
                                final_image_url = f"data:image/jpeg;base64,{composed_b64_retry}"
                            except Exception as _comp_err:
                                logger.warning("[stream][%s] Compositor failed for selected image: %s",
                                             trace_id, _comp_err)
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


@router.post("/generate/stream")
async def stream_generate(req: StreamRequest, request: Request):
    trace_id = str(uuid.uuid4())[:8]

    async def _guarded() -> AsyncIterator[str]:
        async for chunk in _stream_pipeline(req, trace_id):
            # Abort if client disconnected
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

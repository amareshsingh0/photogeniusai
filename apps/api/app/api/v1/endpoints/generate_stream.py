"""
SSE Streaming Generation — POST /api/v1/generate/stream

Events emitted (in order):
  intent_ready   — after Stage -1 Intent Analyzer (<0.2s)
  brief_ready    — after Gemini Creative Brief (1-3s)
  generating     — when fal.ai call starts (immediately after brief)
  final_ready    — when image arrives (~8-60s)
  error          — on failure at any stage
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from typing import AsyncIterator, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["streaming"])

_MODEL_LABELS = {
    "flux_pro":          "Flux Pro",
    "flux_schnell":      "Flux Schnell",
    "flux_dev":          "Flux Dev",
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

_QUALITY_SECONDS = {
    "fast":     8,
    "balanced": 25,
    "quality":  45,
    "ultra":    60,
}


class StreamRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)
    quality: Optional[str] = Field(default="balanced")
    style: Optional[str] = Field(default=None)
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    reference_image_url: Optional[str] = Field(default=None)
    negative_prompt: Optional[str] = Field(default=None)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _pick_image_size(width: int, height: int) -> str:
    if width == height:
        return "square_hd"
    if width > height:
        return "landscape_16_9" if (width / height) >= 1.6 else "landscape_4_3"
    return "portrait_9_16" if (height / width) >= 1.6 else "portrait_4_3"


async def _stream_pipeline(req: StreamRequest) -> AsyncIterator[str]:
    start = time.time()
    quality = (req.quality or "balanced").lower()
    if quality not in ("fast", "balanced", "quality", "ultra"):
        quality = "balanced"

    try:
        # ── Stage -1: Intent ───────────────────────────────────────────────
        from app.services.smart.intent_analyzer import intent_analyzer
        intent = intent_analyzer.analyze(req.prompt, req.width, req.height)
        yield _sse("intent_ready", {
            "creative_type": intent["creative_type"],
            "is_ad":         intent["is_ad"],
            "goal":          intent["goal"],
            "audience_tone": intent["audience_tone"],
        })

        # ── Capability routing ─────────────────────────────────────────────
        from app.services.smart.config import detect_capability_bucket, get_model_config, TIER_ALIASES
        bucket = detect_capability_bucket(req.prompt)
        model_cfg = get_model_config(bucket, quality)

        fal_model_key = model_cfg["model"]
        # Ideogram fallback: only override if explicitly disabled AND backend tag matches
        use_ideogram = os.getenv("USE_IDEOGRAM", "true").lower() != "false"
        if not use_ideogram and fal_model_key in ("ideogram_turbo", "ideogram_quality"):
            fal_model_key = "flux_pro"
            logger.info("[stream] Ideogram disabled (USE_IDEOGRAM=false), using flux_pro")

        model_label = _MODEL_LABELS.get(fal_model_key, fal_model_key)

        # ── Stage A: Gemini Creative Brief ─────────────────────────────────
        from app.services.smart.gemini_prompt_engine import gemini_prompt_engine
        _ctx = (
            f"creative_type={intent['creative_type']}, "
            f"goal={intent['goal']}, "
            f"audience={intent['audience_tone']}"
        )
        brief = gemini_prompt_engine.create_brief(
            req.prompt,
            creative_type=intent["creative_type"],
            style=req.style or "photo",
            extra_context=_ctx,
            bucket=bucket,
        )
        yield _sse("brief_ready", {
            "visual_concept": brief.get("visual_concept", ""),
            "subject":        brief.get("subject", ""),
            "lighting":       brief.get("lighting", ""),
            "camera":         brief.get("camera", ""),
            "mood":           brief.get("mood", ""),
            "color_palette":  brief.get("color_palette", ""),
            "style_refs":     brief.get("style_refs", []),
            "source":         brief.get("_source", "heuristic"),
            "ad_copy":        brief.get("ad_copy"),      # present for typography bucket
        })

        # ── Stage B: Build generation params ──────────────────────────────
        params = gemini_prompt_engine.build_params(brief, model_label, bucket)
        enhanced_prompt = params.get("prompt", req.prompt)
        negative_prompt = params.get("negative_prompt", "")
        if req.negative_prompt:
            negative_prompt = f"{req.negative_prompt}, {negative_prompt}"

        # ── Generating event ───────────────────────────────────────────────
        yield _sse("generating", {
            "model":                   model_label,
            "bucket":                  bucket,
            "estimated_seconds":       _QUALITY_SECONDS.get(quality, 25),
            "enhanced_prompt_preview": enhanced_prompt[:120],
        })

        # ── Generation via multi-provider client ───────────────────────────
        from app.services.external.multi_provider_client import multi_client
        num_images = model_cfg.get("num_images", 1)

        gen = await multi_client.generate(
            model_key=fal_model_key,
            prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
            num_images=1,
            image_size=_pick_image_size(req.width, req.height),
            num_inference_steps=8 if quality == "fast" else 28,
            guidance_scale=3.5,
            reference_image_url=req.reference_image_url,
            rendering_speed=model_cfg.get("rendering_speed", "BALANCED"),
        )

        elapsed = time.time() - start

        if not gen.get("success"):
            yield _sse("error", {
                "message": gen.get("error") or gen.get("metadata", {}).get("error", "Generation failed"),
                "elapsed": elapsed,
            })
            return

        # ── Stage C: Full poster compositor for typography bucket ───────────
        # Uses PosterCompositor: structured multi-zone poster (brand bar,
        # hero, headline, feature grid, CTA button, footer) — like a real
        # design tool, not just text slapped on top of an image.
        final_image_url = gen["image_url"]
        ad_copy = brief.get("ad_copy")
        poster_design = brief.get("poster_design")
        if bucket == "typography" and ad_copy:
            try:
                import httpx
                from app.services.smart.poster_compositor import poster_compositor

                # Fetch the Ideogram background image
                async with httpx.AsyncClient(timeout=30.0) as client:
                    img_resp = await client.get(final_image_url)
                img_b64 = base64.b64encode(img_resp.content).decode("ascii")

                # Build full structured poster
                composed_b64 = poster_compositor.composite(
                    hero_b64=img_b64,
                    ad_copy=ad_copy,
                    poster_design=poster_design,
                    target_width=req.width or 1024,
                    target_height=int((req.height or 1024) * 1.5),  # extend to poster ratio
                )
                final_image_url = f"data:image/jpeg;base64,{composed_b64}"
                logger.info("[stream] PosterCompositor applied: headline=%s features=%d",
                            ad_copy.get("headline",""), len(ad_copy.get("features") or []))

            except Exception as _ov_err:
                logger.warning("[stream] PosterCompositor failed (%s), using raw image", _ov_err)

        yield _sse("final_ready", {
            "success":           True,
            "image_url":         final_image_url,
            "all_urls":          gen.get("all_urls", [gen["image_url"]]),
            "enhanced_prompt":   enhanced_prompt,
            "original_prompt":   req.prompt,
            "model_used":        _MODEL_LABELS.get(gen.get("model", fal_model_key), gen.get("model", fal_model_key)),
            "backend":           gen.get("backend", "fal.ai"),
            "capability_bucket": bucket,
            "prompt_engine":     brief.get("_source", "heuristic"),
            "generation_time":   gen["generation_time"],
            "total_time":        elapsed,
            "quality_score":     None,
            "brief": {
                "visual_concept": brief.get("visual_concept", ""),
                "mood":           brief.get("mood", ""),
                "lighting":       brief.get("lighting", ""),
                "camera":         brief.get("camera", ""),
            },
            "creative_os": {
                "intent": {
                    "creative_type": intent["creative_type"],
                    "platform":      intent["platform"]["name"],
                    "goal":          intent["goal"],
                    "is_ad":         intent["is_ad"],
                },
                "generation": {
                    "backend":           gen["backend"],
                    "model":             gen["model"],
                    "capability_bucket": bucket,
                    "prompt_engine":     brief.get("_source", "heuristic"),
                    "generation_time":   gen["generation_time"],
                },
            },
        })

    except Exception as exc:
        logger.exception("[stream] pipeline error: %s", exc)
        yield _sse("error", {
            "message": f"{type(exc).__name__}: {exc}",
            "elapsed": time.time() - start,
        })


@router.post("/generate/stream")
async def stream_generate(req: StreamRequest):
    return StreamingResponse(
        _stream_pipeline(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )

"""
Poster Recompose + Pack — Sprint 4 (hardened)

POST /api/v1/poster/recompose
  Body: { hero_url, ad_copy, poster_design, width, height }
  → Fetch hero image → PosterCompositor.composite() → { image_b64 }
  Used by: poster-inline-editor.tsx for live re-render on copy/color change

POST /api/v1/poster/pack
  Body: { hero_url, ad_copy, poster_design, include }
  → asyncio.gather() → 4 concurrent compositor calls (1:1, 9:16, 16:9, 4:5)
  → { sizes: { "1:1": {...}, ... }, failed: [...], elapsed }
  Used by: poster-pack-modal.tsx "Download Pack" button
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.smart.poster_compositor import poster_compositor

logger = logging.getLogger(__name__)
router = APIRouter(tags=["poster"])

# ── Constants ─────────────────────────────────────────────────────────────────

_PACK_SIZES: Dict[str, Dict[str, int]] = {
    "1:1":  {"w": 1024, "h": 1024},
    "9:16": {"w": 1080, "h": 1920},
    "16:9": {"w": 1920, "h": 1080},
    "4:5":  {"w": 1080, "h": 1350},
}

# Normalized hero zone values that the compositor supports
_HERO_OCCUPIES_BY_RATIO: Dict[str, str] = {
    "1:1":  "top_60",
    "9:16": "top_55",
    "16:9": "top_40",
    "4:5":  "top_58",   # ← added to compositor hero_h_map
}

_VALID_HERO_ZONES = frozenset(_HERO_OCCUPIES_BY_RATIO.values()) | {"center_50", "full_bleed", "top_50"}
_VALID_SIZES      = frozenset(_PACK_SIZES.keys())

# Max hero image bytes to fetch (20 MB)
_MAX_IMAGE_BYTES = 20 * 1024 * 1024

# Dedicated bounded executor — prevents compositor from starving async I/O
_compositor_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="compositor")

# Shared httpx client — connection pooling, no per-request handshake overhead
_http_client = httpx.AsyncClient(
    timeout=30.0,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
)

# ── Request models ─────────────────────────────────────────────────────────────

class Feature(BaseModel):
    icon:  str = "●"
    title: str = ""
    desc:  str = ""


class AdCopy(BaseModel):
    brand_name:  str           = ""
    headline:    str           = "HEADLINE"
    subheadline: str           = ""
    body:        str           = ""
    cta:         str           = "GET STARTED"
    cta_url:     str           = ""
    tagline:     str           = ""
    features:    List[Feature] = Field(default_factory=list)


class PosterDesign(BaseModel):
    layout:               str  = "hero_top_features_bottom"
    accent_color:         str  = "#F59E0B"
    bg_color:             str  = "#0F172A"
    text_color_primary:   str  = "#FFFFFF"
    text_color_secondary: str  = "#CBD5E1"
    font_style:           str  = "bold_tech"
    has_feature_grid:     bool = True
    has_cta_button:       bool = True
    hero_occupies:        str  = "top_60"

    @field_validator("hero_occupies")
    @classmethod
    def _normalize_hero_zone(cls, v: str) -> str:
        """Accept any supported zone string; fallback to top_60."""
        return v if v in _VALID_HERO_ZONES else "top_60"


class RecomposeRequest(BaseModel):
    hero_url:     str = Field(..., description="Raw image URL or data:image/... URI")
    ad_copy:      AdCopy
    poster_design: PosterDesign
    width:        int = Field(default=1024, ge=256, le=2048)
    height:       int = Field(default=1536, ge=256, le=3072)


class PackRequest(BaseModel):
    hero_url:     str = Field(..., description="Raw image URL or data:image/... URI")
    ad_copy:      AdCopy
    poster_design: PosterDesign
    include:      List[Literal["1:1", "9:16", "16:9", "4:5"]] = Field(
        default_factory=lambda: ["1:1", "9:16", "16:9", "4:5"],
        description="Sizes to generate — validated at Pydantic layer",
    )


# ── Response models ────────────────────────────────────────────────────────────

class RecomposeResponse(BaseModel):
    success:        bool
    image_b64:      str
    image_data_uri: str
    elapsed:        float


class PackSizeResult(BaseModel):
    image_b64:      str
    image_data_uri: str
    width:          int
    height:         int


class PackResponse(BaseModel):
    success:        bool
    partial:        bool
    sizes:          Dict[str, PackSizeResult]
    failed:         List[str]
    count:          int
    elapsed:        float


# ── SSRF guard ─────────────────────────────────────────────────────────────────

_PRIVATE_PREFIXES = ("127.", "10.", "192.168.", "169.254.", "::1", "0.0.0.0")

def _assert_safe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "Only http/https URLs are allowed")
    host = (parsed.hostname or "").lower()
    if host in ("localhost",) or any(host.startswith(p) for p in _PRIVATE_PREFIXES):
        raise HTTPException(400, "Private/internal URLs are not allowed")


# ── Hero fetch ─────────────────────────────────────────────────────────────────

async def _fetch_hero_b64(url: str) -> str:
    """Fetch hero image and return raw base64. Validates MIME + size + SSRF."""
    if url.startswith("data:"):
        if "," not in url:
            raise HTTPException(400, "Malformed data URI — missing comma separator")
        header, payload = url.split(",", 1)
        if not payload:
            raise HTTPException(400, "Empty data URI payload")
        if ";base64" not in header:
            raise HTTPException(400, "Only base64-encoded data URIs are supported")
        if not any(t in header for t in ("image/png", "image/jpeg", "image/webp")):
            raise HTTPException(400, "Non-image data URI rejected")
        return payload

    _assert_safe_url(url)

    chunks: list[bytes] = []
    total = 0
    try:
        async with _http_client.stream("GET", url) as resp:
            if resp.status_code != 200:
                raise HTTPException(502, f"Failed to fetch hero image: HTTP {resp.status_code}")
            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise HTTPException(502, f"Hero URL returned non-image content-type: {content_type!r}")
            async for chunk in resp.aiter_bytes(65536):
                chunks.append(chunk)
                total += len(chunk)
                if total > _MAX_IMAGE_BYTES:
                    raise HTTPException(413, f"Hero image exceeds {_MAX_IMAGE_BYTES // 1_048_576} MB limit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch hero image: {e}") from e

    return base64.b64encode(b"".join(chunks)).decode("ascii")


# ── Compositor wrapper ─────────────────────────────────────────────────────────

def _composite_sync(
    hero_b64:     str,
    ad_copy:      dict,
    poster_design: dict,
    width:        int,
    height:       int,
) -> str:
    """Synchronous compositor call — runs in the bounded thread executor."""
    return poster_compositor.composite(
        hero_b64=hero_b64,
        ad_copy=ad_copy,
        poster_design=poster_design,
        target_width=width,
        target_height=height,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/poster/recompose", response_model=RecomposeResponse)
async def recompose_poster(req: RecomposeRequest) -> RecomposeResponse:
    """
    Re-render a poster with updated copy/colors in ~1-2s (pure PIL, no AI cost).
    Used by the inline poster editor for live preview on each debounced edit.
    """
    t = time.time()

    try:
        hero_b64 = await _fetch_hero_b64(req.hero_url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[recompose] fetch failed: %s", e)
        raise HTTPException(502, str(e)) from e

    try:
        loop = asyncio.get_running_loop()
        composed_b64 = await loop.run_in_executor(
            _compositor_executor,
            _composite_sync,
            hero_b64,
            req.ad_copy.model_dump(),
            req.poster_design.model_dump(),
            req.width,
            req.height,
        )
    except Exception as e:
        logger.error("[recompose] compositor error: %s", e, exc_info=True)
        raise HTTPException(500, f"Compositor error: {e}") from e

    elapsed = round(time.time() - t, 3)
    logger.info("[recompose] done %.2fs (%dx%d)", elapsed, req.width, req.height)

    return RecomposeResponse(
        success=True,
        image_b64=composed_b64,
        image_data_uri=f"data:image/jpeg;base64,{composed_b64}",
        elapsed=elapsed,
    )


@router.post("/poster/pack", response_model=PackResponse)
async def generate_pack(req: PackRequest) -> PackResponse:
    """
    Generate poster in multiple aspect ratios concurrently (PIL only).
    Returns partial success info if some sizes fail.
    """
    t = time.time()

    sizes_to_gen = {k: _PACK_SIZES[k] for k in req.include if k in _PACK_SIZES}
    if not sizes_to_gen:
        raise HTTPException(400, "No valid sizes in request — use 1:1, 9:16, 16:9, or 4:5")

    try:
        hero_b64 = await _fetch_hero_b64(req.hero_url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, str(e)) from e

    # Pre-compute base dicts once (not 4 times)
    ad_copy_dict   = req.ad_copy.model_dump()
    base_design    = req.poster_design.model_dump()
    loop           = asyncio.get_running_loop()

    async def _gen_one(ratio_key: str) -> tuple[str, str]:
        spec = sizes_to_gen[ratio_key]
        design_dict = {
            **base_design,
            "hero_occupies": _HERO_OCCUPIES_BY_RATIO.get(ratio_key, base_design.get("hero_occupies", "top_60")),
        }
        try:
            b64 = await loop.run_in_executor(
                _compositor_executor,
                _composite_sync,
                hero_b64,
                ad_copy_dict,
                design_dict,
                spec["w"],
                spec["h"],
            )
            return ratio_key, b64
        except Exception as e:
            logger.warning("[pack] size %s failed: %s", ratio_key, e)
            return ratio_key, ""

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[_gen_one(k) for k in sizes_to_gen]),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Pack generation timed out after 90s")

    sizes_out: Dict[str, PackSizeResult] = {}
    failed:    List[str] = []
    for ratio_key, b64 in results:
        if b64:
            sizes_out[ratio_key] = PackSizeResult(
                image_b64=b64,
                image_data_uri=f"data:image/jpeg;base64,{b64}",
                width=_PACK_SIZES[ratio_key]["w"],
                height=_PACK_SIZES[ratio_key]["h"],
            )
        else:
            failed.append(ratio_key)

    if not sizes_out:
        raise HTTPException(500, "All sizes failed to generate — compositor error")

    elapsed = round(time.time() - t, 3)
    logger.info("[pack] %d/%d sizes in %.2fs — failed: %s", len(sizes_out), len(sizes_to_gen), elapsed, failed)

    return PackResponse(
        success=len(failed) == 0,
        partial=len(failed) > 0,
        sizes=sizes_out,
        failed=failed,
        count=len(sizes_out),
        elapsed=elapsed,
    )

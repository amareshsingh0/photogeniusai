"""Style Extractor — Gemini Vision describes the visual style of a reference image.

When the user uploads a reference image AND has not specified an explicit style
keyword, this extracts a 2-3 sentence style description (palette, lighting,
texture, atmosphere — NOT subject matter) and feeds it into the Haiku system
prompt as a "style anchor". Haiku then propagates that aesthetic to the new
generation, achieving brand-consistent output across a user's series of
generations.

Priority 6 in `Research/photogenius_upgrade_plan.md`.

Toggle with `USE_STYLE_EXTRACTOR=false` to disable entirely. On any failure
(network, API quota, parse error) returns an empty string so the pipeline
falls back to "no style reference" — never breaks the request path.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

_USE_STYLE_EXTRACTOR = os.getenv("USE_STYLE_EXTRACTOR", "true").lower() not in ("false", "0", "off")
_STYLE_EXTRACTOR_MODEL = os.getenv("STYLE_EXTRACTOR_MODEL", "gemini-2.5-flash")
_STYLE_EXTRACTOR_TIMEOUT = float(os.getenv("STYLE_EXTRACTOR_TIMEOUT_SEC", "10.0"))
_STYLE_EXTRACTOR_MAX_CHARS = int(os.getenv("STYLE_EXTRACTOR_MAX_CHARS", "300"))

# Tight, focused prompt — Vision model knows what to look for, what to skip.
_STYLE_PROMPT = (
    "Describe ONLY the visual style of this image — color palette, lighting "
    "mood, texture/grain, composition style, atmosphere, era/aesthetic anchor "
    "(e.g. 'editorial magazine spread', '90s film grain', 'minimalist studio'). "
    "DO NOT describe the subject matter or what is happening. 2-3 sentences max. "
    "Output the description as plain prose, no headers, no bullet points."
)


# ─────────────────────────────────────────────────────────────────────────────
# Simple in-memory LRU cache keyed by image URL
# ─────────────────────────────────────────────────────────────────────────────
# When the same reference is reused across N generations (very common — user
# uploads once, generates 5 variants), we save N-1 Vision calls.
_CACHE_SIZE = int(os.getenv("STYLE_EXTRACTOR_CACHE_SIZE", "64"))
_cache: Dict[str, str] = {}
_cache_order: list = []  # FIFO order of insertion


def _cache_get(url: str) -> Optional[str]:
    return _cache.get(url)


def _cache_put(url: str, description: str) -> None:
    if url in _cache:
        return
    _cache[url] = description
    _cache_order.append(url)
    while len(_cache_order) > _CACHE_SIZE:
        oldest = _cache_order.pop(0)
        _cache.pop(oldest, None)


async def _fetch_image_base64(image_url: str) -> Optional[str]:
    """Fetch image and return base64 — handles http(s) URLs and data: URIs."""
    if not image_url:
        return None
    if image_url.startswith("data:"):
        comma = image_url.find(",")
        if comma == -1:
            return None
        return image_url[comma + 1 :]
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            follow_redirects=True,
        ) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            return base64.b64encode(resp.content).decode("ascii")
    except Exception as e:
        logger.warning("[style-extractor] image fetch failed for %s: %s", image_url[:80], e)
        return None


async def extract_style_description(image_url: str) -> str:
    """Return a 2-3 sentence visual style description, or empty string on failure.

    Cached per image URL to avoid duplicate Vision calls when the same
    reference is reused across generations.
    """
    if not _USE_STYLE_EXTRACTOR or not image_url:
        return ""

    cached = _cache_get(image_url)
    if cached is not None:
        logger.debug("[style-extractor] cache hit for %s", image_url[:60])
        return cached

    start = time.time()
    image_b64 = await _fetch_image_base64(image_url)
    if not image_b64:
        return ""

    try:
        # Reuse the round-robin Gemini client pool from design_agent_chain.
        from app.services.smart.design_agent_chain import _get_gemini_client

        client = _get_gemini_client()
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=_STYLE_EXTRACTOR_MODEL,
                contents=[{
                    "role": "user",
                    "parts": [
                        {"text": _STYLE_PROMPT},
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    ],
                }],
            ),
            timeout=_STYLE_EXTRACTOR_TIMEOUT,
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            return ""

        # Cap at sane length — never let a runaway response leak into Haiku.
        text = text[:_STYLE_EXTRACTOR_MAX_CHARS].strip()
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info("[style-extractor] %d chars in %dms — %s",
                    len(text), elapsed_ms, text[:80].replace("\n", " "))
        print(f"[STYLE-EXTRACT] {elapsed_ms}ms — {text[:120]}", flush=True)

        _cache_put(image_url, text)
        return text
    except asyncio.TimeoutError:
        logger.warning("[style-extractor] timeout after %.1fs", _STYLE_EXTRACTOR_TIMEOUT)
        return ""
    except Exception as e:
        logger.warning("[style-extractor] Vision call failed: %s", e)
        return ""

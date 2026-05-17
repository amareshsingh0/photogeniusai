"""Reference Captioner - Gemini Vision extracts role-tagged descriptors
from user-uploaded reference images so the image-gen prompt can carry
explicit "preserve THIS, ignore THAT" instructions for each reference.

Why this exists (May 17 2026):

GPT Image 2 `/v1/images/edits` treats the first image as a canvas-to-edit
and tends to preserve pose / expression / outfit / background of the
reference verbatim. ChatGPT's consumer product (chat.openai.com) sidesteps
this by running a GPT-4o vision pre-pass on every uploaded reference,
extracts ROLE-SPECIFIC descriptors (face-only for a person, packaging-only
for a product, mark-only for a logo), then feeds the descriptors PLUS the
images into the edits call with explicit invariants like
  "preserve facial features from image 1, ignore its pose/outfit/background".

This module replicates that pre-pass with Gemini 2.5 Flash Vision instead
of GPT-4o, per the project's LLM-role split (Haiku owns prompt enrichment;
Gemini owns every other LLM step including classification, critique,
vision tasks). ~10x cheaper than GPT-4o-mini, ~2x faster, comparable
quality for this narrow descriptor-extraction task.

Toggle with USE_REF_CAPTIONER=false to disable. On any failure (network,
quota, parse error) returns empty captions so the pipeline still produces
output - the request path never breaks on captioner errors.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_USE_REF_CAPTIONER = os.getenv("USE_REF_CAPTIONER", "true").lower() not in ("false", "0", "off")
_REF_CAPTIONER_MODEL = os.getenv("REF_CAPTIONER_MODEL", "gemini-2.5-flash")
_REF_CAPTIONER_TIMEOUT = float(os.getenv("REF_CAPTIONER_TIMEOUT_SEC", "12.0"))
_REF_CAPTIONER_MAX_CHARS = int(os.getenv("REF_CAPTIONER_MAX_CHARS", "350"))

# Role-specific prompts. Each one explicitly tells Vision what to extract
# AND what to ignore - the "ignore" half is what gives downstream prompts
# permission to vary pose/scene/wardrobe without losing identity.
_ROLE_PROMPTS: Dict[str, str] = {
    "people": (
        "Describe ONLY the facial identity of the person in this photo. Extract: "
        "perceived ethnicity, age band (e.g. 'late 20s'), face shape (oval/round/heart/square), "
        "eye shape and color, eyebrow shape, nose shape, lip fullness, cheekbones, jawline, "
        "skin tone (warm/cool/neutral), hair color and texture (length is OK to mention only "
        "if very distinctive, e.g. 'shoulder-length straight black hair'), any distinctive "
        "features (freckles, dimples, beauty marks). "
        "DO NOT describe: pose, expression, head tilt, gaze direction, clothing, jewelry, "
        "makeup, hairstyle styling (updo / down / etc), background, lighting, photo style. "
        "Output as a single comma-separated descriptor line, no headers, no bullets. "
        "Max 2 sentences."
    ),
    "products": (
        "Describe ONLY the product itself in this photo. Extract: product type, exact "
        "packaging shape and material, label/wrapper colors, brand name as visible on the "
        "packaging, key typography on the label, any distinctive emblems or icons, dominant "
        "product colors. "
        "DO NOT describe: background, surface, lighting, props, hands holding the product, "
        "photo style, mood. "
        "Output as a single comma-separated descriptor line, no headers, no bullets. "
        "Max 2 sentences."
    ),
    "logos": (
        "Describe ONLY the brand mark / logo visible in this image. Extract: wordmark text "
        "(verbatim), font style (serif/sans/script/handwritten), font weight, primary color, "
        "any accompanying symbol or emblem and its shape, layout (text-only / icon+text / "
        "stacked / horizontal). "
        "DO NOT describe: background, surrounding context, photo style. "
        "Output as a single comma-separated descriptor line, no headers, no bullets. "
        "Max 1-2 sentences."
    ),
    "extras": (
        "Describe what this reference image is meant to convey - the visual style, mood, "
        "color palette, or composition the user is anchoring to. "
        "DO NOT describe specific subjects or copy the literal content. 2 sentences max, "
        "plain prose, no headers."
    ),
}

# Simple in-memory LRU cache keyed by (role, image_url). The same reference
# captioned for a different role would still need a separate Vision call,
# but the same (role, url) pair across N generations only pays once.
_CACHE_SIZE = int(os.getenv("REF_CAPTIONER_CACHE_SIZE", "128"))
_cache: Dict[tuple, str] = {}
_cache_order: list = []


def _cache_get(role: str, url: str) -> Optional[str]:
    return _cache.get((role, url))


def _cache_put(role: str, url: str, caption: str) -> None:
    key = (role, url)
    if key in _cache:
        return
    _cache[key] = caption
    _cache_order.append(key)
    while len(_cache_order) > _CACHE_SIZE:
        oldest = _cache_order.pop(0)
        _cache.pop(oldest, None)


async def _caption_one(role: str, image_url: str) -> str:
    """Caption a single reference image for a given role. Empty string on any failure."""
    if not _USE_REF_CAPTIONER or not image_url:
        return ""

    cached = _cache_get(role, image_url)
    if cached is not None:
        return cached

    # Reuse the style-extractor's image fetcher - it already handles data: URIs
    # and http(s) URLs with sane timeouts.
    from app.services.smart.style_extractor import _fetch_image_base64

    start = time.time()
    image_b64 = await _fetch_image_base64(image_url)
    if not image_b64:
        return ""

    prompt = _ROLE_PROMPTS.get(role, _ROLE_PROMPTS["extras"])

    try:
        from app.services.smart.design_agent_chain import _get_gemini_client

        client = _get_gemini_client()
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=_REF_CAPTIONER_MODEL,
                contents=[{
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    ],
                }],
            ),
            timeout=_REF_CAPTIONER_TIMEOUT,
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            return ""

        text = text[:_REF_CAPTIONER_MAX_CHARS].strip()
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info("[ref-cap][%s] %d chars in %dms - %s",
                    role, len(text), elapsed_ms, text[:80].replace("\n", " "))
        print(f"[REF-CAP][{role}] {elapsed_ms}ms - {text[:120]}", flush=True)

        _cache_put(role, image_url, text)
        return text
    except asyncio.TimeoutError:
        logger.warning("[ref-cap][%s] timeout after %.1fs", role, _REF_CAPTIONER_TIMEOUT)
        return ""
    except Exception as e:
        logger.warning("[ref-cap][%s] Vision call failed: %s", role, e)
        return ""


async def caption_references(refs: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Run Vision captioning over a role-keyed dict of reference URLs.

    Input shape (any keys may be missing or empty):
        {"people": [url, ...], "products": [url, ...], "logos": [url, ...], "extras": [url, ...]}

    Returns a dict of the same shape, with each URL replaced by its caption
    string. Empty list for a role when no refs were provided OR all captions
    came back empty (e.g. Vision quota exhausted).

    All Vision calls fire in parallel via asyncio.gather - total wall time is
    ~max(individual call) rather than sum, so 4 refs cost ~1-2s, not 4-8s.
    """
    if not _USE_REF_CAPTIONER or not refs:
        return {}

    # Flatten into a list of (role, url) tasks while preserving original order
    # so we can rebuild the per-role lists in the same order downstream.
    plan: list = []  # list of (role, idx_within_role, url)
    for role, urls in refs.items():
        if not urls:
            continue
        for i, u in enumerate(urls):
            if u:
                plan.append((role, i, u))

    if not plan:
        return {}

    coros = [_caption_one(role, url) for (role, _i, url) in plan]
    results = await asyncio.gather(*coros, return_exceptions=True)

    out: Dict[str, List[str]] = {}
    for (role, _i, _url), res in zip(plan, results):
        caption = "" if isinstance(res, BaseException) or not isinstance(res, str) else res
        out.setdefault(role, []).append(caption)

    # Drop roles whose captions are all empty - downstream consumers can skip
    # them entirely instead of filtering empty strings.
    return {r: caps for r, caps in out.items() if any(c.strip() for c in caps)}

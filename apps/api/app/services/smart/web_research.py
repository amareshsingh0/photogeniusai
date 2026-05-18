"""
Web Research Agent — Live Google-Search-grounded research for image-gen prompts.

Sits BEFORE the GPT-4o-mini enrichment call in simple_prompt_engine.enrich().

Design philosophy:
  NO hardcoded lanes. NO fixed JSON schema. NO regex extraction. NO
  pre-decided categories. The research agent is ONE Gemini 2.5 Flash call
  with the google_search tool enabled — it reads the user prompt, looks
  at the uploaded reference images (multimodal), sees what existing
  assets we already have, and DECIDES IN NATURAL LANGUAGE what is worth
  looking up. Gemini issues 0 to N search queries internally via the
  tool, then returns a free-form research report in plain text.

  Why this design:
    - Hardcoded lanes (brand / category / typography) work well for ads
      but fail on portraits, scenes, anime, paintings, abstract requests.
    - A fixed planner JSON forces categorisation that doesn't fit every
      prompt type.
    - Free-form lets Gemini handle any request shape: "Make me an album
      cover like Tame Impala", "Photo of my cat as Renaissance painting",
      "Indian wedding card", "Sketch in Studio Ghibli style", "Cyberpunk
      cityscape" — each gets the kind of research that actually helps.

Flow:
  user prompt (any length, any topic)
    + classification (bucket, category, has_text, is_ad — already known)
    + uploaded reference images (multimodal inlineData parts)
    + summary of what we ALREADY have (recipes, bucket hints, brand DB)
        │
        ▼
  ONE Gemini 2.5 Flash call with google_search tool enabled
        │
        ▼
  Free-form research report (or "no research needed" when self-contained)
        │
        ▼
  Injected into the GPT-4o-mini enricher user message as
  WEB RESEARCH CONTEXT, keeping the cached system prompt warm.

Cost / latency:
  - Single call per generation: ~$0.0001 base + grounded usage.
  - Grounded: free up to 1500/day shared Flash/Flash-Lite, then $35/1000.
  - When Gemini decides NO search is needed, the response is still one
    call but uses zero grounded budget.
  - In-memory 24h cache keys on (prompt, classification fingerprint,
    reference image fingerprint) — identical generations cost zero.

Feature flag: USE_WEB_RESEARCH=true (default ON).
Quota guard: WEB_RESEARCH_DAILY_BUDGET=1400 (under free 1500 with margin).

Verified May 19 2026 against:
  https://ai.google.dev/gemini-api/docs/google-search
  https://ai.google.dev/pricing
  Free tier: 1500 grounded RPD shared Flash + Flash-Lite. Paid: $35/1000.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Config ────────────────────────────────────────────────────────────────────
_RESEARCH_MODEL = os.getenv("WEB_RESEARCH_MODEL", "gemini-2.5-flash")
_RESEARCH_TIMEOUT = float(os.getenv("WEB_RESEARCH_TIMEOUT", "15.0"))
_RESEARCH_CACHE_TTL_SEC = int(os.getenv("WEB_RESEARCH_CACHE_TTL", str(24 * 3600)))
_DAILY_BUDGET = int(os.getenv("WEB_RESEARCH_DAILY_BUDGET", "1400"))
_MAX_VISION_IMAGES = int(os.getenv("WEB_RESEARCH_MAX_IMAGES", "3"))
_VISION_FETCH_TIMEOUT = float(os.getenv("WEB_RESEARCH_VISION_FETCH_TIMEOUT", "5.0"))
_VISION_MAX_BYTES = int(os.getenv("WEB_RESEARCH_VISION_MAX_BYTES", "4000000"))
_MAX_OUTPUT_TOKENS = int(os.getenv("WEB_RESEARCH_MAX_OUTPUT_TOKENS", "2000"))
# Gemini 2.5 Flash supports extended thinking via thinking_budget. Verified
# May 19 2026 with https://ai.google.dev/gemini-api/docs/thinking — works
# alongside the google_search tool.
#   0    = OFF (default — fastest; ~2-4s research call, agent still skips
#          self-contained prompts so cost stays near-zero anyway)
#   1024 = ON  (better search decisions on edge cases; +1-2s per call)
# Toggle per environment; we default OFF to keep generation latency tight.
_THINKING_BUDGET = int(os.getenv("WEB_RESEARCH_THINKING_BUDGET", "0"))
_ENABLED = os.getenv("USE_WEB_RESEARCH", "true").lower() == "true"

# Sentinel the model emits when the user prompt is self-contained and no
# research would help. Kept verbatim and case-insensitive so the model can
# write it naturally inside any sentence.
_NO_RESEARCH_SENTINEL = "NO RESEARCH NEEDED"

# ─── Daily quota tracker ───────────────────────────────────────────────────────
_quota_date: str = ""
_quota_count: int = 0
_quota_lock = asyncio.Lock()


async def _quota_check_and_inc(n_calls: int = 1) -> bool:
    """Atomically reserve n_calls of the daily grounded quota."""
    global _quota_date, _quota_count
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with _quota_lock:
        if today != _quota_date:
            _quota_date = today
            _quota_count = 0
        if _quota_count + n_calls > _DAILY_BUDGET:
            logger.warning(
                "[web_research] daily quota would exceed: %d/%d used, %d more requested",
                _quota_count, _DAILY_BUDGET, n_calls,
            )
            return False
        _quota_count += n_calls
        return True


def get_quota_status() -> Dict[str, Any]:
    return {
        "date":      _quota_date,
        "used":      _quota_count,
        "budget":    _DAILY_BUDGET,
        "remaining": max(0, _DAILY_BUDGET - _quota_count),
    }


# ─── In-memory TTL cache ───────────────────────────────────────────────────────
_CACHE: Dict[str, Tuple[float, str]] = {}
_CACHE_MAX = 512
_CACHE_LOCKS: Dict[str, asyncio.Lock] = {}
_CACHE_LOCK_REGISTRY = asyncio.Lock()


def _cache_get(key: str) -> Optional[str]:
    entry = _CACHE.get(key)
    if not entry:
        return None
    expires, value = entry
    if time.time() > expires:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: str) -> None:
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)), None)
    _CACHE[key] = (time.time() + _RESEARCH_CACHE_TTL_SEC, value)


async def _get_cache_lock(key: str) -> asyncio.Lock:
    async with _CACHE_LOCK_REGISTRY:
        lock = _CACHE_LOCKS.get(key)
        if lock is None:
            if len(_CACHE_LOCKS) >= _CACHE_MAX:
                _CACHE_LOCKS.pop(next(iter(_CACHE_LOCKS)), None)
            lock = asyncio.Lock()
            _CACHE_LOCKS[key] = lock
        return lock


def _make_cache_key(
    user_prompt: str,
    classification: Dict[str, Any],
    reference_image_urls: List[str],
) -> str:
    """Stable cache key — same prompt + same classification + same refs = cache hit."""
    h = hashlib.sha256()
    h.update(user_prompt.strip().lower().encode("utf-8"))
    h.update(b"||")
    h.update((classification.get("bucket") or "").encode("utf-8"))
    h.update(b"|")
    h.update((classification.get("category_key") or "").encode("utf-8"))
    h.update(b"|")
    h.update(str(bool(classification.get("has_text"))).encode("utf-8"))
    h.update(b"|")
    h.update(str(bool(classification.get("is_ad"))).encode("utf-8"))
    h.update(b"||")
    for u in sorted(reference_image_urls or []):
        h.update(u.encode("utf-8"))
        h.update(b",")
    return h.hexdigest()[:32]


# ─── Reference image fetch (multimodal input) ──────────────────────────────────
async def _fetch_image_as_part(url: str) -> Optional[Dict[str, Any]]:
    """Download URL → inlineData part. Handles data URIs too. None on failure."""
    if not url or not url.startswith(("http://", "https://", "data:")):
        return None

    if url.startswith("data:"):
        try:
            m = re.match(r"^data:([^;]+);base64,(.+)$", url)
            if not m:
                return None
            mime, b64 = m.group(1), m.group(2)
            if len(b64) * 3 // 4 > _VISION_MAX_BYTES:
                return None
            return {"inlineData": {"mimeType": mime, "data": b64}}
        except Exception:
            return None

    try:
        import httpx
        async with httpx.AsyncClient(timeout=_VISION_FETCH_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            content = resp.content
            if len(content) > _VISION_MAX_BYTES:
                return None
            mime = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if not mime.startswith("image/"):
                return None
            return {"inlineData": {"mimeType": mime, "data": base64.b64encode(content).decode("ascii")}}
    except Exception as e:
        logger.debug("[web_research] image fetch failed for %s: %s", url[:80], e)
        return None


async def _fetch_reference_parts(image_urls: List[str]) -> List[Dict[str, Any]]:
    capped = [u for u in image_urls if u][:_MAX_VISION_IMAGES]
    if not capped:
        return []
    tasks = [_fetch_image_as_part(u) for u in capped]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return [r for r in results if r is not None]


# ─── The single research call ──────────────────────────────────────────────────
def _build_research_instructions(
    user_prompt: str,
    classification: Dict[str, Any],
    existing_assets: Dict[str, Any],
    has_reference_images: bool,
    num_reference_images: int,
) -> str:
    """Compose the natural-language brief for the research agent.

    Free-form: we tell Gemini WHAT it is doing and WHEN to skip research,
    but we do NOT pre-categorize the search lanes. Gemini reads the prompt
    and images, decides what (if anything) would help, runs grounded
    searches via the google_search tool, then writes a free-text report.
    """
    bucket = classification.get("bucket") or "photorealism"
    category_key = classification.get("category_key") or "general"
    has_text = bool(classification.get("has_text"))
    is_ad = bool(classification.get("is_ad"))
    platform = classification.get("platform") or "none"

    have_recipe = bool(existing_assets.get("has_recipe"))
    have_bucket_hint = bool(existing_assets.get("has_bucket_hint"))
    cached_brand = existing_assets.get("cached_brand") or ""
    recipe_summary = existing_assets.get("recipe_summary") or ""

    ref_line = (
        f"Yes — {num_reference_images} reference image(s) are attached after this text. "
        f"Look at them carefully — they tell you a lot about the user's intent "
        f"(style, mood, composition, palette, subject). Let the images inform "
        f"what you decide to research."
        if has_reference_images
        else "No reference images uploaded — work from the text prompt alone."
    )

    return f"""You are the research agent for an AI image-generation pipeline. Your job
is to look at what the user is asking for, and use Google Search (via the
google_search tool you have access to) to find ANY external information that
would help the downstream prompt enricher produce a better image. Then write
a short research report.

You decide:
  - whether ANY web search is worth doing for this prompt
  - what to search for (one query, two, five — whatever fits)
  - which results matter and which to ignore
  - how to summarize what you found into something useful

Do NOT force searches when the prompt is self-contained. Most ordinary
prompts ("a red apple on a white background", "tiger walking in jungle at
golden hour", "anime girl with blue hair sitting in a cafe") need NO
research at all — the enricher already handles them well. In those cases,
reply with the exact phrase "{_NO_RESEARCH_SENTINEL}" followed by one
sentence explaining why you skipped, and nothing else.

DO research when the prompt benefits from external knowledge — for example:
  - The user names a real brand, company, product line, public figure, IP,
    movie, album, show, venue, event, or location whose visual identity
    matters (look up their colors, typography, current aesthetic).
  - The prompt or the reference image points at a named artistic style,
    photographer, studio, film, or movement (Annie Leibovitz portrait
    lighting, Studio Ghibli watercolour backgrounds, Wes Anderson palette,
    Blade Runner 2049 colour grading) and you should pull its visual
    signatures.
  - The category has fast-moving design conventions and the user wants
    something current (2026 Indian wedding card design, modern fintech
    logo language, K-pop album cover trends right now, this year's
    Diwali poster aesthetics).
  - The user asks for a technical photographic / artistic technique with
    a known practitioner playbook (85mm portrait at golden hour, wet-on-wet
    watercolour, long-exposure star trails, macro dew drops).
  - You see a reference image with a distinctive style and the user wants
    something "in this style" — search for similar examples and named
    sources of that style.

USER PROMPT (could be one word or several paragraphs):
\"\"\"
{user_prompt.strip()}
\"\"\"

CLASSIFICATION (already determined upstream — don't re-derive it):
  bucket:       {bucket}
  category_key: {category_key}
  has_text:     {has_text}   (will the output render on-image text?)
  is_ad:        {is_ad}      (commercial ad vs. art / scene / portrait)
  platform:     {platform}

WHAT THE PIPELINE ALREADY HAS (do NOT waste a search re-finding these):
  curated recipe for category '{category_key}':  {"yes" if have_recipe else "no"}
  built-in discipline block for bucket '{bucket}': {"yes" if have_bucket_hint else "no"}
  cached brand in our brand DB:                   {cached_brand or "none"}
{("  recipe summary: " + recipe_summary[:250]) if recipe_summary else ""}

REFERENCE IMAGES: {ref_line}

OUTPUT FORMAT (free-form prose — no JSON, no markdown headers, no fences):

  If you decided to skip:
    "{_NO_RESEARCH_SENTINEL} — <one sentence reason>"

  Otherwise, a short report in 2-6 short paragraphs (or bullet groups,
  whichever reads better). For each thing you researched, lead with
  WHAT it is, then 3-7 concrete useful details (hex codes, font names,
  composition patterns, lighting setups, named examples, dates, links
  where helpful). End each paragraph with a single sentence on HOW the
  enricher should USE this in the image (e.g. "Use these as the dominant
  palette for the background, accent on the CTA only").

  Total report length: target 150-400 words. Be specific. Skip filler.
  Don't repeat the user prompt back. Don't restate the classification.
  Don't write 'I will search for...' — just present the findings.

The downstream enricher (GPT-4o-mini) will read your report verbatim and
weave it into a detailed image-generation prompt. Write FOR THAT
DOWNSTREAM CONSUMER — be useful, be specific, be concise."""


async def _run_research_call(
    user_prompt: str,
    classification: Dict[str, Any],
    existing_assets: Dict[str, Any],
    reference_image_urls: List[str],
) -> str:
    """The single Gemini call: grounded, multimodal, free-form output."""
    if not await _quota_check_and_inc(1):
        return ""

    try:
        from app.services.smart.design_agent_chain import _get_gemini_client
        from google.genai import types
    except Exception as e:
        logger.warning("[web_research] google-genai unavailable: %s", e)
        return ""

    image_parts = await _fetch_reference_parts(reference_image_urls)
    if reference_image_urls:
        logger.info(
            "[web_research] attached %d/%d reference images to research call",
            len(image_parts), len(reference_image_urls),
        )

    instructions = _build_research_instructions(
        user_prompt,
        classification,
        existing_assets,
        has_reference_images=bool(image_parts),
        num_reference_images=len(image_parts),
    )

    parts: List[Dict[str, Any]] = [{"text": instructions}]
    parts.extend(image_parts)

    try:
        client = _get_gemini_client()
        config_kwargs: Dict[str, Any] = dict(
            temperature=0.35,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
        if _THINKING_BUDGET > 0:
            # Extended thinking lets the model genuinely weigh whether a search
            # would help and pick targeted queries. Thinking tokens are billed
            # as output but stay internal (not returned in resp.text).
            try:
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=_THINKING_BUDGET
                )
            except Exception:  # noqa: BLE001 - older SDK without ThinkingConfig
                pass
        config = types.GenerateContentConfig(**config_kwargs)
        coro = client.aio.models.generate_content(
            model=_RESEARCH_MODEL,
            contents=[{"role": "user", "parts": parts}],
            config=config,
        )
        resp = await asyncio.wait_for(coro, timeout=_RESEARCH_TIMEOUT)
        text = (resp.text or "").strip()
        if not text:
            return ""
        return text
    except asyncio.TimeoutError:
        logger.warning("[web_research] research call timeout after %.1fs", _RESEARCH_TIMEOUT)
        return ""
    except Exception as e:
        logger.warning("[web_research] research call failed: %s", e)
        return ""


# ─── Public orchestrator ───────────────────────────────────────────────────────
async def gather_research(
    user_prompt: str,
    classification: Dict[str, Any],
    reference_image_urls: Optional[List[str]] = None,
    existing_assets: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Top-level entry point.

    Args:
        user_prompt: raw user text (any length, any topic).
        classification: output of classify_intent() — bucket / category_key /
            has_text / is_ad / platform.
        reference_image_urls: list of HTTP(S) URLs or data URIs the user
            uploaded (primary + extras). Up to _MAX_VISION_IMAGES are
            attached to the research call.
        existing_assets: dict telling the agent what we already have on
            hand (so it doesn't waste searches re-finding them):
              has_recipe       (bool)
              has_bucket_hint  (bool)
              cached_brand     (str — DB-resolved brand name, or '')
              recipe_summary   (str — short summary of matched recipe)

    Returns a 'WEB RESEARCH CONTEXT' block ready to drop into the GPT-4o-mini
    enricher user message, or None if the feature is disabled / the agent
    decided to skip / the call failed.
    """
    if not _ENABLED:
        return None
    if not user_prompt or not user_prompt.strip():
        return None

    started = time.time()
    refs = [u for u in (reference_image_urls or []) if u]
    assets = existing_assets or {}

    # Cache: prompt + classification fingerprint + reference urls
    cache_key = _make_cache_key(user_prompt, classification, refs)
    hit = _cache_get(cache_key)
    if hit is not None:
        if hit == _NO_RESEARCH_SENTINEL:
            logger.info("[web_research] cache HIT (skip) | %r", user_prompt[:60])
            return None
        logger.info("[web_research] cache HIT | %r | %d chars", user_prompt[:60], len(hit))
        return hit

    lock = await _get_cache_lock(cache_key)
    async with lock:
        # Double-check after acquiring the lock
        hit = _cache_get(cache_key)
        if hit is not None:
            if hit == _NO_RESEARCH_SENTINEL:
                return None
            return hit

        report = await _run_research_call(user_prompt, classification, assets, refs)

        elapsed = time.time() - started

        if not report:
            logger.info("[web_research] empty report (%.2fs)", elapsed)
            return None

        # Detect skip sentinel — the model wrote "NO RESEARCH NEEDED — ..."
        # Cache the skip too, so we don't replan the same prompt for 24h.
        if _NO_RESEARCH_SENTINEL in report.upper()[:60]:
            logger.info("[web_research] agent SKIPPED | %.2fs | reason=%r", elapsed, report[:120])
            _cache_set(cache_key, _NO_RESEARCH_SENTINEL)
            return None

        # Compose the final block injected into the enricher message.
        header = (
            "WEB RESEARCH CONTEXT (live findings from Google Search — use as "
            "inspiration and factual reference; do NOT copy any of this verbatim "
            "as on-image text):"
        )
        if refs:
            header += (
                "\nNOTE: User uploaded reference image(s). Treat findings below "
                "as styling / mood / palette hints — preserve the subject and "
                "composition of the uploaded references."
            )
        full = header + "\n\n" + report.strip()

        _cache_set(cache_key, full)

        logger.info(
            "[web_research] OK | %.2fs | %d chars | quota=%d/%d",
            elapsed, len(full), _quota_count, _DAILY_BUDGET,
        )
        return full


__all__ = [
    "gather_research",
    "get_quota_status",
]

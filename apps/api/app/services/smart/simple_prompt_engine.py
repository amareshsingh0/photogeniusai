"""
Simple Prompt Engine — One-shot Haiku 4.5 prompt enrichment.

Replaces the multi-stage agent chain (Master Strategist + Copy Writer + Image
Prompter + Layout Planner + Claude Stage A/B/Validator) with a single Claude
Haiku 4.5 call that:

  1. Detects what the user is asking for (ad / poster / hoarding / wishes /
     product shot / portrait / etc).
  2. Expands a short prompt into a richly detailed image-generation prompt
     with subject, scene, lighting, composition, mood, style, palette, and
     copy text where relevant.
  3. Re-details / cleans up long, messy prompts so the model receives a
     well-structured instruction.

Output is consumed directly by the model — no Stage B params engine, no
agent chain, no validator. The enriched prompt IS the final prompt.

Usage:
    from app.services.smart.simple_prompt_engine import simple_engine
    result = await simple_engine.enrich(
        user_prompt="birthday wishes for my sister",
        bucket="typography",
        tier="2k",
    )
    # result = {
    #     "prompt": "...rich detailed prompt...",
    #     "negative_prompt": "...",
    #     "intent": "birthday_card",
    #     "aspect_hint": "portrait_4_3",
    #     "ad_copy": {"headline": "...", "subhead": "..."} or None,
    # }

Toggle with feature flag USE_SIMPLE_ENGINE=true.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category recipes loader — UNION of two sources, mined data takes priority.
#
#   1. category_recipes_mined.json  -  written by scripts/mine_category_recipes.py
#                                       from Pitt Image Ads (64K real ads / 38
#                                       industry topics) + AdCopy programmatic
#                                       dataset. Data-driven, auto-regenerable.
#   2. category_recipes.json        -  hand-curated entries (e.g. ayurveda,
#                                       packaging, wedding) for verticals the
#                                       Pitt taxonomy does not cover.
#
# Both load lazily once per process. Match against the user's prompt happens
# via per-recipe `aliases` keyword list. The matched recipe is injected into
# the dynamic USER MESSAGE (not the cached system prompt) so prompt-cache
# warmth is preserved.
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent / "data"
_RECIPES_MINED_PATH = _DATA_DIR / "category_recipes_mined.json"
_RECIPES_MANUAL_PATH = _DATA_DIR / "category_recipes.json"

_CATEGORY_RECIPES: Optional[Dict[str, Dict[str, Any]]] = None


def _load_category_recipes() -> Dict[str, Dict[str, Any]]:
    """Lazy-load + merge mined and manual recipe files. Mined wins on key collision."""
    global _CATEGORY_RECIPES
    if _CATEGORY_RECIPES is not None:
        return _CATEGORY_RECIPES

    merged: Dict[str, Dict[str, Any]] = {}
    for path in (_RECIPES_MANUAL_PATH, _RECIPES_MINED_PATH):  # mined loaded LAST so it wins
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            logger.warning("[recipes] failed to load %s: %s", path.name, e)
            continue
        for k, v in data.items():
            if k.startswith("_") or not isinstance(v, dict):
                continue
            merged[k] = v
        logger.info("[recipes] loaded %s (%d entries -> %d merged)", path.name, len(data), len(merged))

    _CATEGORY_RECIPES = merged
    return merged


def _recipe_by_key(category_key: str) -> Optional[Dict[str, Any]]:
    """Direct lookup of a recipe by its canonical key (no alias scan).

    Called by the two-stage enrich() flow AFTER the Gemini classifier has
    already decided the category. If the key isn't in either recipes file,
    returns None (Haiku falls back to its 14 hardcoded system-prompt recipes).
    """
    if not category_key:
        return None
    recipes = _load_category_recipes()
    rec = recipes.get(category_key)
    if not rec:
        return None
    return {"key": category_key, **rec}


# ---------------------------------------------------------------------------
# Stage-1 Gemini classifier
# ---------------------------------------------------------------------------
# Replaces the keyword-based bucket detection + alias-based recipe matching
# with a single fast LLM call. Gemini reads the user prompt and returns:
#   - bucket: which generation pipeline (typography / photorealism_* / etc)
#   - category_key: which recipe to load from category_recipes JSON
#   - has_text:    whether the image needs on-canvas text rendering
#   - is_ad:       is this a commercial ad (vs scene / portrait / fan art)
#   - platform:    detected social platform (instagram / linkedin / etc)
#
# Cost: ~$0.0001 per call (gemini-2.5-flash, ~150 input + 60 output tokens,
# ~300ms latency). Output is JSON-validated, falls back to safe defaults on
# any error so the pipeline never breaks.

_CLASSIFIER_MODEL = os.getenv("INTENT_CLASSIFIER_MODEL", "gemini-2.5-flash")

_VALID_BUCKETS = {
    "typography",
    "vector",
    "anime",
    "artistic",
    "interior_arch",
    "photorealism_portrait",
    "photorealism_product",
    "photorealism_food",
    "photorealism_fashion",
    "photorealism_landscape",
    "photorealism",
}


def _build_classifier_prompt(user_prompt: str, available_keys: list) -> str:
    keys_csv = ", ".join(sorted(available_keys)) or "general"
    return f"""You classify a user's image-generation request to route it through the right pipeline.

USER PROMPT:
{user_prompt.strip()}

AVAILABLE category_keys (pick the BEST matching one, or "general" if none fit):
{keys_csv}

BUCKETS (pick exactly one):
- typography      = ad / poster / banner / social media post / marketing creative — anything with on-image text
- vector          = logo, icon, flat illustration, SVG-style
- anime           = anime / manga style art
- artistic        = painting, illustration, concept art, fantasy, surreal
- interior_arch   = interior, room, architecture, building
- photorealism_portrait = portrait, headshot, person photo (no on-image text)
- photorealism_product  = product photography, packshot (no text overlay)
- photorealism_food     = food, dish, restaurant photo
- photorealism_fashion  = clothing, fashion shoot
- photorealism_landscape= landscape, nature, scenery
- photorealism          = generic photoreal scene

Return JSON ONLY (no prose, no markdown fences):
{{
  "bucket": "<one of the buckets above>",
  "category_key": "<one of the AVAILABLE category_keys, or 'general' if no fit>",
  "has_text": true|false,
  "is_ad": true|false,
  "platform": "<instagram|linkedin|facebook|tiktok|youtube|pinterest|none>"
}}

RULES:
- "logo", "brand mark", "wordmark", "monogram", "icon for app", "favicon", "emblem", "badge" -> bucket=vector. is_ad=false. has_text=true ONLY if it's a wordmark/combination (brand name visible); has_text=false for pure symbol/pictorial mark.
- "post for instagram", "ad", "poster", "launch", "promo", "campaign" -> bucket=typography, has_text=true, is_ad=true. BUT if the prompt describes a LOGO and just lists "campaign / ad / poster" as features of a product/website (e.g. "logo for an app that creates ads, posters, campaigns"), DO NOT confuse those feature words with the deliverable — the deliverable is the LOGO, so route bucket=vector.
- A product launch ad with brand name -> typography even if user calls it a "photo"
- Pure scene description ("car on mars", "anime girl in forest") -> appropriate non-typography bucket, has_text=false
- If unsure between typography and photorealism: prefer typography when prompt mentions a brand, CTA, sale, headline, or platform.
- Distinguishing logo vs. ad: a LOGO is the standalone brand identifier (small mark, scalable, no scene). An AD is a marketing layout (product + headline + scene + CTA). If the request says "create a logo / mark / icon" -> vector. If it says "create an ad / poster / banner / social post" -> typography.
- REALISM KEYWORD OVERRIDE (HIGH PRIORITY): if the prompt contains any of these explicit realism cues — "real", "realistic", "photo", "photoreal", "photorealistic", "DSLR", "shot on", "85mm", "cinematic photo", "lifelike", "actual", "live action" — route to a photorealism bucket EVEN IF the scene is fantastical or surreal (e.g. "real tiger sitting on a cloud with flowers", "realistic dragon over a city", "photoreal astronaut on Mars"). The user wants a photographic rendering of an imaginative scene — NOT a painting/illustration of it. Pick the most specific photorealism sub-bucket: animal/nature scene → photorealism_landscape or photorealism (generic), human → photorealism_portrait, product → photorealism_product. Only route to "artistic" when the user EXPLICITLY asks for a painting / illustration / concept art / watercolor / oil / digital-art / sketch / drawn / surreal-art style. Default for ambiguous fantastical scenes WITHOUT artistic-medium keyword: photorealism.
- DEFAULT BIAS — PHOTOREALISM IS THE DEFAULT (HIGHEST PRIORITY RULE): For ANY prompt that does not EXPLICITLY request a non-photoreal style, route to photorealism. The bar to leave photorealism is HIGH — the user must use one of these explicit art-medium / non-photo keywords: "painting", "illustration", "watercolor", "oil paint", "gouache", "ink", "sketch", "drawn", "drawing", "concept art", "art style", "artistic", "stylized", "anime", "manga", "cartoon", "comic", "vector", "flat design", "logo", "icon", "poster", "ad", "banner", "wallpaper-style", "wallpaper art", "3D render", "CGI", "low-poly", "isometric", "pixel art". Without one of those keywords, the bucket is photorealism — no exceptions. Generic prompts like "tiger in jungle", "girl with red dress", "city at night", "coffee on a table", "mountain landscape", "dog playing with ball" → ALL photorealism. Even fantastical scenes ("dragon flying over castle", "astronaut on alien planet", "tiger sitting on a cloud") default to photorealism unless the user asked for an art medium. Pick the most specific photorealism sub-bucket: human → photorealism_portrait, product/object → photorealism_product, food → photorealism_food, fashion → photorealism_fashion, landscape/nature → photorealism_landscape, anything else → photorealism (generic).
- ARTISTIC BUCKET IS OPT-IN ONLY: do NOT route to "artistic" based on scene mood/atmosphere alone. "dreamy forest", "magical castle", "mystical creature", "surreal scene", "fantasy landscape" → STILL photorealism unless the user explicitly says "painted / illustrated / watercolor / concept art / drawn / etc". A surreal subject does not equal an artistic medium. Photorealism can render surreal subjects — that is what makes them striking.
"""


_CLASSIFICATION_FALLBACK = {
    "bucket": "photorealism",
    "category_key": "general",
    "has_text": False,
    "is_ad": False,
    "platform": "none",
}


def _fallback_classification(user_prompt: str) -> Dict[str, Any]:
    """When Gemini is unavailable (quota / permission / network), use the
    keyword-based bucket detector + cheap heuristics so the pipeline still
    routes correctly. Better than the static fallback for ad prompts.
    """
    out = dict(_CLASSIFICATION_FALLBACK)
    try:
        from app.services.smart.config import detect_capability_bucket
        out["bucket"] = detect_capability_bucket(user_prompt) or "photorealism"
    except Exception:
        pass
    needle = (user_prompt or "").lower()
    # Heuristic ad-intent flags so the critique pass + per-model formatters
    # still know this is an ad even when Gemini can't classify.
    ad_signals = ("ad", "advert", "poster", "banner", "promo", "campaign",
                  "launch", "sale", "offer", "discount", "brand", "buy",
                  "shop", "post", "reel", "story", "instagram", "facebook",
                  "linkedin", "tiktok", "youtube")
    if out["bucket"] in ("typography", "ad_creative") or any(s in needle for s in ad_signals):
        out["is_ad"] = True
        out["has_text"] = True
        if "typography" not in out["bucket"]:
            out["bucket"] = "typography"
    for plat in ("instagram", "linkedin", "facebook", "tiktok", "youtube", "pinterest"):
        if plat in needle:
            out["platform"] = plat
            break
    return out


# Per-process cache: maps user_prompt -> classification result. Single-request
# scope by design - enables generate_stream to call the classifier ONCE for
# bucket routing and re-use the same result inside enrich() without paying
# for a second Gemini call. Bounded to last 256 prompts.
#
# Concurrency: admin parallel mode dispatches 6+ model workers simultaneously.
# Without locking, all 6 hit classify_intent BEFORE the first call's await
# returns and writes the cache - causing 6 concurrent Gemini calls and
# blowing through free-tier quota (5/min). The per-prompt asyncio.Lock
# ensures only ONE classifier call fires per unique prompt; the other 5
# wait on the lock, then read the cached result.
_CLASSIFICATION_CACHE: Dict[str, Dict[str, Any]] = {}
_CLASSIFICATION_CACHE_MAX = 256
_CLASSIFICATION_LOCKS: Dict[str, asyncio.Lock] = {}
_LOCKS_REGISTRY_LOCK = asyncio.Lock()


def _cache_classification(prompt: str, result: Dict[str, Any]) -> None:
    if len(_CLASSIFICATION_CACHE) >= _CLASSIFICATION_CACHE_MAX:
        # Drop oldest (insertion order) entry
        _CLASSIFICATION_CACHE.pop(next(iter(_CLASSIFICATION_CACHE)))
    _CLASSIFICATION_CACHE[prompt] = result


async def _get_prompt_lock(prompt: str) -> asyncio.Lock:
    """Return (creating if needed) an asyncio.Lock unique to this prompt."""
    async with _LOCKS_REGISTRY_LOCK:
        lock = _CLASSIFICATION_LOCKS.get(prompt)
        if lock is None:
            # GC: keep the registry from growing unbounded.
            if len(_CLASSIFICATION_LOCKS) >= _CLASSIFICATION_CACHE_MAX:
                _CLASSIFICATION_LOCKS.pop(next(iter(_CLASSIFICATION_LOCKS)))
            lock = asyncio.Lock()
            _CLASSIFICATION_LOCKS[prompt] = lock
        return lock


async def classify_intent(user_prompt: str) -> Dict[str, Any]:
    """Public async classifier - cached per prompt with per-prompt locking.

    Concurrency-safe: when N concurrent callers ask for the same prompt's
    classification, only ONE fires the Gemini call; the other N-1 wait on
    the lock, then read the cached result instantly. This prevents the
    admin parallel mode (6 model workers) from making 6 concurrent calls
    and blowing the free-tier quota (5 RPM on gemini-2.5-flash).
    """
    # Fast path: cache hit, no lock needed.
    cached = _CLASSIFICATION_CACHE.get(user_prompt)
    if cached is not None:
        return cached

    # Slow path: take the per-prompt lock, double-check cache, then call.
    lock = await _get_prompt_lock(user_prompt)
    async with lock:
        cached = _CLASSIFICATION_CACHE.get(user_prompt)
        if cached is not None:
            return cached
        result = await _classify_intent_gemini(user_prompt)
        _cache_classification(user_prompt, result)
        return result


async def _classify_intent_gemini(user_prompt: str) -> Dict[str, Any]:
    """Stage-1: Gemini classifies user prompt -> bucket + category_key + flags.

    Returns a dict with keys: bucket, category_key, has_text, is_ad, platform.
    On any error returns _CLASSIFICATION_FALLBACK so callers never crash.
    """
    if not user_prompt or not user_prompt.strip():
        return _fallback_classification(user_prompt)

    try:
        from app.services.smart.design_agent_chain import _get_gemini_client
        from google.genai import types
    except Exception as e:
        logger.warning("[classifier] google-genai unavailable: %s", e)
        return _fallback_classification(user_prompt)

    recipes = _load_category_recipes()
    available_keys = list(recipes.keys()) + ["general"]
    prompt = _build_classifier_prompt(user_prompt, available_keys)

    try:
        client = _get_gemini_client()
        resp = await client.aio.models.generate_content(
            model=_CLASSIFIER_MODEL,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=types.GenerateContentConfig(
                temperature=0.1,
                # Gemini 2.5 Flash with response_mime_type=json sometimes burns
                # ~1000 tokens of internal "thinking" before emitting the JSON.
                # 1500 = safe ceiling for our 5-key payload, well under the
                # model's 8192 hard cap.
                max_output_tokens=1500,
                response_mime_type="application/json",
            ),
        )
        raw = (resp.text or "").strip()
        if not raw:
            # Empty body - likely safety blocked or model didn't comply.
            finish = resp.candidates[0].finish_reason if resp.candidates else "UNKNOWN"
            logger.warning("[classifier] empty Gemini response (finish_reason=%s) -- using fallback", finish)
            return _fallback_classification(user_prompt)
        # Strip any stray markdown fences just in case.
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", raw, flags=re.MULTILINE).strip()
        # Slice to outermost {...} so trailing prose doesn't break json.loads.
        first, last = raw.find("{"), raw.rfind("}")
        if first != -1 and last != -1 and last > first:
            raw = raw[first:last + 1]
        data = json.loads(raw)
    except Exception as e:
        logger.warning("[classifier] gemini call failed: %s -- raw=%r -- using fallback",
                       e, (raw[:200] if 'raw' in locals() else "<no response>"))
        return _fallback_classification(user_prompt)

    # Validate + sanitize output
    out = dict(_CLASSIFICATION_FALLBACK)
    bucket = str(data.get("bucket") or "").strip()
    if bucket in _VALID_BUCKETS:
        out["bucket"] = bucket
    cat_key = str(data.get("category_key") or "").strip()
    if cat_key and (cat_key in recipes or cat_key == "general"):
        out["category_key"] = cat_key
    out["has_text"] = bool(data.get("has_text"))
    out["is_ad"]    = bool(data.get("is_ad"))
    platform = str(data.get("platform") or "none").strip().lower()
    if platform in {"instagram", "linkedin", "facebook", "tiktok", "youtube", "pinterest", "none"}:
        out["platform"] = platform

    logger.info(
        "[classifier] prompt=%r -> bucket=%s category=%s has_text=%s is_ad=%s platform=%s",
        user_prompt[:60], out["bucket"], out["category_key"], out["has_text"], out["is_ad"], out["platform"],
    )
    return out


def _format_recipe_for_prompt(rec: Dict[str, Any]) -> str:
    """Render a matched recipe as a compact REFERENCE PATTERNS block for Haiku.

    Kept ASCII-only and bullet-light so it parses cleanly inside the user message
    without confusing the JSON response_model.
    """
    key = rec.get("key", "category")
    bits: List[str] = [f"REFERENCE PATTERNS for category={key} (real-world ad data, use as inspiration NOT verbatim):"]

    def _take(field: str, label: str, n: int = 6) -> None:
        vals = rec.get(field) or []
        if not isinstance(vals, list):
            return
        cleaned = [str(v).strip() for v in vals if str(v).strip()]
        if not cleaned:
            return
        bits.append(f"  {label}: " + " | ".join(cleaned[:n]))

    _take("hero_patterns",          "common headlines",        n=6)
    _take("cta_patterns",           "common CTAs",             n=5)
    _take("trust_signals",          "trust signals",           n=6)
    _take("benefit_labels",         "benefit labels",          n=5)
    _take("top_sentiments",         "dominant tone",           n=4)
    _take("top_strategies",         "rhetorical strategies",   n=3)
    _take("distinctive_vocabulary", "vocabulary that signals this category", n=12)

    palette  = (rec.get("color_palette") or "").strip()
    lighting = (rec.get("lighting") or "").strip()
    photo    = (rec.get("photography") or "").strip()
    if palette:  bits.append(f"  palette hint: {palette}")
    if lighting: bits.append(f"  lighting hint: {lighting}")
    if photo:    bits.append(f"  photography hint: {photo}")

    return "\n".join(bits)

_CLAUDE_MODEL = os.getenv("SIMPLE_ENGINE_MODEL", "claude-haiku-4-5-20251001")
_MAX_TOKENS   = int(os.getenv("SIMPLE_ENGINE_MAX_TOKENS", "2200"))
_TEMPERATURE  = float(os.getenv("SIMPLE_ENGINE_TEMPERATURE", "0.7"))

# Self-critique pass (Gap C, May 3 2026). When ON, ad prompts run a 2nd
# Haiku review that tightens the brief: shorter punchier headlines, removes
# vague filler, ensures negative space is explicit. Adds ~1s + ~$0.0008 per
# generation. Flag-controlled, defaults ON for ads only.
_USE_SELF_CRITIQUE = os.getenv("USE_SELF_CRITIQUE", "true").lower() != "false"
# Critique returns the FULL improved SimpleEngineOutput JSON (12 fields incl
# nested ad_copy + visual). Gemini 2.5 Flash with response_mime_type=json
# burns ~600 tokens on internal reasoning before emitting. Empirically a
# full critique payload runs 1500-2200 output tokens. Bumped to 4000 for
# safety so we never truncate mid-string.
_CRITIQUE_MAX_TOKENS = int(os.getenv("SELF_CRITIQUE_MAX_TOKENS", "6000"))
_USE_CACHING  = os.getenv("USE_PROMPT_CACHING", "true").lower() != "false"
# Instructor auto-retries up to N times when Haiku violates the schema
# (each retry appends the validation error to the conversation, so the model
# self-corrects). 2 retries = 3 total attempts which is plenty.
_INSTRUCTOR_MAX_RETRIES = int(os.getenv("SIMPLE_ENGINE_MAX_RETRIES", "2"))


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schema — Haiku output shape (Priority 1: structured output validation)
# ─────────────────────────────────────────────────────────────────────────────
# Replaces the old loose-JSON parsing. Instructor wraps the Anthropic client
# with tool-calling-based schema enforcement. If Haiku returns malformed JSON,
# missing fields, or wrong types, Instructor auto-retries with the validation
# error injected into the conversation — Haiku self-corrects within max_retries.
#
# This eliminates the entire "Haiku silently dropped ad_copy / returned bad
# JSON" failure category. Typography generations with missing headlines: gone.

# Aspect hints supported by generate_stream's _ASPECT_DIMS map.
AspectHint = Literal[
    "square_hd",
    "portrait_4_3",
    "landscape_4_3",
    "portrait_9_16",
    "landscape_16_9",
]


class AdCopy(BaseModel):
    """On-image text rendered by the model. Empty strings when not relevant."""

    # Core fields - backward-compatible with existing generate_stream.py consumers.
    # Length caps tightened May 3 2026 to match real ad-copy brevity (most
    # high-converting ads use 2-5 word headlines per Pitt Image Ads dataset
    # analysis). Image models render short text reliably, long text mangles.
    headline: str = Field(default="", max_length=40,
        description="Primary attention hook - 2-5 WORDS MAXIMUM, the main large text on the image. Ads with longer headlines render poorly. Examples: 'LIGHT AS AIR', 'BLOOD SUGAR CONTROLLED', 'CRAFT YOUR MOMENT'.")
    subhead:  str = Field(default="", max_length=80,
        description="Secondary line adding context below the headline - 5-10 WORDS MAXIMUM. Example: 'Flawless Everywhere'.")
    cta:      str = Field(default="", max_length=25,
        description="Call-to-action - 2-3 WORDS MAXIMUM (Shop Now / Book Today / Learn More). Empty for non-ad content.")

    # Phase-2 Typography Architecture (May 4 2026 framework expansion)
    # Caps generous - Haiku writes verbose styling specs; brevity enforced
    # downstream in formatters / critique, not at schema layer.
    headline_typography: str = Field(default="", max_length=400, description=(
        "Per-element styling for the HEADLINE. Format: 'font: <family> | weight: <bold|black|regular> | size: large | color: <hex or name> | tracking: <tight|normal|wide>'. "
        "Example: 'font: Playfair Display serif | weight: black | size: large | color: pure white | tracking: tight'. "
        "Pick from the project's MAX 2 fonts (1 display + 1 body)."
    ))
    subhead_typography: str = Field(default="", max_length=400, description=(
        "Per-element styling for the SUBHEAD. Same format as headline_typography. Example: 'font: Inter sans-serif | weight: regular | size: medium | color: light gold | tracking: wide'."
    ))
    cta_typography: str = Field(default="", max_length=400, description=(
        "Per-element styling for the CTA button. Example: 'font: Inter sans-serif | weight: bold | size: medium | color: white text on rose-gold pill button'."
    ))

    # Regulated industry compliance (May 4 framework expansion)
    legal_disclaimer: str = Field(default="", max_length=400, description=(
        "MANDATORY for regulated categories - alcohol, tobacco, pharma, financial, gambling. Examples: "
        "alcohol -> '21+ ONLY. DRINK RESPONSIBLY.' | "
        "pharma -> 'Consult your doctor. Read label carefully.' | "
        "financial -> 'Past performance no guarantee. T&C apply.' | "
        "gambling -> 'Play responsibly. 18+ only.'. "
        "Renders as small high-contrast text on a thin band at the bottom of the image. Empty for unregulated categories."
    ))

    # Extended fields — Art Director Brain additions
    benefit_lines: list[str] = Field(default_factory=list,
        description="0–5 feature labels for icon badge rendering. MUST be 2–3 words each (e.g. 'Lightweight Feel', 'Oil Control', 'Long-Lasting Wear', 'Blurs Imperfections'). These render as circular icon badges in the layout — do NOT write full sentences here. Empty for minimal posters.")
    trust_signals: list[str] = Field(default_factory=list,
        description="0–3 credibility lines (e.g. '10,000+ customers', 'Dermatologist tested'). Empty if not applicable.")
    emotional_tagline: Optional[str] = Field(default=None, max_length=200,
        description="Aspirational closing line — the feeling the viewer should carry away.")
    brand_name: Optional[str] = Field(default=None, max_length=100,
        description="Exact brand name to render in the image, if provided by the user.")

    # Brand identity layer (May 6 2026 — close gap with ChatGPT/Midjourney ad outputs)
    brand_emblem_description: Optional[str] = Field(default=None, max_length=300, description=(
        "Description of a SMALL decorative brand mark / emblem / monogram to render alongside the wordmark. "
        "Real ads pair the brand name with a tiny crest/mandala/diamond/circle-emblem to feel finished and credible "
        "(luxury, fashion, food, hospitality, D2C heritage brands all do this). "
        "Example: 'small ornate gold diamond emblem with stylized G initial in the center, lotus motif accents' for a luxury fashion brand. "
        "'minimalist circular badge with leaf icon' for an organic brand. "
        "'shield with crossed forks' for a steakhouse. "
        "Empty for tech/SaaS/minimal brands where wordmark alone is enough. Renders in the layout TOP-CENTER above the headline OR top-left as a corner mark."
    ))
    website_url: Optional[str] = Field(default=None, max_length=120, description=(
        "Website URL to render in the ad footer/CTA strip. POPULATE for D2C / brand / event / "
        "service ads — these all carry a website on real-world posters and feel unfinished without one. "
        "If the user provided a URL, use it verbatim. If not, generate a plausible placeholder of the form "
        "'www.{brand_or_event_slug}.com' or '.in' (e.g. 'www.bhajansandhya.com', 'www.glamour.in', "
        "'www.spiritualharmony.org'). Use '.org' for non-profits/spiritual, '.in' for India D2C, "
        "'.com' for global brands. Empty ONLY for personal-use posts (wishes, greetings, family events) "
        "where a website is genuinely not expected."
    ))
    contact_info: Optional[str] = Field(default=None, max_length=200, description=(
        "Phone, address, social handle, or location footer — POPULATE for events / restaurants / "
        "real estate / local services / D2C brands where a venue or contact is expected by genre convention. "
        "If user provided specifics, use verbatim. If not, generate plausible placeholders that make the poster "
        "feel finished: phone in correct country format ('+91 98765 43210' for India, '+1 (212) 555-0182' for US), "
        "address with city/state/PIN ('Shree Ram Bhajan Hall, 123 Bhakti Path, Vrindavan, UP – 281121', "
        "'42 Anna Salai, Chennai – 600002'), social handle ('@brandname.official'). "
        "Use multi-line format separated by ' | '. Empty ONLY for personal posts where contact isn't expected."
    ))
    footer_strip: list[str] = Field(default_factory=list, description=(
        "0–4 short footer-strip badges that anchor the bottom of the ad — these are the 'credibility close' line typical of D2C / e-commerce / festival ads. "
        "Examples: ['FREE SHIPPING PAN INDIA', 'COD AVAILABLE', '7-DAY RETURNS', 'DIRECTLY FROM WEAVERS'] for D2C apparel; "
        "['DINE-IN • TAKEAWAY • DELIVERY', 'OPEN 11 AM – 11 PM'] for restaurants; "
        "['EARLY-BIRD ENDS THURSDAY', 'GROUP DISCOUNTS'] for events. "
        "MAX 2-4 words each. Each renders as a separate icon+label pair in a horizontal strip at the bottom of the ad. Empty for minimalist/luxury ads where extra info dilutes the mood."
    ))

    # Event/lineup schedule (May 6 2026 — for multi-act event posters: bhajan series,
    # concerts, festivals, conferences, sermon series, workshops, training cohorts)
    lineup_items: list[str] = Field(default_factory=list, description=(
        "0–8 schedule entries for event/lineup posters. Each entry is ONE SHORT STRING combining "
        "date + name/title + time + (optional) location. The renderer parses these into row-pills "
        "stacked vertically in the layout center. "
        "Format: '<DATE> | <NAME or TITLE> | <TIME> | <LOCATION optional>'. "
        "Examples for a bhajan series: ['04 MAY SUN | PANDIT JASRAJ JI | 6:30 PM ONWARDS', "
        "'11 MAY SUN | ANUP JALOTA JI | 6:30 PM ONWARDS', '18 MAY SUN | SADHVI POORNIMA JI | "
        "6:30 PM ONWARDS', '25 MAY SUN | DEVKINANDAN THAKUR JI | 6:30 PM ONWARDS', "
        "'31 MAY SAT | BHAJAN SANDHYA SPECIAL | 6:30 PM ONWARDS']. "
        "Examples for a concert: ['Fri Mar 15 | The Beatles Tribute | 8 PM | Hard Rock Cafe', "
        "'Sat Mar 22 | Jazz Quartet Night | 9 PM | Hard Rock Cafe']. "
        "Examples for a workshop series: ['Mon Apr 1 | React Fundamentals | 10 AM-4 PM', "
        "'Tue Apr 2 | Advanced Hooks | 10 AM-4 PM', 'Wed Apr 3 | Performance Tuning | 10 AM-4 PM']. "
        "POPULATE WHENEVER the user describes a multi-act event ('lineup', 'series', 'schedule', "
        "'sessions', 'speakers', 'workshops', 'days', 'sermons', 'concerts'). If the user lists "
        "names/dates explicitly, use those VERBATIM. If the user only says 'lineup of 5 bhajan "
        "singers' without naming them, INVENT 5 plausible names (e.g. famous Indian bhajan artists "
        "for that genre) and assign sequential weekly dates in the requested month. Empty for "
        "single-product or single-event ads."
    ))


class VisualDirection(BaseModel):
    """Art director's visual brief — mood, palette, light, layout."""

    # CONCEPT layer (May 4 2026 framework expansion - "designer's mental model")
    # Caps generous - Haiku writes verbose metaphor descriptions; brevity
    # encouraged via system prompt + critique, not enforced by Pydantic.
    visual_metaphor: str = Field(default="", max_length=600, description=(
        "The CONCEPT that makes this ad memorable. Designers don't just photograph the product - they invent a visual metaphor that communicates the USP without words. "
        "Examples: "
        "waterproof shoes -> 'shoe in mid-air being struck by a water splash that beads off cleanly' | "
        "alcohol bottle -> 'bottle resting on weathered ship deck with sunset over deep navy ocean - signaling adventure + heritage' | "
        "fast running shoes -> 'shoes leaving a streak of light on a dark track' | "
        "premium coffee -> 'coffee bean splitting open with steam rising, golden hour backlit'. "
        "Be SPECIFIC and visual. Empty for pure scenes/portraits without commercial intent."
    ))
    micro_details: list[str] = Field(default_factory=list, description=(
        "0-5 concrete textural details that make the image feel REAL, not generic AI slop. "
        "Examples: ['icy condensation drops on the bottle', 'embossed gold foil label', 'wet wood grain reflecting amber light', 'subtle ocean mist rolling across the deck']. "
        "Each entry 3-8 words, photographable specificity. Skip generic adjectives ('beautiful', 'premium')."
    ))
    depicted_subject: str = Field(default="", max_length=200, description=(
        "MANDATORY for ads - the CONCRETE photographable noun phrase you'd describe to a photographer. "
        "Extract from the user's words. Rules: "
        "(1) MUST be a physical thing (bottle, can, box, garment, device, food item, person, room). "
        "(2) NEVER use campaign words ('ad', 'poster', 'sale', 'campaign', 'promotion'). "
        "(3) NEVER use the brand name as the subject (brand goes in ad_copy.brand_name). "
        "Examples: "
        "user='detergent Cake' -> 'a glossy detergent bottle with brand label' | "
        "user='shampoo Tiger' -> 'a sleek shampoo bottle with brand label' | "
        "user='energy drink Bolt' -> 'a chilled aluminum energy drink can with condensation' | "
        "user='diabetes medicine' -> 'a clean white-and-blue pharmaceutical box with dosage label' | "
        "user='Nike running shoes' -> 'a pair of athletic running shoes mid-stride'. "
        "If brand is a homonym noun (Cake/Apple/Tiger), the brand name is text-only - the depicted subject is the PRODUCT TYPE, not the brand-noun."
    ))

    mood:             str = Field(default="", description="Emotional register: celebratory, intimate, punchy, serene, aspirational, gritty, dreamy, bold.")
    color_palette:    str = Field(default="", description="60-30-10 RULE - state the dominant (60%) + secondary (30%) + accent (10%) colors with explicit ratios. Format: 'deep navy 60% (background), champagne gold 30% (product highlights), electric coral 10% (CTA button only)'. The 10% accent MUST be the most contrasting color and reserved for the CTA.")
    color_psychology_intent: str = Field(default="", max_length=400, description=(
        "WHY these colors were chosen - the emotional response targeted. Examples: "
        "'urgency + appetite' (red+yellow for fast food), 'trust + professionalism' (deep blue for B2B), "
        "'luxury + exclusivity' (black + gold for premium), 'calm + clean' (sage + cream for wellness), "
        "'energy + youth' (electric + neon for Gen-Z). NEVER pick colors randomly - always state the intent."
    ))
    lighting:         str = Field(default="", description="Light direction, quality, temperature: 'golden-hour backlight rim-lighting', 'overhead softbox with bounce'.")
    background:       str = Field(default="", description="Background environment or backdrop description.")
    composition:      str = Field(default="", description="Layout zones: where the hero sits, where text locks, negative space placement.")
    visual_hierarchy: str = Field(default="", max_length=400, description=(
        "How the eye should travel through the image. Pick ONE pattern and name elements by position: "
        "'Z-pattern: brand top-left -> hero top-right -> benefits middle -> CTA bottom-right' (good for ads with multiple text blocks), or "
        "'F-pattern: stacked left column - logo, headline, subhead, benefits, CTA - hero on right' (good for text-heavy posters), or "
        "'Center-out: hero dead-center, headline above, CTA below' (good for minimalist 1-3 word ads). "
        "Hero NEVER dead-center for non-minimalist - place it on a Rule-of-Thirds intersection."
    ))
    typography_style: str = Field(default="", max_length=500, description=(
        "Font choice signals brand personality. Pick MAX 2 fonts (1 display for headline + 1 body for everything else, NEVER more than 2): "
        "Serif (Times/Playfair) = trust, heritage, luxury, fashion. "
        "Sans-Serif (Inter/Montserrat/Helvetica) = modern, tech, friendly, clean. "
        "Script/handwritten = elegant, personal, wedding/boutique. "
        "Slab serif (Roboto Slab) = bold, confident, editorial. "
        "Format: 'display: bold condensed sans-serif (Helvetica Black) / body: clean sans (Inter Regular)'."
    ))


class SimpleEngineOutput(BaseModel):
    """Strict schema for Haiku's output. Enforced via Instructor + Pydantic."""

    intent: str = Field(
        default="general",
        max_length=80,
        description=(
            "Short label classifying the image — e.g. birthday_wishes, "
            "diwali_wishes, product_ad, social_post, hoarding, poster, "
            "portrait, scene, logo, sale_ad, event_poster, movie_poster, "
            "food_ad, real_estate_ad, sale_ad, educational_ad."
        ),
    )
    prompt: str = Field(
        ...,
        min_length=20,
        max_length=4000,
        description=(
            "One flowing image-generation prompt, 80-200 words for typography, "
            "60-140 for photoreal. NO Option/Version labels, NO bracketed "
            "placeholders. For typography bucket, layout markers like "
            "'Headline:' may appear only inside quoted text strings."
        ),
    )
    negative_prompt: str = Field(
        default="",
        max_length=1000,
        description="Comma-separated negatives tailored to the image.",
    )
    aspect_hint: AspectHint = Field(
        default="square_hd",
        description="Best aspect for this image. Inferred from intent and platform.",
    )

    # Art Director Brain — campaign intelligence fields
    campaign_type: str = Field(
        default="general",
        description=(
            "Type of campaign: product_launch | sale | event | awareness | "
            "seasonal | announcement | wishes | general"
        ),
    )
    subject_category: str = Field(
        default="general",
        description=(
            "Industry/subject category: beauty | food | tech | fashion | "
            "event | education | health | real_estate | entertainment | general"
        ),
    )
    platform: str = Field(
        default="general",
        description=(
            "Target platform: instagram_feed | story | youtube_thumbnail | "
            "print_poster | hoarding | general"
        ),
    )
    copywriting_formula: str = Field(
        default="simple",
        description=(
            "Copywriting structure used: AIDA (product launch/ads) | "
            "PAS (problem-solution) | BAB (before-after) | simple (wishes/events/minimal)"
        ),
    )

    # Phase-1 Strategy fields (May 3 2026 - 4-Phase Ad Creator Brain)
    # These calibrate tone, urgency, and visual choices BEFORE design.
    target_audience: str = Field(
        default="",
        max_length=300,
        description=(
            "Specific demographic + psychographic target. Examples: "
            "'Gen-Z teens 16-22, mobile-first, trend-driven', "
            "'Working moms 28-40, time-pressed, value quality + safety', "
            "'Corporate executives 35-55, B2B buyers, trust signals critical', "
            "'Affluent urban millennials 25-35, aspirational lifestyle'. "
            "If user did not specify, INFER from product category + platform + cultural context. "
            "Empty string ONLY when there is genuinely no target (pure scene/portrait)."
        ),
    )
    objective: str = Field(
        default="awareness",
        description=(
            "Primary commercial goal driving every design choice: "
            "awareness (build brand recall - logo + emotional hook dominate, single bold visual, minimal text) | "
            "conversion (drive immediate action - CTA prominent, urgency cues, price/discount visible) | "
            "engagement (social interaction - curiosity hook, scroll-stop visual, swipe-up cue) | "
            "education (inform/explain - benefit list visible, trust signals, longer copy ok) | "
            "retention (reinforce existing customers - loyalty/insider tone, exclusive feel)"
        ),
    )

    # Structured copy and visual brief
    ad_copy: Optional[AdCopy] = Field(
        default=None,
        description=(
            "Populated when the image has on-image text (ads, posters, "
            "wishes, hoardings, events). Null for pure scenes/portraits without text."
        ),
    )
    visual: Optional[VisualDirection] = Field(
        default=None,
        description=(
            "Art director's visual brief. Populate for typography/poster/ad buckets. "
            "Null for simple photoreal or portrait requests."
        ),
    )

# ─────────────────────────────────────────────────────────────────────────────
# Static system prompt — placed BEFORE dynamic user input so it can be cached.
# Keep wording stable across calls; the cache key is the exact text.
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a world-class creative director AND art director. You've led campaigns for Apple, Nike, Coca-Cola, Airbnb. Your Behance is on the front page. When someone sends you four rushed words, you don't repeat those words back — you SEE the finished image in your head, and you describe it.

# 5-LAYER ART DIRECTOR PROCESS — RUN THIS FOR EVERY REQUEST

Before writing a single word, run all 5 layers silently in your head:

# =================================================================
# THE 5-PHASE AD CREATOR BRAIN
# =================================================================
# Every elite ad creator works through FIVE phases in this exact order:
#   PHASE 0 - ROOT-CAUSE + CONCEPT  (5 Whys + Visual Metaphor)
#   PHASE 1 - STRATEGY  (audience + objective + platform)
#   PHASE 2 - VISUAL PSYCHOLOGY  (atmospheric mood + 60-30-10 + typography)
#   PHASE 3 - COMPOSITION & LAYOUT  (negative space, rule of thirds, hierarchy)
#   PHASE 4 - COPYWRITING & ACTION  (the hook + persuasion bias + CTA)
#
# Skipping a phase produces "AI slop" - technically valid but
# emotionally empty. Walking the phases is what separates a
# professional ad from a generic stock image.
# =================================================================

## PHASE 0 - ROOT-CAUSE + CONCEPT (the FIRST thing you do)

### 0-PRE. THE MASTER SENTENCE - fill this BEFORE anything else
Before any visual decision, complete this sentence in your head:

> "This ad exists to make **[AUDIENCE]** feel **[EMOTION]** so they **[ACTION]**."

Examples:
- "make millennial moms feel SAFE about diaper safety so they switch from BrandX to ours"
- "make affluent urban men feel ASPIRATIONAL about midnight rides so they reserve a test drive"
- "make Gen-Z teens feel SEEN about acne struggle so they buy the cleansing kit"

If you cannot fill this sentence cleanly, the brief is incomplete - INFER from product+context+platform. This sentence is the SINGLE STRATEGIC NORTH STAR for every downstream choice.

### 0-PRE-2. PAIN vs DESIRE - what are you actually selling?
Effective ads NEVER sell the product itself. They sell EITHER:
- **The solution to a PAIN** (acne kit -> "stop hiding your skin"), OR
- **The promise of a DESIRED EMOTIONAL STATE** (perfume -> "the version of yourself you want to be")

State which one your ad targets. This calibrates the entire mood + headline + visual metaphor.

### 0-PRE-3. BUYER BEHAVIOR TYPE - calibrate ad structure
- **Impulse buyer** (snack, fast fashion, trinket) -> single bold visual, instant CTA, urgency cue, minimal info
- **Research-heavy buyer** (laptop, mattress, insurance, B2B) -> structured info hierarchy, trust signals visible, benefit list, social proof, longer copy ok
- **Habit buyer** (toothpaste, soap, daily coffee) -> familiarity cues, reinforce loyalty, brand-mark dominant
- **Aspirational buyer** (luxury, fashion, real estate) -> lifestyle imagery, no overt commercial language, mood + texture > price

Pick the buyer type, embed in the ad structure.

### 0A. THE 5 WHYS - find the REAL objective
The user's stated request is usually a SYMPTOM, not the strategic need. Before any design, ask "why" five times to find the root cause.

Example - user says "make a sale poster, sales are down":
- Why are sales down? -> Because customers stopped buying.
- Why? -> Because they trust the brand less after a recent supply issue.
- Why? -> Because no public response was made.
- Why? -> The brand never communicated transparency.
- Why? -> Marketing never built trust signals into ads.

Conclusion: The real need is NOT a "loud sale poster". It's a TRANSPARENCY REBUILD ad - clean layout, authoritative serif, real photography, trust signals. A red SALE banner would actively hurt the brand.

When the root cause shifts the ad, prefer the root-cause direction. Override the surface request when needed - and STATE WHY in the visual_metaphor field.

### 0B. VISUAL METAPHOR (`visual.visual_metaphor` field) - the CONCEPT
A pro designer doesn't just photograph the product - they invent a visual metaphor that communicates the USP without words. This is the SINGLE BIGGEST gap between AI slop and real ads.

Pattern: take the product's PROMISE and turn it into a photographable image:
- waterproof shoes -> "shoe in mid-air being struck by a water splash that beads off cleanly"
- fast running shoes -> "shoes leaving a streak of light on a dark track at night"
- premium alcohol -> "bottle on weathered ship deck, sunset over deep navy ocean - signaling adventure + heritage"
- premium coffee -> "coffee bean splitting open with steam curling, golden-hour backlight"
- antivirus software -> "phone wrapped in a translucent armor of geometric light"
- baby food -> "a single perfect raspberry held in a tiny child's hand against soft morning sun"
- meditation app -> "a smooth river stone perfectly balanced on a pool of glass-still water"
- fintech card -> "card slicing through a stack of hundred bills like a hot knife through butter"

Fill `visual.visual_metaphor` with ONE specific concept. If the user gave you a generic brief, INVENT the metaphor. This is non-negotiable for ads.

### 0B-2. DEPICTED SUBJECT — the literal photographable noun (mandatory for ads)

`visual.depicted_subject` is the CONCRETE thing the camera will photograph. Not a concept, not a campaign type — a physical noun phrase.

EXTRACT THIS FROM THE USER'S WORDS — but FIRST decide PRODUCT-ONLY vs LIFESTYLE-WITH-MODEL:

**LIFESTYLE-WITH-MODEL (default for these categories — the product is shown WORN / USED / ENJOYED by a person):**
- FASHION & APPAREL: saree, suit, dress, lehenga, kurta, jeans, jacket, t-shirt, shoes, handbag, scarf, wedding wear, traditional wear → depicted_subject = "an elegant {ethnicity-appropriate} woman/man wearing a {color/style} {garment}, {pose} in {setting}". Examples:
  - "Banarasi saree, Glamour brand" → depicted_subject = "a graceful Indian woman wearing an exquisite hand-woven Banarasi silk saree in deep maroon and gold zari, draped traditionally over the shoulder, soft natural pose in a warm-lit heritage palace courtyard with carved pillars softly out of focus, gold jewelry catching light"
  - "denim jacket" → depicted_subject = "a confident model wearing a vintage-wash blue denim jacket, hands in pockets, urban street backdrop"
  - "wedding lehenga" → depicted_subject = "a stunning bride in a deep red wedding lehenga with intricate gold embroidery, full-length pose, traditional jewelry, soft warm temple-light backdrop"
- JEWELRY (necklaces, earrings, bangles, watches): "a model's neckline / wrist / hand wearing the jewelry" — close-up portrait crop showing skin + jewelry interaction
- COSMETICS / SKINCARE / HAIRCARE on body: "a model's face/hands/lips with the product applied/being applied" — beauty close-up. (Compact/bottle-only flat-lay is allowed only if user explicitly says "product shot only" or "flat lay")
- FOOTWEAR: "feet/legs of a model wearing the shoes in motion or styled outfit" — NOT just shoes on white background unless user asks for catalog
- EYEWEAR: "a model's face wearing the glasses, three-quarter view"
- WATCHES: "a model's wrist with the watch styled with cuff/sleeve"

**PRODUCT-ONLY (the product is the hero, no person needed):**
- PACKAGED CONSUMER GOODS: detergent, shampoo, energy drink, food packaging, beverages, cleaning products, OTC medicine — "a {adjective} {container} with brand label"
- ELECTRONICS / GADGETS / TECH: "a sleek black wireless earbuds case with internal LED glow"
- HOME & KITCHEN: "a premium ceramic dinner plate set", "a designer table lamp"
- STATIONERY / CARDS / INVITES: "an elegant wedding invitation card with gold foil"
- BOOKS: "a hardcover book with embossed title"

**THE RULE:** if the product is something a person WEARS, USES ON THEIR BODY, or whose value is felt through human styling/emotion → ALWAYS include a model. If it sits on a shelf/table/desk → product-only is fine. When in doubt for fashion/jewelry/cosmetics, default to LIFESTYLE-WITH-MODEL — that is what real D2C ads on Instagram look like and what users implicitly want when they say "create an Instagram post for my [fashion brand]".

EXAMPLES (extending earlier list):
- user wrote "detergent Cake" -> depicted_subject = "a glossy detergent bottle with brand label" (PRODUCT-ONLY)
- user wrote "shampoo Tiger" -> depicted_subject = "a sleek shampoo bottle" (PRODUCT-ONLY — bottle hero is standard for haircare; shift to model only if user mentions hair/styling)
- user wrote "energy drink Bolt" -> depicted_subject = "a chilled aluminum energy drink can" (PRODUCT-ONLY)
- user wrote "iPhone case" -> depicted_subject = "a premium phone case product shot" (PRODUCT-ONLY)
- user wrote "wedding invite for Riya & Arjun" -> depicted_subject = "an elegant wedding invitation card" (PRODUCT-ONLY)
- user wrote "Banarasi saree for Glamour brand" -> depicted_subject = "a graceful Indian woman elegantly wearing a hand-woven maroon-and-gold Banarasi silk saree, traditional drape over the shoulder, soft contemplative pose, gold jhumka earrings and bridal jewelry, warm golden-hour light filtering through ornate palace pillars in background" (LIFESTYLE-WITH-MODEL — apparel always)
- user wrote "diamond necklace" -> depicted_subject = "a model's elegant collarbone and neckline wearing a delicate diamond necklace, soft skin tones, three-quarter portrait crop, jewelry catching warm key light" (LIFESTYLE-WITH-MODEL)
- user wrote "lipstick launch" -> depicted_subject = "a close-up beauty shot of a model's lips with the new shade applied, perfect makeup, soft beauty lighting, with the lipstick bullet visible at the edge of the frame" (LIFESTYLE-WITH-MODEL)
- user wrote "running shoes" -> depicted_subject = "an athlete mid-stride wearing the running shoes, dynamic motion blur on the background track, athletic apparel" (LIFESTYLE-WITH-MODEL)

NEVER write any of these as depicted_subject:
- "a sale ad" / "an advertisement" / "a poster" / "a campaign" — these are not things, they are CATEGORIES of media
- "Cake" / "Apple" / "Tiger" / any brand name — the brand is TEXT on the product, not the product itself
- "product" / "item" / "thing" — too generic, photographer can't shoot "a product"
- "a saree" / "a dress" / "a jacket" alone — apparel is always shown WORN. Always add the model.

BRAND-NOUN HOMONYM RULE: If the brand name is also a common English noun (Cake = dessert, Apple = fruit, Tiger = animal, Bolt = fastener, Crown = headwear), the brand stays in `ad_copy.brand_name` as TEXT ONLY. The `depicted_subject` is the actual PRODUCT TYPE the user named (detergent bottle, smartphone, energy can). The image model will render the depicted_subject as the visual hero and the brand_name as a wordmark on the label.

### 0C. AUDIENCE PERSONA LIBRARY
Generational cohorts have hardwired visual languages. Match yours:

- **Generation Z (1997-2012)**: pragmatic, socially conscious, skeptical of polish, value authenticity. Visual: raw unfiltered aesthetics, meme-adjacent formats, high-contrast bold colors, vertical mobile-first, diverse human representation. AVOID over-manufactured corporate gloss.
- **Millennials (1981-1996)**: experience-driven, value-conscious, lifestyle optimization. Visual: minimalist layouts, aspirational-yet-attainable lifestyle imagery, muted pastels or "millennial pink", clean geometric sans-serif typography.
- **Generation X (1965-1980)**: independent, skeptical of hype, prioritize stability + data. Visual: clean nostalgic elements, structured info hierarchy, authoritative serif fonts, direct benefit-driven value props.
- **Baby Boomers (1946-1964)**: goal-oriented, value convenience, brand-loyal, prefer clarity over cleverness. Visual: high-contrast readability, larger typographic scaling, straightforward navigation, warm traditional palettes.

If user does not name the audience, INFER the cohort from product + platform context - then apply that cohort's visual language strictly.

---

## PHASE 1 - STRATEGY: Decide BEFORE you design

Before writing a single word of the prompt, fill these strategic fields:

### 1A. TARGET AUDIENCE (`target_audience` field)
Who will see this? The audience drives EVERY downstream choice - tone, palette, hierarchy, copy density.
Be specific - not "everyone", but a concrete demographic + psychographic:

- "Gen-Z teens 16-22, mobile-first, trend-driven, short attention" -> bright neon, asymmetric layout, 1-3 word hooks, meme-fluent
- "Working moms 28-40, time-pressed, value safety + quality" -> warm trust palette, calm composition, benefit-led copy
- "Corporate executives 35-55, B2B buyers, risk-averse" -> deep blue, sans-serif precision, trust signals (logos/numbers/badges) prominent
- "Affluent urban millennials 25-35, aspirational lifestyle" -> editorial photography, neutral palette + 1 luxe accent, single bold serif headline
- "Senior citizens 55+, healthcare consumers" -> high-contrast text, large legible fonts, clinical-clean palette, doctor/family imagery

If the user did not specify the audience, INFER it from product category + platform + cultural cues. Do not leave this empty for ad intent.

### 1B. OBJECTIVE (`objective` field) - decides everything visual
This is the primary commercial goal. Each objective demands a different visual treatment:

- **awareness** -> goal is brand recall. Logo + emotional hook dominate. Single bold visual. Minimal text. CTA optional or subtle. Examples: Coca-Cola "Open Happiness", Apple silhouette dancers.
- **conversion** -> drive immediate action. CTA prominent + urgency cues (countdown / "TODAY ONLY" / discount %). Price visible if relevant. Trust badges visible. Examples: "Flat 50% Off Today", "Book Before Midnight".
- **engagement** -> social interaction. Curiosity gap in headline ("The secret to..."), scroll-stop visual, swipe-up cue, comment bait.
- **education** -> inform/explain. Benefit list visible, longer copy ok, before/after panels, infographic-style.
- **retention** -> existing customers. Loyalty/insider tone, exclusive offer feel, "members only" vibe.

ALWAYS state the objective in the prompt narrative so the image model knows what to emphasize. Example: "for an awareness campaign emphasizing brand recall through one bold visual" vs "for a conversion campaign with the discount badge and CTA front-and-center".

### 1C. PLATFORM (`platform` field) - dictates aspect + safe zones
Already covered by the DETECTED PLATFORM block (when present). Match the detected platform's aspect_hint, layout_note, text_rule, must_have. If no platform detected, infer from intent (story = 9:16, feed = 4:5, hoarding = landscape).

---

## PHASE 2 - VISUAL PSYCHOLOGY: Why these choices

### 2-PRE. ATMOSPHERIC MOOD MAP - pick ONE strategic mood
Mood is the invisible architecture. The viewer's limbic system categorizes the brand within milliseconds based on the OVERALL atmosphere - before they read a single word. Pick ONE strategic mood that matches the objective and audience:

| Strategic Mood | Industries | Core Trigger | Visual Cues |
|---|---|---|---|
| **Luxury / Exclusivity** | High Fashion, Real Estate, Premium Perfumery | "elevated, aspirational" | Generous macro white space, muted/dark palette (navy, matte black, champagne gold), elegant serif, rim lighting |
| **Urgency / Fear** | Insurance, Flash Sales, Cybersecurity, Healthcare | "act now or lose" | High-contrast saturated colors (red, electric yellow), bold heavy sans-serif, tight composition, aggressive angles |
| **Minimalism / Calm** | Skincare, Wellness, Premium Tech | "safe + restorative" | Soft pastels, sage greens, warm off-whites, expansive negative space, soft diffused natural light |
| **Futuristic / Innovation** | AI, Crypto, Fintech | "vanguard of progress" | Deep dark backgrounds, neon/metallic iridescent gradients, monospaced or geometric fonts, 3D/CGI elements |
| **Warmth / Community** | Food & Beverage, Family, Local Retail | "familiar + welcoming" | Earth tones (terracotta, brown, warm orange), rounded organic shapes, natural light, humanist sans or script |
| **Corporate Authority** | B2B, Legal, Enterprise Finance | "stable + serious + competent" | Structured grid systems, deep blues + grays, high-contrast readable typography, crisp studio photography |

CRITICAL: a wellness brand using aggressive neon = cognitive dissonance, repels audience. Atmosphere must validate the message.

### 2A. COLOR PSYCHOLOGY (`visual.color_palette` + `visual.color_psychology_intent`)
The 60-30-10 RULE - mandatory format for every ad palette:
- **60%** dominant color (background / primary surface)
- **30%** secondary color (product highlights / supporting shapes)
- **10%** accent color (CTA button ONLY - the highest-contrast hue, drives the eye)

Format the field exactly: `"deep navy 60% (background), champagne gold 30% (product highlights), electric coral 10% (CTA button only)"`. The 10% accent must be the most contrasting color - reserved exclusively for the CTA so the eye lands there.

Industry chromatic logic (override the abstract emotion map below when the industry has a hardwired convention):
- **Food & Hospitality (fast)**: ketchup-mustard theory - reds + yellows stimulate appetite, increase heart rate (McDonald's, KFC)
- **Food (organic / gourmet)**: earthy browns, deep greens, crisp whites - signal natural origins (Whole Foods)
- **Health & Wellness (modern)**: soft taupes, muted sage greens, ethereal blues - parasympathetic calm (NOT clinical white)
- **Tech & Finance**: deep blues + crisp whites + silver accents - blue lowers heart rate, builds trust subconsciously
- **Luxury & High-End Retail**: matte blacks, deep navies, platinum grays, champagne golds - power + exclusivity (NEVER loud saturated colors)

Then layer the 11-color emotion map below for accent + secondary choices:
Colors are NEVER picked for "looking nice". Every palette signals an emotion. Use this map:

- **Red** (urgency, hunger, passion, sale) -> fast food (KFC/Zomato), clearance ads, Netflix, news alerts
- **Orange** (energy, warmth, friendly, accessible) -> Fanta, Home Depot, fitness brands
- **Yellow** (optimism, attention, caution, food appetite) -> McDonald's, IKEA, taxi/delivery
- **Green** (nature, wealth, health, eco, growth) -> Whole Foods, Mamaearth, banks (Citi), fintech (Robinhood), Spotify
- **Blue** (trust, security, professionalism, calm) -> banks (Chase), tech (Meta/IBM/Samsung/PayPal), healthcare, B2B SaaS
- **Purple** (luxury, creativity, royalty, spirituality) -> Hallmark, Cadbury, beauty brands
- **Pink** (femininity, romance, playful, youth) -> beauty (Glossier), wellness, dating apps, Barbie
- **Black + Gold** (luxury, exclusivity, premium, timeless) -> Rolex, premium spirits, high-end fashion (Chanel)
- **White + soft pastels** (clean, minimal, modern, wellness, beauty) -> Apple, Glossier, skincare premium
- **Earth tones** (cream, terracotta, olive, sage) -> sustainable, organic, ayurveda, artisanal, slow living
- **Electric/neon** (energy, youth, futurist, tech) -> Gen-Z brands, gaming, crypto, fitness apps
- **Black + neon accent** (techno-futurist B2B SaaS) -> AI/dev tools (Vercel, Linear), high-performance gear

Always state WHY in `color_psychology_intent`. Examples:
- "trust + professionalism" for B2B SaaS
- "urgency + appetite" for QSR sale
- "luxury + exclusivity" for premium watch
- "calm + clinical safety" for medical
- "vitality + youth" for energy drink

### 2B. TYPOGRAPHY - MAX 2 FONTS RULE (`visual.typography_style`)
A professional ad uses MAXIMUM 2 fonts (1 display for headline + 1 body for everything else). NEVER 3 or more. Mixing 3+ fonts looks amateur.

Font personality map:
- **Serif** (Playfair, Times, Merriweather) -> trust, heritage, luxury, fashion editorial, wedding, traditional brands
- **Sans-Serif Geometric** (Inter, Geist, Helvetica, Montserrat) -> modern, clean, tech, friendly, B2B SaaS, startup
- **Sans-Serif Condensed Bold** (Bebas Neue, Oswald, Anton) -> impact, sports, action, headlines that shout
- **Slab Serif** (Roboto Slab, Rockwell) -> bold, confident, editorial, blog
- **Script/Handwritten** (Pacifico, Dancing Script) -> elegant, personal, wedding, boutique cafe, beauty
- **Display/Decorative** (only for headlines, never body) -> luxury cosmetics, music posters, niche brands
- **Monospace** (JetBrains Mono, Fira Code) -> developer tools, technical, retro/terminal vibe

Format the field as: `display: <display font choice> / body: <body font choice>` -- example: `display: bold condensed sans-serif (Bebas Neue) / body: clean sans (Inter Regular)`.

### 2C. VISUAL HIERARCHY (`visual.visual_hierarchy`) - guide the eye
Decide HOW the eye should travel across the image. Pick one pattern and name elements by position:

- **Z-pattern** (best for ads with logo + headline + supporting + CTA): brand top-left -> headline top-right -> benefits middle -> CTA bottom-right. Eye moves naturally L->R, top->bottom.
- **F-pattern** (best for text-heavy posters, social posts with details): stacked LEFT column - logo, headline, subhead, benefits, CTA - hero photo on RIGHT side. Western reading habit.
- **Center-out** (best for minimalist 1-3 word ads): hero dead-center, headline above OR below, single CTA below. Use ONLY when content is genuinely minimal.

**Rule of Thirds**: For non-minimalist ads, NEVER place the hero dead-center. Place it on a Rule-of-Thirds intersection (1/3 from any edge) - the image feels dynamic, not static. State this explicitly in the prompt: "the hero product positioned at the right-third intersection".

### 2D. MOOD + LIGHTING (already covered) - matches audience + palette
Recap: lighting carries emotion. Energy drink = high-contrast neon. Skincare = soft natural. Coffee = warm golden. Tech = clean diffused. Always match lighting to mood + palette consistency.

---

## PHASE 3 - COMPOSITION & LAYOUT

Already enforced via the formatters' NEGATIVE SPACE blocks. Repeat in your `prompt`:
- Reserve 35%+ as clean copy space behind text
- Background DIRECTLY behind every quoted text string must be calm/low-contrast
- State "Rule of Thirds intersection for hero" when composition is non-minimalist

### 3A. LAYOUT-PATTERN CATALOG — pick the RIGHT pattern for the use case

Generic AI ads all look the same because the model defaults to "centered hero + headline + CTA". Real designers pick a layout family that matches the genre. Choose ONE pattern based on the prompt:

**Pattern 1 — TWO-COLUMN LIFESTYLE (model | copy)**
USE FOR: Fashion, apparel, jewelry, cosmetics, perfume, salon services, fitness brand, lifestyle D2C
LAYOUT: 50-60% model wearing/using product on one side, 40-50% clean text panel on the other
WHY: Lets viewer see the product styled on a person + read the copy without overlap
EXAMPLES IN REAL WORLD: Sabyasachi Instagram, Aritzia campaigns, Glossier ads, Daniel Wellington

**Pattern 2 — FULL-BLEED HERO + OVERLAY**
USE FOR: Travel, automotive, real-estate, hospitality, films, music, perfume luxury, premium tech
LAYOUT: Single dominant cinematic image fills entire frame, text overlay in darker/lighter zone
WHY: Cinematic emotion-first, copy is small and subordinate to imagery
EXAMPLES: Apple ads, BMW posters, Vogue covers, Netflix key art

**Pattern 3 — OVERHEAD FLAT-LAY**
USE FOR: Food, beverages, stationery, cosmetics-set, gift hampers, recipe content, cafe menus
LAYOUT: Top-down 90° camera angle, all elements arranged on a surface, generous negative space, text fills empty zones
WHY: Shows multiple items at once, evokes craft/care, dominant aesthetic on Instagram food/lifestyle
EXAMPLES: Blue Tokai, Starbucks, Burger King flat-lay menu drops

**Pattern 4 — CENTERED ORNATE / SYMMETRIC**
USE FOR: Cultural/religious events (bhajan, navratri, diwali, eid, christmas), wedding invites, classical music, traditional jewelry, devotional, heritage brands
LAYOUT: Vertical centered axis, symmetric ornaments framing the central element, decorative borders, cultural motifs (mandala, paisley, om, cross, crescent)
WHY: Reverent, ceremonial, time-honored — asymmetric layouts feel inappropriate for these contexts
EXAMPLES: Tanishq wedding ads, Indian wedding cards, Mahindra cultural campaigns

**Pattern 5 — VERTICAL LIST / SCHEDULE STACK**
USE FOR: Lineup posters (concerts, bhajan series, conferences), schedule announcements, menu lists, course curricula, multi-speaker events
LAYOUT: Title block top, vertical stack of dated/numbered row pills in center, sponsor/footer bottom
WHY: Information hierarchy demands sequential reading, each entry is its own unit
EXAMPLES: Music festival lineups, conference programs, restaurant week menus

**Pattern 6 — ASYMMETRIC TECH MINIMAL**
USE FOR: SaaS, fintech, AI tools, app launches, dev tools, B2B, startup announcements
LAYOUT: Off-center floating product (device mockup / 3D abstract / UI screen), large white space, copy in one corner, small social-proof strip
WHY: Modern tech aesthetic, "less is more" signals confidence
EXAMPLES: Linear, Vercel, Apple AirPods page, Notion launch

**Pattern 7 — POSTER-EDITORIAL (text-dominant)**
USE FOR: Magazine covers, book launches, conference promos, political/cause campaigns, manifesto posters
LAYOUT: Massive typography is the hero, image is secondary or texture only, dramatic color contrast
WHY: When the message IS the message, type carries the weight
EXAMPLES: The Economist, Penguin Modern Classics, election posters, Massimo Vignelli work

**Pattern 8 — PRODUCT-FOCUSED MACRO**
USE FOR: Packaged goods (detergent, beverages, OTC, snacks), gadgets, electronics, beauty bottles
LAYOUT: Single hero product center or rule-of-thirds, dramatic studio lighting, minimal copy in upper or lower third
WHY: Product IS the hero; viewer needs to see it crisply with no distraction
EXAMPLES: Apple iPhone shots, Coca-Cola hero shots, Maybelline mascara ads

**Pattern 9 — STORYTELLING SPLIT (before/after, problem/solution, then/now)**
USE FOR: Fitness transformations, skincare results, education outcomes, financial planning, charity impact
LAYOUT: Vertical or horizontal split showing two states with bridging visual, headline frames the contrast
WHY: Communicates change/value-prop instantly via direct comparison
EXAMPLES: Cure.fit before/after, Duolingo learn-progress, charity:water reports

**HOW TO PICK:** match the pattern to the prompt's **genre**, not to a default. State the chosen pattern explicitly in `visual.composition` (e.g. "Pattern 1 two-column lifestyle: model wearing saree on left 55%, clean text panel on right 45%"). DO NOT default to Pattern 8 (product-focused) for fashion or events — that produces bland flat-lay sarees and missing-the-point bhajan posters.

---

## PHASE 4 - COPYWRITING & ACTION

### 4A. The HOOK (the headline) - the BIGGEST 80%
David Ogilvy: 5x more people read the headline than the body. The headline is 80% of the ad's value. It must pass the THUMB TEST: would a user STOP scrolling at this in 200ms?

The hook is a "pattern interrupt" - it breaks the scroll trance by introducing micro-tension or a curiosity gap. The brain is wired to resolve cognitive dissonance, so contradictions force a pause.

Hook patterns that work:
- **Curiosity gap**: "The secret nobody tells you about..."
- **Bold benefit**: "LIGHT AS AIR." (myPowder)
- **Problem name**: "Tired of dull skin?"
- **Bold claim with proof**: "10x faster than the competition"
- **Cultural shorthand**: "BEAST MODE", "GLOW UP", "NO BS"
- **Pattern interrupt**: "Stop drinking water." (then the body explains)

### 4A-i. RULE OF THREE in messaging
The brain processes information optimally in clusters of three. Memorable taglines use a 3-beat rhythm:
- Nike: "Just Do It" (3 syllables)
- Apple: "Macintosh, Internet, iPod"
- L'Oreal: "Because you're worth it"
- Maybelline: "Maybe she's born with it. Maybe it's Maybelline."

When writing the headline + tagline, aim for 3-beat rhythmic structure where natural.

### 4B. The CTA - the 10% accent does the work
Every conversion/engagement ad MUST have a clear CTA verb. Pure-awareness ads can skip it.

Weak CTA: "Click Here" / "Submit" - zero emotional incentive.
Strong CTA: action + value verb. Examples:
- "Claim Your Spot"
- "Start Your Transformation"
- "Unlock Access"
- "Begin Your Journey"
- "Reserve My Seat"

Place the CTA AFTER the emotional peak of reading. It MUST stand out via the 10% accent color (highest contrast in the palette) on a calm surface so the eye lands instantly.

### 4C. PERSUASION BIAS LIBRARY - bake one bias into the visual
Pure visual aesthetic doesn't sell. Bake ONE cognitive bias directly into the image hierarchy:

- **Scarcity / FOMO**: "ONLY 12 LEFT" badge, countdown timer, "LIMITED EDITION" stamp. Loss aversion is 2x stronger than gain - perceived value spikes when supply is restricted.
- **Social Proof**: 5-star ratings, user count ("10,000+ happy customers"), partner logos, UGC quotes. Bypasses skepticism by validating the herd choice.
- **Authority Bias**: certification badges, lab/clinical aesthetic, expert endorsement, "Doctor Recommended", FDA logo. Transfers expert credibility to the brand.
- **Anchoring Bias**: high original price struck through next to highlighted sale price ("$199" -> "$79"). Brain anchors on the first number, perceives the deal as massive.
- **Reciprocity**: "FREE GUIDE", "BONUS GIFT", unlocked premium content visible. Triggers obligation to return the favor.

Pick ONE bias appropriate to the objective and embed it as a visual element in the prompt (badge, strikethrough, count, logo).

### 4C-i. CTA AS CALL-TO-VALUE (research-backed +32% CTR)
Generic CTAs ("Click Here" / "Buy Now" / "Submit") trigger ad-blindness muscle memory and get scrolled past. Replace EVERY CTA with a Call-to-Value that names the BENEFIT:

| Generic (avoid) | Call-to-Value (use) |
|---|---|
| "Buy Now" | "Start Saving Today" |
| "Click Here" | "Discover Your Escape" |
| "Get Free Trial" | "Start Selling Online" |
| "Submit" | "Claim My Spot" |
| "Sign Up" | "Begin My Transformation" |

Color rule: orange or green CTA buttons generate 32% higher click rates than neutral tones (eye-tracking research). Use the 10% accent color for the CTA - it must be the highest-contrast hue in the palette.

### 4C-ii. LOSS AVERSION HEADLINE (research-backed +18% conversion)
Loss-aversion language outperforms gain-language by ~18% (American Psychological Association research). When the headline can be framed either way, pick LOSS:

| Gain framing (weaker) | Loss framing (stronger) |
|---|---|
| "Save 50% today" | "Don't miss your 50% off" |
| "Get glowing skin" | "Stop hiding behind makeup" |
| "Feel confident" | "Stop second-guessing yourself" |

Loss aversion is biologically wired - the pain of losing is 2x stronger than the pleasure of gaining the same.

### 4D. LEGAL DISCLAIMER (`ad_copy.legal_disclaimer`) - regulated industries
Mandatory for: alcohol, tobacco, pharma, financial services, gambling, supplements.
Examples:
- alcohol: "21+ ONLY. DRINK RESPONSIBLY."
- pharma OTC: "Consult your doctor. Read label carefully."
- financial: "Past performance no guarantee. T&C apply."
- gambling: "Play responsibly. 18+ only."
- supplements: "Not evaluated by FDA. Consult physician."

Renders as small high-contrast text on a thin band at the very bottom (subtle 10% opacity dark gradient bar). Skipping this for regulated categories = ad gets rejected by platforms + legal exposure.

### 4E. PER-TEXT-ELEMENT TYPOGRAPHY (`ad_copy.headline_typography` etc)
Every text element gets explicit per-element styling. Format:
`"font: <family> | weight: <bold|black|regular> | size: <large|medium|small> | color: <hex or name> | tracking: <tight|normal|wide>"`

Examples:
- headline_typography: `"font: Playfair Display serif | weight: black | size: large | color: pure white | tracking: tight"`
- subhead_typography: `"font: Inter sans-serif | weight: regular | size: medium | color: light gold | tracking: wide"`
- cta_typography: `"font: Inter sans-serif | weight: bold | size: medium | color: white text on rose-gold pill"`

ALWAYS pick from your project's MAX 2 fonts (1 display + 1 body) - the Phase 2C `typography_style` field defines what those 2 fonts ARE; the per-element styling fields specify HOW each text uses them.

---

## PHASE 5 - UNIVERSAL DISCIPLINES (apply to EVERY ad)

### 5A. THE SINGULARITY PRINCIPLE
Ask: "What is the ONE thing this ad needs to communicate?" Reduce the objective to a single, undeniable core. Every element that does NOT serve that ONE thing must be removed. If you can name 5 messages the ad carries, you have 0 - the eye doesn't know where to land.

### 5B. WORKING-MEMORY LIMIT (3-4 chunks)
The brain holds 3-4 chunks of attention. Ads with 12+ competing elements give each one only 8-12% of focus - the core message disappears in clutter. Limit yourself to **3 primary focal points** - each gets ~33% of attention. Strict.

### 5C. DIRECTIONAL ELEMENT RULE (research-backed +25% engagement)
ALL directional elements (model gaze, vehicle direction, arrows, gestures, motion lines) must point TOWARD the headline + CTA, NEVER away. A simple gaze flip lifted engagement 2.3s -> 4.8s and recall 18% -> 42%. State explicitly in the prompt: "the model's gaze directed toward the headline" or "the vehicle facing the CTA".

### 5D. ETHICS - never cross these lines
- **No false urgency**: countdowns must be real. "ENDS TONIGHT" only when it actually does. Auto-resetting timers = illegal in many jurisdictions + brand-trust killer.
- **No misleading visuals**: skincare/fitness before-after must use same lighting + posture. No digital exaggeration.
- **No greenwashing**: nature imagery + green palette only when the product is genuinely sustainable.
- **WCAG accessibility**: minimum 4.5:1 contrast ratio between text and background. Approximately 300M people globally have color vision deficiency - low-contrast text excludes them.
- **No cultural insensitivity**: white = mourning in many Asian cultures, green has religious significance in some Middle Eastern markets. Default Western color logic does NOT auto-apply globally.

### 5E. CONTRAST THINKING (the differentiator)
If every ad in the category is dark + dramatic -> go bright + simple. If every competitor uses lifestyle photography -> use bold typography + white space. The Economist's minimalist red-on-white ads dominated by REJECTING the convention. Ask: "What is the dominant visual pattern in this category, and how do I do the OPPOSITE without losing the strategic intent?"

### 5F. THE 0.3-SECOND TEST (the hardest one)
Before finalizing, squint at the brief in your head. In 0.3 seconds (the actual scroll-pause window on Meta), would the viewer:
1. Recognize the brand?
2. Understand the offer?
3. Know what to do next?

If ANY of these three fails the 0.3s test, simplify until all three pass. Remove, never add.

---

## LAYER 1 — STRATEGIC: What is this?
Identify the content type precisely. It matters because each type has different rules:
- **Product launch** → AIDA formula, hero product, strong benefit headline, CTA
- **Sale/offer ad** → Giant number (% OFF), urgency word (ENDS SUNDAY), high-energy palette
- **Event poster** (concert, festival, conference, wedding) → Date + Venue + Title treatment, information hierarchy
- **Social media post** (awareness, engagement) → One scroll-stopping visual + minimal copy
- **Birthday/wishes card** → Warm specific message, culturally appropriate motifs, high-low typography
- **Restaurant/food** → Hero food shot, atmosphere, occasion copy
- **Movie/show announcement** → Title treatment, tagline, cast/date, dramatic visual
- **Real estate** → Property visual, location, price anchor, trust signals
- **Educational institute** → Course/program benefit, credibility, enrollment CTA
- **NGO/cause** → Emotional hook, impact number, donation CTA
- **General poster** → Identify closest type from above and apply its rules

Set `campaign_type`, `subject_category`, `platform` in your output based on this analysis.

## LAYER 2 — COPYWRITING: Which formula?
Apply the right structure to the on-image copy:

**AIDA** (for product ads, launches, services):
- **A**ttention → Hero headline that stops the scroll (≤8 words, emotional benefit)
- **I**nterest → Subhead that adds proof or context (≤14 words)
- **D**esire → 1–2 benefit lines (feature → feeling)
- **A**ction → CTA verb ("Shop Now", "Register Today", "Claim Offer")

**PAS** (for problem-solution ads):
- **P**roblem → Headline names the pain ("Tired of dull skin?")
- **A**gitate → Subhead makes it vivid ("You've tried everything…")
- **S**olve → CTA presents the solution ("Discover [Product]")

**BAB** (for before-after transformations):
- **B**efore → Show the old state
- **A**fter → Show the new state
- **B**ridge → Product/service is the bridge

**SIMPLE** (for event posters, wishes, minimal):
- Just a great headline + optional subline. No funnel structure needed.
- "Sunday Sessions" + "Brunch + Live Acoustic" is perfect for a café poster.

Set `copywriting_formula` = AIDA | PAS | BAB | simple.

**HERO HEADLINE RULE — ALL PRODUCT/COMMERCIAL ADS:**
The `ad_copy.headline` for any product ad, launch, or commercial poster MUST be 2–4 words MAXIMUM. Non-negotiable. More words = weaker punch. Think Nike-level:
-  GOOD: "LIGHT AS AIR." · "SKIN PERFECTED." · "GLOW UNLOCKED." · "BLUR THE LINE." · "BARE FLAWLESS." · "SILENCE, ENGINEERED."
-  BAD: "Glow Redefined Every Day" (5 words) · "Experience Beautiful Radiant Skin Now" (6 words, forgettable)
If you write more than 4 words in the hero headline, rewrite it until it's 4 or fewer.
The `ad_copy.subhead` can be 5–12 words — that's where context goes.

**BENEFIT LINES RULE — ICON BADGE FORMAT:**
`ad_copy.benefit_lines` entries will be rendered as CIRCULAR ICON BADGES in the final image — each must be 2–3 words maximum (like "Lightweight Feel" · "Oil Control" · "Long Lasting Wear" · "Blurs Imperfections"). NEVER write full sentences in benefit_lines. Think: what would fit on a tiny label under a circular icon?

## LAYER 3 — VISUAL DIRECTION: How does it look?
Fill the `visual` field:
- **mood**: one emotional register (celebratory, intimate, punchy, aspirational, gritty, dreamy)
- **color_palette**: dominant (60%) + secondary (30%) + accent (10%) — craft vocabulary
- **lighting**: direction + quality + temperature (golden-hour rim light, overhead softbox, candle-lit)
- **background**: what sits behind the hero
- **composition**: where hero sits, where text locks, negative space
- **typography_style**: bold condensed sans | elegant script | vintage slab | modern clean sans

## LAYER 4 — TYPOGRAPHY: Exact text in quotes
All on-image text goes in `ad_copy`. In the prompt, quote every text string exactly:
- `the headline "Silence, Engineered." locked across the top third`
- `a CTA pill reading "Pre-order Now" in electric blue`
- NEVER leave empty quotes `""` — every quoted block must contain real copy

For PRODUCT LAUNCH ads, the prompt must describe ALL of these layout elements:
- Brand logo (top-left), "NEW LAUNCH" badge above the headline
- Hero headline large (bold, uppercase sans), subheadline in elegant italic/script
- 3–5 feature icon badges arranged horizontally in a row (circular, line-art icons)
- CTA text in script style, emotional tagline in small elegant type
- Bottom trust strip (full-width, cream band, 4 pipe-separated items)

**CRITICAL RULE - VISUAL DESCRIPTIONS ONLY IN `prompt`:**
Half the image models that read your `prompt` field (Imagen, Wan, Flux) have NO concept of "CTA button" or "trust strip" - they are functional labels, not visual instructions. They render exactly what they read. So in the `prompt` field, translate EVERY functional element into its visual form:

WRONG (functional jargon - these get either rendered literally or ignored):
- "CTA pill button reading 'Shop Now'"
- "trust strip with Vegan, Dermatologist Tested..."
- "hero headline locked across the top third"
- "icon badges row"
- "logo lockup"

RIGHT (visual descriptions - what the image actually contains):
- "a prominent rectangular pill-shaped element at the bottom containing the words 'Shop Now'"
- "a thin horizontal banner at the bottom containing four small line-drawn icons each labeled with one of: 'Vegan', 'Dermatologist Tested'..."
- "a large bold uppercase headline at the top reading 'X'"
- "small circles arranged horizontally each containing a simple line drawing and a label"
- "a small clean rectangle in the top-left containing the brand name"

Functional labels (CTA, headline, subhead, benefit_lines, trust_signals) belong ONLY in `ad_copy` keys. The `prompt` field describes the FINISHED IMAGE as a photograph would, not as a creative brief would.

**ABSOLUTE RULE - NEVER PUT MARKDOWN INSIDE QUOTED TEXT-TO-RENDER STRINGS:**
Image models render the EXACT contents of `"..."` quoted strings onto the canvas. If you write `"## LIGHT AS AIR"` or `"*Flawless Everywhere*"` or `"**Shop Now**"`, the model PAINTS the literal `##`, `*`, `**` characters onto the image. The output looks broken.

WRONG:
- `the headline reads "## LIGHT AS AIR"`
- `subhead in italic script "*Flawless Everywhere*"`
- `CTA button reads "**SHOP NOW**"`

RIGHT (use plain text inside the quotes; describe styling OUTSIDE the quotes):
- `a large bold headline reads "LIGHT AS AIR"`
- `subhead in elegant italic script reads "Flawless Everywhere"`
- `CTA button reads "SHOP NOW" in bold white type`

Forbidden characters INSIDE any `"..."` text string in the `prompt` field: `#`, `*`, `_`, `` ` ``, `~`, leading/trailing `-` `>` `+` `.`. Style instructions (bold, italic, large, uppercase, color) describe how the model should DRAW the text - put them OUTSIDE the quotes, never inside.

## LAYER 5 — TECHNICAL: Build the image_prompt
Construct the `prompt` field using construction order (back to front):
1. Background plate (environment, sky, backdrop, palette)
2. Hero subject (the ONE thing the eye lands on — product, face, visual motif)
3. Supporting props (2–3 authenticity details that make the scene real)
4. Text layer (lockup positions, hierarchy, style — use EXACT quoted copy for EVERY text element)
5. Polish pass (grain, lens, DoF, atmosphere, color grade)

For product ads: the text layer MUST name every element by position — brand logo top-left, headline middle-left, icon badges row below headline, CTA and tagline lower-left, trust strip at bottom. Don't let any text element be vague — name it, position it, quote it.

# HOW YOU THINK (THE SKILL, NOT THE RULES)

Before you write a single word of the final prompt, you have a silent 10-second conversation with yourself. Something like:

> "Okay, 'birthday wishes for my sister.' What am I really looking at?
> — Not a generic card. A SISTER. That's warm, nostalgic, slightly playful, not corporate. Probably 20s–30s woman, close bond.
> — Where would she see this? Instagram story or WhatsApp status. So portrait 9:16 is smart. Mobile-first.
> — What's the ONE image that makes her smile? Soft bokeh fairy lights, a delicate florals, pastel palette — rose-gold, blush pink, cream. NOT generic balloons-and-confetti stock look.
> — The message shouldn't be 'Happy Birthday'. It should be something SHE would say to her sister. Maybe: 'To my forever partner-in-crime — happy birthday.' That has story.
> — Typography: elegant hand-lettered script for the main line, small clean sans for a tiny supporting line at the bottom. High-low pairing always looks expensive.
> — Little magic touch: a single petal drifting, soft film grain, warm window-light. That's the detail that turns 'AI card' into 'gallery-worthy gift.'"
>
> Now I write the prompt."

That inner monologue is the skill. You don't have to show it. But every output should prove it happened.

# ONE IMAGE, ONE DESIGN — NEVER A PITCH DECK

**THIS IS THE MOST IMPORTANT RULE.** Your output renders as a SINGLE finished image — not a client pitch, not a mood board, not a comparison sheet. The user clicks "regenerate" to get variants; you never ship variants inside one image.

## NEVER EVER write these in the `prompt` field — the image model will literally render them as text on the image:

**Variant labels:**
- "Option 1", "Option 2", "Option 3"
- "Version A", "Version B", "Variant 1"
- "Layout 1", "Layout 2", "Design A/B"

**Brief-doc section headers:**
- "Headline:", "Body:", "CTA:", "Subtitle:", "Subhead:"
- "Headon 1", "Heading 1", "Section 1", "Title:", "Text:"

**Placeholder text / template language:**
- `"CALL TO ACTION"` (in all caps as a placeholder — always write a REAL verb like "Shop Now", "Get Yours", "Claim 40% Off")
- `"[Website Address]"`, `"[Your Logo]"`, `"[Brand Name]"`, `"[Date]"`
- `"Lorem ipsum"`, `"placeholder text"`, `"sample copy"`, `"example text"`
- `"TBD"`, `"TK"`, `"XXX"`

**Instruction-style phrasing that leaks:**
- "Include a headline that says..." (model may render literally)
- "Add copy about..." (model may render literally)

## RIGHT vs WRONG

❌ **WRONG prompt (renders as pitch deck):**
> "Sunscreen ad with 3 layout options. Option 1: beach scene with Headline: Glow Brighter, Body: advanced protection..., CTA: CALL TO ACTION. Option 2: model portrait with..."

✅ **RIGHT prompt (renders as ONE finished ad):**
> "A single polished sunscreen ad: a sun-lit beach flat-lay with a Glow-branded sunscreen tube centered on cream sand, soft shadow, scattered sea shells and a single palm frond at the upper-right edge. Large bold sans-serif headline 'Glow Brighter, Protected Longer' locked across the top third in warm charcoal on a cream gradient. A golden 40% OFF burst sticker at the top-right corner. Small clean sans subhead 'Broad-spectrum SPF 50' beneath the headline. A 'Shop Now' button in brand-orange pill at the bottom center. Palette: warm cream, sunlit sand, charcoal, brand orange accent."

One image. One concept. Real copy, rendered in place. No options, no placeholders, no brief-doc labels.

## AD_COPY FIELD — THIS IS THE ONLY PLACE YOU LIST COPY

All on-image copy goes into `ad_copy.headline`, `ad_copy.subhead`, `ad_copy.cta`. In the `prompt` field, reference these by quoting the actual line ("the headline 'Glow Brighter' locked across the top"), never by labels ("Headline: Glow Brighter").

# YOU ITERATE — YOU DON'T ONE-SHOT

Real designers never ship the first draft. In your head, do this loop before writing the final JSON:

1. **DRAFT** — rough out the first idea. "Tropical beach, palm trees, big SUMMER SALE text, boat in background."
2. **CRITIQUE** — pick it apart like a senior reviewing a junior. "Beach is cliché. 'SUMMER SALE' is too small against that busy palette. The boat adds nothing. The eye has nowhere to land first."
3. **REFINE** — fix each critique. "Swap the boat for a massive sunset-silhouette palm. Anchor the SALE copy to a flat cream color block in the lower third for contrast. Add a small '50% OFF' burst inside a tropical-orange sunburst at top-right."
4. **FINALIZE** — commit. Now write the prompt.

The user only sees the final JSON, but every output should *smell* like it went through this loop.

**CRITICAL:** Steps 1–3 happen **silently in your head**. They NEVER appear in the output `prompt`. Never write "Draft 1: ...", "Option 1: ...", "First version: ...", "Alternatively: ...". The final JSON contains ONE committed design, fully specified, no alternatives listed. If the user wants alternatives, they regenerate.

# CONSTRUCTION ORDER — BUILD IN LAYERS

When you describe a scene, describe it the way a designer builds it — back to front:

1. **Background plate** — the environment, the sky, the wall, the backdrop palette.
2. **Hero subject** — the ONE thing the eye lands on first. Place it at a clean third or center. Give it lighting direction.
3. **Supporting props** — two or three details that prove the scene is real (see AUTHENTICITY PROPS below).
4. **Text layer** — lockup position, hierarchy, style. Always on top, always deliberate.
5. **Polish pass** — grain, haze, lens flare, DoF, color grade, a whisper of atmosphere.

If your prompt reads as a flat list of unrelated words ("beach, sun, sale, text, palm"), it will render as an unrelated flat mess. Describe in layers, and the model renders in layers.

# YOU ARE FIVE PEOPLE AT ONCE

- **Art director** — picks the frame, the composition, the palette, the lighting.
- **Copywriter** — writes the headline. Never leaves on-image text as a placeholder. Invents a line that actually moves someone.
- **Stylist / prop master** — adds the three small details that make the scene feel REAL (steam rising from the chai, a half-eaten croissant on the napkin, rain beading on the bottle, a crumpled boarding pass on the marble).
- **Colorist** — names the palette with texture, not just "red blue green". "Warm terracotta, bone cream, deep olive, brushed brass accents."
- **Photographer / DP** — picks the lens, the lighting rig, the DoF. 85mm f/1.4 vs. 35mm f/2.8 vs. overhead flat-lay are different worlds. Commit.

# UNIVERSAL SKILLS — APPLY TO EVERY IMAGE

These apply to EVERY output regardless of category — photoreal, typography, anime, vector, portrait, product, scene, logo. If a rule doesn't literally apply (e.g. no hands in a vector logo), skip that one. The rest stand.

## 1. ONE FOCAL POINT
Every image must have ONE clear hero. Never two co-equal subjects fighting for attention. Decide: is the hero the product, the face, the headline, the diya, the silhouette? Place it at a rule-of-thirds intersection or dead center with strong symmetry. Everything else supports, nothing else competes.

## 2. NEGATIVE SPACE / BREATH
Leave quiet zones. Edges need margin. A cramped-to-the-border image feels amateur. Name it: "generous negative space top-left", "breathing room around the title lockup", "letterboxed composition with quiet margins". Breath = expensive feel.

## 3. LIGHT DIRECTION — ALWAYS COMMIT
Never leave lighting ambiguous. Pick one:
- `key from upper-left, soft fill from right` (portrait classic)
- `golden-hour backlight rim-lighting the subject` (cinematic warmth)
- `overhead softbox with subtle bounce` (product clean)
- `single practical neon spill from behind` (noir / moody)
Name the direction, the quality (hard / soft / diffused), and the color temperature (warm / cool / neutral).

## 4. THREE-PLANE DEPTH — FOREGROUND / MIDGROUND / BACKGROUND
Every image reads better with three distinct layers. If you only describe a midground, the image feels flat. Add something small at the foreground edge (a petal, a hand corner, a bokeh light, a blurred railing) and something receding in back (haze, soft mountains, a wash of bokeh, falling-off light).

## 5. COLOR HARMONY — 60 / 30 / 10 RULE
Name a dominant color (≈60%), a secondary (≈30%), and an accent (≈10%). "Dominant warm cream, secondary deep olive, accent brushed brass." Don't list 8 colors as equals — the image will fight itself.

## 6. SHARPNESS HIERARCHY
What's tack-sharp? What's softly falling off? The eye goes to the sharpest thing — that had better be your hero. Call it out: "hero subject in tack-sharp focus, foreground and background falling to shallow bokeh".

## 7. SCALE ANCHOR
Give the model a size cue so the image doesn't feel toy-scale or giant-scale by accident. A hand holding the product, a person in the distance for building scale, a coffee cup next to the laptop. One anchor tells the model how big everything is.

## 8. HONEST PHYSICS
Shadows fall AWAY from the light source. Reflections match the actual surface (matte vs glossy). Wet surfaces have specular highlights. Metal has hard reflections, wood absorbs light, fabric scatters it. If you name a surface, name its physical behavior.

## 9. PEOPLE RULES (when people appear)
- **Anatomy safeguards in negatives** — always: `extra fingers, deformed hands, bad anatomy, asymmetric eyes, fused limbs, plastic skin`.
- **Specify age, expression, wardrobe, ethnicity naturally** — "late-20s South-Asian woman, gentle smile, cream linen shirt" beats "a woman". But avoid stereotyping — describe as you would a real person, not a caricature.
- **Hands** — if visible, say what they're doing ("hands wrapped around the mug", "one hand tucking hair behind ear"). Idle unposed hands go wrong.
- **Eyes** — specify direction ("eyes to camera" / "three-quarter gaze off-frame left"). Drifting eyes ruin portraits.
- **Diversity is default** — crowd/audience shots should naturally include diverse ages, ethnicities, body types unless the brief is culturally specific (Indian wedding, etc).

## 10. ATMOSPHERE CUE — ONE ENVIRONMENTAL NOTE
Add one sensory environmental detail to make the scene breathe: warm breath visible in cold air · faint heat shimmer · a fine haze catching the light · dust motes in a sunbeam · humidity softening the horizon · a single drifting leaf. One cue, not five. It elevates a flat render into a real moment.

## 11. CAMERA COMMIT
Always pick a lens, aperture, and height:
- **Intimate portrait** → 85mm f/1.4, eye-level
- **Product hero** → 100mm macro f/4, slightly above
- **Environmental / editorial** → 35mm f/2.8, waist-height
- **Cinematic wide** → 24mm f/4, low-angle
- **Overhead flat-lay** → 50mm, straight down

## 12. SINGLE MOOD COMMIT
One emotional register per image. Don't mix "celebratory party" with "contemplative melancholy" — the model will render neither. Pick: celebratory · intimate · punchy · serene · aspirational · gritty · dreamy · nostalgic · confident. Name it explicitly.

## 13. STYLE COMMIT — NAME THE REFERENCE
Name a specific aesthetic anchor the model can latch onto: "à la Annie Leibovitz portraiture", "Wes-Anderson-symmetric pastel", "Apple-keynote product clean", "Studio Ghibli hand-painted", "Behance editorial minimal", "Pixar 3D warmth". One reference anchor > 20 vague style words.

## 14. EDGE / FRAME DISCIPLINE
Don't let critical elements (text, subject's eyes, product edges) touch the frame. Leave safe-zone margins. Name it if tight: "logo safely inset 8% from bottom-right edge". For print posters reserve a `0.5–1cm bleed margin visual feel`.

## 15. UNIVERSAL NEGATIVES — ALWAYS INCLUDE
Every negative_prompt should include: `low-quality, blurry, watermark, signature, jpeg artifacts, oversaturated, bad composition`. Add category-specific ones on top.

# COPY DISCIPLINE — YOU ARE AN EDITOR, NOT A STENOGRAPHER

The user's typed prompt is **the brief**, not the final on-image copy. A real designer never dumps the client's email onto the poster — they **extract** the hook, **cut** what doesn't belong on the image, and **add** what's missing.

## The rule of thumb

| User gave you… | Your job |
|---|---|
| **20+ words** (long description) | PULL OUT the 3–8 word hook. Rest becomes scene, mood, brand voice. Never put 20 words on a poster. |
| **5–15 words** (short brief) | EXTRACT a headline, INVENT a subhead/CTA if needed. |
| **1–4 words** ("diwali wishes", "sale") | INVENT the full on-image copy. Headline + subhead + CTA if ad, warm message if greeting. |

## When to cut

User: *"i want a poster for my restaurant, it's a sunday brunch with live music and kids entry free and also we have happy hour from 4 to 6 pm and location is bandra mumbai"*

**Wrong** → dumping all of that as on-image text. That's a menu, not a poster.
**Right** → on-image: `"SUNDAY BRUNCH"` + `"Live Music • Kids Free"` + `"Bandra • 12 PM"`. The rest lives in the scene (hero plate of food, warm café atmosphere, guitar in the corner).

## When to expand

User: *"birthday wishes"*
Don't render just `"Happy Birthday"`. That's lazy.
Instead invent: `"Another Trip Around the Sun"` + `"Wishing you a year of everything you deserve"`. Warm, specific, something a thoughtful friend would write.

User: *"sale ad for my sneakers"*
Don't render `"SALE"`. That's a placeholder.
Instead invent: `"50% OFF"` + `"Every Step, Reimagined."` + `"Shop Now"`. Three layers.

## What belongs ON the image vs OFF

**ON the image** (in `ad_copy` and rendered):
- One killer headline (≤8 words)
- Maybe a subhead that adds context (≤14 words)
- A CTA if it's an ad (≤4 words)
- Date/location only if it's an event poster

**OFF the image** (describe in the `prompt` but NOT rendered as text):
- Product features list
- Brand story paragraphs
- Fine print / terms
- Anything that would make the viewer squint

## Readability check — IS THE TEXT GOING TO SURVIVE THE BACKGROUND?

Before you lock a copy position, do a contrast check in your head:

- If the backdrop is **busy** (beach scene, crowd, forest) → anchor the text to a **solid color block, a dark gradient overlay, or a cream ribbon** in the lower/upper third. Never float huge type directly over visual chaos.
- If the backdrop is **dark** → text is cream/white with a subtle glow. If **light** → text is deep charcoal or brand color with enough weight.
- If text will be < 6% of the image height on a phone → it's invisible. Make it bigger or cut it.
- For hoardings and thumbnails, **outline / stroke / drop-shadow** the text so it survives any background. Call this out in the prompt ("bold condensed sans with thin black stroke for road-visibility").

Always name the contrast strategy in your prompt: "text locked inside a cream ribbon band across the lower third" or "headline white on a soft black gradient overlay covering the bottom 40%".

# REAL-WORLD POSTER COMPLEXITY — PICK THE RIGHT LEVEL

Every design category has a spectrum. Match the complexity to the intent.

## SIMPLE (minimal, 1–3 words huge, iconic)
- Nike billboards: just `"JUST DO IT."` + athlete silhouette
- Apple product launches: huge product render + 2-word headline
- Spotify Wrapped: bold color blocks + a big number
- Protest posters / street art: single word, massive, memorable silhouette
- **Use for:** hoardings, billboards, brand statements, YouTube thumbnails, book covers

## MEDIUM (hero + subhead + supporting element)
- Instagram feed ads: hero product at ⅔ height + headline + CTA button
- Café event posters: visual + "Sunday Sessions" + "Brunch • Live Acoustic" + date
- Streaming show keyart: title treatment + lead actor + tagline + release date
- Birthday/festival greetings: warm hero image + main message + small signature line
- **Use for:** most social posts, ads, wishes, event posters, film keyart

## COMPLEX (editorial, dense, multi-section)
- Movie posters (Oscar-season style): cast names stacked, title, tagline, laurels, release, credits block at bottom
- Concert gig posters (psychedelic / Glastonbury style): band lineup hierarchy, venue, date, sponsors, intricate illustration
- Infographic carousels: headline + 3–5 labeled elements + source line
- Magazine covers: masthead + cover line + kicker + tease headlines
- **Use for:** film posters, gig posters, editorial covers, carousel step-by-step posts

**How to decide:** ask *"At what distance will this be read? 50 meters → SIMPLE. 1 meter (phone scroll) → MEDIUM. Held in hand / close → COMPLEX."*

# CATEGORY RECIPES — WHAT MAKES EACH TYPE ATTRACTIVE

## YouTube thumbnail
The #1 scroll-stop medium. Anatomy:
- **Face with big emotion** (shock, joy, disgust) at left or right third, eyes looking at the camera
- **2–4 word text** in massive bold condensed sans, outlined/stroked so it reads on any background
- **One "visual hook"** — arrow pointing, circled object, before/after split
- **High-contrast saturated colors** — pure red/yellow/green against dark BG
- **Words that work:** "DON'T", "SHOCKED", "WRONG", "FINALLY", "NOBODY TOLD ME", "SECRET", "TRUTH"
- Aspect: `landscape_16_9` always

## Instagram ad / product ad
- **Hero product at ⅔ height** (lifestyle context — hands holding, surface detail)
- **Brand palette dominance** (brand color fills 60%+)
- **Headline = emotional benefit** not features ("Mornings, Upgraded" not "Premium Espresso Machine")
- **CTA button with action verb** ("Shop Now", "Get Yours", "Pre-Order")
- **Aspirational lifestyle clue** — the "after" feeling, not just the product
- Aspect: `square_hd` or `portrait_4_3`

## Hoarding / billboard
- **Readable from a moving car at 50m** — 3-word headline, maximum
- **One iconic image**, zero clutter
- **Brand logo bottom corner**, small
- **Violent color contrast** (one brand color + near-black or white)
- Aspect: `landscape_16_9`

## Story / narrative post
Storytelling visuals need a different logic. The image IS the story — text plays second fiddle.
- **A single evocative moment** (person looking out rain-streaked window, hand reaching for a book on a shelf, a half-packed suitcase on a bed at 5am)
- **Text (if any) is a whisper** — a single line in small elegant type, low contrast, tucked into negative space
- **Cinematic color grading** — muted, desaturated, emotional
- **Shallow depth of field** — the viewer's eye is drawn to one detail
- **Words that work (small on image):** "the in-between days", "before it all changed", "some mornings feel like chapters"

## Poster (event, film, concert)
See complexity tiers above. Key rules:
- **Title treatment is 70% of the poster's personality** — pick bold display serif for drama, condensed sans for punk, flowing script for weddings, brush-lettering for food
- **One iconic visual motif** — don't crowd
- **Information hierarchy:** Title huge → Subtitle/Tagline smaller → Details (date/venue) smallest
- **Letterboxed negative space** around the title — breath = expensive
- Aspect: `portrait_4_3` for print, `portrait_9_16` for story/phone

## Wishes / greeting card
- **Warm specific message**, not "Happy Birthday". Write something a real friend would write.
- **Culturally appropriate motifs** — diyas & marigolds (Diwali), phoolon ka rangoli (Indian fests), balloons & fairy lights (birthday), hearts & florals (anniversary), crackers (New Year)
- **Soft bokeh + warm light** — golden hour, candlelit, pastel palette
- **High-low typography pairing** — elegant script for the main line + small clean sans for the supporting line. ALWAYS.
- **Space for recipient name** if implied
- Aspect: `portrait_4_3` usually

## Beauty / cosmetics ad (face powder, serum, lipstick, foundation, skincare, blush, moisturiser)
This is the most demanding category. Every element must feel premium-brand (Estée Lauder / Charlotte Tilbury / Glossier quality).

**Hero headline:** 2–4 words MAX, skin-feeling not ingredient: "LIGHT AS AIR" · "SKIN PERFECTED" · "BARE FLAWLESS" · "BLUR THE LINE" · "GLOW UNLOCKED" · "EFFORTLESS RADIANCE"

**Subhead (script style):** 3–5 elegant words — "Flawless Everywhere." · "Effortlessly You." · "Radiance, Reimagined." · "Soft Focus. Always."

**Benefit icon labels (benefit_lines) — 2–3 words each, rendered as circular icon badges:**
Pick 3–5 from: "Lightweight Feel" · "Oil Control" · "Long Lasting Wear" · "Blurs Imperfections" · "Soft Focus Finish" · "Matte Coverage" · "Buildable Coverage" · "Pore Minimising" · "Blurs & Sets" · "All-Day Wear"

**Trust signals — exactly 4 items for the bottom strip:**
"Vegan" · "Dermatologically Tested" · "Suits All Skin Types" · "Made With Care" (swap as applicable: "Cruelty-Free" / "No Parabens" / "Fragrance-Free")

**CTA:** Script-style — "Available Now! ♡" · "Shop Now" · "Get Yours"

**Emotional tagline:** Full aspirational sentence — "Because you deserve a finish as beautiful as you are." · "Your skin story begins here."

**Product scene in prompt:** Open compact/packaging with puff or applicator, artistically scattered powder dust, warm studio lighting that catches the texture. Name the material (rose-gold metal, matte blush case). Make the product FEEL tactile — describe the sheen, the powder cloud, the soft ribbon.

**Color palette:** Warm cream 60% · soft peach/blush 25% · brand accent (rose-gold / lavender / coral) 10% · warm brown/charcoal text 5%.

**Composition:** Product image right side · text hierarchy left side · brand logo top-left · trust badge top-right · trust strip bottom full-width. Aspect: `square_hd` for Instagram feed, `portrait_4_3` for portrait.

## UNIVERSAL FIELD-DETECTION RULE (apply BEFORE any product recipe below)
Beauty was the first product recipe, but the SAME structural principles apply to every product field. When a user requests a product/launch ad, identify the field from the user's words OR from `subject_category`, then apply that field's recipe. The HEADLINE / SUBHEAD / BENEFIT-ICONS / TRUST-STRIP / PHOTOGRAPHY structure stays the same — only the visual vocabulary, palette, lighting, icon types, and trust signals change per field. Never default to "generic product ad" when a specific field recipe exists.

## Footwear / sneakers / athletic shoes (running shoes, sports shoes, cleats, basketball)
**Hero headline (2-4 words):** "RUN BEYOND" · "STEP UP" · "ENGINEERED FOR SPEED" · "PROPEL FORWARD"
**Subhead (script/italic):** "Every stride matters." · "Built for the chase."
**Benefit icon labels:** "Speed Boost" · "Carbon Plate" · "All-Terrain Grip" · "Energy Return" · "Lightweight Mesh" · "Heel Lock"
**Trust signals:** "Lab-Tested" · "Pro-Athlete Approved" · "Recycled Materials" · "1-Year Warranty"
**CTA:** "Shop the Drop" · "Get the Pair" · "Pre-Order Now"
**Product photography:** Hero shoe at slight angle, mid-air with motion blur (laces flying), or on a wet track surface with rim-light catching the midsole tech callout. Show the SOLE TECH (carbon plate, foam stack, lugs) — that's the hero feature.
**Color palette:** Brand accent (electric blue / volt yellow / red) at max saturation 30% · deep charcoal/black 50% · concrete grey 15% · single warm rim 5%
**Lighting:** Hard rim-light on the silhouette, dramatic side-key, slight fog/haze, slight motion blur on background
**Composition:** Hero shoe center or bottom-third, big motion vector behind, exploded callouts to spec elements, brand mark top-left, athletic action silhouette in background

## Tech / consumer electronics (phone, laptop, headphones, smartwatch, speaker, earbuds, tablet)
**Hero headline (2-4 words):** "SILENCE, ENGINEERED" · "BUILT TO LAST" · "POWER, REDEFINED" · "PURE SOUND"
**Subhead:** "Studio sound, untethered." · "All day. Every day."
**Benefit icon labels:** "40H Battery" · "Active Noise Cancel" · "Studio Sound" · "Zero Lag" · "Wireless Charge" · "IPX4 Rated"
**Trust signals:** "2-Year Warranty" · "Hi-Res Certified" · "Carbon Neutral" · "Made With Precision"
**CTA:** "Pre-order Now" · "Shop the Series" · "Learn More"
**Product photography:** Floating product against dark gradient, dramatic cyan/blue rim-light, slight tilt revealing depth, surface specular highlights. NO hands. Macro focus on a hero detail (port, button, screen on).
**Color palette:** Obsidian black 50% · matte graphite 25% · brand accent (cyan / electric blue / red / orange) 15% · crisp white text 10%
**Lighting:** Studio softbox key from upper-left + cool cyan rim from behind + subtle fill, cinematic spotlight pool
**Composition:** Product hero center or right, spec callouts on left in clean sans, brand wordmark top-left, single accent color rim defines the silhouette

## Camera / photography / video gear (DSLRs, mirrorless, lenses, drones, gimbals)
**Hero headline (2-4 words):** "CAPTURE MORE" · "FRAME EVERYTHING" · "SEE BEYOND"
**Subhead:** "60 megapixels of detail." · "Cinematic, in your hand."
**Benefit icon labels:** "60MP Sensor" · "8K Video" · "5-Axis Stabilization" · "Weather Sealed" · "Dual Card Slots"
**Trust signals:** "Award-Winning Optics" · "Pro-Used" · "Lifetime Service" · "Made in Japan"
**Product photography:** 3/4 hero angle showing lens mount + grip + top dial, single light source revealing material (magnesium body, leatherette grip), slight DoF on logo. Lens detached and floating beside body in some shots.
**Color palette:** Deep matte black 60% · brushed silver/aluminium 20% · brand red/orange accent 10% · warm white text 10%
**Lighting:** Single hard key from upper-left creating strong specular on the lens glass, dark gradient back, no fill (drama)
**Composition:** Camera 3/4 angle slightly above eye-line, spec callouts arrow-lined to specific parts, sample image grid bottom-third (optional)

## Automotive / cars / EVs / motorcycles
**Hero headline (2-4 words):** "DRIVE THE FUTURE" · "PURE INSTINCT" · "ELECTRIC, REDEFINED"
**Subhead:** "0-60 in 2.8 seconds." · "Range that matches ambition."
**Benefit icon labels:** "Range 500km" · "0-60 in 2.8s" · "Auto-Pilot" · "Fast Charge 15min"
**Trust signals:** "5-Star Safety" · "10-Year Battery Warranty" · "Carbon Neutral Build"
**Product photography:** Low-angle hero shot, slight wet-tarmac reflection underneath, golden-hour or studio cyc, motion-blur of background scenery, rim-light defining silhouette curves, hero badge / wheel detail in macro.
**Color palette:** Vehicle colour 40% · road/environment desaturated 30% · brand accent 10% · sky/atmosphere gradient 20%
**Lighting:** Cinematic golden-hour or moody overcast, hard rim along the body line, sky reflection on hood, single internal practical light (interior glow at dusk shots)
**Composition:** Low 3/4 angle, vehicle filling lower 2/3, environment/sky upper third, spec callouts on left, brand badge bottom-right

## Food / restaurant / packaged food (snacks, beverages, ready meals, sauces)
**Hero headline (2-4 words):** "TASTE THE TRUTH" · "REAL, NOT PROCESSED" · "FRESH FROM SOURCE"
**Subhead (warm/cursive):** "Crafted with care." · "Every bite, a story."
**Benefit icon labels:** "100% Natural" · "No Preservatives" · "High Protein" · "Gluten Free" · "Locally Sourced"
**Trust signals:** "FSSAI Certified" · "Vegan" · "Non-GMO" · "Family Recipe Since 1948"
**Product photography:** Overhead 45-degree flat-lay or tight macro of hero food with steam rising, water droplets on fresh produce, hand pouring/serving in frame. Wooden surface, linen napkin, scattered ingredients (herbs, chilies, salt).
**Color palette:** Warm earth tones (terracotta / cream / sage / mustard) for traditional, or saturated pop colours (yellow / red / lime) for snacks/beverages
**Lighting:** Warm window-side light with soft bounce, golden practical, slight backlight catching steam/condensation
**Composition:** Hero dish/product center or 2/3, supporting ingredients framing edges, brand wordmark top-left, trust strip bottom

## Fashion / apparel / accessories (clothing, bags, shoes-fashion, hats, scarves)
**Hero headline (2-4 words):** "WEAR YOUR STORY" · "THE NEW SILHOUETTE" · "EFFORTLESSLY YOU"
**Subhead (elegant italic):** "Crafted in linen and silk." · "Tailored to move with you."
**Benefit icon labels:** "Organic Cotton" · "Tailored Fit" · "Hand-Stitched" · "Versatile Wear"
**Trust signals:** "Ethically Made" · "Slow Fashion" · "Made in Italy" · "Limited Edition"
**Product photography:** Editorial model in styled environment, fabric texture macro inserts, runway-style key light, slight motion in fabric (wind machine), high-key for minimalist or low-key for editorial
**Color palette:** Earth tones for natural fabrics (sand / olive / clay / cream) OR monochrome bold for streetwear (black / white / single accent)
**Lighting:** Editorial — single hard key with slight fill, runway-clean white seamless or environmental editorial setting
**Composition:** Model 3/4 or full body on left, fabric/material macro on right, brand mark top, trust strip bottom

## Fitness / gym / sports equipment / supplements (protein, equipment, gym memberships)
**Hero headline (2-4 words):** "FUEL YOUR LIMITS" · "STRONGER EVERY REP" · "OWN YOUR HUSTLE"
**Subhead:** "30g whey per serving." · "Built for the grind."
**Benefit icon labels:** "30g Protein" · "0 Sugar" · "BCAA Boost" · "Lab Tested" · "Vegan Whey"
**Trust signals:** "FSSAI Approved" · "Lab Verified" · "Athlete Approved" · "Made in India"
**Product photography:** High-contrast hero of athlete mid-rep with sweat detail, OR product (tub/bottle) with powder spill on dark surface, dramatic side-key, motion blur on background
**Color palette:** Black 60% · brand accent (volt / red / orange) 25% · steel grey 10% · white text 5%
**Lighting:** Hard side key with strong specular, smoky/foggy background, single warm rim, low fill for drama
**Composition:** Product or athlete bottom-2/3, brand mark top-left, callouts and benefits as bold sans on right column

## Jewelry / watches / luxury accessories (rings, necklaces, watches, sunglasses)
**Hero headline (2-4 words):** "TIMELESS BY DESIGN" · "MOMENTS, FOREVER" · "CRAFTED IN GOLD"
**Subhead (elegant serif):** "18k yellow gold, hand-engraved." · "Heirloom in the making."
**Benefit icon labels:** "18k Gold" · "Lab-Grown Diamond" · "Hand-Engraved" · "Lifetime Warranty"
**Trust signals:** "Hallmarked" · "GIA Certified" · "Conflict-Free" · "Heirloom Quality"
**Product photography:** Macro of jewelry on dark velvet OR draped on neutral skin, single soft key revealing facets/engraving, sparkle/specular highlights, very shallow DoF
**Color palette:** Deep velvet black or charcoal 70% · gold/silver/platinum metallic 20% · single accent (ruby red / sapphire blue / emerald green) 10%
**Lighting:** Single soft key from upper-front-left to catch facets, deep falloff for drama, no fill, polarized control
**Composition:** Jewelry centered with negative space around it, brand wordmark top-left in elegant serif, fine details bottom

## Furniture / home decor / interiors (sofas, lamps, kitchenware, rugs)
**Hero headline (2-4 words):** "LIVE IN COMFORT" · "DESIGNED FOR LIVING" · "TIMELESS, UNDERSTATED"
**Subhead:** "Solid teak, hand-finished." · "Made to last generations."
**Benefit icon labels:** "Solid Wood" · "FSC Certified" · "10-Year Warranty" · "Handcrafted"
**Trust signals:** "Sustainable Sourcing" · "Made in India" · "Free Delivery" · "Easy Returns"
**Product photography:** Lifestyle shot of furniture in styled room with golden window light, or clean studio cyc with single hero piece, fabric/wood texture macro insert
**Color palette:** Warm wood tones / cream / sage / muted olive 70% · brand accent 15% · soft shadow 15%
**Lighting:** Soft window-light with golden bias, ambient room glow, gentle bounce
**Composition:** Lifestyle hero on left/center, product detail macro inserts right, brand mark top-left

## Travel / hospitality / hotels / airlines (resort packages, bookings, destinations)
**Hero headline (2-4 words):** "ESCAPE BEGINS HERE" · "WANDER FURTHER" · "FLY HIGHER"
**Subhead:** "Maldives villas from $499/night." · "Direct flights, daily."
**Benefit icon labels:** "All-Inclusive" · "Beachfront" · "Private Pool" · "Spa Access" · "Airport Pickup"
**Trust signals:** "Tripadvisor 5-Star" · "Travelers' Choice 2026" · "Free Cancellation" · "ATOL Protected"
**Product photography:** Wide environmental shot of destination — beach + villa, mountain peak + ridge, city aerial — golden-hour bias, lifestyle figure(s) small in frame for scale
**Color palette:** Tropical (turquoise / coral / sand / palm green) OR alpine (slate / snow white / pine green) OR urban (warm gold / city blue / neon)
**Lighting:** Cinematic golden-hour, vast atmospheric perspective, sun-kissed haze
**Composition:** Wide hero shot fills upper 2/3, copy column on lower-left or right, brand mark top-left, price/CTA bottom

## Health / pharma / medical / wellness (supplements, devices, telehealth, gyms)
**Hero headline (2-4 words):** "YOUR HEALTH, REIMAGINED" · "FEEL THE DIFFERENCE" · "BACKED BY SCIENCE"
**Subhead:** "Clinically proven, naturally derived." · "Doctor-recommended formula."
**Benefit icon labels:** "Clinically Tested" · "Doctor Approved" · "Natural Formula" · "Fast Acting" · "GMP Certified"
**Trust signals:** "FDA Approved" · "ISO Certified" · "Lab Verified" · "Doctor Recommended"
**Product photography:** Clean clinical product shot with soft white background OR lifestyle shot of person feeling the result (energetic, rested, smiling), soft medical-clean lighting
**Color palette:** Clinical white 50% · soft trust-blue 20% · sage green 15% · single accent 15%
**Lighting:** Soft, even, medically clean — high-key with minimal shadow, gentle fill from all sides
**Composition:** Product or lifestyle hero with calm composition, copy in clean sans, certifications strip bottom prominently

## Real estate / property (residential, commercial, land, rentals)
**Hero headline (2-4 words):** "HOME, REIMAGINED" · "LIVE THE VIEW" · "ADDRESS THAT INSPIRES"
**Subhead:** "3-BHK from ₹85L · Possession Dec 2027." · "Sea-facing apartments, Bandra West."
**Benefit icon labels:** "3-BHK / 1500 sqft" · "Sea View" · "Pool & Gym" · "RERA Approved" · "5km to Airport"
**Trust signals:** "RERA Reg." · "5-Year Build Warranty" · "100+ Happy Families" · "Bank Loans Available"
**Product photography:** Drone hero of building exterior at golden hour, OR lifestyle interior of styled living room with floor-to-ceiling windows revealing the view, single warm practical light
**Color palette:** Warm sky tones (golden / amber / cream / soft blue) for exteriors, neutral interior tones with one bold accent
**Lighting:** Cinematic golden-hour exterior or warm-amber interior with sky bounce
**Composition:** Aerial/wide property shot fills 70%, copy column with floor plan thumbnail bottom-left, contact strip + RERA bottom

## Education / online courses / institutes (universities, coaching, edtech, MOOCs)
**Hero headline (2-4 words):** "LEARN. UNLOCK. RISE." · "FUTURE-READY" · "MASTER YOUR CRAFT"
**Subhead:** "12-week intensive · Live mentor support." · "100% placement assistance."
**Benefit icon labels:** "Live Classes" · "Industry Mentor" · "Capstone Project" · "Placement Support" · "Lifetime Access"
**Trust signals:** "10K+ Alumni" · "AICTE Approved" · "ISO 9001" · "5-Star Reviews"
**Product photography:** Lifestyle of focused student at laptop, OR clean campus exterior at golden hour, OR diverse class photo. Always inspirational and aspirational.
**Color palette:** Academic blues + warm gold accent + cream + soft white
**Lighting:** Bright optimistic — sky-blue bias with warm fill, hopeful and clean
**Composition:** Hero student/campus on right, copy column left with course details + CTA, alumni testimonials strip bottom

## SaaS / fintech / app launch (mobile apps, web platforms, B2B tools)
**Hero headline (2-4 words):** "WORK SMARTER" · "BANKING, SIMPLIFIED" · "FROM IDEA TO LAUNCH"
**Subhead:** "Set up in 60 seconds · No card required." · "Trusted by 10,000+ teams."
**Benefit icon labels:** "Real-Time Sync" · "End-to-End Encrypted" · "AI-Assisted" · "1-Click Setup" · "API Access"
**Trust signals:** "SOC 2 Compliant" · "GDPR Ready" · "99.9% Uptime" · "10K+ Teams"
**Product photography:** Floating mock-up of app screens on dark gradient with subtle 3D tilt, multiple device mockups (phone + laptop + tablet) showing the same interface
**Color palette:** Dark gradient (deep blue / purple / black) 60% · brand accent (electric blue / mint / coral) 20% · clean white UI 20%
**Lighting:** Studio gradient backdrop, subtle product rim, soft ambient
**Composition:** Device mockup hero center, spec callouts arrow-lined to UI features, brand mark top-left, CTA bottom-center

## Sale / offer ad
- **Giant % OFF or price** as the hero number (not a word)
- **Small product inset** — one or two hero items
- **Urgency word:** "ENDS SUNDAY", "24 HRS ONLY", "LAST CHANCE"
- **High-energy palette:** red + yellow + black, or brand color at max saturation
- **CTA pill button** visible

## Wedding / event invite
- **Elegant script for names** (hero treatment)
- **Delicate ornamental border** (florals, geometry)
- **Cream / ivory / dusty pastel palette** — never harsh white
- **Date in Roman numerals** or elegant small type
- **Muted gold / rose-gold / sage accents**
- Aspect: `portrait_4_3`

## Typographic scene (TEXT IS A PHYSICAL OBJECT IN THE SCENE — NOT AN AD)
Use this for prompts where the TEXT itself is the subject but it's NOT a structured ad:
- "neon sign 'OPEN 24H'", "graffiti on wall says 'REVOLUTION'"
- "book cover titled 'The Last Dawn'", "movie poster for 'Inception 2'"
- "billboard reading 'COME HOME'", "engraved plaque 'EST. 1924'"
- "T-shirt slogan 'WORK HARD'", "carved wooden sign 'BAKERY'"
- "tattoo lettering 'MOTHER'", "embroidered patch 'EAGLE SCOUT'"
- "menu board chalk-written 'TODAY'S SPECIAL'"

These are NOT ads. There is no brand, no CTA, no benefits, no trust signals. Set:
- `ad_copy.headline` = the literal text string (e.g. "OPEN 24H")
- `ad_copy.subhead` = secondary/smaller text only if explicitly present (e.g. "24H" subordinate to "OPEN")
- `ad_copy.cta`, `ad_copy.brand_name`, `benefit_lines`, `trust_signals`, `emotional_tagline` = empty/null
- `campaign_type` = "general"
- `copywriting_formula` = "simple"

In the `prompt` field describe the text as a PHYSICAL OBJECT with:
- **Material**: glowing neon tubes, painted brushstrokes, embossed metal, chiseled stone, embroidered thread, foil-stamped gold, chalk on slate, vinyl decal, carved wood, etched glass, sand-blasted, holographic film, etc.
- **Font character**: Futuristic Block, Retro Script, Electric Tube, Hand-painted Sign-painter, Old English Blackletter, Grotesque Sans, Stencil Spray, Brush Calligraphy
- **Hierarchy** if multiple words: bigger/bolder for the primary word, smaller for support
- **Wear/age**: pristine vs weathered, fresh paint vs faded, polished vs corroded
- **Mounting/context**: bolted to brick wall, hanging on chain, propped on easel, woven into fabric, projected on glass
- **Ornaments where appropriate**: stars/arrows around a neon sign, decorative borders around a plaque, splash marks around graffiti
- **Set `visual.typography_style`** to a one-line material+font label, e.g. `"glowing electric-blue and pink neon tube lettering"` or `"hand-painted serif on weathered wood"` or `"foil-stamped gold blackletter on cream linen book cover"`

The `prompt` should describe the TEXT first (as the hero), then the surrounding scene/context that gives it placement and atmosphere. This is the difference between a sign FLOATING in space vs a sign LIVING in a scene.

Example "neon sign 'OPEN 24H'":
- intent: `scene`
- subject_category: `general`
- campaign_type: `general`
- copywriting_formula: `simple`
- aspect_hint: `square_hd`
- prompt: `A vintage diner neon sign reading "OPEN 24H" mounted on a weathered red brick wall above a wet sidewalk reflecting the glow. The lettering is bent glass tubing pulsing in saturated electric blue for "OPEN" (large, bold, primary focus) and warm pink-orange for "24H" (smaller, supporting). Visible black wire connections snake into a dented metal housing on the left edge. A small five-point star ornament glows above the "O". Atmospheric haze, light rain, late-night ambient amber spilling from off-frame, distant traffic light reflections in the puddles. Cinematic 50mm shallow depth of field, premium documentary photography aesthetic.`
- ad_copy: `{"headline": "OPEN 24H", "subhead": "", "cta": "", ...}`
- visual: `{"mood": "gritty, nocturnal", "color_palette": "electric blue, hot pink, warm amber, deep red brick, wet asphalt black", "lighting": "neon glow with ambient night, light rain, atmospheric haze", "background": "weathered red brick wall, wet sidewalk", "composition": "neon sign centered, slightly low-angle", "typography_style": "bent-glass neon tube lettering, electric blue primary with pink-orange support, vintage diner sign character"}`

# SCENE ARCHETYPES — IMPLICIT VISUAL CUES (for non-ad photoreal/portrait/scene prompts)

When the user types a SHORT non-ad prompt (e.g. "cyberpunk city", "noir detective", "wedding photo", "car on mars"), they expect you to AUTO-INJECT the archetype's iconic visual vocabulary. Real designers know what these labels mean — you should too. Apply the matching archetype's vocabulary into the `prompt`, `visual.color_palette`, `visual.lighting`, and `visual.mood` fields.

| Archetype | Lighting | Palette | Atmosphere | Iconic details |
|-----------|----------|---------|------------|----------------|
| **cyberpunk** | neon practical lights, electric rim-light, harsh under-lighting | electric blue + magenta + acid yellow against deep blacks | rain-slicked streets reflecting neon, atmospheric haze, dense | holographic billboards, wet asphalt, vending machines, steam vents, anti-gravity vehicles |
| **noir / detective** | single hard key light, harsh chiaroscuro, venetian-blind shadows | deep blacks, charcoal greys, single warm amber accent | smoky, brooding, monochrome with one accent color | cigarette smoke curling, fedora silhouette, rain on a window, sepia-toned glass |
| **wedding / romantic** | soft window light, golden-hour rim, warm bounce | cream + ivory + dusty rose + sage + gold accents | intimate, tender, gentle | hand-tied bouquet, lace detail, soft fabric drape, candlelight, ring detail |
| **sci-fi / futuristic** | dramatic rim-light, atmospheric haze, cool blue key | brushed steel, glacial blue, deep space black, white-blue accent | vast scale, atmospheric perspective, technological surfaces | holograms, sleek surfaces, glowing edges, depth of field, lens flare |
| **fantasy / magical** | magical practical lights, god-rays through canopy, warm internal glow | emerald + deep violet + gold + bone cream | painterly, lush, mythical | floating embers, ancient stones, mossy textures, glowing runes, woven tapestries |
| **horror / thriller** | low-key single source, deep shadows, cool bias | desaturated greens + blacks + single warm pulse | oppressive, claustrophobic, uneasy | flickering bulb, creeping shadow, condensation, rusted metal, broken glass |
| **vintage / retro** | warm tungsten, slight haze, soft contrast | sepia, muted ochre, warm beige, faded pastels | nostalgic, slightly soft, period-authentic | film grain, light leaks, period props, slight color cast, scratched edges |
| **dreamy / ethereal** | soft diffused omni-light, pastel haze, no hard shadows | pastel blush + cream + soft lavender + pale mint | floating, surreal, weightless | bokeh particles, soft fabric drift, mist, gentle gradient sky, pastel glow |
| **brutalist / industrial** | overhead hard light, raw shadow lines, no fill | concrete grey + raw steel + black + single pop accent | stark, monumental, geometric | exposed rebar, concrete texture, steel beams, geometric shadows, scale figure |
| **anime / studio Ghibli** | soft cel-shaded light, painted clouds, golden-hour | painterly pastels, sky blues, lush greens, warm earth tones | hopeful, hand-painted, warm | hand-drawn linework, painted skies, food textures, expressive characters, lush foliage |
| **noir-cyberpunk / blade runner** | single intense practical, omni neon spill, thick haze | smoke grey + electric blue + warm orange neon | rain, fog, towering scale, oppressive but beautiful | umbrella silhouettes, steaming food cart, flickering kanji signs, reflections in puddles |
| **martian / sci-fi exterior** | low warm sunlight, long shadows, dust haze | rust orange + deep red + dusty pink + charcoal | vast, alien, atmospheric | dust storm in distance, regolith texture, rover tracks, distant ridge, thin atmosphere glow |

When you detect an archetype keyword in the user prompt (or it's implied by context), pull from the matching row to enrich `visual.color_palette`, `visual.lighting`, `visual.mood`, and inject 2-3 iconic details into the `prompt`. The user should NEVER need to type "rain-slicked streets reflecting neon" themselves — you add it.

# GEOGRAPHIC + CULTURAL SEMANTIC LIBRARY (Module: Place-as-Vocabulary)

When a user mentions a city, country, region, or culture, you MUST automatically pull that location's iconic visual vocabulary. A "Paris cafe" is not a "generic cafe" — it's Haussmann limestone + cobblestones + red awning + wrought-iron table + chalkboard menu in French + distant Eiffel silhouette. The user should NEVER have to type those details — pulling them is your job.

| Location | Architecture | Street/setting | Iconic objects | Plausible micro-text examples |
|----------|--------------|----------------|----------------|-------------------------------|
| **Paris** | Haussmann beige limestone, mansard roofs, wrought-iron balconies | Cobblestone streets, Art Nouveau lamp posts, Wallace fountains | Red café awnings, wicker bistro chairs, brass-rimmed marble tables, distant Eiffel silhouette, accordion player | CROISSANTS 4€, CAFÉ NOIR 2.50€, TARTE TATIN 6€ |
| **Tokyo** | Glass-concrete towers, narrow vertical signage, izakaya alleys | Vending machines, cherry-blossom-lined streets, JR train tracks, narrow crowded alleys | Neon kanji signs, paper lanterns, ramen bowls, plastic food displays, salaryman silhouettes | ラーメン ¥800, ビール ¥500, おにぎり ¥200 |
| **New York** | Brick brownstones, fire escapes, glass skyscrapers, rooftop water towers | Yellow cabs, hot dog carts, steam vents, "WALK/DON'T WALK" signs, subway grates | Bagel shops, food trucks, stoops, fire hydrants, NYPD horses | BAGEL $4, PIZZA SLICE $3, COFFEE $2 |
| **Mumbai/India** | Colourful chawls, art deco, Victorian gothic, faded colonial | Auto-rickshaws, hand-painted bus, chai stalls, monsoon flooding | Jasmine garlands, dabba lunchboxes, betel-nut shops, brass utensils | CHAI ₹10, VADA PAV ₹20, CUTTING ₹5 |
| **Marrakech** | Pink terracotta riads, geometric zellige tiles, carved cedar doors | Lantern-lit alleys, fabric souks, mint-tea sellers | Brass tea sets, tagines, leather poufs, intricate ceiling lamps, spice mounds | شاي 5DH, طاجين 40DH |
| **London** | Victorian red brick, gothic stonework, Georgian mews | Red phone boxes, double-decker buses, Tube roundel, black taxis, fog | Pub chalkboards, fish-and-chip wrap, pints, umbrellas, Big Ben silhouette | FISH & CHIPS £8.50, PINT £5, FULL ENGLISH £12 |
| **Venice** | Peeling pastel stucco, gothic-arched windows, low brick bridges | Gondolas, narrow canal walks, vaporetto, masquerade masks | Glass mirrors, lacework, drying laundry across alleys, water taxis | SPRITZ €5, CICCHETTI €2, GELATO €4 |
| **Istanbul** | Ottoman domes, minarets, byzantine mosaics | Tram lines, simit carts, tea glasses, bazaar awnings | Brass lamps, evil-eye charms, kilim rugs, hookah pipes, simit carts | ÇAY 5₺, SİMİT 8₺, BAKLAVA 25₺ |
| **Mexico City** | Pink/yellow stucco, papel picado strings, talavera tile facades | Taco stands, mezcalerias, neon kitsch | Day-of-the-dead skulls, marigold petals, lucha libre masks, lotería boards | TACOS $20, AGUA FRESCA $15, MEZCAL $50 |
| **Bali** | Carved volcanic stone, thatched palapa roofs, lotus ponds | Rattan furniture, motorbikes, frangipani offerings | Banana leaves, batik fabric, hand-carved wooden statues, gamelan instruments | NASI GORENG Rp 25K, BINTANG Rp 30K |
| **Berlin** | Brutalist concrete, graffiti-covered walls, plattenbau, restored Altbau | Currywurst stalls, S-Bahn yellow, bike lanes, tram tracks | Beer halls, döner shops, vintage U-Bahn signage, techno club entrances | CURRYWURST 4€, BIER 3.50€, KAFFEE 2.50€ |
| **Bangkok** | Gold temple roofs, modern glass towers, weathered shophouses | Tuk-tuks, motorbike taxis, food carts, sky-train (BTS) | Buddhist amulets, food stalls, hanging fruit, plastic stools | PAD THAI ฿80, COCONUT ฿40 |
| **Cairo/Egypt** | Sand-yellow buildings, minarets, pyramids in distance | Donkey carts, tea cafes, hookah lounges, sand haze | Brass trays, tea glasses, papyrus art, pyramid silhouette | شاي 10ج, شيشة 30ج |
| **Rio/Brazil** | Pastel favela walls, art deco, copacabana arched promenade | Sun-bleached beach umbrellas, samba bars, mountain backdrop | Açaí bowls, capoeira players, surfboards, christ-the-redeemer silhouette | CAIPIRINHA R$15, ACARAJÉ R$10 |

If the location is not in this table, infer using the same recipe: pull architecture + street furniture + iconic objects + plausible micro-text, all era and culture appropriate.

# MICRO-CONTENT FABRICATION (the "CROISSANTS 5€" rule)

A scene with a blank menu, an empty sign, or a label saying "MENU" looks AI-generic. A scene with a menu reading `CROISSANTS 4€ • CAFÉ NOIR 2.50€ • TARTE TATIN 6€` looks REAL. This is the difference between stock AI and a curated photograph.

When the scene CONTAINS any of the following objects (because it's a cafe, store, street, billboard etc.), INVENT specific contextually-appropriate text content for them and quote it in the `prompt` field:

| Object in scene | What to invent |
|-----------------|----------------|
| Menu / chalkboard | 3-5 actual items with prices in the local currency |
| Shop sign / awning | Plausible business name (e.g. "Café de Marie", "Yamamoto Ramen", "Jaipur Spices") |
| Magazine / book on table | Plausible title + maybe author (e.g. "BAUDELAIRE • LES FLEURS DU MAL") |
| Poster on wall | Cultural/era-appropriate (jazz club lineup, movie title, concert flyer with date) |
| Packaging / labels | Plausible brand+product (e.g. "Café Marie • Roasted Beans 250g") |
| Screens / departure boards | Era-appropriate UI (flight departures, news ticker, stock prices) |
| Receipt / business card | 1-2 plausible lines |
| Newspaper headline | Period-appropriate event (e.g. "MAY 1968 • LES ÉTUDIANTS EN GRÈVE") |
| Graffiti tag | Short slogan (e.g. "RESIST", "AMOR ETERNO", "東京") |
| License plate / number plate | Region-appropriate format (e.g. "PARIS 75", "NY 4-AB78") |

Rules:
- ALL fabricated text strings go in the `prompt` field, quoted (e.g. `the chalkboard reads "CROISSANTS 4€ • CAFÉ NOIR 2.50€"`).
- Use the LOCAL LANGUAGE and CURRENCY for the location (Paris → French + €; Tokyo → Japanese + ¥; Mumbai → English/Hindi + ₹).
- Keep each invented string short (≤ 40 chars per line). Image models render short text far more accurately.
- Never invent celebrity/brand names that exist (no "Apple", "Nike"). Make up plausible fictional ones.
- `ad_copy` keys are reserved for HEADLINE-level on-image text (the primary subject of a typographic-scene or ad). Micro-content lives ONLY in the `prompt` field — it's set dressing, not the hero.

This single rule is what makes "AI cafe stock photo" become "this place actually exists in the 11th arrondissement".

# AUTHENTICITY PROPS — WHAT MAKES A SCENE FEEL LIVED-IN

A generic scene feels like stock. A scene with **three small plausible details** feels real. Pick from the right bank for the category:

**Event / concert / festival:** stage rigging and steel truss silhouettes · follow-spot beams cutting through haze · speaker stacks flanking the stage · laser fan overhead · hands in the air out-of-focus foreground · wristbands · confetti mid-air caught in spotlight · smoke-machine haze · hanging LED panels · tiny stage crew silhouettes.

**Café / food / restaurant:** flour dust on the marble · a wooden spoon handle poking out of frame · half-drunk coffee with latte art fading · partial chalkboard menu blurred in back · a folded apron over a chair · steam rising · a single fresh herb sprig · crumbs on a napkin · mismatched ceramic plates.

**Product / tech:** a fingerprint ghost on the glass · soft dust particles in the key light · specular highlight across brushed metal · subtle shadow pooling · a single reflection of the studio softbox · one accessory barely in frame suggesting scale.

**Street / urban:** rain puddle reflecting neon · a crumpled poster on a wall · newspaper blowing past · one cyclist silhouette blurred by motion · condensation on a bus window · a single pigeon mid-takeoff.

**Wedding / intimate:** a pair of linked hands at the edge · scattered rose petals on stone · a candle burning just inside frame · a ribbon trailing off a chair · soft tulle catching side-light · a single dewdrop on a flower.

**Home / bedroom / lifestyle:** a half-read book face-down · coffee cup ring on wood · morning light on a crumpled linen sheet · a cat tail curling off the edge · a plant shadow on the wall · slippers kicked to one side.

**Office / corporate / desk:** a sticky note corner-of-frame · a coffee mug with tiny latte art · a pen mid-spin · laptop LED reflecting in glass · cable management left casually real.

Pick 2–3 per scene. Overstuffing = clutter. Absence = sterile. Two or three is the sweet spot.

# NO REAL NAMES, YES FAKE PLAUSIBLE DETAILS

**Never** render real celebrity names, real brand logos, real trademarked characters, or real copyrighted titles on the image. That's legal suicide and the model often garbles them anyway.

**Instead invent plausibly-real-looking fakes:**
- Festival needs a lineup? → "LUNA • ECHO • THE SUNFIELDS • NOVA STATE" (invented band names, believable vibe)
- Product needs a brand mark? → use a generic mark ("a small minimal wordmark logo in the corner") or describe the user's brand_kit if provided
- Magazine cover needs a name? → "QUARTERLY", "SIGNAL", "LOUNGE N°14" (generic editorial flavor)
- Movie poster needs a title? → use the user's title verbatim if given, else invent ("A FIELD BEYOND THE DAWN")

This is how movie set-dec departments do it: fake brands that *look* real, so the audience believes without a real logo ever appearing.

# VOCABULARY — WORDS THAT SIGNAL QUALITY

When describing the scene/prompt (not on-image text), reach for specific craft vocabulary. These words tell the image model you mean business:

**Lighting:** golden-hour rim light · volumetric god rays · Rembrandt key light · softbox bounce · practical neon spill · candle-lit chiaroscuro · window-light overcast · cinematic backlight · butterfly beauty lighting · moody single-source.

**Composition:** rule of thirds · symmetric hero · dutch angle · low-angle heroic · overhead flat-lay · negative-space editorial · rule of odds · leading lines · off-center dynamic.

**Texture / material:** brushed brass · matte obsidian · wet chrome · linen weave · marble veining · velvet drape · aged paper · risograph grain · 35mm film grain · specular highlights.

**Palette names:** muted pastel · teal-orange cinematic · bleach-bypass · earthy terracotta · midnight navy · rose-gold warm · sage and bone · desaturated noir · vaporwave pastel · high-key minimal.

**Style / medium:** editorial magazine spread · Behance-grade · Studio-Ghibli-style · Pixar 3D · Wes-Anderson-symmetric · Annie-Leibovitz-portrait · Apple-keynote-clean · National-Geographic-realism.

**Mood words:** aspirational · intimate · punchy · contemplative · celebratory · premium minimal · gritty documentary · dreamy ethereal · bold rebellious · warm nostalgic.

**Energy / motion / dynamism:** swirling light trails · motion-blurred crowd · confetti caught mid-air · streaking headlights · windswept hair · dust kicked up in slow-motion · splashing liquid frozen · rippling silk in wind · falling petals · long-exposure light streaks · frenetic pan-blur background · zoom-burst radial.

**Crowd / collective life:** out-of-focus sea of raised hands · silhouetted audience edges · anonymous diverse figures at mid-distance · a blurred couple in profile · a child on a parent's shoulders in silhouette · backs-of-heads watching the stage · a single clear face emerging from a crowd wash.

Use 3–6 of these per prompt, not all 50. Pick the ones that serve the intent.

# BEFORE → AFTER (LEARN THE DELTA)

## Example A — tiny input, huge output
**User:** "diwali wishes"

**Bad (just echo):** "A Diwali wishes image with diyas and lights. 'Happy Diwali.'"

**Good (pro):**
- intent: `diwali_wishes`
- aspect_hint: `portrait_4_3`
- prompt: A warm, cinematic Diwali greeting composition in soft evening light: a shallow-focus hero row of three hand-crafted terracotta diyas in the lower third, their flames flickering warm amber, with a row of soft golden-bokeh fairy lights curving across the background. Scattered marigold petals and a few delicate rangoli chalk strokes in deep crimson and saffron frame the bottom edge. Floating above the diyas, elegant hand-lettered calligraphic script reads "Happy Diwali" in rich gold foil, with a smaller clean serif line underneath reading "May your home glow as brightly as these lights." Palette: warm amber, deep maroon, saffron gold, ivory cream, charcoal shadow. Rich filmic grain, shallow depth of field, 85mm portrait lens feel, candle-lit mood, premium festive greeting card aesthetic.
- negative_prompt: distorted text, garbled letters, extra flames, low-quality, watermark, cluttered
- ad_copy: {"headline": "Happy Diwali", "subhead": "May your home glow as brightly as these lights.", "cta": ""}

Notice how the pro version INVENTED: the three-diya count, the marigold petals, the hand-lettered script, the second line of copy, the lens, the grain, the exact palette. The user said two words. You delivered a complete creative brief.

## Example B — messy long input, tighter output
**User:** "i want a post for my cafe it has good coffee and pastries location in bandra mumbai and we are doing a sunday special brunch with live music acoustic guitar and i want it to look good on insta feed square"

**Good (pro):**
- intent: `social_post`
- aspect_hint: `square_hd`
- prompt: A scroll-stopping Instagram feed image for a Bandra café's Sunday acoustic brunch: an overhead ⅞ hero shot of a rustic wooden table at soft morning window-light, a flat-white with latte art and a golden flaky croissant on a ceramic plate centered left, a half-strummed acoustic guitar resting across the upper right corner, a small vase of pampas grass softening the edge, one warm-toned vintage filter over the whole frame. Large bold display-serif headline "Sunday Sessions" locked across the top third in warm charcoal, with a smaller clean sans subhead "Brunch + Live Acoustic • Bandra" in the lower third. Palette: warm oat cream, rich espresso brown, sage green, soft brass. 35mm lens feel, shallow DoF on the foreground coffee, airy café ambience, editorial lifestyle mood, Behance-grade polish.
- negative_prompt: distorted text, extra fingers, cluttered background, blown highlights, garbled letters, watermark
- ad_copy: {"headline": "Sunday Sessions", "subhead": "Brunch + Live Acoustic • Bandra", "cta": ""}

Notice: you stripped the messy phrasing, kept the spine (Bandra café, Sunday brunch, acoustic, square feed), and UPGRADED — you added the pampas grass, the latte art, the guitar placement, the palette, the typography lockup.

## Example C — product ad
**User:** "ad for my new wireless earbuds, black color, premium feel"

**Good (pro):**
- intent: `product_ad`
- aspect_hint: `portrait_4_3`
- prompt: A hero product advertisement for premium matte-black wireless earbuds: the earbuds case floating at center, slightly tilted, lid open revealing both buds with soft internal LED glow, hovering above a pool of rippling liquid-black surface that reflects a faint teal rim-light. Deep obsidian gradient background with a single cool cyan spotlight from upper-left creating a dramatic rim on the case. Brand wordmark "SoundX" in small crisp white sans at top-left. A small "NEW LAUNCH" label with thin rules above the headline. Bold condensed white sans-serif headline "SILENCE, ENGINEERED." at upper-left. Elegant italic subhead "Studio sound, untethered." beneath it. A horizontal row of three circular icon badges with labels: "40H Battery" (battery icon), "Studio Sound" (waveform icon), "Zero Lag" (lightning icon). CTA pill "Pre-order Now" in electric cyan at lower-left. Palette: obsidian black, matte graphite, cyan electric blue, crisp white. 100mm macro-feel lens, f/2.8 depth, studio product photography lighting with key + rim + subtle fill, premium tech brand aesthetic à la Apple × Sony.
- negative_prompt: low-quality, scratched surface, dusty, plastic cheap look, distorted text, watermark, jpeg artifacts
- ad_copy: {"headline": "SILENCE, ENGINEERED.", "subhead": "Studio sound, untethered.", "cta": "Pre-order Now", "benefit_lines": ["40H Battery", "Studio Sound", "Zero Lag"], "trust_signals": ["Noise Cancelling", "IPX4 Rated", "Made With Precision", "2-Year Warranty"], "emotional_tagline": "Your world, on your terms.", "brand_name": "SoundX", "brand_emblem_description": "minimalist circular badge with a stylized sound-wave glyph in cyan, sitting just above the SoundX wordmark", "website_url": "www.soundx.io", "contact_info": "@soundx.official | support@soundx.io", "footer_strip": ["FREE SHIPPING WORLDWIDE", "2-YEAR WARRANTY", "30-DAY RETURNS", "SECURE CHECKOUT"]}

## Example D — beauty/cosmetics launch (HIGHEST STANDARD — study this)
**User:** "facepowder launching post for instagram, brand name is myPowder"

**Good (pro):**
- intent: `product_ad`
- campaign_type: `product_launch`
- subject_category: `beauty`
- aspect_hint: `square_hd`
- copywriting_formula: `AIDA`
- prompt: A premium Instagram square beauty advertisement, Estée Lauder quality level. Warm cream-to-blush gradient background with artistically scattered loose face powder dust across the lower-right. Hero product: an open rose-gold compact face powder case with the lid propped elegantly, exposing the silky pressed powder puck with "myPowder" embossed in rose-gold, accompanied by a velvet puff applicator with a satin "myPowder" ribbon tab in the foreground. Overhead beauty lighting with a warm softbox creating a gentle specular highlight along the compact edge. Left text column: a small ornate rose-gold floral emblem (stylized 'm' monogram inside a delicate diamond outline with lotus petal accents) sits at the very top, with "myPowder" wordmark logo immediately below it in soft rose-gold cursive, then "LOVE YOUR SKIN. EVERYDAY." in tiny tracking-spaced cream caps beneath the wordmark. A small "NEW LAUNCH" badge with delicate flanking rules just above the headline. Large bold condensed charcoal sans-serif headline "LIGHT AS AIR." followed by elegant rose-brown italic script subheadline "Flawless Everywhere." A small intro line reads "Introducing myPowder Face Powder" with "FACE POWDER" styled as a rounded rose-tinted label badge. Body copy sentence "For a smooth, matte and naturally radiant finish." Below that, a horizontal row of 4 circular icon badges: "Lightweight Feel" (feather), "Blurs & Sets" (sparkle), "Oil Control" (droplet), "Long Lasting Wear" (clock). Script CTA "Available Now! ♡" in rose. Tagline in small elegant sans "Because you deserve a finish as beautiful as you are. ♡" just above the bottom strip. Bottom strip: a horizontal footer band split into two rows — top row is the trust signals "VEGAN | DERMATOLOGICALLY TESTED | SUITS ALL SKIN TYPES | MADE WITH CARE ♡". Below it, a thin secondary band with the FOOTER_STRIP badges shown as small icon+label pairs: a tiny truck icon "FREE SHIPPING PAN INDIA", a wallet icon "COD AVAILABLE", a return-arrow icon "7-DAY EASY RETURNS", a checkmark-shield icon "100% AUTHENTIC". To the lower-right of the CTA pill, a tiny rose-gold website URL "www.mypowder.in" is rendered. At the very bottom-left edge, contact info appears in micro-text: "+91 98765 43210 | Worli, Mumbai – 400018 | @mypowder.beauty". Circular trust badge top-right: "SOFT FOCUS ALL DAY" with tiny heart. Palette: warm cream 60%, soft peach-blush 25%, rose-gold accent 10%, charcoal text 5%. Commercial beauty photography, 100mm macro feel, premium print-ready ad quality.
- negative_prompt: distorted text, garbled letters, extra product, cluttered, cheap looking, low quality, watermark, blurry
- ad_copy: {"headline": "LIGHT AS AIR.", "subhead": "Flawless Everywhere.", "cta": "Available Now! ♡", "benefit_lines": ["Lightweight Feel", "Blurs & Sets", "Oil Control", "Long Lasting Wear"], "trust_signals": ["Vegan", "Dermatologically Tested", "Suits All Skin Types", "Made With Care"], "emotional_tagline": "Because you deserve a finish as beautiful as you are.", "brand_name": "myPowder", "brand_emblem_description": "small ornate rose-gold floral emblem with a stylized 'm' monogram inside a delicate diamond outline, lotus petal accents, sits centered above the myPowder wordmark", "website_url": "www.mypowder.in", "contact_info": "+91 98765 43210 | Worli, Mumbai – 400018 | @mypowder.beauty", "footer_strip": ["FREE SHIPPING PAN INDIA", "COD AVAILABLE", "7-DAY EASY RETURNS", "100% AUTHENTIC"]}

Notice how Example D names EVERY element with exact position, quotes EVERY text string, describes the product tactilely (embossed, velvet puff, satin ribbon), specifies icon types (feather, sparkle, droplet, clock), AND populates the complete BRAND-IDENTITY LAYER (brand_emblem_description + website_url + contact_info + footer_strip). This is what separates a finished real-world ad from an unfinished AI draft. EVERY D2C / brand / product / event poster MUST populate these 4 fields — they exist on every real ad you've ever seen on Instagram or print.

## Example E — fashion / apparel ad with MODEL (lifestyle, not product-only)
**User:** "Generate an instagram post for a d2c brand that is selling a banarasi saree and brand name is glamour."

**Good (pro):**
- intent: `product_ad`
- campaign_type: `product_launch`
- subject_category: `fashion`
- aspect_hint: `square_hd`
- copywriting_formula: `AIDA`
- prompt: A premium Instagram square fashion advertisement, Sabyasachi-quality editorial heritage feel. Two-column composition: LEFT 55% — a graceful Indian woman in her late 20s elegantly wearing an exquisite hand-woven Banarasi silk saree in deep marigold orange with intricate gold zari floral motifs across the pallu, draped traditionally over her left shoulder, hands gently meeting at her waist showing delicate gold bangles and a statement ring, soft contemplative downward gaze, hair pulled into a low traditional bun adorned with a single jasmine string, antique gold jhumka earrings and a layered gold-and-pearl choker with kundan stones, soft golden-hour light streaming through ornate carved sandstone palace pillars in the soft-focus background, marigold petals scattered subtly on the floor at her feet. RIGHT 45% — clean cream gradient text panel. Top-right corner of the LEFT column: a small saffron orange ribbon banner reading "D2C BRAND CRAFTED FOR YOU" in tiny white serif caps. Top of right panel: small ornate orange diamond emblem with stylized 'g' monogram inside, lotus petal flourishes above and below, sits centered. Below the emblem: "GLAMOUR" wordmark in elegant marigold-orange display serif, with "TIMELESS. ELEGANT. YOU." in tiny tracking-spaced charcoal caps beneath it. Center-locked: large refined display serif headline "The Heritage of" in deep charcoal followed by a hand-lettered orange italic script word "Banarasi Weaves" with a delicate ornamental flourish beneath it. Subhead in small clean sans-serif: "Exquisite hand-woven sarees, woven with tradition and made for you." Below: a horizontal row of 4 circular icon badges in soft saffron with thin gold rings: "Pure Silk" (silk-thread icon), "Authentic Banarasi" (loom icon), "Lightweight & Comfortable" (feather icon), "Made With Love" (heart icon). Bottom of right panel: a wide warm-cream "Shop Now" CTA pill in solid marigold orange with a thin gold border and "www.glamour.in" in tiny rose-gold text just below it. At the very bottom, a thin saffron footer band split into two rows: top row reads "FREE SHIPPING PAN INDIA | COD AVAILABLE | 7-DAY EASY RETURNS | DIRECTLY FROM WEAVERS"; below it a micro-text contact line "+91 98765 43210 | Glamour Studio, Connaught Place, Delhi – 110001 | @glamour.official". Palette: warm cream 55% (background and right panel), saffron-marigold orange 30% (saree, accents, CTA), antique gold 10% (embroidery, jewelry, emblem), deep charcoal 5% (text). Cinematic editorial fashion photography, 85mm portrait lens feel, shallow depth of field, soft golden-hour rim light on the saree's silk weave, Vogue India heritage editorial mood.
- negative_prompt: distorted face, extra fingers, mangled hands, blurry saree details, garbled text, watermark, cluttered background, plastic skin
- ad_copy: {"headline": "The Heritage of Banarasi Weaves", "subhead": "Exquisite hand-woven sarees, woven with tradition and made for you.", "cta": "Shop Now", "benefit_lines": ["Pure Silk", "Authentic Banarasi", "Lightweight & Comfortable", "Made With Love"], "trust_signals": ["100% Authentic", "Direct From Weavers", "Heirloom Quality"], "emotional_tagline": "Timeless. Elegant. You.", "brand_name": "GLAMOUR", "brand_emblem_description": "small ornate saffron-orange diamond emblem with a stylized 'g' monogram in the center, delicate lotus petal flourishes above and below, sits centered above the GLAMOUR wordmark", "website_url": "www.glamour.in", "contact_info": "+91 98765 43210 | Glamour Studio, Connaught Place, Delhi – 110001 | @glamour.official", "footer_strip": ["FREE SHIPPING PAN INDIA", "COD AVAILABLE", "7-DAY EASY RETURNS", "DIRECTLY FROM WEAVERS"]}

Notice how Example E centers a HUMAN MODEL wearing the saree (not just the fabric). For fashion / apparel / jewelry / cosmetics-on-body / footwear / eyewear, the depicted_subject is ALWAYS a person wearing/using the product — that is what real Instagram fashion ads look like, and what users implicitly mean when they say "create a post for my saree brand". Product-only flat-lay belongs to packaged-goods (detergent, drinks, electronics), not to fashion.

# TEXT ON IMAGE — YOU'RE THE COPYWRITER TOO

When the output needs words on the image:
- ALWAYS write the actual line. Never leave "a headline about X". Invent it.
- **PRESERVE the user's exact terminology.** If the user says "song", write "song" — DO NOT substitute "single" / "track" / "tune". If they say "shop", don't write "store". If they say "discount", don't write "sale". Use *their* word — even if industry jargon would sound more polished. The image must match what the user typed in spirit and vocabulary.
- **PRESERVE user-quoted strings VERBATIM and put OFFERS in HEADLINE.** If the user wrote text inside quotes (`"..."`, `'...'`) OR named a specific offer/discount/percentage/price/date (e.g. `upto 30% off`, `Buy 1 Get 1`, `Sale ends Sunday`, `₹999 only`, `flat 50% off`), that EXACT text MUST appear in `ad_copy.headline` — NOT subhead, NOT tagline. The offer IS the primary message; it MUST be the loudest text on the canvas. Image models render only 3 strings reliably (brand + headline + CTA), so if the offer is buried in subhead it gets DROPPED. Patterns triggering this rule: any of `%`, `off`, `free`, `save`, `buy N get M`, `flat`, `₹`, `$`, `from ₹X`, `starting at`, `limited time`, `sale`, `discount` → headline. Use the brand voice for subhead (`"Tough on stains."`), not the offer.

- **DO NOT HALLUCINATE OFFERS / DISCOUNTS / DEADLINES / PRICES THE USER DID NOT MENTION.** This is the #1 cause of fake-feeling ad output. If the user says "create an Instagram post for a saree brand" without mentioning a sale, percentage, deadline, or price — DO NOT invent "20% OFF", "LIMITED TIME", "Sale ends Sunday", "Flat 50% Off", "Early Bird ₹999". The user did not authorize a discount; inventing one is a fabrication that hurts trust and could mislead real customers. Default behavior when user doesn't mention an offer: build the ad around emotional positioning + trust signals + product story, NOT around a fake promo. Banned hallucinations unless user explicitly mentioned them: "%", "off", "limited time", "ends today/tonight/Friday", any price ("₹X", "$X", "from ₹X"), "early bird", "flash sale", "clearance", "exclusive deal". If the prompt is positioning-focused (heritage, craftsmanship, lifestyle, brand intro), the ad has NO promo — just the brand story.

- **EVENT / LINEUP / SERIES POSTERS USE `lineup_items`, NOT `benefit_lines`.** When the user prompt contains "lineup", "series", "schedule", "sessions", "speakers", "concerts", "performances", "workshops", "sermons", "festival days", "monthly calendar", or describes a multi-act / multi-date event — the schedule entries belong in `ad_copy.lineup_items` as one string per entry (format: '<DATE> | <NAME or TITLE> | <TIME> | <LOCATION optional>'), NOT collapsed into 3 generic benefit pills like "Live Performances / Community Gathering / Evening Sessions". Generic pills are a SIGN THE LINEUP DATA WAS LOST. If the user said "lineup" but didn't list specific names, INVENT 4-6 plausible names (genuine artists/speakers from the genre — for bhajan: Pandit Jasraj, Anup Jalota, Sadhvi Poornima, Devkinandan Thakur etc; for tech: real conference speakers from that domain) with sequential weekly dates in the requested month and a consistent time. The `benefit_lines` field is for product features (Pure Silk / Lightweight / Made With Love), NEVER for collapsing schedule data. If user said "lineup", you MUST output a populated `lineup_items` array — empty `lineup_items` for a lineup prompt is a critical failure.

- **USER-STATED COLORS / FONTS / LANGUAGE / VISUAL DIRECTIONS ARE LAW — NEVER OVERRIDE.** When the user explicitly states a color ("use white orange color", "in blue and gold", "pastel pink palette"), a font ("in serif", "use script lettering"), a language ("Hindi", "Hinglish", "include English and Tamil"), an aspect ratio, or any concrete visual direction — that instruction is NON-NEGOTIABLE and overrides all default industry-color logic, archetype defaults, and atmospheric mood mappings. The 60-30-10 ratio, color psychology guides, and industry-chromatic-logic exist to fill the GAPS when the user is silent — they NEVER override an explicit user instruction. If the user said "white and orange" for a devotional poster, the palette is "warm cream/off-white 60% (background), saffron orange 30% (accent panels), deep marigold orange 10% (CTA/dates)" — NOT maroon, NOT red, NOT gold-on-burgundy even if "devotional/temple" archetype suggests those. If the user says "Hindi welcome line included", at least one prominent Hindi line MUST appear on canvas verbatim. If the user names specific people/dates/times ("Pandit X on May 4 at 6:30 PM"), every name/date/time renders verbatim in the layout — no swapping for fictional alternatives, no dropping the time. Direct user words are the floor; archetype guidance only applies above that floor.

- **POPULATE THE FULL BRAND-IDENTITY LAYER FOR D2C / E-COMMERCE / EVENT / SERVICE ADS.** A real-world ad is incomplete without 4 elements that ChatGPT/Midjourney always include but AI ad engines often skip. You MUST populate these schema fields whenever the ad is for a brand/business/event:

  • `brand_emblem_description` — describe a small decorative crest/mandala/diamond/circle-emblem to render ABOVE the wordmark or in the top-left corner. Real ads pair the brand name with a tiny ornate mark. For luxury fashion: "small ornate gold diamond emblem with stylized first-letter monogram inside, lotus motif accents". For organic: "minimalist circular badge with leaf icon". For events/spiritual: "small mandala with om symbol". Empty ONLY for tech/SaaS where wordmark alone fits the minimal aesthetic.

  • `website_url` — generate a plausible URL for D2C/brand/event ads. Format: `www.{brandslug}.in` for Indian brands, `.com` for global, `.org` for non-profits/spiritual. Examples: `www.glamour.in`, `www.bhajansandhya.com`, `www.spiritualharmony.org`. Renders in the CTA strip. Empty ONLY for personal posts (wishes, family events).

  • `contact_info` — generate plausible phone + address for events/restaurants/local services/D2C heritage brands. Format: `+91 98765 43210 | <Venue/Office>, <Area>, <City> – <PIN>`. Real-feel placeholder makes the poster finished. Empty for personal posts only.

  • `footer_strip` — 3-4 short footer-strip badges for the bottom credibility close. For D2C: `["FREE SHIPPING PAN INDIA", "COD AVAILABLE", "7-DAY RETURNS", "DIRECTLY FROM WEAVERS"]`. For events: `["FAMILY WELCOME", "PARKING AVAILABLE", "ENTRY FREE", "ALL AGES"]`. For restaurants: `["DINE-IN • TAKEAWAY • DELIVERY", "OPEN 11 AM – 11 PM"]`. EMPTY footer = poster looks like an unfinished draft.

  TEST: if your output has only `headline` + `subhead` + `cta` + `benefit_lines` + `trust_signals`, the ad is INCOMPLETE. The brand-identity layer (emblem + website + contact + footer) is what separates an unfinished AI draft from a real-world ChatGPT-class poster.

- **QUOTED TEXT IS A FLOOR, NOT A CEILING — STILL INVENT THE FULL AD FRAMEWORK.** When the user writes `"with text 'BEAT FEST 2026' and 'March 15'"` or `"with text 'GRAND OPENING' and 'Free Dessert'"`, those quoted strings are the **mandatory** copy — but the ad is NOT complete with just those. A real festival/restaurant/event poster also needs: a fictional **brand name** (e.g. "PULSE PRESENTS", "EMBER & SAGE"), 2-4 short **benefit_lines** (e.g. "60+ Artists", "3 Stages", "Food Trucks" / "Hand-Crafted", "Local Sourcing", "Live Music"), 2-3 **trust_signals** (e.g. "Sold Out 2025", "Press Pick" / "Zomato 4.7★", "Time Out Approved"), an **emotional_tagline** (e.g. "One Night. Pure Sound." / "Where every plate becomes a story."), and a **cta** (e.g. "Get Tickets", "Reserve Now"). User-quoted text fills `headline` + maybe `subhead`; you fill EVERYTHING ELSE. A poster with only a giant headline + date and nothing else looks like a placeholder, not a finished ad. Compare: ❌ `BEAT FEST 2026 / March 15` (3 elements, looks like a draft) vs ✅ `BEAT FEST 2026 / March 15 / 60+ Artists • 3 Stages • Food Trucks / "Pulse Presents" wordmark / Get Tickets button / "One Night. Pure Sound." tagline / Sold Out 2025 trust badge` (8 elements, finished poster).
- Use straight double quotes for exact render: `"Mornings, Upgraded"`.
- **NEVER leave empty quotes `""` inline.** If you reference on-image text, the quotes MUST contain the actual line — write `the CTA pill reads "Shop Now"`, never `the CTA pill reads ""`. Empty quotes will render as literal floating quotation marks on the image. Every quoted block in the prompt must contain real copy that ALSO appears in the corresponding `ad_copy` field (headline, subhead, or cta).
- Keep headlines ≤ 8 words, subheads ≤ 14, CTA ≤ 4.
- For wishes: write a warm specific line, not "Happy Birthday" generic. Think of what a thoughtful friend would write.
- For ads: write a line that sells the feeling, not the feature. "Mornings, Upgraded" beats "Premium Coffee Machine".
- Suggest typography style in words (bold display serif, elegant calligraphic script, condensed modern sans, vintage slab serif) — don't describe letterforms.
- Place text spatially: "headline locked across the top third in bold sans-serif, white on dark overlay".

# ASPECT RATIO — INFER FROM INTENT

- Instagram feed / square post → `square_hd`
- Story / Reel cover / mobile-first poster → `portrait_9_16`
- Print poster / wishes / greeting → `portrait_4_3`
- Hoarding / YouTube thumb / widescreen ad → `landscape_16_9`
- Magazine spread / web banner → `landscape_4_3`

If the user specified a canvas, honor it. Otherwise pick what the medium demands.

# NEGATIVE PROMPT

Fill it when quality matters. Tailor to the image:
- portraits → `extra fingers, deformed hands, bad anatomy, plastic skin, asymmetric eyes`
- text-heavy → `distorted text, garbled letters, misspelled words, extra letters`
- products → `dust, scratches, smudges, cheap plastic look, bad reflection`
- always safe → `low-quality, blurry, watermark, signature, jpeg artifacts`

# OUTPUT FORMAT — JSON ONLY

{
  "intent": "<birthday_wishes | diwali_wishes | product_ad | social_post | hoarding | event_poster | movie_poster | sale_ad | food_ad | real_estate_ad | educational_ad | concert_poster | wedding_invite | portrait | scene | logo | general>",
  "prompt": "<one flowing paragraph — 80–200 words for typography/posters, 60–140 for photoreal. Every creative decision made. Exact quoted copy strings for all text.>",
  "negative_prompt": "<comma-separated negatives tailored to image type, or empty string>",
  "aspect_hint": "<square_hd | portrait_4_3 | landscape_4_3 | portrait_9_16 | landscape_16_9>",
  "campaign_type": "<product_launch | sale | event | awareness | seasonal | announcement | wishes | general>",
  "subject_category": "<beauty | food | tech | fashion | event | education | health | real_estate | entertainment | general>",
  "platform": "<instagram_feed | story | youtube_thumbnail | print_poster | hoarding | general>",
  "copywriting_formula": "<AIDA | PAS | BAB | simple>",
  "ad_copy": {
    "headline":          "<primary attention hook ≤8 words, or empty>",
    "subhead":           "<secondary context line ≤14 words, or empty>",
    "cta":               "<action verb ≤4 words — Shop Now / Register / Learn More, or empty>",
    "benefit_lines":     ["<2–3 word icon label e.g. 'Lightweight Feel'>", "<2–3 word e.g. 'Oil Control'>", "<optional 3rd>"],
    "trust_signals":     ["<Vegan>", "<Dermatologically Tested>", "<Suits All Skin Types>", "<Made With Care>"],
    "emotional_tagline": "<aspirational closing line, or null>",
    "brand_name":        "<exact brand name if user provided, or null>"
  },
  "visual": {
    "mood":             "<one emotional register>",
    "color_palette":    "<dominant + secondary + accent with craft vocabulary>",
    "lighting":         "<direction + quality + temperature>",
    "background":       "<background description>",
    "composition":      "<hero placement + text zones + negative space>",
    "typography_style": "<font style guidance>"
  }
}

Rules:
- `ad_copy` → populate for anything with on-image text (ads, posters, wishes, events, hoardings). `null` only for pure scenes/portraits with zero text.
- `visual` → populate for typography/poster/ad buckets. `null` for simple photoreal/portrait requests.
- `benefit_lines` → 2–3 word ICON LABELS (not full sentences). Rendered as circular icon badges in the image. Empty array `[]` when not applicable.
- `trust_signals` → use empty array `[]` when not applicable, never null. For beauty/health/product ads: always populate with 3–4 items.
- `emotional_tagline` and `brand_name` → use `null` when not applicable.
- For product ads: `headline` MUST be ≤4 words. Rewrite until it is.

# MENTAL QA PASS — LOOK AT THE FINISHED IMAGE IN YOUR HEAD

Before you ship, do a 5-second simulation. Close your eyes, imagine the rendered image on a phone screen, and answer these:

1. **Eye-landing test** — where does the eye go FIRST? Is that the thing that matters most? (For an ad: the product or headline. For a thumbnail: the face + big word. For wishes: the warm hero visual.)
2. **Read-order test** — after the first landing, where does the eye travel? Is that a clean path (top→bottom, big→small)? Or does it ping-pong confused?
3. **Contrast test** — is every text element legible against what sits behind it? If no, you forgot the background color-block or gradient.
4. **Clutter test** — remove one thing. Does the image get better? If yes, the original was overstuffed. Strip it.
5. **Stock-test** — does it look like a generic stock template? If yes, add the one specific detail that makes it feel hand-made (the latte art, the single petal, the wristband, the light leak).
6. **Recreate test** — if I handed this prompt to a real photographer + designer with zero other context, could they recreate the exact image in your head?
7. **Leak test** — scan the `prompt` for forbidden words: "Option", "Version", "Variant", "Headline:", "Body:", "CTA:", "CALL TO ACTION", "[", "]", "Draft", "Alternatively". If ANY appear as labels or placeholders, DELETE them and write the actual content inline.

If any answer is "no", revise the prompt before emitting JSON. A good prompt survives all seven.

Never wrap JSON in code fences. Never add commentary. JSON only."""


# Some bucket → guidance hints we append to the user message so the model knows
# what kind of image is being generated. This stays small (one line).
_BUCKET_HINTS = {
    "typography":            "Output is text-heavy (poster/wishes/banner). Prioritize legible copy + supportive imagery.",
    "photorealism": (
        "Output is a PHOTOREAL image. Apply CINEMATIC PHOTOGRAPHY DISCIPLINE (not optional):\n"
        "  1. CAMERA — name a real lens (24mm/35mm/50mm/85mm/100mm macro), aperture (f/1.4 - f/16), "
        "shutter feel (frozen/motion-blur), and ISO mood (clean/grainy). Match focal length to "
        "subject distance: 24-35mm wide environmental, 50mm natural, 85-100mm flattering compression.\n"
        "  2. LIGHTING — specify direction (key + fill + rim), quality (hard/soft/diffused/golden-hour/"
        "overcast), and color temperature (warm 3200K / neutral 5600K / cool 7500K). Avoid flat "
        "ambient unless the look demands it.\n"
        "  3. COMPOSITION — Rule of Thirds intersection for the subject, leading lines, foreground-"
        "midground-background depth, intentional negative space. Mention crop (full / medium / close-up).\n"
        "  4. ATMOSPHERE — micro-details that sell realism: skin pores, fabric weave, dust motes in "
        "light shafts, moisture, surface imperfections, subsurface scattering on translucent objects.\n"
        "  5. ANTI-PATTERNS — explicitly negate in `negative_prompt`: 'illustrated, cartoon, "
        "painterly, plastic skin, waxy texture, over-smoothed, AI-rendered look, extra fingers, "
        "fused limbs, text artifacts, watermark, low-res, blurry except where intentional'.\n"
        "Output `prompt` must read like a photographer's brief — concrete and physical, not abstract."
    ),
    "photorealism_portrait": (
        "Output is a PHOTOREAL PORTRAIT of a HUMAN. Apply PORTRAIT-PHOTOGRAPHY DISCIPLINE:\n"
        "  1. SUBJECT IDENTITY — describe the person specifically: age range, gender presentation, "
        "ethnicity (when relevant + respectful), distinguishing features, hair (length/color/style), "
        "wardrobe (era + texture). Avoid generic 'beautiful woman / handsome man' — be concrete.\n"
        "  2. EXPRESSION + POSE — name the emotion (contemplative, joyful, defiant, serene), "
        "eye direction (camera / off-frame / down), micro-expression (slight smile, parted lips, "
        "raised brow), body language (shoulders square / turned 3/4, hands placement).\n"
        "  3. CAMERA — 85mm or 100mm prime preferred for flattering compression, f/1.8 - f/2.8 for "
        "creamy bokeh, shallow DOF with eyes tack-sharp. Eye-level for connection; slight low-angle "
        "for power; high-angle for vulnerability.\n"
        "  4. LIGHTING — name a setup: Rembrandt (45° key, triangle on cheek), loop (slight nose "
        "shadow), butterfly (centered key, beauty light), split (half-face shadow), clamshell "
        "(top + bottom diffused). Specify quality (soft / hard / window / golden hour) and ratio.\n"
        "  5. ANATOMICAL CORRECTNESS — explicitly require 'two eyes symmetric, five fingers per "
        "hand, natural teeth, realistic skin texture with pores'. In negative_prompt: 'extra "
        "fingers, mangled hands, asymmetric eyes, plastic skin, doll-like, waxy, uncanny valley, "
        "deformed, missing limbs, fused features, blurry face'.\n"
        "  6. WARDROBE + BACKGROUND — describe fabric (linen / wool / silk / leather), color "
        "harmony with skin tone, background bokeh (urban out-of-focus / studio gradient / nature). "
        "Background should support, not compete.\n"
        "Treat this like a real photo brief — the model needs physical specifics, not adjectives."
    ),
    "photorealism_product": (
        "Output is a COMMERCIAL PRODUCT SHOT. Apply PACKSHOT DISCIPLINE:\n"
        "  1. PRODUCT FIDELITY — describe the exact product (shape, label, material, dimensions). "
        "If the user named a brand, the label/text must be spelled correctly. Hero angle: 3/4 view "
        "preferred for dimensionality; flat-lay for cosmetics/food; eye-level for bottles.\n"
        "  2. SURFACE + BACKDROP — surface material (marble / wood / linen / acrylic / seamless "
        "paper), color story that complements the product, optional props that suggest use-context "
        "(no clutter — max 2-3 supporting elements).\n"
        "  3. LIGHTING — softbox key + fill + rim is the studio default. For glass/liquid: backlight "
        "for translucency. For metal: large diffused source to wrap highlights. Mention specular "
        "highlights and shadow density.\n"
        "  4. CAMERA — 50-100mm to avoid distortion, f/8-f/11 for full product sharpness, eye-level "
        "or slight elevation. Shallow DOF only when isolating one item among props.\n"
        "  5. MICRO-DETAILS — condensation droplets on cold drinks, steam from hot food, embossed "
        "label texture, wood grain, fabric weave. These sell premium-ness.\n"
        "  6. ANTI-PATTERNS in negative_prompt: 'distorted product shape, misspelled label, "
        "wrong logo, plastic-looking food, fake-looking glass, harsh flat flash, busy background, "
        "competing brands visible, dust/scratches unless intentional'."
    ),
    "artistic": (
        "Output is ARTISTIC / STYLIZED illustration. Apply FINE-ART DISCIPLINE:\n"
        "  1. NAME THE MEDIUM — be specific: oil paint, gouache, watercolor wash, ink + ink wash, "
        "digital painting (mention software feel: Procreate / Photoshop), charcoal, pastel, mixed "
        "media, woodblock print, screen print, etching. NEVER just say 'painted'.\n"
        "  2. ARTIST / MOVEMENT REFERENCE (when appropriate) — anchor the style: 'in the spirit "
        "of Mucha (Art Nouveau)', 'reminiscent of Studio Ghibli backgrounds', 'Beksinski "
        "dystopian surreal', 'Hopper urban solitude'. ONE reference, not a soup of names. Avoid "
        "living artists by name when possible (use movement/era instead).\n"
        "  3. BRUSHWORK / LINE QUALITY — describe the marks: visible impasto strokes, fine "
        "stippling, wet-on-wet bleeds, hard-edged ink linework, scratchy charcoal hatching, "
        "smooth airbrush gradient. The texture of the medium must be readable.\n"
        "  4. COLOR PALETTE — specify a constrained palette (3-5 named colors / value range / "
        "temperature bias). Mention the relationship: complementary, analogous, monochrome with "
        "pop, muted earth + one saturated accent. Avoid 'colorful' or 'vibrant' alone.\n"
        "  5. MOOD + COMPOSITION — atmospheric mood (melancholy, reverent, whimsical, ominous), "
        "compositional device (golden spiral, triangular, frame-within-frame, rule of thirds), "
        "depth via atmospheric perspective.\n"
        "  6. ANTI-PATTERNS in negative_prompt: 'photorealistic, 3D render, photograph, plastic "
        "look, AI-default soft glow, generic concept art, oversaturated, smooth gradient where "
        "brushwork is wanted, watermark, signature unless requested'."
    ),
    "anime": (
        "Output is ANIME / MANGA / JAPANESE ILLUSTRATION. Apply ANIME-PRODUCTION DISCIPLINE:\n"
        "  1. STYLE ERA / STUDIO HINT — name the visual lineage: '90s cel anime (visible cel "
        "shading, hand-painted backgrounds)', 'modern digital anime (clean vector lines, gradient "
        "shading)', 'Studio Ghibli watercolor backgrounds + hand-drawn characters', 'shōnen action "
        "(bold inks, speed lines)', 'shōjo (soft pastels, sparkles, large eyes)', 'seinen "
        "(realistic proportions, muted palette)'. Pick ONE.\n"
        "  2. LINEWORK — describe ink quality: clean tapered lines, varied weight (heavier on "
        "shadow side), no outline (paint-only), thick-thin manga ink. Specify whether outlines "
        "are black or colored-into-shading.\n"
        "  3. SHADING — cel-shaded (2-3 hard tone steps), soft anime gradient, painterly, "
        "screentone (manga dots/hatching). Skin: name the tone-step count. Hair: shine band "
        "placement.\n"
        "  4. CHARACTER DESIGN — specifics: hair (color / cut / movement), eye shape and color, "
        "face proportions (chibi / standard / realistic), outfit construction (school uniform / "
        "fantasy armor / streetwear with named pieces), expression archetype.\n"
        "  5. BACKGROUND TREATMENT — Ghibli-style detailed painted, simple gradient, photographic "
        "blur with cel character on top, pure white with speed lines, abstract geometric. Background "
        "and character must visually agree (don't mix photoreal bg + chibi character unless intentional).\n"
        "  6. ANTI-PATTERNS in negative_prompt: 'photorealistic skin texture, 3D render, "
        "western cartoon (Disney/Pixar) proportions unless requested, AI-default anime girl face, "
        "bad anatomy, broken hands, extra fingers, fused limbs, watermark, low quality, blurry'."
    ),
    "vector": (
        "Output is a vector/flat-design asset. If the user is asking for a LOGO, BRAND MARK, "
        "ICON, MONOGRAM, EMBLEM, BADGE, or APP ICON, treat it as professional 2026-era brand-"
        "identity work. Modern logos are NOT static decorations — they are cognitive triggers "
        "engineered for the human visual cortex (50ms judgment window) and adaptive across "
        "16px favicons → billboards. Apply this 7-PHASE COGNITIVE FRAMEWORK:\n"
        "\n"
        "  ── PHASE 1: STRATEGIC DIAGNOSIS (the WHY before any shape) ──\n"
        "  Infer from the user's words: industry sector, brand archetype, target audience, "
        "core personality. Pick ONE archetype and state it explicitly:\n"
        "    • Caregiver / Innocent → soft circles, organic forms, warm muted hues\n"
        "    • Ruler / Sage → squares + verticals, deep blue or black + gold, classical serif\n"
        "    • Hero / Magician → triangles, dynamic diagonals, high-contrast accent color\n"
        "    • Explorer / Creator → organic abstract forms, vibrant unexpected palette\n"
        "    • Lover / Jester → flowing curves, warm reds/pinks, expressive script\n"
        "    • Outlaw / Rebel → broken/disrupted geometry, monochrome with one shock color\n"
        "  This archetype dictates EVERY downstream choice. Without it, the mark is decoration.\n"
        "\n"
        "  ── PHASE 2: COGNITIVE-EASE PROCESSING ORDER ──\n"
        "  The brain processes a logo in this exact biological sequence: COLOR (instant "
        "endocrine response) → FORM (Gestalt recognition) → MOTION (if any) → MEANING. "
        "Optimize each layer:\n"
        "    • Color FIRST: pick a deliberate palette that matches the neuro-response (blue = "
        "parasympathetic / trust; red = amygdala / urgency; yellow = serotonin / optimism; "
        "green = neutral / growth; orange = warmth/energy; purple = imagination/luxury; "
        "earth tones = authenticity). 2026 palettes are CONFIDENT and HIGH-CONTRAST — NOT "
        "washed-out beige minimalism, NOT cold corporate gray. For CREATOR / DESIGN / MEDIA / "
        "PLATFORM brands specifically, default to a 3-4 color SATURATED palette — typically "
        "a smooth gradient combining a warm hue (orange/pink/coral) WITH a cool hue "
        "(purple/blue/teal) plus a deep dark anchor (charcoal/navy). 2-color cyan-and-magenta "
        "is a tired AI default; push for richer multi-stop palettes (e.g. purple→pink→orange "
        "sunset, teal→indigo→violet twilight, coral→fuchsia→amber) when archetype is Creator/"
        "Magician/Lover. Reserve 2-color flat palettes for Ruler/Sage/Caregiver brands.\n"
        "    • Form SECOND: leverage Gestalt (closure, figure-ground, similarity). Clever "
        "negative space the brain SUBCONSCIOUSLY COMPLETES = high cognitive reward (FedEx "
        "arrow, NBC peacock).\n"
        "    • Strip everything that adds noise. Cognitive ease > clever complexity.\n"
        "\n"
        "  ── PHASE 3: SHAPE PSYCHOLOGY (deliberate geometry) ──\n"
        "  Every primary shape carries inherent meaning. Pick ONE dominant family:\n"
        "    • CIRCLES / OVALS → unity, community, safety, inclusivity, wholeness\n"
        "    • SQUARES / RECTANGLES → stability, order, professional trust, durability\n"
        "    • TRIANGLES → energy, ambition, innovation, forward momentum\n"
        "    • ORGANIC / ABSTRACT → authenticity, biological growth, creativity, sustainability\n"
        "    • HORIZONTAL LINES → calm, balance, groundedness\n"
        "    • VERTICAL LINES → strength, ambition, vertical growth\n"
        "  2026 trend: blend rigid geometry with TACTILE MATERIALITY — controlled imperfections, "
        "subtle hand-drawn-ness, slight roughened edges to escape cold AI-default polish.\n"
        "\n"
        "  ── PHASE 4: MARK TYPE DECISION ──\n"
        "  CRITICAL DEFAULT: Real iconic logos are SYMBOLS, not letters. Apple = apple "
        "silhouette (NOT letter A). Nike = swoosh (NOT letter N). Twitter = bird (NOT T). "
        "Target = bullseye (NOT T). Airbnb = bélo curve (NOT A). Spotify = sound waves "
        "(NOT S). Shell = shell. Mercedes = three-point star. McDonald's = arches (kind of M, "
        "but read as arches). Apps and products iconize a CONCEPT or OBJECT, not their "
        "first letter. Only legacy brands or super-short names default to wordmark/lettermark.\n"
        "  Order of preference for NEW brand prompts (default unless user specifies):\n"
        "    1. PICTORIAL SYMBOL (PRIMARY DEFAULT) — recognizable object or metaphor that "
        "represents the brand's PURPOSE, not its name. Examples: Apple = apple, Twitter = "
        "bird, Target = bullseye, Slack = hashtag/octothorpe, Airbnb = belonging-curve, "
        "Patreon = loop, GitHub = octocat. For an image-generation platform: think 'lens', "
        "'aperture', 'spark', 'prism', 'frame', 'eye', 'pixel-fragmenting butterfly', "
        "'paint splash', 'star burst', 'play-button-as-portal'. Pick a symbol that evokes "
        "the brand's WHAT (creativity / generation / vision / transformation), NOT its name.\n"
        "    2. ABSTRACT MARK — pure geometry meaning nothing literal but uniquely ownable "
        "(Nike swoosh, Adidas trefoil, Mastercard circles, Microsoft 4-square, Pepsi orb, "
        "Mitsubishi diamonds). Best when no literal object fits. Should suggest a feeling "
        "(motion, balance, energy) without illustrating the name.\n"
        "    3. COMBINATION (symbol + wordmark) — Burger King, Starbucks, Lacoste. Use when "
        "the symbol can also stand alone but you want brand-name visibility on the first "
        "encounter. The symbol still does the heavy lifting; the wordmark is for context.\n"
        "    4. EMBLEM / BADGE / STAMP — symbol inside circular/shield container (Harley, "
        "Starbucks original, NFL teams, Warner Bros). Signals heritage and authenticity. "
        "Strong 2026 trend against AI sameness.\n"
        "    5. WORDMARK — typography IS the mark (FedEx, Coca-Cola, Google, Visa, Sony). "
        "ONLY use when name is short (≤6 chars), highly distinctive, and the user has "
        "explicitly indicated 'just text logo / wordmark / typography logo'. Do NOT default "
        "to wordmark for SaaS/app/product brands.\n"
        "    6. LETTERMARK / MONOGRAM — 1-3 stylized initials (IBM, HBO, CNN, NASA, P&G, "
        "GE). ONLY use for very long names that abbreviate cleanly OR when user says 'a "
        "stylized P / monogram of P'. Do NOT default to lettermark for new brand prompts.\n"
        "  HARD RULE: Unless the user prompt explicitly says 'wordmark', 'lettermark', "
        "'stylized letter X', 'monogram', or 'just the brand name', DEFAULT TO PICTORIAL "
        "SYMBOL or ABSTRACT MARK. The brand name appears in the wordmark BELOW the symbol "
        "(combination layout), but the SYMBOL is the focal point — not a stylized first "
        "letter. A logo is supposed to be recognizable WITHOUT reading any letters.\n"
        "\n"
        "  ── PHASE 5: TYPOGRAPHY — HYPER-EXPRESSIVE, NOT BLANDED ──\n"
        "  The 2010s 'blanding' era of safe geometric sans-serif is OVER. 2026 typography is "
        "expressive and ownable. Specify ONE typeface with a clear personality:\n"
        "    • Custom-drawn letterform (highest distinctiveness — for premium brands)\n"
        "    • Heritage serif / Storybook Gothic (warmth, narrative depth, established trust)\n"
        "    • Geometric grotesque WITH a signature quirk (ink trap, missing notch, unexpected "
        "kerning, shifted dot — micro-details as ownership anchors)\n"
        "    • Humanist sans (friendly, approachable — caregiver brands)\n"
        "    • Slab serif (editorial sturdiness — sports, news, food)\n"
        "    • Mono / technical (dev tools, fintech, cryptography)\n"
        "    • Script / calligraphy (luxury, hospitality, personal brands)\n"
        "  EXACT brand name in QUOTES is non-negotiable for wordmarks/combinations. Specify "
        "weight (light/regular/medium/bold/black) and tracking. NEVER pixelate letterforms "
        "unless the brand IS pixel-themed.\n"
        "  • LETTER-ACCURACY GUARANTEE — if the brand starts with a specific letter (e.g. "
        "'Pixium' starts with P, NOT F), state in the prompt MULTIPLE TIMES that the mark "
        "depicts the exact letter (e.g. 'the capital letter P with a closed bowl on the right "
        "side, vertical stem on the left, NOT an F or B or D'). Image models routinely "
        "confuse P↔F↔R, B↔E, O↔Q, C↔G when only stated once. Reinforce by describing the "
        "letter's anatomy: 'P has one closed bowl at the top half attached to a vertical "
        "stem — the bowl must close cleanly back to the stem'. ALWAYS add to negative_prompt: "
        "'wrong letter, F instead of P, R instead of P, distorted letterform, mirrored "
        "letter, missing bowl on P, open counter where it should be closed'.\n"
        "\n"
        "  ── PHASE 6: TECHNICAL + ACCESSIBILITY CONSTRAINTS ──\n"
        "  • SCALABILITY: readable from 16px favicon → billboard. Strip fine details. NO drop "
        "shadows, NO 3D bevels, NO photoreal shading. Flat color default; max ONE subtle "
        "2-stop gradient if it serves the concept.\n"
        "  • B&W-FIRST PRINCIPLE: the silhouette must be strong in pure solid black-on-white. "
        "Color is the emotional layer ON TOP of an already-strong form. If it fails B&W, the "
        "form is wrong.\n"
        "  • NEGATIVE SPACE: ≥25% padding on all sides. Mark sits centered on a clean solid "
        "background (pure white, off-white, or one brand color). Use negative space as "
        "intentional design element where possible.\n"
        "  • WCAG CONTRAST: minimum 4.5:1 contrast ratio for body text, 3:1 for the mark "
        "against its background. Avoid color combinations that fail color-blindness tests "
        "(red+green together, blue+purple together) unless contrast handles it.\n"
        "  • RESPONSIVE SYSTEM IMPLIED: design assuming the mark will need a stripped-down "
        "monogram version for tiny UI surfaces — keep core silhouette identifiable. "
        "CRITICAL: this is a CONCEPTUAL principle, NOT a rendering instruction. NEVER ask the "
        "image model to render multiple versions of the logo (small + large + monogram + "
        "wordmark) in a single output. Output ONE primary mark + (if board format) one "
        "wordmark + tagline + feature icons. Do NOT include a second small 'header logo' or "
        "'app icon preview' alongside the hero mark — that creates two competing focal "
        "points and confuses the brand.\n"
        "  • SINGLE CLEAN LETTERFORM: when the mark is a letterform (P, A, M etc), it must "
        "be ONE single clean shape — NOT two letters overlaid, NOT a scribbled outline "
        "circling the letter, NOT three ribbon-folds stacked competing for attention. "
        "Pick ONE construction concept (e.g. 'a single capital P with a cleanly closed bowl, "
        "filled with a smooth purple-to-orange gradient') and execute it crisply. Multiple "
        "stacked/overlapping/competing strokes = amateur output.\n"
        "\n"
        "  ── PHASE 7: ANTI-PATTERNS (force into negative_prompt) ──\n"
        "  'photo background, 3D render, drop shadow, bevel, glossy plastic, realistic "
        "texture, wrong letters, misspelled brand name, extra characters, distorted "
        "typography, generic swoosh + globe + gear cliché, AI-default geometric P/A/B in "
        "cyan-and-black, AI-default soft glow, washed-out beige minimalism, cold corporate "
        "gray, blanded safe sans-serif, friction-free synthetic AI polish, lorem ipsum, "
        "sample text, watermark, signature, multiple competing focal points, busy ornaments, "
        "pixelated letterforms unless brand is pixel-themed'.\n"
        "\n"
        "  ── ANTI-DEFAULTS (push past the obvious) ──\n"
        "  TWO LAZY DEFAULTS to actively avoid:\n"
        "    LAZY DEFAULT #1 — 'use the first letter of the brand name as the logo'. This "
        "is the AI-generation crutch. Apple is not letter A. Nike is not letter N. Twitter "
        "is not letter T. Real iconic logos are CONCEPTS and OBJECTS, not initials. If your "
        "instinct is to make a stylized 'P' or 'A' or 'M' for a new brand, STOP and design "
        "a real symbol first. Letter-based marks (wordmark/lettermark) are reserved for "
        "specific cases (legacy brands, very short names, when user explicitly asks).\n"
        "    LAZY DEFAULT #2 — 'literal illustration of the brand name'. When the brand "
        "name suggests something obvious (Pixium → pixels, Sunrise → sun, Forge → "
        "hammer/anvil, Loop → circle), the AMATEUR picks the most direct symbol. The "
        "PROFESSIONAL pushes to a second or third interpretation OR uses the obvious "
        "element ONLY as a subtle micro-anchor inside a more distinctive concept. Strong "
        "2026 logos earn their meaning through unexpected association.\n"
        "  TEST: 'Could a competitor with a different name use this same logo?' If yes, the "
        "mark is too generic. 'Would this logo still make sense if the brand was called "
        "something different?' If yes, you have a real symbol. If the logo only works "
        "BECAUSE of the brand name (e.g. it's just the letter P), you don't have a logo — "
        "you have a typography exercise.\n"
        "\n"
        "  ── 2026 TREND CHECKLIST (apply where they enhance the concept) ──\n"
        "    • Tactile materiality — controlled hand-drawn imperfections to escape AI-default polish\n"
        "    • Stamp/seal/badge identities — circular emblem signals authenticity in misinfo era\n"
        "    • Storybook gothic / heritage serif — nostalgia + credibility for digital-first brands\n"
        "    • Strategic color saturation — fewer colors but MAXIMUM intentional contrast\n"
        "    • Micro-detail anchors — one signature notch/dot/kerning quirk as ownable element\n"
        "    • Retro-futurism — sleek precision + nostalgic typographic reference\n"
        "    • Atmospheric gradient (sparingly) — neo-mint, sunset, twilight blends for emotional depth\n"
        "  Use AT MOST 2 trends per design — overstacking trends defeats cognitive ease.\n"
        "\n"
        "  ── DELIVERABLE FORMAT: ISOLATED MARK vs BRAND BOARD ──\n"
        "  Read the user's intent carefully and pick ONE format:\n"
        "    (A) ISOLATED MARK — just the logo on a clean background. Use when user says "
        "'just a logo', 'simple mark', 'icon only', 'favicon', 'app icon'. Pure mark + "
        "optional small wordmark, generous negative space, nothing else.\n"
        "    (B) BRAND IDENTITY BOARD — ONE hero logo + tagline + feature/service showcase row "
        "in a clean presentation layout. Use when user describes a STARTUP / PLATFORM / "
        "SERVICE and lists features ('a platform that does X, Y, Z'), or asks for a 'brand "
        "intro', 'launch graphic', 'identity sheet'. This is what ChatGPT/Midjourney produce "
        "by default for SaaS/product brand prompts. \n"
        "    LAYOUT (strict, do not deviate):\n"
        "      • TOP-CENTER: ONE single hero logo (mark + wordmark stacked OR side-by-side). "
        "ONLY ONE logo on the canvas. NO secondary 'header logo' in the corner, NO 'favicon "
        "preview'. Just one hero.\n"
        "      • MIDDLE: tagline in a small refined sans-serif (3-5 words, e.g. 'Imagine. "
        "Design. Inspire. Anywhere.')\n"
        "      • BOTTOM: horizontal row of 4-7 circular feature icons with a single-word "
        "label BELOW each icon. Each icon has its own brand-palette color (rotating through "
        "the gradient hues so the row feels cohesive). Labels are mandatory — unlabeled "
        "icons leave the viewer guessing.\n"
        "    Use `ad_copy` schema generously: `brand_name` = the literal brand, "
        "`emotional_tagline` = 3-5-word brand promise, `benefit_lines` = the feature list as "
        "short labels (Typography, Poster, Ad, Thumbnail, Campaign, etc — exactly as user "
        "stated them).\n"
        "  DEFAULT: if the user lists multiple use-cases/features for the brand, ALWAYS pick "
        "(B) BRAND BOARD — that is what they're describing, even if they used the word 'logo'. "
        "Do not strip the features — they are the brand's value proposition and belong in the "
        "deliverable.\n"
        "\n"
        "Output `prompt` describes CONCEPT → archetype → palette (with neuro-rationale) → "
        "shape family → mark type → typography (with personality) → construction details → "
        "B&W-first hero mark + (if board format) tagline + feature icon row layout. NOT a "
        "real-world scene. For ISOLATED MARK: `ad_copy` is empty for pure symbols; "
        "`ad_copy.headline` carries literal brand text for wordmarks/combinations. For BRAND "
        "BOARD: populate `ad_copy.brand_name`, `ad_copy.emotional_tagline`, "
        "`ad_copy.benefit_lines` (the feature labels). The `prompt` reads like a senior brand "
        "designer's brief, not a generic image prompt. If the request is NOT a logo (flat "
        "illustration, sticker, infographic, icon set), ignore Phases 1/4/5 and just specify "
        "shapes, palette, geometry, no photo realism."
    ),
    "fast":                  "Output is a quick general image. Cover subject + scene + lighting + style succinctly.",
}

# ─────────────────────────────────────────────────────────────────────────────
# Platform specs — layout rules injected into the user message so Haiku knows
# the exact constraints for each output surface. Static system prompt stays
# cached; platform hint goes in the dynamic user message (no cache break).
# ─────────────────────────────────────────────────────────────────────────────
PLATFORM_SPECS: Dict[str, Dict[str, Any]] = {
    "instagram_feed": {
        "aspect_hint":   "square_hd",
        "layout_note":   "Square 1:1 feed post. Safe text zone: center 80%. Brand mark top-left. CTA bottom-center. Thumb-stop visual in first ⅓.",
        "text_rule":     "Headline max 6 words. Keep copy minimal — users scroll fast. One clear focal point.",
        "must_have":     "High-contrast hero element + single focal point + legible headline at mobile size.",
    },
    "instagram_feed_portrait": {
        "aspect_hint":   "portrait_4_3",
        "layout_note":   "Portrait 4:5 feed. Safe text: center 85%. Left-text / right-visual split works well.",
        "text_rule":     "Headline on left third. Product or hero visual on right two-thirds.",
        "must_have":     "Clean left-right balance. Text must be legible at thumbnail size.",
    },
    "story": {
        "aspect_hint":   "portrait_9_16",
        "layout_note":   "Vertical 9:16 story. Avoid top 15% (status bar) and bottom 15% (swipe-up UI). Safe zone: middle 70%.",
        "text_rule":     "Large bold text in the middle safe zone. Background fills full frame edge-to-edge.",
        "must_have":     "Full-bleed immersive visual. Text in safe zone only. One clear message.",
    },
    "youtube_thumbnail": {
        "aspect_hint":   "landscape_16_9",
        "layout_note":   "16:9 widescreen. MUST have: expressive face (left or right third) + 2-4 word bold text (opposite third) + high-contrast colors.",
        "text_rule":     "Max 4 words. Bold condensed sans with stroke/outline so it reads on any background. High saturation.",
        "must_have":     "Emotional face expression + big text + max 3 high-contrast colors. Readable as 120px thumbnail.",
    },
    "print_poster": {
        "aspect_hint":   "portrait_4_3",
        "layout_note":   "Print poster. Full information hierarchy: Title large → Subtitle → Details → Fine print at bottom. Rich detail appropriate.",
        "text_rule":     "Can carry more copy than digital. Still follow hierarchy: big → medium → small.",
        "must_have":     "Clear title treatment. Date/venue if event. Professional print-ready feel.",
    },
    "hoarding": {
        "aspect_hint":   "landscape_16_9",
        "layout_note":   "Billboard/hoarding. Read from moving vehicle at 50m. MAX 5 words total. One iconic image. Brand logo bottom corner.",
        "text_rule":     "3-5 words headline only. Nothing else. Violent color contrast. Zero visual clutter.",
        "must_have":     "One bold image + one bold line. That is all.",
    },
}

# Keyword patterns to detect platform from user prompt (checked before Haiku runs)
_PLATFORM_KEYWORDS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:instagram\s+story|ig\s+story|insta\s+story|reel\s+cover|whatsapp\s+status)\b", re.IGNORECASE), "story"),
    (re.compile(r"\b(?:youtube\s+thumbnail|yt\s+thumbnail|thumbnail)\b", re.IGNORECASE), "youtube_thumbnail"),
    (re.compile(r"\b(?:hoarding|billboard|hoardings|out[-\s]of[-\s]home|ooh\s+ad)\b", re.IGNORECASE), "hoarding"),
    (re.compile(r"\b(?:print\s+poster|a4\s+poster|a3\s+poster|flyer|brochure|pamphlet)\b", re.IGNORECASE), "print_poster"),
    (re.compile(r"\b(?:instagram\s+(?:post|feed|ad)|ig\s+(?:post|feed)|insta\s+(?:post|feed)|instagram)\b", re.IGNORECASE), "instagram_feed"),
]


def _detect_platform(user_prompt: str) -> Optional[str]:
    """Quick keyword scan to detect platform before Haiku runs.

    Returns a platform key from PLATFORM_SPECS, or None if no match.
    Haiku will refine/override this in its output `platform` field.
    """
    for pattern, platform in _PLATFORM_KEYWORDS:
        if pattern.search(user_prompt):
            return platform
    return None


def _build_user_message(
    user_prompt: str,
    bucket: str,
    tier: str,
    width: Optional[int],
    height: Optional[int],
    style: Optional[str],
    brand_kit: Optional[Dict[str, Any]],
    style_reference_description: Optional[str] = None,
    recipe: Optional[Dict[str, Any]] = None,
) -> str:
    parts = [f"USER REQUEST:\n{user_prompt.strip()}"]
    bucket_hint = _BUCKET_HINTS.get(bucket)
    if bucket_hint:
        parts.append(f"BUCKET: {bucket} - {bucket_hint}")

    # Category recipe injection. Recipe is pre-resolved by the Stage-1 Gemini
    # classifier (see _classify_intent_gemini). Goes in the dynamic user
    # message so the cached system prompt stays warm across all categories.
    if recipe is not None:
        parts.append(_format_recipe_for_prompt(recipe))
    parts.append(f"TARGET QUALITY TIER: {tier}")
    if width and height and not (width == 1024 and height == 1024):
        parts.append(f"REQUESTED CANVAS: {width}x{height} (use this to pick aspect_hint)")

    # Platform detection — inject layout constraints into user message.
    # This is dynamic so it doesn't break the static system prompt cache.
    detected_platform = _detect_platform(user_prompt)
    if detected_platform and detected_platform in PLATFORM_SPECS:
        spec = PLATFORM_SPECS[detected_platform]
        parts.append(
            f"DETECTED PLATFORM: {detected_platform}\n"
            f"  Aspect: {spec['aspect_hint']} — set aspect_hint to this.\n"
            f"  Layout: {spec['layout_note']}\n"
            f"  Text rule: {spec['text_rule']}\n"
            f"  Must-have: {spec['must_have']}"
        )

    if style:
        parts.append(f"USER STYLE PREFERENCE: {style}")
    if style_reference_description:
        # Priority 6 — Style anchor extracted from a reference image via Gemini Vision.
        # Haiku should treat this as a hard aesthetic anchor (palette / lighting /
        # texture / composition style), NOT as a description of the new scene's
        # subject matter. The user's actual subject is in USER REQUEST.
        parts.append(
            "STYLE REFERENCE (extracted from user's uploaded reference image — "
            "anchor the new image's aesthetic to this; do NOT copy the subject):\n"
            + style_reference_description.strip()
        )
    if brand_kit:
        bk_bits = []
        if brand_kit.get("brand_name"):    bk_bits.append(f"brand={brand_kit['brand_name']}")
        if brand_kit.get("primary_color"): bk_bits.append(f"primary={brand_kit['primary_color']}")
        if brand_kit.get("accent_color"):  bk_bits.append(f"accent={brand_kit['accent_color']}")
        if brand_kit.get("font_style"):    bk_bits.append(f"font_style={brand_kit['font_style']}")
        if bk_bits:
            parts.append("BRAND KIT: " + ", ".join(bk_bits))
    parts.append("Now produce the JSON object. Output JSON only.")
    return "\n\n".join(parts)


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)

# Defensive sanitizer — strips pitch-deck / brief-doc leaks that sometimes slip
# through even when the system prompt forbids them. Runs on the final prompt
# string BEFORE it hits the image model.
_LEAK_PATTERNS = [
    # Markdown headers / stray hash chars — image models render `###` literally
    # on canvas. Kill every run of 1-6 hash chars regardless of position.
    (re.compile(r"^\s*#{1,6}\s+", re.MULTILINE), ""),
    (re.compile(r"\s+#{1,6}\s+"), " "),
    (re.compile(r"#{2,6}"), ""),  # any remaining ##, ###, #### standalone
    # Markdown bold/italic markers
    (re.compile(r"\*{1,3}([^\*]+)\*{1,3}"), r"\1"),
    # "Option 1" / "Option 1:" / "OPTION 1" — with or without trailing punctuation
    (re.compile(r"\b(?:Option|Version|Variant|Layout|Design|Concept|Approach)\s+(?:\d+|[A-E]|One|Two|Three|Four)\s*[:.\-–—]?\s*", re.IGNORECASE), ""),
    # "NOVA.3", "NOVA 3", "BRAND.1" — trailing number on brand that signals variant
    (re.compile(r"(\b[A-Z][A-Z0-9]{2,})\s*[.\-]\s*[1-9]\b"), r"\1"),
    # Brief-doc labels: "Headline:", "Body:", "CTA:", "Subtitle:", "Subhead:", "Title:", "Text:", "Caption:", "Visual:", "Goal:"
    (re.compile(r"\b(?:Headline|Body|CTA|Subtitle|Subhead|Title|Text|Tagline|Caption|Visual|Visual\s+Suggestion|Goal|Hook|Description|Voice|Mood|Vibe|Concept|Idea|Suggestion|Product|Discount|Brand|Why\s+an?\s+\w+)\s*[:?]\s*", re.IGNORECASE), ""),
    # Typoed variants the model has been seen rendering: "Visption", "Captin"
    (re.compile(r"\b(?:Visption|Captin|Captain\s+\d+|Vipsion)\s*\d*\s*[:?]?\s*", re.IGNORECASE), ""),
    # Standalone "+" markers used as bullets in pitch decks
    (re.compile(r"(?:^|\s)\+\s+(?=\S)"), " "),
    # "Body copy:", "Body text:" multi-word labels
    (re.compile(r"\bBody\s+(?:copy|text|paragraph)\s*[:?]\s*", re.IGNORECASE), ""),
    # "CALL TO ACTION" as placeholder (unique phrase — if real CTA was present, it'd be an actual verb)
    (re.compile(r"\bCALL\s+TO\s+ACTION\b", re.IGNORECASE), ""),
    # "Headon 1", "Heading 1", "Section 1", "Panel 1"
    (re.compile(r"\b(?:Headon|Heading|Section|Panel|Frame)\s+\d+\b", re.IGNORECASE), ""),
    # Known template placeholders — pure UI elements, drop entirely.
    (re.compile(r"\[(?:Website\s*Address|Your\s*Logo|Logo|URL|Date|Sale\s*Ends?\s*Date|While\s*Supplies?\s*Last|Insert[^\]]*|Click\s*Here|Brand\s*Name|Company\s*Name|Tagline)\]", re.IGNORECASE), ""),
    # Remaining bracketed content — UNWRAP, don't drop. [Pixium Gold] → Pixium Gold.
    # Reason: dropping loses real brand/product names; unwrapping lets the model
    # use them as actual scene subjects. The output sanitizer at generate_stream
    # still has the standalone-line check for any leaked brief structure.
    (re.compile(r"\[([^\]\n]{1,80})\]"), r"\1"),
    # Curly-brace placeholders: {brand}, {{logo}} — same rule, unwrap.
    (re.compile(r"\{{1,2}([^}\n]{1,80})\}{1,2}"), r"\1"),
    # Placeholder chatter
    (re.compile(r"\b(?:Lorem ipsum|placeholder text|sample copy|example text|TBD|TK|XXX|YOUR\s+\w+\s+HERE)\b", re.IGNORECASE), ""),
    # "Draft 1", "First version", "Alternatively"
    (re.compile(r"\bDraft\s+\d+\b", re.IGNORECASE), ""),
    (re.compile(r"\b(?:Alternatively|First version|Second version|Initial draft)\b\s*[:.\-–—]?\s*", re.IGNORECASE), ""),
    # Multi-panel / collage / mood-board language
    (re.compile(r"\b(?:collage|grid layout|multi[- ]panel|split[- ]screen|A/B comparison|mood[- ]?board|pitch deck|design sheet|variation sheet|layout options?)\b", re.IGNORECASE), ""),
    # NOTE: Previously had a regex that stripped "Shop Now / Click here / Buy now /
    # Learn more / Discover your X / Elevate your X / Order today" unconditionally.
    # That was destructive — it stripped legitimate CTA copy that Haiku wrote inside
    # quotes (e.g. `reading "Shop Now"`), leaving empty quotes that the image model
    # rendered as floating quotation marks. Removed 2026-04-26. The ad_copy.cta
    # field + _fill_empty_quotes_from_adcopy + system-prompt rules already keep
    # CTA text inside quotes; we don't need a sanitize-time stripper.
]

# Always append these to negative_prompt — prevents image model from generating
# multi-panel design-sheet style outputs even when prompt is clean. Aggressive
# list because Seedream/Imagen still hallucinate pitch-deck layouts from shorter prompts.
_ANTI_COLLAGE_NEGATIVES = (
    "collage, grid layout, multi-panel, split-screen, two panels, three panels, "
    "four panels, six panels, A/B comparison, mood-board, design sheet, pitch deck, "
    "variation sheet, layout options, multiple options shown, "
    "Option 1, Option 2, Option 3, Option 4, before-after split, side-by-side comparison, "
    "text-heavy design, wall of text, body copy block, paragraph of text, "
    "annotated design, labeled sections, numbered sections, headline plus body plus CTA layout, "
    "brief document, creative brief layout, Instagram carousel, multi-slide layout, "
    "image split into regions, framed sub-images"
)


# ─────────────────────────────────────────────────────────────────────────────
# Affirmative anchors (Priority 2 — P-Distill / Reverse-Activation defense)
# ─────────────────────────────────────────────────────────────────────────────
# Research finding (From Orchestration to Oracles, p.4): "Reverse Activation"
# — when a prompt contains "no collage" / "no grid" / "not multi-panel", the
# text encoder STILL tokenizes the negated concepts and injects their feature
# vectors into early-denoising cross-attention. The diffusion model starts
# generating the negated layouts and then tries (often fails) to suppress
# them. Affirmative-only constraints score 116/120 vs negative-only 72/120
# in standardized intent-matching benchmarks across diffusion architectures.
#
# Strategy: replace mixed pos/neg anchors ("Not a collage, not a grid...")
# with purely affirmative phrasings. Used for providers that DROP negative
# prompts entirely (Seedream / Recraft / Grok / Wan / Imagen) — for those
# providers, anti-collage signal MUST live inside the positive prompt or it
# never reaches the model.

# Short universal anchor — prepended to every Stage-2 prompt regardless of
# provider. Sets the "one cohesive image" intent from the first token.
_AFFIRMATIVE_SINGLE_IMAGE_ANCHOR = "ONE single unified image, one cohesive composition. "

# Stronger anchor — applied when the prompt's negative_prompt contains
# anti-collage triggers AND the provider drops negatives. Pure affirmative
# language, zero "no/not" particles.
_AFFIRMATIVE_NO_COLLAGE_ANCHOR = (
    "A single continuous photograph spanning the entire canvas as one unbroken scene, "
    "one cohesive composition rendered as one committed final design, "
    "presented as a finished publication-ready artwork. "
)

# Trigger words that indicate the caller's negative_prompt is anti-collage.
# When ANY of these appear in the negative, the provider-side fold-in
# replaces the negatives with the strong affirmative anchor.
_ANTI_COLLAGE_TRIGGER_WORDS = (
    "collage", "panel", "grid", "option", "pitch deck", "design sheet",
)


def has_anti_collage_signal(negative_prompt: str) -> bool:
    """Return True if the negative_prompt contains anti-collage trigger words."""
    if not negative_prompt:
        return False
    lower = negative_prompt.lower()
    return any(w in lower for w in _ANTI_COLLAGE_TRIGGER_WORDS)


# Sentence-level killer — if a sentence/clause mentions any of these multi-variant
# trigger words, drop the WHOLE sentence. Splits on '.', '!', '?', and newlines.
# These words almost always mean the LLM is describing a layout with multiple
# panels/options/concepts inside one image, which the image model then renders.
_MULTI_VARIANT_TRIGGERS = re.compile(
    r"\b(?:options?|variants?|versions?|concepts?|alternatives?|side[\s-]by[\s-]side|"
    r"comparison|comparisons|panels?|grid|collage|moodboard|mood[\s-]board|"
    r"three\s+(?:designs?|ads?|posters?|layouts?|variations?)|"
    r"multiple\s+(?:designs?|ads?|posters?|layouts?|variations?|angles?|shots?)|"
    r"two\s+(?:designs?|ads?|posters?|layouts?)|"
    r"four\s+(?:designs?|ads?|posters?|layouts?)|"
    r"(?:left|right|top|bottom)\s+panel|carousel|slide\s+\d+)\b",
    re.IGNORECASE,
)


def _drop_multi_variant_sentences(text: str) -> str:
    """Drop entire sentences that mention multi-variant/panel/option language."""
    if not text:
        return text
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    kept = [p for p in pieces if p and not _MULTI_VARIANT_TRIGGERS.search(p)]
    return " ".join(kept).strip()


# Item 4 (Round 2 quality upgrade) - content filter trigger blacklist.
# Research PDF page 10 flagged this as a Medium-risk failure mode: words like
# "busty" trigger silent refusals or sterilization even in benign advertising
# contexts. We replace with neutral synonyms BEFORE the prompt reaches any
# provider. List grows over time from real telemetry of refused generations.
_CONTENT_FILTER_BLACKLIST = {
    "busty":      (r"\bbusty\b", "full-figure"),
    "sexy":       (r"\bsexy\b", "elegant"),
    "hot girl":   (r"\bhot\s+girl\b", "stylish woman"),
    "skimpy":     (r"\bskimpy\b", "minimal"),
    "nude":       (r"\bnude\b", "bare-skin tone"),
    # extend from telemetry of refused generations
}
_CONTENT_FILTER_PATTERNS = [
    (trigger, re.compile(pattern, re.IGNORECASE), repl)
    for trigger, (pattern, repl) in _CONTENT_FILTER_BLACKLIST.items()
]


# Item 4 (Round 2) - literal metadata leak defense.
# Research PDF page 9-10 flagged this as a CRITICAL risk: API config key/value
# pairs (model_version, temperature, seed, etc) accidentally end up in the
# prompt-text field and get rendered verbatim on the image. Defensive strip.
_METADATA_LEAK_PATTERN = re.compile(
    r"\b(?:model(?:_version)?|temperature|top_k|top_p|seed|api_key|"
    r"max_tokens|response_format|tool_choice|frequency_penalty|presence_penalty)"
    r"\s*[:=]\s*[\"']?[\w\-\.\d]+[\"']?",
    re.IGNORECASE,
)
_CODE_FENCE_REMNANT_PATTERN = re.compile(r"```(?:json|python|text)?|```", re.IGNORECASE)


def _scrub_content_filter_triggers(text: str) -> str:
    """Replace known content-filter trigger words with neutral synonyms.
    Logs every replacement so we can grow the blacklist from real refusals.
    """
    if not text:
        return text
    out = text
    for trigger, pattern, repl in _CONTENT_FILTER_PATTERNS:
        if pattern.search(out):
            logger.info("[content-filter] scrubbed: %s -> %s", trigger, repl)
            print(f"[content-filter] scrubbed: {trigger} -> {repl}", flush=True)
            out = pattern.sub(repl, out)
    return out


def _scrub_metadata_leaks(text: str) -> str:
    """Strip API config key/value pairs that leaked into the prompt text."""
    if not text:
        return text
    if _METADATA_LEAK_PATTERN.search(text) or _CODE_FENCE_REMNANT_PATTERN.search(text):
        cleaned = _CODE_FENCE_REMNANT_PATTERN.sub("", text)
        cleaned = _METADATA_LEAK_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"\{\s*,?\s*\}", "", cleaned)
        cleaned = re.sub(r",\s*,+", ", ", cleaned)
        cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
        logger.warning("[metadata-leak] scrubbed config keys from prompt")
        print("[metadata-leak] scrubbed config keys from prompt", flush=True)
        return cleaned.strip()
    return text


# Markdown chars that image models render literally when wrapped inside the
# "..." text-to-render strings: hashes, asterisks, underscores, backticks,
# tildes. Plus stray leading/trailing punctuation that has no visual purpose.
_MARKDOWN_IN_QUOTE_RE = re.compile(r'"([^"]{0,200})"')
_MARKDOWN_CHARS_RE = re.compile(r"^[\s#*_`~\->.+]+|[\s#*_`~\->.+]+$")
_INNER_MD_CHARS_RE = re.compile(r"[#*_`~]+")


def _scrub_markdown_inside_quotes(text: str) -> str:
    """Strip markdown markers from inside `"..."` text-to-render strings.

    Image models render the contents of quoted strings verbatim onto the
    canvas. If Haiku writes `"## LIGHT AS AIR"` or `"*Flawless Everywhere*"`,
    the model paints `##` and `*` characters onto the image. Rule: keep the
    words inside quotes; nuke the markup chars + leading/trailing junk.
    """
    if not text or '"' not in text:
        return text

    changed = [False]
    def _fix(m: "re.Match[str]") -> str:
        inner = m.group(1)
        cleaned = _INNER_MD_CHARS_RE.sub("", inner)
        cleaned = _MARKDOWN_CHARS_RE.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned != inner:
            changed[0] = True
        return f'"{cleaned}"' if cleaned else '""'

    result = _MARKDOWN_IN_QUOTE_RE.sub(_fix, text)
    if changed[0]:
        logger.info("[markdown-in-quotes] scrubbed markdown markers from quoted text")
        print("[markdown-in-quotes] scrubbed markdown markers from quoted text", flush=True)
    return result


def _sanitize_prompt(text: str, bucket: str = "") -> str:
    """Strip pitch-deck / placeholder language that image models render literally.

    For typography/ad_creative buckets, layout markers (Headline:, Body:, CTA:,
    ## section dividers) are intentionally preserved - GPT Image 2 and text-capable
    models use them for correct text placement and hierarchy rendering.

    Round 2 additions: content-filter trigger scrub + literal-metadata leak
    defense (research PDF pages 9-10).
    """
    if not text:
        return text
    original = text
    _is_typography = bucket in ("typography", "ad_creative")

    # Pass 0a: scrub content-filter trigger words so the prompt isn't refused.
    text = _scrub_content_filter_triggers(text)

    # Pass 0b: strip any leaked API config key/value pairs.
    text = _scrub_metadata_leaks(text)

    # Pass 0c: scrub markdown markers from INSIDE quoted text strings.
    # Haiku sometimes writes `"## LIGHT AS AIR"` or `"*Flawless Everywhere*"`
    # inside the prompt - image models then render the literal `##` / `*` chars
    # ON the canvas because they treat the quoted block as text-to-render.
    # Keep the quoted text itself; just strip the markup chars and stray
    # leading/trailing punctuation.
    text = _scrub_markdown_inside_quotes(text)

    # Pass 1: drop entire sentences mentioning multi-variant trigger words.
    text = _drop_multi_variant_sentences(text)

    # Pass 2: regex strip individual leak patterns (labels, brackets, etc).
    # For typography bucket: skip the brief-doc label pattern (index 6) so
    # "Headline:", "Body:", "CTA:", "Tagline:" etc. survive into the image model.
    for i, (pattern, replacement) in enumerate(_LEAK_PATTERNS):
        if _is_typography and i == 6:
            # index 6 = brief-doc labels (Headline/Body/CTA/Subtitle/Tagline...)
            # Keep these - GPT Image 2 uses them for structured text layout.
            continue
        text = pattern.sub(replacement, text)

    # For typography: also preserve ## section dividers (indices 0-2 strip hashes).
    # Re-pass is avoided by the index skip above since hashes are indices 0-2 and
    # brief-doc labels are index 6. But ## that SURVIVED (because they were inside
    # sentences) still get cleaned by indices 0-2 — which is correct: we only want
    # to keep "Headline:" style markers, not random ## hash chars.

    # Collapse doubled spaces / stray punctuation left by strips
    text = re.sub(r"  +", " ", text)
    text = re.sub(r" ([,.;:])", r"\1", text)
    text = text.strip()
    if text != original:
        logger.info("[simple-engine] sanitized leak patterns from prompt (len %d→%d) bucket=%s", len(original), len(text), bucket or "none")
        print(f"[SANITIZE] dropped {len(original) - len(text)} chars bucket={bucket or 'none'}", flush=True)
    return text


def _fill_empty_quotes_from_adcopy(prompt: str, ad_copy: Optional["AdCopy"]) -> str:
    """Replace empty quote pairs `""` in prompt with matching ad_copy field.

    Haiku occasionally writes `the CTA button reads ""` — putting the actual
    CTA only in `ad_copy.cta` and forgetting to inline it. The image model then
    renders literal floating quotation marks. We fix this by:

      1. Finding each `""` pair in the prompt
      2. Looking at the 80 chars BEFORE it for noun cues (cta/button → cta;
         subhead/subtitle → subhead; default → headline)
      3. Substituting the matching ad_copy text, OR dropping the empty quotes
         entirely if no ad_copy field is available.

    Idempotent — does nothing if prompt has no `""` pairs.
    """
    if not prompt or '""' not in prompt:
        return prompt
    original = prompt

    def _pick_field(context_lower: str) -> str:
        if ad_copy is None:
            return ""
        if any(k in context_lower for k in ("cta", "button", "pill", "call to action", "call-to-action")):
            return (ad_copy.cta or "").strip()
        if any(k in context_lower for k in ("subhead", "subtitle", "sub-head", "sub-headline", "supporting line")):
            return (ad_copy.subhead or "").strip()
        # Default: assume the empty quote was meant for the headline
        return (ad_copy.headline or "").strip()

    def _replace(match):
        start = max(0, match.start() - 80)
        context = original[start:match.start()].lower()
        text = _pick_field(context)
        return f'"{text}"' if text else ""

    cleaned = re.sub(r'""', _replace, prompt)
    # Tidy up any double spaces / orphan punctuation left by drops
    cleaned = re.sub(r"  +", " ", cleaned)
    cleaned = re.sub(r" ([,.;:])", r"\1", cleaned).strip()

    if cleaned != original:
        dropped = original.count('""') - cleaned.count('""')
        logger.info("[simple-engine] filled %d empty-quote pairs from ad_copy", dropped)
        print(f"[EMPTY-QUOTE-FIX] filled/dropped {dropped} empty quote pairs", flush=True)
    return cleaned


def _parse_json_loose(text: str) -> Dict[str, Any]:
    """Extract a JSON object from the model output, tolerating stray fences."""
    cleaned = _JSON_FENCE_RE.sub("", text).strip()
    # Find the first { and last } — model sometimes adds a stray comment
    first = cleaned.find("{")
    last  = cleaned.rfind("}")
    if first == -1 or last == -1 or last <= first:
        raise ValueError("No JSON object found in model output")
    candidate = cleaned[first:last + 1]
    return json.loads(candidate)


class SimplePromptEngine:
    """Single-call Haiku 4.5 prompt enricher with Pydantic-validated output."""

    def __init__(self):
        self._model = _CLAUDE_MODEL
        self._client = None  # lazy — Instructor-wrapped Anthropic client

    def _get_client(self):
        """Return an Instructor-wrapped Anthropic client.

        Instructor patches the client so calls with `response_model=...` enforce
        the Pydantic schema via Anthropic tool-calling. Schema violations trigger
        automatic retries (max_retries) with the validation error appended to the
        conversation — the model corrects its own output before we see it.
        """
        if self._client is None:
            import anthropic
            import instructor
            key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set — required for simple_prompt_engine")
            self._client = instructor.from_anthropic(anthropic.Anthropic(api_key=key))
        return self._client

    async def enrich(
        self,
        user_prompt: str,
        bucket: str = "fast",
        tier: str = "1k",
        width: Optional[int] = None,
        height: Optional[int] = None,
        style: Optional[str] = None,
        brand_kit: Optional[Dict[str, Any]] = None,
        style_reference_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enrich a user prompt into a production-ready image-gen prompt.

        Args:
            style_reference_description: 2-3 sentence visual style summary
                (palette/lighting/texture) extracted from a user's uploaded
                reference image via Gemini Vision (Priority 6). Optional —
                empty string when the user provided no reference or the
                extraction failed.

        Returns a dict with: prompt, negative_prompt, intent, aspect_hint, ad_copy, _elapsed.
        On failure, falls back to a minimal dict echoing the user prompt so the
        pipeline never breaks.
        """
        start = time.time()
        try:
            # STAGE 1 - Gemini intent classifier (replaces keyword-based bucket
            # detection AND alias-based recipe matching). Returns:
            #   {bucket, category_key, has_text, is_ad, platform}
            # Gemini decides; we lookup the matching recipe by exact key.
            # Uses the per-process cache so a prior classify_intent() call from
            # generate_stream's bucket layer doesn't pay twice.
            classification = await classify_intent(user_prompt)
            recipe = _recipe_by_key(classification.get("category_key") or "")

            # If the caller passed a bucket but Gemini disagrees with high
            # signal (e.g. typography vs photorealism_*), trust Gemini for the
            # Haiku brief. The actual model routing in generate_stream uses the
            # classification result via the returned dict.
            effective_bucket = classification.get("bucket") or bucket

            # STAGE 2 - Haiku enrichment with recipe-pre-injected user message.
            user_msg = _build_user_message(
                user_prompt, effective_bucket, tier, width, height, style, brand_kit,
                style_reference_description=style_reference_description,
                recipe=recipe,
            )
            # Instructor returns a validated Pydantic instance (or raises after
            # max_retries exhausts). No more loose-JSON parsing.
            output: SimpleEngineOutput = await asyncio.to_thread(self._call_sync, user_msg)

            # STAGE 2.5 - Critique pass via GEMINI (per project rule: Haiku
            # owns enrichment; Gemini owns all other LLM steps). Only runs
            # for ad intent where headline tightness + copy-space matter.
            # 10-point checklist covering all 4 phases of the ad-creator
            # framework. Adds ~$0.0001 + ~1.5s. Failure is non-fatal.
            if _USE_SELF_CRITIQUE and bool(classification.get("is_ad")):
                critique_start = time.time()
                improved = await self._critique_with_gemini(output, user_prompt, classification)
                logger.info(
                    "[critique] (%.2fs) headline: %r -> %r | objective=%s audience=%r",
                    time.time() - critique_start,
                    (output.ad_copy.headline if output.ad_copy else "") or "",
                    (improved.ad_copy.headline if improved.ad_copy else "") or "",
                    improved.objective,
                    (improved.target_audience or "")[:60],
                )
                output = improved

            # ORDER MATTERS: sanitize FIRST, then fill empty quotes.
            # Reason: _sanitize_prompt has a CTA-verb stripper ("Shop Now",
            # "Click here", etc — line ~674) that would re-empty any quoted
            # CTA text we just filled. Sanitizing first strips bare scaffolding
            # CTA language; the fill step then writes the legitimate ad_copy
            # text inside quotes where the image model can render it.
            sanitized = _sanitize_prompt(output.prompt.strip(), bucket=effective_bucket)
            clean_prompt = _fill_empty_quotes_from_adcopy(sanitized, output.ad_copy)
            raw_neg = output.negative_prompt.strip()
            combined_neg = f"{raw_neg}, {_ANTI_COLLAGE_NEGATIVES}" if raw_neg else _ANTI_COLLAGE_NEGATIVES

            ad_copy_dict: Optional[Dict] = None
            if output.ad_copy is not None:
                ad_copy_dict = output.ad_copy.model_dump()

            visual_dict: Optional[Dict] = None
            if output.visual is not None:
                visual_dict = output.visual.model_dump()

            return {
                "prompt":               clean_prompt,
                "negative_prompt":      combined_neg,
                "intent":               output.intent.strip() or "general",
                "aspect_hint":          output.aspect_hint,
                "ad_copy":              ad_copy_dict,
                # Art Director Brain — campaign intelligence
                "campaign_type":        output.campaign_type or "general",
                "subject_category":     output.subject_category or "general",
                "platform":             output.platform or "general",
                "copywriting_formula":  output.copywriting_formula or "simple",
                "visual":               visual_dict,
                # Phase-1 Strategy fields (May 3 2026 - 4-Phase Ad Creator Brain)
                "target_audience":      output.target_audience or "",
                "objective":            output.objective or "awareness",
                # Stage-1 classifier output (Gemini) -- generate_stream uses
                # `classification.bucket` to override keyword-based detection.
                "classification":       classification,
                "_recipe_key":          (recipe or {}).get("key"),
                "_elapsed":             time.time() - start,
                "_source":              "simple_engine",
            }
        except ValidationError as ve:
            # Instructor exhausted retries — Haiku could not produce valid JSON
            # even after self-correction. Log the schema errors and fall back.
            # Logged at WARNING + print so it surfaces in pm2 logs reliably
            # (logger.error sometimes filtered by handler config).
            err_summary = [
                f"{'.'.join(str(p) for p in e.get('loc', ()))}={e.get('type', '?')}"
                for e in ve.errors()[:5]
            ]
            logger.warning(
                "[simple-engine] Pydantic validation failed after %d retries (%d errors) - falling back to RAW user prompt. Fields: %s",
                _INSTRUCTOR_MAX_RETRIES, ve.error_count(), ", ".join(err_summary),
            )
            print(f"[SIMPLE-ENGINE-VALIDATION-FAIL] {ve.error_count()} errors: {err_summary}", flush=True)
            # Print full first error for debugging
            if ve.errors():
                first = ve.errors()[0]
                print(f"[SIMPLE-ENGINE-VALIDATION-FAIL] first error: loc={first.get('loc')} msg={first.get('msg')} input_len={len(str(first.get('input', '')))}", flush=True)
            return self._fallback(user_prompt, start, f"validation_error: {ve.error_count()} issues")
        except Exception as e:
            logger.exception("[simple-engine] enrich failed: %s — falling back to raw prompt", e)
            return self._fallback(user_prompt, start, str(e))

    @staticmethod
    def _fallback(user_prompt: str, start: float, error: str) -> Dict[str, Any]:
        """Safe fallback so the pipeline never breaks on engine failure."""
        return {
            "prompt":          user_prompt,
            "negative_prompt": f"low-quality, blurry, distorted, watermark, extra fingers, {_ANTI_COLLAGE_NEGATIVES}",
            "intent":          "general",
            "aspect_hint":     "square_hd",
            "ad_copy":         None,
            "_elapsed":        time.time() - start,
            "_source":         "simple_engine_fallback",
            "_error":          error,
        }

    def _call_sync(self, user_msg: str) -> SimpleEngineOutput:
        """Single Claude call with Pydantic validation — runs in worker thread."""
        client = self._get_client()

        if _USE_CACHING:
            # Static system prompt cached; user message stays dynamic.
            # Instructor passes through to Anthropic, so cache_control still works.
            system = [{
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            system = _SYSTEM_PROMPT

        # response_model + max_retries = automatic schema enforcement.
        # If Haiku returns malformed output, Instructor re-prompts with the
        # validation error appended, up to max_retries times.
        return client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system,
            temperature=_TEMPERATURE,
            messages=[{"role": "user", "content": user_msg}],
            response_model=SimpleEngineOutput,
            max_retries=_INSTRUCTOR_MAX_RETRIES,
        )

    async def _critique_with_gemini(
        self, draft: SimpleEngineOutput, user_prompt: str, classification: Dict[str, Any]
    ) -> SimpleEngineOutput:
        """Stage-2.5 critique pass via Gemini 2.5 Flash.

        Per project decision (May 3 2026): Haiku owns prompt enrichment; Gemini
        owns ALL other LLM steps (intent classification + critique + future
        review tasks). Same model that already classified the intent reviews
        the Haiku draft against a 10-point ad-creator checklist covering all
        4 phases (Strategy / Visual Psychology / Composition / Copy).

        Returns the improved SimpleEngineOutput. Failure non-fatal - returns
        the original draft so the pipeline never breaks.

        Cost / latency: ~$0.0001 + ~1.5s per ad generation (Gemini 2.5 Flash
        with response_mime_type=json, ~600 input + ~800 output tokens).
        """
        try:
            from app.services.smart.design_agent_chain import _get_gemini_client
            from google.genai import types
        except Exception as e:  # noqa: BLE001
            logger.warning("[critique] google-genai unavailable: %s -- skipping critique", e)
            return draft

        # Pull every relevant draft field for the review.
        ac = draft.ad_copy
        vis = draft.visual
        review_msg = (
            f"USER ORIGINAL REQUEST:\n{user_prompt.strip()}\n\n"
            f"INTENT CLASSIFIER (from Stage-1 Gemini):\n"
            f"  bucket={classification.get('bucket')}, category={classification.get('category_key')}, "
            f"is_ad={classification.get('is_ad')}, has_text={classification.get('has_text')}, "
            f"platform={classification.get('platform')}\n\n"
            f"HAIKU FIRST DRAFT (review and improve - DO NOT start over):\n"
            f"=== prompt (image-gen prompt) ===\n{draft.prompt[:2000]}\n\n"
            f"=== ad_copy ===\n"
            f"  headline:              {(ac.headline if ac else '') or '(empty)'}\n"
            f"  headline_typography:   {(ac.headline_typography if ac else '') or '(empty)'}\n"
            f"  subhead:               {(ac.subhead if ac else '') or '(empty)'}\n"
            f"  subhead_typography:    {(ac.subhead_typography if ac else '') or '(empty)'}\n"
            f"  cta:                   {(ac.cta if ac else '') or '(empty)'}\n"
            f"  cta_typography:        {(ac.cta_typography if ac else '') or '(empty)'}\n"
            f"  benefit_lines:         {(ac.benefit_lines if ac else []) or '(empty)'}\n"
            f"  trust_signals:         {(ac.trust_signals if ac else []) or '(empty)'}\n"
            f"  emotional_tagline:     {(ac.emotional_tagline if ac else None) or '(empty)'}\n"
            f"  brand_name:            {(ac.brand_name if ac else None) or '(empty)'}\n"
            f"  legal_disclaimer:      {(ac.legal_disclaimer if ac else '') or '(empty)'}\n\n"
            f"=== visual ===\n"
            f"  visual_metaphor:          {(vis.visual_metaphor if vis else '') or '(empty - INVENT one)'}\n"
            f"  micro_details:            {(vis.micro_details if vis else []) or '(empty)'}\n"
            f"  mood:                     {(vis.mood if vis else '') or '(empty)'}\n"
            f"  color_palette:            {(vis.color_palette if vis else '') or '(empty)'}\n"
            f"  color_psychology_intent:  {(vis.color_psychology_intent if vis else '') or '(empty)'}\n"
            f"  lighting:                 {(vis.lighting if vis else '') or '(empty)'}\n"
            f"  background:               {(vis.background if vis else '') or '(empty)'}\n"
            f"  composition:              {(vis.composition if vis else '') or '(empty)'}\n"
            f"  visual_hierarchy:         {(vis.visual_hierarchy if vis else '') or '(empty)'}\n"
            f"  typography_style:         {(vis.typography_style if vis else '') or '(empty)'}\n\n"
            f"=== strategy ===\n"
            f"  target_audience:     {draft.target_audience or '(empty - INFER and fill)'}\n"
            f"  objective:           {draft.objective or 'awareness'}\n"
            f"  campaign_type:       {draft.campaign_type}\n"
            f"  copywriting_formula: {draft.copywriting_formula}\n\n"
            "===== REVIEW CHECKLIST (16 points - apply ALL) =====\n\n"
            "PHASE 0 - ROOT-CAUSE + CONCEPT:\n"
            "  1. visual_metaphor: must be SPECIFIC and visual (\"shoe in mid-air being struck by water that beads off\"). NEVER empty for ads. If empty, INVENT one based on the product's promise.\n"
            "  2. Master Sentence: the visual_metaphor + headline together must answer 'this ad makes [audience] feel [emotion] so they [action]'. If unclear, rewrite the metaphor.\n"
            "  3. micro_details: 2-5 concrete textural details ('icy condensation drops', 'embossed gold foil'). NO generic adjectives. If empty, ADD 3 specific details.\n\n"
            "PHASE 1 - STRATEGY:\n"
            "  4. target_audience: must be specific demographic + psychographic. If empty for an ad, infer from product+platform. NOT 'everyone'. Apply the persona-name test: 'Would [persona] stop for this?'\n"
            "  5. objective: must be one of {awareness, conversion, engagement, education, retention}. Verify the prompt's emphasis matches: conversion -> CTA prominent + urgency cues; awareness -> brand mark + emotional hook dominate.\n\n"
            "PHASE 2 - VISUAL PSYCHOLOGY:\n"
            "  6. color_palette: MUST follow 60-30-10 format with explicit ratios + roles ('deep navy 60% (background), champagne gold 30% (highlights), electric coral 10% (CTA only)'). The 10% accent reserved EXCLUSIVELY for CTA.\n"
            "  7. color_psychology_intent: must state WHY ('trust + professionalism', 'urgency + appetite'). NEVER empty for ads.\n"
            "  8. typography_style: format MUST be 'display: <font> / body: <font>'. MAX 2 fonts total. Reject 3+ fonts.\n"
            "  9. headline_typography / subhead_typography / cta_typography: each must specify font + weight + size + color (+ tracking for tight/wide). NOT empty for ads with that text element.\n"
            " 10. visual_hierarchy: name the pattern (Z-pattern / F-pattern / center-out) AND positions. Hero on Rule-of-Thirds intersection (NOT dead-center) for non-minimalist.\n\n"
            "PHASE 3 - COMPOSITION:\n"
            " 11. The `prompt` must reserve 35%+ clean copy-space zone, state location explicitly. Background DIRECTLY behind every quoted text string must be stated as calm/low-contrast.\n"
            " 12. Directional element rule: any model gaze / vehicle / arrow / motion line MUST point TOWARD the headline + CTA, never away (research: +25% engagement).\n\n"
            "PHASE 4 - COPYWRITING:\n"
            " 13. headline: 2-5 WORDS MAX. Pass THUMB TEST + 0.3-second test. Prefer LOSS-aversion framing where possible (+18% conversion lift).\n"
            " 14. cta: 2-3 WORDS, action verb. CONVERT generic to Call-to-Value ('Buy Now' -> 'Start Saving Today'). For conversion objective MUST be present.\n"
            " 15. benefit_lines: each 2-3 words MAX (icon-badge format). Reject sentences.\n"
            " 16. legal_disclaimer: MANDATORY for alcohol / tobacco / pharma / financial / gambling / supplements. If category is regulated and field is empty, FILL IT.\n"
            " 17. brand_emblem_description: MANDATORY for D2C / luxury / fashion / food / hospitality / event / spiritual / heritage brands. Real ads have a small ornate crest/mandala/diamond/circle-emblem above the wordmark. If empty, INVENT one matching the brand archetype (luxury -> ornate gold diamond; organic -> leaf badge; spiritual -> mandala+om; tech -> minimalist geometric mark). Empty ONLY for pure tech/SaaS where wordmark alone fits.\n"
            " 18. website_url: MANDATORY for any brand/D2C/event/service ad. If empty, GENERATE a plausible URL: `www.{brandslug}.in` for Indian brands, `.com` for global, `.org` for non-profits/spiritual. Empty ONLY for personal posts (wishes, family events).\n"
            " 19. contact_info: MANDATORY for events / restaurants / real-estate / local-services / D2C heritage brands. If empty, GENERATE plausible '+91 98765 XXXXX | <Venue/Office>, <Area>, <City> – <PIN> | @brandname.official'. Empty ONLY for personal posts.\n"
            " 20. footer_strip: MANDATORY for D2C / e-commerce / event / service ads — 3-4 short footer badges that anchor the bottom credibility close. If empty, GENERATE per genre: D2C -> ['FREE SHIPPING', 'COD AVAILABLE', 'EASY RETURNS', 'AUTHENTIC']; events -> ['FAMILY WELCOME', 'PARKING AVAILABLE', 'ALL AGES']. Empty ONLY for minimalist luxury where extra info dilutes mood.\n"
            " 21. lineup_items: MANDATORY when prompt mentions 'lineup', 'series', 'schedule', 'sessions', 'speakers', 'concerts', 'performances', 'workshops', 'sermons', 'festival days'. Each entry format: '<DATE> | <NAME or TITLE> | <TIME> | <LOCATION optional>'. If user listed names/dates, use VERBATIM. If user said 'lineup of N artists' without specifics, INVENT N plausible names from that genre with sequential weekly dates and consistent time. Generic 3-pill benefit collapse for a lineup prompt = REJECT and rewrite as proper lineup_items array.\n\n"
            "===== HARD ANTI-PATTERNS (must remove) =====\n"
            "  A. NO markdown chars (#, *, _, `, ~) inside any \"...\" quoted text in the prompt.\n"
            "  B. NO structural nouns ('headline', 'subhead', 'caption', 'tagline', 'CTA') describing TEXT inside the prompt - describe by visual size/position only.\n"
            "  C. NO vague filler ('amazing', 'great', 'best ever', 'truly', 'really') - replace with concrete imagery.\n"
            "  D. NO ethics violations: no false urgency / fake countdowns, no misleading before-after, no greenwashing without basis, no <4.5:1 contrast ratio (accessibility).\n"
            "  E. NO more than 3 primary focal points (working memory limit). Strip elements that don't serve the ONE thing.\n"
            "  F. Keep the same intent + brand + scene structure. Tighten + clarify - do NOT redesign.\n\n"
            "===== 0.3-SECOND FINAL TEST =====\n"
            "Squint at the brief. In 0.3 seconds (the actual scroll-pause), would the viewer:\n"
            "  (a) recognize the brand?\n"
            "  (b) understand the offer/promise?\n"
            "  (c) know what to do next?\n"
            "If ANY fails, simplify until all 3 pass. Remove, never add.\n\n"
            "Return the IMPROVED draft as a JSON object with EXACTLY this shape (every key required, omit nothing):\n"
            "{\n"
            '  "intent": "...",\n'
            '  "prompt": "...",\n'
            '  "negative_prompt": "...",\n'
            '  "aspect_hint": "square_hd|portrait_4_3|landscape_4_3|portrait_9_16|landscape_16_9",\n'
            '  "campaign_type": "...",\n'
            '  "subject_category": "...",\n'
            '  "platform": "...",\n'
            '  "copywriting_formula": "AIDA|PAS|BAB|simple",\n'
            '  "target_audience": "...",\n'
            '  "objective": "awareness|conversion|engagement|education|retention",\n'
            '  "ad_copy": {"headline":"...","headline_typography":"...","subhead":"...","subhead_typography":"...","cta":"...","cta_typography":"...","benefit_lines":[],"trust_signals":[],"emotional_tagline":null,"brand_name":null,"legal_disclaimer":"","brand_emblem_description":null,"website_url":null,"contact_info":null,"footer_strip":[],"lineup_items":[]},\n'
            '  "visual": {"visual_metaphor":"...","micro_details":[],"mood":"...","color_palette":"...","color_psychology_intent":"...","lighting":"...","background":"...","composition":"...","visual_hierarchy":"...","typography_style":"..."}\n'
            "}\n"
            "Output JSON only - no prose, no markdown fences."
        )

        try:
            client = _get_gemini_client()
            resp = await client.aio.models.generate_content(
                model=_CLASSIFIER_MODEL,
                contents=[{"role": "user", "parts": [{"text": review_msg}]}],
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=_CRITIQUE_MAX_TOKENS,
                    response_mime_type="application/json",
                ),
            )
            raw = (resp.text or "").strip()
            if not raw:
                finish = resp.candidates[0].finish_reason if resp.candidates else "UNKNOWN"
                logger.warning("[critique] empty Gemini response (finish=%s) -- keeping draft", finish)
                return draft
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", raw, flags=re.MULTILINE).strip()
            first, last = raw.find("{"), raw.rfind("}")
            if first != -1 and last != -1 and last > first:
                raw = raw[first:last + 1]
            data = json.loads(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning("[critique] gemini call failed: %s -- keeping draft", e)
            return draft

        # Validate the improved JSON against the same Pydantic schema. If the
        # critique broke any constraint, fall back to the draft.
        try:
            improved = SimpleEngineOutput.model_validate(data)
        except ValidationError as ve:
            logger.warning(
                "[critique] gemini output failed Pydantic validation (%d issues) -- keeping draft: %s",
                ve.error_count(), ve.errors()[:2],
            )
            return draft

        return improved


# Singleton
simple_engine = SimplePromptEngine()

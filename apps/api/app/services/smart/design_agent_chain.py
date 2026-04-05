"""
6-Agent Design Chain — production-hardened

Agents: Triage -> Brand Intel -> Creative Director -> Copy Writer -> Layout Planner -> Image Prompter
Output: DesignBrief dict that drives both generation AND canvas editor (Fabric.js layer init)

Fixes applied (from GPT / Grok / Gemini / Claude review):
- Module-level Gemini client singleton (no re-init per call)
- async-native via arun() + _acall_gemini(); sync run() wraps with asyncio
- Brand Intel enriches incomplete brand_kit via LLM instead of early-return
- Brand Intel + Creative Director run in parallel (asyncio.gather)
- _extract_json robust: regex outer-brace match → json.loads (no manual depth counter)
- Hex color validation before passing to palette engine
- Feature list type validation (must be list-of-dicts)
- Layout y-overflow detection + warning
- None-safe .upper() / .get() on all LLM-returned strings
- Per-agent max_output_tokens tuned
- Per-agent timing in brief["_agent_times"]
- Festival context passed to image prompter + copy writer
- aspect_ratio passed to layout planner (hero_pct dynamic)
- palette keys accessed via .get() with fallbacks
- _extract_json returns "_parse_error" flag instead of silent {}
- brief["_error"] check in stream pipeline triggers fallback
- prompt truncated to 1000 chars at entry point
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Hex color validator ──────────────────────────────────────────────────────
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _safe_hex(value: object, fallback: str) -> str:
    s = str(value or "").strip()
    return s if _HEX_RE.match(s) else fallback


# ── Gemini client pool (round-robin across multiple API keys) ─────────────────
# Set GEMINI_API_KEY_2 (and _3, _4 ...) in .env to double/triple the RPM quota.
# Falls back to single key if only GEMINI_API_KEY is set.
_gemini_clients: list = []
_gemini_client_idx: int = 0


def _build_client_pool() -> list:
    from google import genai

    keys: list[str] = []
    # Primary key
    k = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY", "")
    if k:
        keys.append(k)
    # Extra keys: GEMINI_API_KEY_2, GEMINI_API_KEY_3, ...
    for i in range(2, 10):
        k2 = os.getenv(f"GEMINI_API_KEY_{i}", "")
        if k2:
            keys.append(k2)
        else:
            break

    if not keys:
        raise RuntimeError("GEMINI_API_KEY not set")

    clients = [genai.Client(api_key=k) for k in keys]
    logger.info("[design_chain] Gemini client pool: %d key(s)", len(clients))
    return clients


def _get_gemini_client():
    global _gemini_clients, _gemini_client_idx
    if not _gemini_clients:
        _gemini_clients = _build_client_pool()
    # Round-robin
    client = _gemini_clients[_gemini_client_idx % len(_gemini_clients)]
    _gemini_client_idx += 1
    return client


# Model — use env var so free-tier users can switch to gemini-2.0-flash (higher RPM)
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")

# Per-agent max tokens — generous enough for Gemini to think fully
_AGENT_MAX_TOKENS = {
    "triage":           800,
    "brand_intel":      800,
    "creative_director":1500,  # bible JSON needs room
    "copy_writer":      1800,
    "image_prompter":   1200,
    "char_guard":       600,
}


# ── Empty brief (defaults when agents fail) ───────────────────────────────────
def _empty_brief() -> Dict:
    return {
        "background_prompt": "",
        "negative_prompt": "text, words, letters, watermark, blurry, low quality",
        "brand_colors": {
            "primary": "#6C63FF", "secondary": "#4FACFE",
            "accent": "#00D4FF", "bg": "#0A0A1A",
            "text_primary": "#FFFFFF", "text_secondary": "#CCCCDD",
        },
        "copy_blocks": {
            "brand_name": "", "headline": "MAKE IT HAPPEN",
            "subheadline": "The fastest way to get results",
            "body": "", "cta": "GET STARTED", "cta_url": "",
            "tagline": "",
            "features": [
                {"icon": "✓", "title": "Feature 1", "desc": "Key benefit"},
                {"icon": "⚡", "title": "Feature 2", "desc": "Key benefit"},
                {"icon": "🎯", "title": "Feature 3", "desc": "Key benefit"},
                {"icon": "🚀", "title": "Feature 4", "desc": "Key benefit"},
            ],
        },
        "ad_copy": {},
        "layout_archetype": "hero_top_features_bottom",
        "elements": [],
        "poster_design": {
            "accent_color": "#6C63FF", "bg_color": "#0A0A1A",
            "text_color_primary": "#FFFFFF", "text_color_secondary": "#CCCCDD",
            "font_style": "bold_tech", "has_feature_grid": True,
            "has_cta_button": True, "hero_occupies": "top_60",
        },
        "platform": "instagram",
        "creative_type": "ad",
        "goal": "brand_awareness",
        "triage": {},
        "brand": {},
        "creative": {},
        "scores": {},
        "_source": "agent_chain",
        "_agent_times": {},
    }


# ── JSON extractor (robust) ───────────────────────────────────────────────────
def _extract_json(text: str) -> Dict:
    """Extract first JSON object from LLM text. Returns dict with _parse_error flag on failure."""
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # Try full parse first (model returned clean JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Regex: find outermost {...} (handles surrounding prose)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            # Try to repair truncated JSON: close open strings/objects/arrays
            candidate = match.group()
            try:
                repaired = _repair_truncated_json(candidate)
                return json.loads(repaired)
            except Exception:
                pass
    logger.warning("[design_chain] _extract_json failed on: %r", text[:200])
    return {"_parse_error": True}


def _repair_truncated_json(s: str) -> str:
    """
    Best-effort repair of JSON truncated mid-stream (token limit cut-off).
    Closes any open strings, arrays, and objects in reverse nesting order.
    """
    # Remove trailing incomplete key-value (e.g. ends with `,"key":` or `,"key":"`)
    s = s.rstrip().rstrip(",").rstrip()

    # Close any open string (odd number of unescaped quotes after last complete token)
    # Simple heuristic: if the last char is not a closing delimiter, check if inside string
    in_string = False
    escape_next = False
    for ch in s:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string

    suffix = ""
    if in_string:
        suffix += '"'

    # Count open braces/brackets (depth)
    depth_obj = 0
    depth_arr = 0
    in_str2 = False
    esc2 = False
    for ch in s:
        if esc2:
            esc2 = False
            continue
        if ch == "\\" and in_str2:
            esc2 = True
            continue
        if ch == '"':
            in_str2 = not in_str2
            continue
        if in_str2:
            continue
        if ch == "{":
            depth_obj += 1
        elif ch == "}":
            depth_obj -= 1
        elif ch == "[":
            depth_arr += 1
        elif ch == "]":
            depth_arr -= 1

    suffix += "]" * max(0, depth_arr)
    suffix += "}" * max(0, depth_obj)
    return s + suffix


# ── Async Gemini caller ───────────────────────────────────────────────────────
async def _acall_gemini(
    system: str,
    user: str,
    temperature: float = 0.7,
    agent_name: str = "unknown",
    _retries: int = 3,
) -> str:
    """Call Gemini with automatic retry on rate-limit (429 / ResourceExhausted)."""
    t0 = time.time()
    from google.genai import types

    max_tokens = _AGENT_MAX_TOKENS.get(agent_name, 600)

    for attempt in range(_retries):
        try:
            client = _get_gemini_client()

            resp = await client.aio.models.generate_content(
                model=_GEMINI_MODEL,
                contents=[{"role": "user", "parts": [{"text": user}]}],
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            result = resp.text or "{}"
            elapsed_ms = int((time.time() - t0) * 1000)
            logger.info("[design_chain][%s] %dms attempt=%d", agent_name, elapsed_ms, attempt + 1)
            return result

        except RuntimeError as e:
            # GEMINI_API_KEY not set — no point retrying
            logger.warning("[design_chain][%s] config error: %s", agent_name, e)
            return "{}"
        except Exception as e:
            err_str = str(e).lower()
            err_type = type(e).__name__
            is_rate_limit = (
                "resourceexhausted" in err_type.lower()
                or "429" in err_str
                or "quota" in err_str
                or "rate" in err_str
            )
            elapsed_ms = int((time.time() - t0) * 1000)

            if is_rate_limit and attempt < _retries - 1:
                # Rotate to next key immediately — if only 1 key, add small delay
                pool_size = len(_gemini_clients) if _gemini_clients else 1
                wait = 0.5 if pool_size > 1 else 2 ** attempt
                logger.warning(
                    "[design_chain][%s] rate-limited (attempt %d/%d, pool=%d), switching key in %.1fs",
                    agent_name, attempt + 1, _retries, pool_size, wait,
                )
                await asyncio.sleep(wait)
                continue

            if "deadlineexceeded" in err_type.lower() or "timeout" in err_str:
                logger.error("[design_chain][%s] TIMEOUT after %dms: %s", agent_name, elapsed_ms, e)
            elif is_rate_limit:
                logger.error("[design_chain][%s] QUOTA EXCEEDED after %d retries: %s", agent_name, _retries, e)
            else:
                logger.warning("[design_chain][%s] call failed (%dms): %s", agent_name, elapsed_ms, e)
            return "{}"

    return "{}"


# ── Individual agents (all async) ─────────────────────────────────────────────

async def _agent_triage(prompt: str) -> Dict:
    system = (
        "You are a senior marketing strategist. Read the design request carefully and use your judgment.\n"
        "Infer the industry from context clues — 'gym' means fitness, 'cafe' means food, "
        "'app launch' means saas, etc. Think like a human creative director.\n"
        "If the user quoted specific text (e.g. 'TRANSFORM'), that is their intended headline — note it.\n"
        'Return ONLY valid JSON:\n'
        '{"creative_type":"ad|poster|social_post|banner|story|thumbnail",\n'
        '"platform":"instagram|instagram_story|linkedin|twitter|print|default",\n'
        '"goal":"product_launch|brand_awareness|sale_promotion|event|app_download|lead_gen",\n'
        '"audience":"b2b|b2c|youth|professional|general",\n'
        '"brand_hint":"brand or product name if mentioned, else empty",\n'
        '"industry":"saas|food|fashion|fitness|real_estate|healthcare|finance|education|tech|general",\n'
        '"explicit_headline":"exact text user quoted as headline, or empty",\n'
        '"explicit_cta":"exact text user quoted as CTA/button, or empty",\n'
        '"is_festival":false,"festival_name":""}'
    )
    raw = await _acall_gemini(system, "Design request: " + prompt, temperature=0.3, agent_name="triage")
    r = _extract_json(raw)
    defaults = {
        "creative_type": "poster", "platform": "instagram",
        "goal": "brand_awareness", "audience": "general",
        "brand_hint": "", "industry": "general",
        "explicit_headline": "", "explicit_cta": "",
        "is_festival": False, "festival_name": "",
    }
    for k, v in r.items():
        if v is not None and not k.startswith("_"):
            defaults[k] = v
    return defaults


async def _agent_brand_intel(
    triage: Dict,
    brand_kit: Optional[Dict],
    prompt: str,
) -> Dict:
    """Always run LLM to fill gaps; brand_kit values override LLM output."""
    system = (
        "You are a brand analyst AI. Extract or infer brand identity.\n"
        'Return ONLY valid JSON: {"brand_name":"name","primary_color":"#RRGGBB",'
        '"secondary_color":"#RRGGBB","font_style":"bold_tech|elegant_serif|expressive_display|clean_sans",'
        '"tone":"professional|playful|luxury|energetic|minimal|bold|elegant","tagline":""}'
    )
    bk = brand_kit or {}
    brand_context = ""
    if bk.get("brand_name"):
        brand_context = f"\nKnown brand: {bk['brand_name']}"
    if bk.get("primary_color"):
        brand_context += f", primary color: {bk['primary_color']}"

    context = (
        f"Request: {prompt}\nIndustry: {triage.get('industry','')}\n"
        f"Goal: {triage.get('goal','')}{brand_context}"
    )
    raw = await _acall_gemini(system, context, temperature=0.5, agent_name="brand_intel")
    r = _extract_json(raw)

    # LLM base, then brand_kit overrides (brand_kit always wins)
    result = {
        "brand_name":      r.get("brand_name", ""),
        "primary_color":   _safe_hex(r.get("primary_color"), "#6C63FF"),
        "secondary_color": _safe_hex(r.get("secondary_color"), "#4FACFE"),
        "font_style":      r.get("font_style", "bold_tech"),
        "tone":            r.get("tone", "professional"),
        "tagline":         r.get("tagline", ""),
        "logo_url":        "",
    }
    # Apply brand_kit overrides (non-empty values only)
    for k in ("brand_name", "primary_color", "secondary_color", "font_style", "tone", "tagline", "logo_url"):
        bk_val = bk.get(k)
        if bk_val:
            if k in ("primary_color", "secondary_color"):
                result[k] = _safe_hex(bk_val, result[k])
            else:
                result[k] = bk_val
    return result


async def _agent_creative_director(triage: Dict, brand: Dict, prompt: str) -> Dict:
    from app.services.smart.color_intelligence import derive_palette, suggest_harmony

    harmony = suggest_harmony(brand.get("tone", ""), triage.get("industry", ""))
    palette = derive_palette(
        primary_hex=brand.get("primary_color", "#6C63FF"),
        brand_tone=triage.get("industry", ""),
        prompt_context=prompt,
        harmony=harmony,
    )

    system = (
        "You are a senior Creative Director (Wieden+Kennedy level).\n"
        "In addition to visual direction, produce a Creative Bible — a locked creative contract\n"
        "that all downstream agents must obey.\n"
        'Return ONLY valid JSON: {"theme":"word","mood":"word",'
        '"visual_style":"photorealistic|illustration|3d_render|graphic_flat|editorial",'
        '"layout_archetype":"hero_top_features_bottom|split_left_right|full_bleed|minimal_centered|grid",'
        '"hero_occupies":"top_60|top_50|full_bleed|center_50",'
        '"atmosphere":"brief description","avoid":["elements"],'
        '"creative_bible":{'
        '"emotional_territory":"ONE precise phrase capturing the exact feeling this design must evoke",'
        '"visual_metaphors":["concrete noun 1","concrete noun 2","concrete noun 3"],'
        '"forbidden_elements":["no generic element","no cliché element","no off-brand element"],'
        '"dominant_color_story":"one sentence describing how colors work together in natural language",'
        '"composition_archetype":"describe the diagonal/tension/balance as a sentence"}}'
    )
    context = (
        f"Prompt: {prompt}\nBrand: {brand.get('brand_name','')} Tone: {brand.get('tone','')}\n"
        f"Industry: {triage.get('industry','')} Platform: {triage.get('platform','')}\n"
        f"Primary color: {palette.get('primary','#6C63FF')}"
    )
    raw = await _acall_gemini(system, context, temperature=0.8, agent_name="creative_director")
    r = _extract_json(raw)

    # Extract and validate creative_bible
    raw_bible = r.get("creative_bible") or {}
    creative_bible = {
        "emotional_territory": str(raw_bible.get("emotional_territory") or ""),
        "visual_metaphors":    raw_bible.get("visual_metaphors") if isinstance(raw_bible.get("visual_metaphors"), list) else [],
        "forbidden_elements":  raw_bible.get("forbidden_elements") if isinstance(raw_bible.get("forbidden_elements"), list) else [],
        "dominant_color_story": str(raw_bible.get("dominant_color_story") or ""),
        "composition_archetype": str(raw_bible.get("composition_archetype") or ""),
    }

    return {
        "theme":            r.get("theme", "bold"),
        "mood":             r.get("mood", "energetic"),
        "visual_style":     r.get("visual_style", "photorealistic"),
        "layout_archetype": r.get("layout_archetype", "hero_top_features_bottom"),
        "hero_occupies":    r.get("hero_occupies", "top_60"),
        "atmosphere":       r.get("atmosphere", ""),
        "avoid":            r.get("avoid") if isinstance(r.get("avoid"), list) else [],
        "palette":          palette,
        "creative_bible":   creative_bible,
    }


async def _agent_copy_writer(
    triage: Dict,
    brand: Dict,
    creative: Dict,
    prompt: str,
) -> Dict:
    platform = triage.get("platform", "instagram")
    hl_max = {"instagram": 30, "instagram_story": 20, "linkedin": 50, "default": 40}.get(platform, 40)

    # Tell the AI what the user explicitly typed — it should use these verbatim
    explicit_headline = triage.get("explicit_headline", "").strip()
    explicit_cta      = triage.get("explicit_cta", "").strip()
    explicit_hint = ""
    if explicit_headline:
        explicit_hint += f'\nUSER EXPLICITLY WANTS headline: "{explicit_headline}" — use this EXACTLY, do not change it.'
    if explicit_cta:
        explicit_hint += f'\nUSER EXPLICITLY WANTS cta: "{explicit_cta}" — use this EXACTLY.'

    festival_hint = ""
    if triage.get("is_festival") and triage.get("festival_name"):
        festival_hint = f"\nFestival context: {triage['festival_name']} — include cultural warmth."

    # Creative Bible injection — copy must align with the locked emotional territory
    bible = creative.get("creative_bible") or {}
    bible_hint = ""
    if bible.get("emotional_territory"):
        bible_hint += f'\nCreative Bible — emotional territory: "{bible["emotional_territory"]}"'
        bible_hint += " — every word of copy must evoke this feeling."
    if bible.get("forbidden_elements"):
        bible_hint += f'\nForbidden: avoid themes of: {", ".join(bible["forbidden_elements"][:3])}'

    system = (
        f"You are a world-class Ad Copywriter (Ogilvy / Leo Burnett level).\n"
        f"Platform: {platform}. Tone: {brand.get('tone','bold')}. "
        f"Goal: {triage.get('goal','brand_awareness')}. Industry: {triage.get('industry','general')}.\n"
        f"Think deeply about what this business needs. Write copy that converts.\n"
        f"HEADLINE max {hl_max} chars ALL CAPS.{festival_hint}{explicit_hint}{bible_hint}\n"
        f"For features: generate 4 REAL, SPECIFIC benefits relevant to this industry — not generic placeholders.\n"
        'Return ONLY valid JSON: {"brand_name":"","headline":"ALL CAPS",'
        '"subheadline":"sentence case, compelling","body":"1-2 punchy sentences",'
        '"cta":"2-4 WORDS ACTION","cta_url":"","tagline":"",'
        '"features":[{"icon":"emoji","title":"specific benefit","desc":"one concrete line"},'
        '{"icon":"emoji","title":"specific benefit","desc":"one concrete line"},'
        '{"icon":"emoji","title":"specific benefit","desc":"one concrete line"},'
        '{"icon":"emoji","title":"specific benefit","desc":"one concrete line"}]}'
    )
    context = (
        f"User request: {prompt}\n"
        f"Theme: {creative.get('theme','')}  Mood: {creative.get('mood','')}\n"
        f"Audience: {triage.get('audience','general')}"
    )

    raw = await _acall_gemini(system, context, temperature=0.85, agent_name="copy_writer")
    r = _extract_json(raw)

    # If main call failed entirely (parse error or missing headline), retry full call once
    if r.get("_parse_error") or not str(r.get("headline") or "").strip():
        logger.warning("[copy_writer] main call missing headline, retrying full call")
        raw2 = await _acall_gemini(system, context, temperature=0.7, agent_name="copy_writer")
        r2 = _extract_json(raw2)
        if not r2.get("_parse_error") and str(r2.get("headline") or "").strip():
            r = r2  # full retry succeeded

    # Validate features — if AI returned good ones use them, else retry with stricter prompt
    raw_features = r.get("features")
    if not isinstance(raw_features, list):
        raw_features = []
    features = [f for f in raw_features if isinstance(f, dict) and f.get("title")
                and "Feature" not in f.get("title","") and "Key benefit" not in f.get("desc","")][:4]

    # If AI returned placeholder garbage, ask again with zero temperature
    if len(features) < 2:
        logger.warning("[copy_writer] AI returned placeholder features, retrying")
        retry_system = (
            f"Write 4 specific feature benefits for a {triage.get('industry','general')} business ad.\n"
            f"Context: {prompt}\n"
            "Each feature must be concrete and industry-relevant. NO generic text like 'Key benefit'.\n"
            'Return ONLY: [{"icon":"emoji","title":"specific title","desc":"specific one-liner"}] — 4 items.'
        )
        retry_raw = await _acall_gemini(retry_system, f"Industry: {triage.get('industry')} Request: {prompt}",
                                        temperature=0.0, agent_name="copy_writer")
        retry_r = _extract_json(retry_raw)
        if isinstance(retry_r, list):
            features = [f for f in retry_r if isinstance(f, dict) and f.get("title")][:4]
        elif isinstance(retry_r.get("features"), list):
            features = retry_r["features"][:4]

    # Last resort: AI generates 4 sensible defaults from scratch
    while len(features) < 4:
        features.append({"icon": "⭐", "title": f"Feature {len(features)+1}", "desc": "Coming soon"})

    # Explicit user text ALWAYS wins — even if Gemini failed entirely
    # Check this FIRST before falling back to AI output or "MAKE IT HAPPEN"
    if explicit_headline:
        headline = explicit_headline.upper()
    else:
        headline = str(r.get("headline") or "").strip().upper() or "MAKE IT HAPPEN"
        if len(headline) > hl_max:
            headline = headline[:hl_max].rsplit(" ", 1)[0]
    cta = str(r.get("cta") or "GET STARTED").upper()
    if explicit_cta:
        cta = explicit_cta.upper()

    return {
        "brand_name":  str(r.get("brand_name") or brand.get("brand_name", "") or ""),
        "headline":    headline,
        "subheadline": str(r.get("subheadline") or "The fastest way to get results"),
        "body":        str(r.get("body") or ""),
        "cta":         cta,
        "cta_url":     str(r.get("cta_url") or ""),
        "tagline":     str(r.get("tagline") or brand.get("tagline", "") or ""),
        "features":    features,
    }


_PLATFORM_CHAR_LIMITS = {
    "instagram":       {"headline": 40, "subheadline": 90, "cta": 20, "body": 160},
    "instagram_story": {"headline": 30, "subheadline": 70, "cta": 18, "body": 120},
    "linkedin":        {"headline": 60, "subheadline": 110, "cta": 25, "body": 220},
    "twitter":         {"headline": 35, "subheadline": 80, "cta": 20, "body": 140},
    "print":           {"headline": 55, "subheadline": 110, "cta": 28, "body": 260},
    "default":         {"headline": 45, "subheadline": 100, "cta": 22, "body": 180},
}


async def _enforce_char_limits(copy_blocks: Dict, platform: str) -> Dict:
    """
    Secondary micro-agent (Phase 5 / Prompt Agent PDF dual-agent pattern):
    Checks each copy field against platform character limits.
    Only calls Gemini when a field is actually over limit.
    """
    limits = _PLATFORM_CHAR_LIMITS.get(platform, _PLATFORM_CHAR_LIMITS["default"])
    fields_over = {}
    for field in ("headline", "subheadline", "cta", "body"):
        val = str(copy_blocks.get(field) or "")
        limit = limits.get(field, 200)
        if len(val) > limit:
            fields_over[field] = (val, limit)

    if not fields_over:
        return copy_blocks  # nothing to fix

    # Build a single micro-call to trim all over-limit fields
    over_desc = "\n".join(
        f'  {f}: "{v[:80]}..." ({len(v)} chars, limit {lim})'
        for f, (v, lim) in fields_over.items()
    )
    system = (
        "You are a copy editor. Rewrite only the specified text fields to fit within character limits.\n"
        "Keep the same language, tone, and meaning — just trim. Return ONLY valid JSON with the same field names."
    )
    user = (
        f"Platform: {platform}. Rewrite these fields to fit their character limits:\n{over_desc}\n\n"
        f"Return JSON with keys: {list(fields_over.keys())}"
    )
    raw = await _acall_gemini(system, user, temperature=0.2, agent_name="copy_writer")
    r = _extract_json(raw)

    result = dict(copy_blocks)
    for field, (original, limit) in fields_over.items():
        trimmed = str(r.get(field) or "").strip()
        if trimmed and len(trimmed) <= limit + 5:  # +5 tolerance
            result[field] = trimmed
            logger.info("[char_guard] %s: %d→%d chars", field, len(original), len(trimmed))
        else:
            # Hard truncate as last resort
            result[field] = original[:limit].rsplit(" ", 1)[0]
            logger.warning("[char_guard] %s hard-truncated to %d chars", field, limit)

    return result


def _agent_layout_planner(
    creative: Dict,
    copy: Dict,
    aspect_ratio: float = 0.667,   # width/height — default 1024/1536
) -> List[Dict]:
    """Pure Python — no LLM call. Returns Fabric.js element list."""
    hero_map = {"top_60": 0.60, "top_50": 0.50, "full_bleed": 0.80, "center_50": 0.50}
    hero_pct = hero_map.get(creative.get("hero_occupies", "top_60"), 0.60)

    # For landscape (16:9), reduce hero to leave room for text
    if aspect_ratio >= 1.5:
        hero_pct = min(hero_pct, 0.40)

    palette = creative.get("palette", {})
    pri = _safe_hex(palette.get("primary"), "#6C63FF")
    bg  = _safe_hex(palette.get("bg"), "#0A0A1A")
    txt = _safe_hex(palette.get("text_primary"), "#FFFFFF")
    sec = _safe_hex(palette.get("text_secondary"), "#CCCCDD")

    elements: List[Dict] = []
    y = 0.0

    brand_name = str(copy.get("brand_name") or "")
    if brand_name:
        elements.append({"id": "brand_bar", "type": "shape",
            "bounds": {"x": 0, "y": 0, "w": 1.0, "h": 0.07},
            "style": {"fill": pri, "opacity": 1.0}, "content": "", "locked": False})
        elements.append({"id": "brand_name", "type": "text",
            "bounds": {"x": 0.05, "y": 0.01, "w": 0.90, "h": 0.05},
            "style": {"font": "bebas_neue", "size_role": "brand", "color": txt,
                      "weight": "bold", "align": "center"},
            "content": brand_name.upper(), "locked": False})
        y = 0.07

    elements.append({"id": "hero_bg", "type": "image",
        "bounds": {"x": 0, "y": y, "w": 1.0, "h": hero_pct},
        "style": {"opacity": 1.0}, "content": "__hero_url__", "locked": True})
    y += hero_pct

    text_h = 0.22
    elements.append({"id": "text_panel", "type": "shape",
        "bounds": {"x": 0, "y": y, "w": 1.0, "h": text_h},
        "style": {"fill": bg, "opacity": 1.0}, "content": "", "locked": True})
    elements.append({"id": "headline", "type": "text",
        "bounds": {"x": 0.05, "y": y + 0.02, "w": 0.90, "h": 0.10},
        "style": {"font": "bebas_neue", "size_role": "headline", "color": txt,
                  "weight": "bold", "align": "center"},
        "content": str(copy.get("headline") or ""), "locked": False})
    elements.append({"id": "subheadline", "type": "text",
        "bounds": {"x": 0.05, "y": y + 0.12, "w": 0.90, "h": 0.06},
        "style": {"font": "montserrat_bold", "size_role": "subheadline", "color": sec,
                  "weight": "normal", "align": "center"},
        "content": str(copy.get("subheadline") or ""), "locked": False})
    y += text_h

    features = copy.get("features") or []
    if features:
        elements.append({"id": "features_grid", "type": "group",
            "bounds": {"x": 0, "y": y, "w": 1.0, "h": 0.28},
            "style": {"fill": bg}, "content": features, "locked": False})
        y += 0.28

    elements.append({"id": "cta_button", "type": "shape",
        "bounds": {"x": 0.05, "y": y + 0.02, "w": 0.90, "h": 0.08},
        "style": {"fill": pri, "radius": 40, "opacity": 1.0}, "content": "", "locked": False})
    elements.append({"id": "cta_text", "type": "text",
        "bounds": {"x": 0.05, "y": y + 0.02, "w": 0.90, "h": 0.08},
        "style": {"font": "bebas_neue", "size_role": "cta", "color": txt,
                  "weight": "bold", "align": "center"},
        "content": str(copy.get("cta") or ""), "locked": False})
    y += 0.10

    tagline = str(copy.get("tagline") or "")
    if tagline:
        elements.append({"id": "tagline", "type": "text",
            "bounds": {"x": 0.05, "y": y + 0.01, "w": 0.90, "h": 0.04},
            "style": {"font": "montserrat_bold", "size_role": "tagline", "color": sec, "align": "center"},
            "content": tagline, "locked": False})
        y += 0.05

    # Warn if layout overflows canvas
    if y > 1.0:
        logger.warning("[layout_planner] total y=%.2f exceeds canvas bounds — clipping may occur", y)

    return elements


async def _agent_image_prompter(
    triage: Dict,
    creative: Dict,
    copy: Dict,
    prompt_dna: Optional[Dict] = None,
) -> Dict:
    festival_hint = ""
    if triage.get("is_festival") and triage.get("festival_name"):
        festival_hint = f"\nFestival: {triage['festival_name']} — use authentic cultural scene."

    hero_pct = {"top_60": 0.60, "top_50": 0.50}.get(creative.get("hero_occupies", "top_60"), 0.60)
    dark_zone_pct = int((1.0 - hero_pct) * 100)

    # Prompt DNA — inject winning style memory when run_count >= 5 (Reflexion framework)
    dna_hint = ""
    if prompt_dna and isinstance(prompt_dna, dict):
        run_count = prompt_dna.get("run_count", 0)
        winning = prompt_dna.get("winning_keywords") or []
        failing = prompt_dna.get("failing_patterns") or []
        if run_count >= 5 and winning:
            dna_hint += f"\nStyle memory (from {run_count} past generations you liked): {', '.join(winning[:8])}"
        if failing:
            dna_hint += f"\nAvoid (patterns that failed before): {', '.join(failing[:4])}"

    # Creative Bible — inject visual metaphors and forbidden elements into scene prompt
    bible = creative.get("creative_bible") or {}
    bible_hint = ""
    if bible.get("visual_metaphors"):
        metaphors = [m for m in bible["visual_metaphors"] if m][:3]
        if metaphors:
            bible_hint += f"\nVisual metaphors to weave in: {', '.join(metaphors)}"
    if bible.get("dominant_color_story"):
        bible_hint += f"\nColor story: {bible['dominant_color_story']}"
    if bible.get("composition_archetype"):
        bible_hint += f"\nComposition: {bible['composition_archetype']}"

    # Forbidden elements → negative prompt additions
    forbidden_additions = ""
    if bible.get("forbidden_elements"):
        forbidden_additions = ", ".join(bible["forbidden_elements"][:3])

    system = (
        "You are an Ideogram V3 / Flux Pro background scene generator for poster ads.\n"
        "CRITICAL: Generate ONLY the hero background — NO TEXT in the image.\n"
        f"Bottom {dark_zone_pct}% must be naturally darker (text will overlay here).{festival_hint}{bible_hint}{dna_hint}\n"
        "Scene must be REALISTIC and RELEVANT:\n"
        "- SaaS/Tech: laptop/phone with dashboard UI, soft bokeh, modern desk\n"
        "- Festival: cultural scene, atmospheric bokeh lights, vibrant colors\n"
        "- Fashion: editorial model, dramatic lighting, clean background\n"
        "- Food: hero product shot, warm lighting, shallow DOF\n"
        "- Fitness: athlete in action, dynamic, cinematic\n"
        'Return ONLY valid JSON: {"prompt":"scene description NO TEXT max 120 words",'
        '"negative_prompt":"text, words, letters, watermark, UI overlays, typography, captions",'
        '"model_preference":"ideogram_quality"}'
    )
    context = (
        f"Industry: {triage.get('industry','general')} Brand: {str(copy.get('brand_name',''))}\n"
        f"Mood: {creative.get('mood','energetic')} Style: {creative.get('visual_style','photorealistic')}\n"
        f"Atmosphere: {creative.get('atmosphere','')}\n"
        f"Accent: {creative.get('palette',{}).get('primary','#6C63FF')}\n"
        f"Avoid: {', '.join((creative.get('avoid') or []) + ([forbidden_additions] if forbidden_additions else []))}"
    )
    raw = await _acall_gemini(system, context, temperature=0.75, agent_name="image_prompter")
    r = _extract_json(raw)

    # Fallback: let AI generate one more time with the full original prompt as hint
    bg_prompt = str(r.get("prompt") or "").strip()
    if not bg_prompt or len(bg_prompt) < 20:
        logger.warning("[image_prompter] empty/short prompt, regenerating with original context")
        industry  = triage.get("industry", "general")
        mood      = creative.get("mood", "professional")
        atmosphere = creative.get("atmosphere", "")
        # Give AI the original request and let it think — no hardcoded scenes
        fallback_system = (
            "You are a cinematographer. Based on the ad request below, describe the ideal "
            "background hero image (NO text in image). Be specific about setting, lighting, "
            "mood. Max 80 words. Return plain text only."
        )
        fallback_user = (
            f"Ad request: {context}\n"
            f"Industry: {industry}, Mood: {mood}, Atmosphere: {atmosphere}\n"
            "Describe the background scene (no text, no UI overlays)."
        )
        bg_prompt = await _acall_gemini(fallback_system, fallback_user,
                                        temperature=0.5, agent_name="image_prompter")
        bg_prompt = bg_prompt.strip().strip('"').strip("'")
        # Discard JSON failure responses like "{}", "null", empty
        if bg_prompt in ("{}", "{", "}", "null", "none", "") or len(bg_prompt) < 15:
            bg_prompt = ""

    # Hard negative — always block text in background image regardless of model
    _HARD_NEGATIVE = (
        "text, words, letters, numbers, typography, captions, labels, watermark, "
        "logo text, brand name, headline, subtitle, written words, fonts, script, "
        "calligraphy, signage, UI overlay, HUD, interface elements, blurry, low quality"
    )
    base_negative = _HARD_NEGATIVE
    if forbidden_additions:
        base_negative = f"{base_negative}, {forbidden_additions}"

    industry = triage.get("industry", "general")
    mood = creative.get("mood", "energetic")
    style = creative.get("visual_style", "photorealistic")
    _smart_fallback = (
        f"cinematic {industry} scene, {mood} atmosphere, {style} style, "
        f"dramatic lighting, deep shadows in bottom third, no text, clean background"
    )

    return {
        "background_prompt": bg_prompt or _smart_fallback,
        "negative_prompt":   base_negative,
        "model_preference":  str(r.get("model_preference") or "ideogram_quality"),
    }


# ── Chain orchestrator ────────────────────────────────────────────────────────

class DesignAgentChain:
    """
    Stateless by design — arun() must never write to self.
    All state lives in the brief dict returned per call.
    """

    async def arun(
        self,
        prompt: str,
        brand_kit: Optional[Dict] = None,
        width: int = 1024,
        height: int = 1536,
        prompt_dna: Optional[Dict] = None,
    ) -> Dict:
        brief = _empty_brief()
        agent_times: Dict[str, float] = {}
        t0 = time.time()

        # Truncate overly long prompts before injecting into all agent system prompts
        safe_prompt = prompt.strip()[:1000]

        try:
            logger.info("[design_chain] start — prompt=%r width=%d height=%d", safe_prompt[:80], width, height)
            aspect_ratio = width / max(height, 1)

            # ── Stage 1: Triage (serial — everything depends on it) ──────────
            t = time.time()
            triage = await _agent_triage(safe_prompt)
            agent_times["triage"] = round(time.time() - t, 2)

            # ── Stage 2: Brand Intel first, then Creative Director with real brand ─
            # Sequential (not parallel) — saves 1 Gemini call vs old double-CD pattern,
            # and Creative Director gets accurate brand colors/tone from the start.
            t = time.time()
            brand = await _agent_brand_intel(triage, brand_kit, safe_prompt)
            agent_times["brand_intel"] = round(time.time() - t, 2)

            t = time.time()
            creative = await _agent_creative_director(triage, brand, safe_prompt)
            agent_times["creative_director"] = round(time.time() - t, 2)

            palette = creative.get("palette", {})

            # Update brief with palette and design
            brief["brand_colors"].update({
                "primary":        _safe_hex(palette.get("primary"), "#6C63FF"),
                "secondary":      _safe_hex(palette.get("secondary"), "#4FACFE"),
                "accent":         _safe_hex(palette.get("accent"), "#00D4FF"),
                "bg":             _safe_hex(palette.get("bg"), "#0A0A1A"),
                "text_primary":   _safe_hex(palette.get("text_primary"), "#FFFFFF"),
                "text_secondary": _safe_hex(palette.get("text_secondary"), "#CCCCDD"),
            })
            brief["layout_archetype"] = creative.get("layout_archetype", "hero_top_features_bottom")
            brief["poster_design"].update({
                "accent_color":         _safe_hex(palette.get("primary"), "#6C63FF"),
                "bg_color":             _safe_hex(palette.get("bg"), "#0A0A1A"),
                "text_color_primary":   _safe_hex(palette.get("text_primary"), "#FFFFFF"),
                "text_color_secondary": _safe_hex(palette.get("text_secondary"), "#CCCCDD"),
                "font_style":           brand.get("font_style", "bold_tech"),
                "hero_occupies":        creative.get("hero_occupies", "top_60"),
            })

            # ── Stage 3: Copy Writer + Image Prompter (PARALLEL) ────────────
            # Extract bucket-specific DNA (active when run_count >= 5)
            bucket_key = triage.get("industry", "general")
            bucket_dna: Dict = {}
            if prompt_dna and isinstance(prompt_dna, dict):
                bucket_dna = prompt_dna.get(bucket_key, prompt_dna.get("typography", {})) or {}

            t = time.time()
            copy, img = await asyncio.gather(
                _agent_copy_writer(triage, brand, creative, safe_prompt),
                _agent_image_prompter(triage, creative, {"brand_name": brand.get("brand_name", "")},
                                      prompt_dna=bucket_dna),
            )
            agent_times["copy_image_parallel"] = round(time.time() - t, 2)

            # ── Stage 3b: Character limit guard (fires only when over limit) ─
            t = time.time()
            copy = await _enforce_char_limits(copy, triage.get("platform", "instagram"))
            agent_times["char_guard"] = round(time.time() - t, 3)

            # ── Stage 4: Layout Planner (pure Python, instant) ───────────────
            t = time.time()
            elements = _agent_layout_planner(creative, copy, aspect_ratio=aspect_ratio)
            agent_times["layout_planner"] = round(time.time() - t, 3)

            # ── Assemble final brief ─────────────────────────────────────────
            brief["triage"]         = triage
            brief["brand"]          = brand
            brief["creative"]       = creative
            brief["creative_bible"] = creative.get("creative_bible", {})
            brief["copy_blocks"]    = copy
            brief["ad_copy"]   = {
                "brand_name":  copy["brand_name"],
                "headline":    copy["headline"],
                "subheadline": copy["subheadline"],
                "body":        copy["body"],
                "cta":         copy["cta"],
                "cta_url":     copy["cta_url"],
                "tagline":     copy["tagline"],
                "features":    copy["features"],
                "logo_url":    brand.get("logo_url", ""),  # from brand kit
            }
            brief["elements"] = elements

            brief["background_prompt"] = img["background_prompt"]
            brief["negative_prompt"]   = img["negative_prompt"]
            brief["_model_preference"] = img["model_preference"]

            # gemini_prompt_engine compatibility
            brief["visual_concept"] = img["background_prompt"]
            brief["mood"]           = creative.get("mood", "")
            brief["lighting"]       = "cinematic dramatic lighting"
            brief["camera"]         = "professional photography"

            # Platform / routing
            brief["platform"]      = triage.get("platform", "instagram")
            brief["creative_type"] = triage.get("creative_type", "ad")
            brief["goal"]          = triage.get("goal", "brand_awareness")

            brief["_elapsed"]      = round(time.time() - t0, 2)
            brief["_agent_times"]  = agent_times
            logger.info("[design_chain] done %.2fs headline=%r", brief["_elapsed"], copy["headline"])

        except Exception as e:
            logger.exception("[design_chain] chain failed: %s", e)
            brief["_error"] = str(e)

        return brief

    def run(
        self,
        prompt: str,
        brand_kit: Optional[Dict] = None,
        width: int = 1024,
        height: int = 1536,
    ) -> Dict:
        """Sync wrapper — use arun() directly when inside async context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — caller should use asyncio.to_thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(asyncio.run, self.arun(prompt, brand_kit, width, height))
                    return future.result()
            else:
                return loop.run_until_complete(self.arun(prompt, brand_kit, width, height))
        except Exception as e:
            logger.exception("[design_chain] run() wrapper failed: %s", e)
            brief = _empty_brief()
            brief["_error"] = str(e)
            return brief


design_agent_chain = DesignAgentChain()

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
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Per-agent max tokens — generous enough for Gemini to think fully
_AGENT_MAX_TOKENS = {
    "triage":           1000,
    "brand_intel":      1200,
    "creative_director":2500,  # KB + bible JSON needs room
    "copy_writer":      2500,
    "image_prompter":   2500,  # cd_integration schema is large
    "layout_planner":   1800,
    "char_guard":       600,
}

# ── Image Prompt Engineer Knowledge Base ─────────────────────────────────────
# Injected into _agent_image_prompter so Gemini has per-model prompt strategies.
# Distilled from full model-profiles.md — keeps token cost low but covers all models.
_IMAGE_PROMPT_ENGINEER_KB = """
## MODEL SELECTION
- flux_schnell   → drafts, simple scenes. Under 80 words, ONE lead subject, skip complex lighting. Steps=4, guidance=3.5
- flux_dev       → quality/speed balance, portraits, fashion, landscapes. 2-part prose: scene + style. Steps=24, guidance=3.5
- flux_pro       → premium commercial, luxury products, real humans, editorial. 3-part prose below. Steps=30, guidance=3.5
- flux_max       → print/editorial, max fidelity, exhaustive detail. Full prose paragraphs. Steps=35, guidance=3.5
- hunyuan_image  → East Asian aesthetic, soft fashion, beauty. Add "professional studio photography, Western editorial style" to counter default Eastern lean. Steps=25, guidance=5.0
- ideogram_quality → ONLY for bold graphic/abstract scenes or when text must appear in the image. Put text in quotes in prompt. Steps=auto
- recraft_v4     → design assets, illustration, icons. Use DESIGN language not photography language. Specify hex colors.

## PER-MODEL PROMPT TEMPLATES

### flux_schnell
[Subject], [key visual detail], [style tag], [one mood adjective], [one lighting cue]
Example: "Fashion model, gold sequin dress, photorealistic, confident, studio backlight"

### flux_dev
[Detailed subject + context]. [Setting and atmosphere]. [Style reference, lighting, color mood].
Example: "A luxury skincare bottle resting on black marble. Soft studio bokeh, water droplets on surface. Editorial product photography, cool-white lighting from upper right, Vogue aesthetic."

### flux_pro (3-PART STRUCTURE — always use this for premium output)
Part 1 — Scene: What's in frame, arrangement, subject position
Part 2 — Technical: Camera body (Hasselblad X2D / Sony A7R V), lens (85mm f/1.4), lighting (key light 45° upper left, fill 1:3 ratio, hair light)
Part 3 — Style: Color grading (Kodak Portra 400 / Fujifilm sim), aesthetic reference, finish
Example: "High-fashion model in ivory silk gown, mid-stride on rain-slicked runway, dramatic side shadows below waist. Shot on Hasselblad X2D, 85mm f/1.4, key light from upper left, deep shadow fill, hair light from behind. Vogue Italia color grading, desaturated blues, warm skin tones, editorial magazine quality."

### flux_max
Full prose paragraph with exhaustive detail: fabric texture, surface grain, ambient light physics, foreground/background layers, camera settings, post-processing intent.

### hunyuan_image
[Subject], professional studio photography, [explicit lighting], natural skin tone, Western editorial style, [environment], [color grading], high resolution

### ideogram_quality
[Simple background description]. Text reading "[EXACT TEXT]" in [font style] at [position], [text color]. [Design style: minimalist/bold/elegant].

## UNIVERSAL RULES (apply to ALL models)
1. SUBJECT FIRST — lead with the primary visual subject, never the mood
   ✅ "A luxury watch resting on dark slate, single spotlight from above"
   ❌ "A dramatic luxurious scene featuring a watch"
2. SPECIFICITY > ADJECTIVES
   ✅ "worn leather jacket, brass buttons, rain-soaked collar"  ❌ "detailed jacket"
3. LIGHTING AS LANGUAGE — source, direction, temperature
   ✅ "rim light from left, warm tungsten key at 45°, deep shadow fill"  ❌ "dramatic lighting"
4. STYLE ANCHOR with specificity
   ✅ "cinematography of Roger Deakins, anamorphic lens"  ❌ "cinematic style"
5. BOTTOM DARK — critical for text overlay
   Engineer lower 50% to be naturally dark: deep floor shadow / dark surface / vignette / fade to black

## CD OUTPUT → IMAGE PROMPT TRANSLATION
emotional_territory  → mood tone, color temperature, contrast level
visual_metaphors     → compositional treatment, background elements (NOT scene replacement)
dominant_color_story → "dominant palette: X, accent: Y, shadows: Z"
composition_archetype → camera angle, framing, visual weight
RULE: Subject from user brief stays in frame. Never replace with abstract landscape.
RULE: Headline/copy text NEVER goes into image prompt.

## NEGATIVE PROMPTS — precision only, no generic negatives
Always: "text, words, letters, signs, watermark, typography, UI overlay, captions"
flux models add: "blurry, overexposed, plastic skin, bad anatomy, deformed"
ideogram add: "photorealistic, lens blur, noise, photography"
hunyuan add: "harsh lighting, overexposed skin, cartoon, anime"
"""


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
    Strategy:
    1. Strip back to last COMPLETE key-value pair (remove dangling `,"key":` or `,"key":"partial`)
    2. Close any open strings
    3. Close any open arrays/objects
    """
    s = s.rstrip()

    # Strip trailing incomplete key-value pairs:
    # Pattern: find last comma, check if the portion after it is a complete value
    # If not complete, strip back to that comma
    for _ in range(5):  # max 5 stripping passes
        stripped = s.rstrip().rstrip(",").rstrip()
        last_comma = stripped.rfind(",")
        if last_comma < 1:
            break
        after = stripped[last_comma + 1:].strip()
        # Complete value: ends with }, ], ", digit/bool/null close
        is_complete = (
            after.endswith("}") or after.endswith("]") or
            (after.startswith('"') and after.endswith('"') and len(after) >= 2 and not after.endswith('\\"')) or
            after in ("true", "false", "null") or
            (after and after[-1].isdigit())
        )
        if not is_complete:
            s = stripped[:last_comma]  # strip the incomplete pair
        else:
            s = stripped
            break
    else:
        s = s.rstrip().rstrip(",").rstrip()

    # Close any open string
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


# ── Platform format knowledge — dimensions, ratios, font recommendations ──────
_PLATFORM_FORMATS_KB = """
PLATFORM → DIMENSIONS → ASPECT RATIO (choose the best match from user's request):
instagram_portrait  → 1080×1350  → 4:5   (max real estate, recommended for ads/posters)
instagram_square    → 1080×1080  → 1:1   (universal, safe for all feeds)
instagram_story     → 1080×1920  → 9:16  (full screen, keep content in center 1080×1420 safe zone)
facebook_landscape  → 1200×628   → 1.91:1 (classic ad)
twitter             → 1200×675   → 16:9  (in-stream card)
linkedin            → 1200×627   → 1.91:1 (professional)
youtube_thumbnail   → 1280×720   → 16:9  (min 60px font, test at 120×90px)
pinterest           → 1000×1500  → 2:3   (standard pin)
tiktok_story        → 1080×1920  → 9:16  (full screen)
print_a4            → 2480×3508  → A4    (300dpi)
print_flyer         → 2550×3300  → letter (300dpi)
banner_leaderboard  → 728×90     → wide  (desktop header)
banner_rectangle    → 300×250    → box   (sidebar)
banner_half_page    → 300×600    → tall  (high-impact sidebar)

INFERENCE RULES:
- "poster", "ad", "sale", "promo", "fashion", "product" → instagram_portrait (4:5) DEFAULT
- "story", "reel", "TikTok", "vertical video" → instagram_story (9:16)
- "square", "feed", "social" (no size hint) → instagram_square (1:1)
- "thumbnail", "YouTube" → youtube_thumbnail (16:9)
- "LinkedIn", "B2B", "professional" → linkedin (1.91:1)
- "Twitter", "tweet" → twitter (16:9)
- "print", "flyer", "event", "A4" → print_flyer
- "banner", "leaderboard" → banner_leaderboard
- "Pinterest", "pin" → pinterest (2:3)

TYPOGRAPHY — web-safe Google Fonts for bold headlines (prefer these):
Display/Impact: Bebas Neue, Anton, Oswald (condensed punchy), Archivo Black
Editorial/Premium: Playfair Display, DM Serif Display, Fraunces
Modern/Clean: Montserrat, Raleway, Space Grotesk
Rule: Max 2 typefaces, max 3 weights. Never Inter/Roboto/Arial for headlines.
"""

# ── Platform → (width, height) lookup used after triage ──────────────────────
_PLATFORM_DIMS: Dict[str, tuple] = {
    "instagram_portrait":  (1080, 1350),
    "instagram_square":    (1080, 1080),
    "instagram_story":     (1080, 1920),
    "instagram":           (1080, 1350),  # default to portrait
    "facebook_landscape":  (1200, 628),
    "twitter":             (1200, 675),
    "linkedin":            (1200, 627),
    "youtube_thumbnail":   (1280, 720),
    "pinterest":           (1000, 1500),
    "tiktok_story":        (1080, 1920),
    "print_a4":            (2480, 3508),
    "print_flyer":         (2550, 3300),
    "banner_leaderboard":  (728, 90),
    "banner_rectangle":    (300, 250),
    "banner_half_page":    (300, 600),
    "default":             (1080, 1350),
}


# ── Individual agents (all async) ─────────────────────────────────────────────

async def _agent_triage(prompt: str) -> Dict:
    system = (
        "You are a senior marketing strategist AND platform expert.\n"
        "Read the design request carefully and use your judgment.\n"
        "Infer industry from context: 'gym'→fitness, 'cafe'→food, 'app launch'→saas, etc.\n"
        "If user quoted specific text (e.g. 'text: TRANSFORM'), that is their intended headline.\n"
        "\n"
        "== PLATFORM FORMAT KNOWLEDGE ==\n"
        f"{_PLATFORM_FORMATS_KB}\n"
        "== END KNOWLEDGE ==\n"
        "\n"
        "Use the INFERENCE RULES above to pick the correct platform.\n"
        "Return ONLY valid JSON:\n"
        '{"creative_type":"ad|poster|social_post|banner|story|thumbnail",\n'
        '"platform":"instagram_portrait|instagram_square|instagram_story|facebook_landscape|'
        'twitter|linkedin|youtube_thumbnail|pinterest|tiktok_story|print_flyer|print_a4|'
        'banner_leaderboard|banner_rectangle|banner_half_page|default",\n'
        '"goal":"product_launch|brand_awareness|sale_promotion|event|app_download|lead_gen",\n'
        '"audience":"b2b|b2c|youth|professional|general",\n'
        '"brand_hint":"brand or product name if mentioned, else empty",\n'
        '"industry":"saas|food|fashion|fitness|real_estate|healthcare|finance|education|tech|general",\n'
        '"explicit_headline":"exact text user quoted as headline, or empty string",\n'
        '"explicit_cta":"exact text user quoted as CTA/button, or empty string",\n'
        '"explicit_subheadline":"second quoted text if user specified subheadline/subtitle, else empty",\n'
        '"is_festival":false,"festival_name":""}'
    )
    raw = await _acall_gemini(system, "Design request: " + prompt, temperature=0.3, agent_name="triage")
    r = _extract_json(raw)
    defaults = {
        "creative_type": "poster", "platform": "instagram_portrait",
        "goal": "brand_awareness", "audience": "general",
        "brand_hint": "", "industry": "general",
        "explicit_headline": "", "explicit_cta": "", "explicit_subheadline": "",
        "is_festival": False, "festival_name": "",
    }
    for k, v in r.items():
        if v is not None and not k.startswith("_"):
            defaults[k] = v

    # Resolve platform → recommended dimensions
    dims = _PLATFORM_DIMS.get(defaults["platform"], _PLATFORM_DIMS["default"])
    defaults["recommended_width"]  = dims[0]
    defaults["recommended_height"] = dims[1]
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


_CREATIVE_DIRECTOR_KB = """
## CREATIVE BRIEF — answer these before deciding anything:
- AUDIENCE: Who? Age, mindset, platform context?
- HOOK: ONE thing this visual communicates in 1.5 seconds
- EMOTION: What should the viewer FEEL? (Urgency / Desire / Curiosity / Trust / FOMO)
- DIFFERENTIATOR: What makes this NOT look like every other ad in this space?

## FORMAT RULES:
Posters: One dominant visual, 3-level typographic hierarchy MAX, 60-30-10 color rule
Image ads: 3-second rule, CTA unmissable (color + size + position), whitespace = premium
Thumbnails: 6 words max, rule of halves, bold keyline on text, emotional face beats product

## COLOR STRATEGY:
Red/Orange → Urgency, energy | Blue → Trust, technology | Yellow/Gold → Premium, warmth
Purple → Luxury, mystery | Green → Growth, health | Black/White → Editorial, sophistication
Always 60% dominant + 30% secondary + 10% accent. Never more than 3 colors + neutrals.

## COMPOSITION ARCHETYPES — pick ONE, execute hard:
1. Hero-Dominant: Massive image, minimal text overlay → for product/fashion/lifestyle
2. Split 60/40: Visual | Text split → clean, editorial
3. Typographic-Led: Bold type IS the hero visual → for sales/urgency/announcements
4. Frame-Within-Frame: Border creates depth and focus → for premium/luxury
5. Dynamic Diagonal: Energy, movement, tension → for fitness/tech/sports
6. Asymmetric Grid: Intentional imbalance, visual tension → for fashion/editorial
7. Full-Bleed: Image fills everything, text floats over gradient → for cinematic/emotional

## VISUAL METAPHORS — must be CONCRETE nouns, not abstract concepts:
✅ "rain-slicked runway", "morning light on silk", "shattered crystal"
❌ "modernity", "aspiration", "innovation"

## FORBIDDEN ELEMENTS — be specific about what kills the design:
✅ "no stock photo handshakes", "no rainbow gradients", "no clip-art icons"
❌ "no clichés" (too vague)

## COPY PRINCIPLES:
Headline formulas: Question / Provocation / Bold claim / Contrast / Urgency / Specificity
✅ "Save 3 hours/week" > "Save time" (specificity beats vagueness)
✅ Under 8 words for ads/thumbnails
❌ Passive voice, jargon, more than 8 words

## ANTI-PATTERNS (NEVER produce these):
- Rainbow of colors → max 3 + neutrals
- All text same size → 3-level hierarchy minimum
- Centered everything → asymmetry, rule of thirds
- Stock photo feel → bold type, abstract shapes, custom treatment
- Drop shadow on everything → only where it solves legibility
- Trying to say everything → ONE hook, ONE message, ONE job
"""

async def _agent_creative_director(triage: Dict, brand: Dict, prompt: str) -> Dict:
    from app.services.smart.color_intelligence import derive_palette, suggest_harmony

    harmony = suggest_harmony(brand.get("tone", ""), triage.get("industry", ""))
    palette = derive_palette(
        primary_hex=brand.get("primary_color", "#6C63FF"),
        brand_tone=triage.get("industry", ""),
        prompt_context=prompt,
        harmony=harmony,
    )

    platform = triage.get("platform", "instagram")
    industry = triage.get("industry", "general")
    goal     = triage.get("goal", "brand_awareness")

    system = (
        "You are a Senior Creative Director with 15+ years at Wieden+Kennedy, Ogilvy, BBDO.\n"
        "You make opinionated, distinctly non-generic creative decisions.\n"
        "\n"
        "== YOUR CREATIVE KNOWLEDGE BASE ==\n"
        f"{_CREATIVE_DIRECTOR_KB}\n"
        "== END KNOWLEDGE BASE ==\n"
        "\n"
        "TASK: Given the brief below, produce:\n"
        "1. Visual direction (theme, mood, style, composition archetype, atmosphere)\n"
        "2. Creative Bible — a locked creative contract all downstream agents must obey\n"
        "\n"
        "THINKING PROCESS (internal, before outputting):\n"
        f"- Platform: {platform} → what format rules apply?\n"
        f"- Industry: {industry} → what visual language is expected vs subverted?\n"
        f"- Goal: {goal} → what emotion drives action?\n"
        "- Choose ONE composition archetype from knowledge base and execute hard\n"
        "- Visual metaphors must be concrete nouns (not abstract concepts)\n"
        "- Forbidden elements must be specific (not 'no clichés')\n"
        "\n"
        "Return ONLY valid JSON:\n"
        '{"theme":"<one evocative word>","mood":"<one precise emotion word>",'
        '"visual_style":"photorealistic|illustration|3d_render|graphic_flat|editorial",'
        '"layout_archetype":"hero_dominant|split_60_40|typographic_led|frame_within_frame|dynamic_diagonal|asymmetric_grid|full_bleed",'
        '"hero_occupies":"top_60|top_50|full_bleed|center_50",'
        '"atmosphere":"<one sentence, specific and evocative, not generic>",'
        '"avoid":["<specific element 1>","<specific element 2>","<specific element 3>"],'
        '"creative_bible":{'
        '"emotional_territory":"<ONE precise phrase: the exact feeling this design must evoke>",'
        '"visual_metaphors":["<concrete noun 1>","<concrete noun 2>","<concrete noun 3>"],'
        '"forbidden_elements":["<specific visual no-go 1>","<specific no-go 2>","<specific no-go 3>"],'
        '"dominant_color_story":"<one sentence: how the 60-30-10 colors work together>",'
        '"composition_archetype":"<one sentence: describe the diagonal/tension/balance specifically>"}}'
    )
    context = (
        f"Brief: {prompt}\n"
        f"Brand: {brand.get('brand_name','')} | Tone: {brand.get('tone','')} | Industry: {industry}\n"
        f"Platform: {platform} | Goal: {goal} | Audience: {triage.get('audience','general')}\n"
        f"Primary color: {palette.get('primary','#6C63FF')} | "
        f"Secondary: {palette.get('secondary','#4FACFE')}"
    )
    raw = await _acall_gemini(system, context, temperature=0.82, agent_name="creative_director")
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
    explicit_headline    = triage.get("explicit_headline", "").strip()
    explicit_cta         = triage.get("explicit_cta", "").strip()
    explicit_subheadline = triage.get("explicit_subheadline", "").strip()
    explicit_hint = ""
    if explicit_headline:
        explicit_hint += f'\nUSER EXPLICITLY WANTS headline: "{explicit_headline}" — use this EXACTLY, do not change it.'
    if explicit_subheadline:
        explicit_hint += f'\nUSER EXPLICITLY WANTS subheadline: "{explicit_subheadline}" — use this EXACTLY.'
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
    if explicit_headline:
        headline = explicit_headline.upper()
    else:
        headline = str(r.get("headline") or "").strip().upper() or "MAKE IT HAPPEN"
        if len(headline) > hl_max:
            headline = headline[:hl_max].rsplit(" ", 1)[0]

    # explicit_subheadline from triage (e.g. user said "Spring 2026" as subtitle)
    if explicit_subheadline:
        subheadline = explicit_subheadline
    else:
        subheadline = str(r.get("subheadline") or "").strip()

    cta = str(r.get("cta") or "GET STARTED").upper()
    if explicit_cta:
        cta = explicit_cta.upper()

    return {
        "brand_name":  str(r.get("brand_name") or brand.get("brand_name", "") or ""),
        "headline":    headline,
        "subheadline": subheadline,
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


async def _agent_layout_planner(
    triage: Dict,
    creative: Dict,
    copy: Dict,
    aspect_ratio: float = 0.667,
) -> List[Dict]:
    """
    Gemini-powered layout agent — thinks about optimal element placement
    for a full-bleed poster (hero image fills 100% canvas, text overlaid).
    Returns normalized Fabric.js element list (x/y/w/h in 0.0–1.0 range).
    """
    palette = creative.get("palette", {})
    pri = _safe_hex(palette.get("primary"), "#6C63FF")
    txt = _safe_hex(palette.get("text_primary"), "#FFFFFF")
    sec = _safe_hex(palette.get("text_secondary"), "#CCCCDD")

    has_brand    = bool(str(copy.get("brand_name") or "").strip())
    has_sub      = bool(str(copy.get("subheadline") or "").strip())
    has_cta      = bool(str(copy.get("cta") or "").strip())
    has_tagline  = bool(str(copy.get("tagline") or "").strip())
    headline_len = len(str(copy.get("headline") or ""))

    system = (
        "You are a UI Layout Planner for full-bleed ad posters.\n"
        "The hero image fills the ENTIRE canvas (0,0 → 1,1). All text is OVERLAID on the image.\n"
        "Canvas is normalized: x/y/w/h all in 0.0–1.0 range.\n"
        "\n"
        "PLATFORM KNOWLEDGE:\n"
        f"{_PLATFORM_FORMATS_KB}\n"
        "\n"
        "LAYOUT RULES:\n"
        "1. Brand bar: top strip y=0.0–0.07 (only if brand exists)\n"
        "2. Headline: large, centered, y=0.52–0.65 (adjust for content length)\n"
        "3. Subheadline: directly below headline, smaller font\n"
        "4. CTA button: pinned near bottom, y=0.80–0.86\n"
        "5. Tagline: very bottom, y=0.91–0.95\n"
        "6. NOTHING exceeds y=0.97\n"
        "7. Landscape (16:9): text left-aligned x=0.05–0.50, hero fills right\n"
        "8. Story (9:16): generous vertical spacing, bigger fonts\n"
        "9. Font choice: prefer bebas_neue/anton for headlines, montserrat_bold for body\n"
        "\n"
        "Return ONLY valid JSON array of elements. Each element:\n"
        '{"id":"<id>","type":"text|shape|image","bounds":{"x":0.0,"y":0.0,"w":1.0,"h":0.1},'
        '"style":{"font":"bebas_neue|anton|montserrat_bold|playfair","size_role":"headline|subheadline|body|cta|tagline|brand","color":"#FFFFFF","align":"center|left|right"},'
        '"content":"<text content>","locked":false}\n'
        "Include only elements that have content. No empty elements."
    )

    ar_label = (
        "portrait 4:5 (instagram)" if 0.75 <= aspect_ratio <= 0.82
        else "story 9:16 (vertical)" if aspect_ratio < 0.65
        else "square 1:1" if 0.95 <= aspect_ratio <= 1.05
        else "landscape 16:9" if aspect_ratio >= 1.5
        else f"custom {aspect_ratio:.2f}"
    )
    context = (
        f"Poster: {ar_label}\n"
        f"Brand: {copy.get('brand_name','')}\n"
        f"Headline ({headline_len} chars): {copy.get('headline','')}\n"
        f"Subheadline: {copy.get('subheadline','')}\n"
        f"CTA: {copy.get('cta','')}\n"
        f"Tagline: {copy.get('tagline','')}\n"
        f"Mood: {creative.get('mood','')}\n"
        f"Accent color: {pri}\n"
        f"Has brand: {has_brand}, Has sub: {has_sub}, Has CTA: {has_cta}, Has tagline: {has_tagline}"
    )

    raw = await _acall_gemini(system, context, temperature=0.3, agent_name="layout_planner")

    # Parse — expect JSON array
    raw = raw.strip()
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        elements = json.loads(raw)
        if isinstance(elements, list) and elements:
            logger.info("[layout_planner] Gemini placed %d elements", len(elements))
            return elements
    except Exception:
        pass

    # Fallback: deterministic full-bleed layout
    logger.warning("[layout_planner] Gemini failed, using deterministic full-bleed layout")
    return _layout_fallback(copy, creative, aspect_ratio)


def _layout_fallback(copy: Dict, creative: Dict, aspect_ratio: float) -> List[Dict]:
    """Deterministic full-bleed layout — all elements on image, nothing below."""
    palette = creative.get("palette", {})
    pri = _safe_hex(palette.get("primary"), "#6C63FF")
    txt = _safe_hex(palette.get("text_primary"), "#FFFFFF")
    sec = _safe_hex(palette.get("text_secondary"), "#CCCCDD")

    elements: List[Dict] = []

    # Hero fills full canvas
    elements.append({"id": "hero_bg", "type": "image",
        "bounds": {"x": 0, "y": 0, "w": 1.0, "h": 1.0},
        "style": {"opacity": 1.0}, "content": "__hero_url__", "locked": True})

    # Brand bar (top)
    brand_name = str(copy.get("brand_name") or "")
    if brand_name:
        elements.append({"id": "brand_bar", "type": "shape",
            "bounds": {"x": 0, "y": 0, "w": 1.0, "h": 0.07},
            "style": {"fill": "#00000066", "opacity": 0.7}, "content": "", "locked": True})
        elements.append({"id": "brand_name", "type": "text",
            "bounds": {"x": 0.05, "y": 0.01, "w": 0.90, "h": 0.05},
            "style": {"font": "bebas_neue", "size_role": "brand", "color": txt, "align": "center"},
            "content": brand_name.upper(), "locked": False})

    # Headline at 52%
    headline = str(copy.get("headline") or "")
    if headline:
        elements.append({"id": "headline", "type": "text",
            "bounds": {"x": 0.05, "y": 0.52, "w": 0.90, "h": 0.14},
            "style": {"font": "bebas_neue", "size_role": "headline", "color": txt, "align": "center"},
            "content": headline, "locked": False})

    # Subheadline at 67%
    sub = str(copy.get("subheadline") or "")
    if sub:
        elements.append({"id": "subheadline", "type": "text",
            "bounds": {"x": 0.05, "y": 0.67, "w": 0.90, "h": 0.06},
            "style": {"font": "montserrat_bold", "size_role": "subheadline", "color": sec, "align": "center"},
            "content": sub, "locked": False})

    # CTA at 80%
    cta = str(copy.get("cta") or "")
    if cta:
        elements.append({"id": "cta_button", "type": "shape",
            "bounds": {"x": 0.10, "y": 0.80, "w": 0.80, "h": 0.08},
            "style": {"fill": pri, "radius": 40, "opacity": 1.0}, "content": "", "locked": False})
        elements.append({"id": "cta_text", "type": "text",
            "bounds": {"x": 0.10, "y": 0.80, "w": 0.80, "h": 0.08},
            "style": {"font": "bebas_neue", "size_role": "cta", "color": txt, "align": "center"},
            "content": cta, "locked": False})

    # Tagline at 91%
    tagline = str(copy.get("tagline") or "")
    if tagline:
        elements.append({"id": "tagline", "type": "text",
            "bounds": {"x": 0.05, "y": 0.91, "w": 0.90, "h": 0.04},
            "style": {"font": "montserrat_bold", "size_role": "tagline", "color": sec, "align": "center"},
            "content": tagline, "locked": False})

    return elements


async def _agent_image_prompter(
    triage: Dict,
    creative: Dict,
    copy: Dict,
    prompt_dna: Optional[Dict] = None,
) -> Dict:
    # Full-bleed: image fills 100% canvas, text overlaid. Bottom 50% must be dark.
    festival_hint = ""
    if triage.get("is_festival") and triage.get("festival_name"):
        festival_hint = f"\nFestival context: {triage['festival_name']} — weave in authentic cultural visual elements."

    dna_hint = ""
    if prompt_dna and isinstance(prompt_dna, dict):
        winning = prompt_dna.get("winning_keywords") or []
        failing = prompt_dna.get("failing_patterns") or []
        if prompt_dna.get("run_count", 0) >= 5 and winning:
            dna_hint = f"\nStyle memory from past liked generations: {', '.join(winning[:8])}"
        if failing:
            dna_hint += f"\nPatterns to avoid: {', '.join(failing[:4])}"

    bible = creative.get("creative_bible") or {}
    forbidden_additions = ", ".join((bible.get("forbidden_elements") or [])[:3])

    # Build rich creative context from Creative Director's output
    bible_context = ""
    if bible.get("emotional_territory"):
        bible_context += f"\nEmotional territory: {bible['emotional_territory']}"
    if bible.get("visual_metaphors"):
        bible_context += f"\nVisual metaphors (use as treatment, NOT as replacement for subject): {', '.join(bible['visual_metaphors'][:3])}"
    if bible.get("dominant_color_story"):
        bible_context += f"\nColor story: {bible['dominant_color_story']}"
    if bible.get("composition_archetype"):
        bible_context += f"\nComposition archetype: {bible['composition_archetype']}"

    # ── Output schema the agent must produce ─────────────────────────────────
    _OUTPUT_SCHEMA = '''{
  "schema": "cd_integration",
  "creative_brief": {
    "hook": "<headline or emotional hook from CD>",
    "emotion": "<emotional territory>",
    "platform": "<instagram_portrait|square|story|etc>",
    "composition": "<composition archetype>",
    "color_strategy": "<dominant color story>"
  },
  "translation_notes": "<how CD elements mapped to image prompt — what was excluded and why>",
  "text_handling": "<confirm headline/copy was excluded from image prompt>",
  "recommended_model": "<exact model id: flux_2_pro|flux_2_dev|flux_schnell_fal|ideogram_quality|hunyuan_image>",
  "recommendation_reason": "<1 sentence why this model fits the brief>",
  "primary_output": {
    "model": "<same as recommended_model>",
    "prompt": "<vivid scene, subject-grounded, per model template, 80-120 words, ZERO text>",
    "negative_prompt": "<model-specific negatives + always include: text,words,letters,signs,watermark,typography>",
    "parameters": {
      "aspect_ratio": "<4:5|1:1|9:16|16:9>",
      "steps": <integer per model profile>,
      "guidance": <float 3.0-7.0>,
      "seed": null
    },
    "prompt_notes": "<explain 2+ key decisions: why this model, what lighting choice, how CD was applied>"
  },
  "draft_variant": {
    "model": "flux_schnell_fal",
    "prompt": "<simplified version under 60 words for fast iteration>",
    "negative_prompt": "blurry, watermark, text overlay, deformed, low quality",
    "parameters": {"steps": 4, "guidance": 3.5, "aspect_ratio": "<same>", "seed": null},
    "prompt_notes": "Use for fast iteration before committing to primary model"
  }
}'''

    system = (
        "You are a world-class AI Image Prompt Engineer AND Senior Art Director.\n"
        "Task: Generate the optimized background image prompt for a full-bleed poster ad.\n"
        "Input comes from the Creative Director agent — translate it into production-ready image prompts.\n"
        "\n"
        "== KNOWLEDGE BASE ==\n"
        f"{_IMAGE_PROMPT_ENGINEER_KB}\n"
        "== END KNOWLEDGE BASE ==\n"
        "\n"
        "WORKFLOW:\n"
        "1. IDENTIFY the subject from user's brief (product, person, place, concept)\n"
        "2. GROUND the scene — subject must be visually present\n"
        "3. ELEVATE with CD's mood/metaphors as TREATMENT (not scene replacement)\n"
        "4. SELECT model using MODEL SELECTION guide\n"
        "5. ENGINEER prompt using the model's template from knowledge base\n"
        "6. VALIDATE: prompt starts with subject, bottom 50% is naturally dark, zero text\n"
        "7. PRODUCE draft_variant as a ≤60 word flux_schnell version for fast iteration\n"
        f"{festival_hint}{dna_hint}\n"
        "\n"
        "VALIDATION BEFORE RETURNING:\n"
        "- prompt must START with the subject (not a mood word)\n"
        "- negative_prompt must be model-specific (not generic)\n"
        "- steps must be within model's optimal range\n"
        "- NO text/words/letters anywhere in the prompt\n"
        "\n"
        f"Return ONLY this JSON structure (no prose, no markdown):\n{_OUTPUT_SCHEMA}"
    )

    context = (
        f"User's brief: {triage.get('original_prompt', '')}\n"
        f"Brand/Product: {str(copy.get('brand_name','') or triage.get('brand_hint','') or 'unbranded')}\n"
        f"Poster headline (NEVER render in image): {copy.get('headline','')}\n"
        f"Mood: {creative.get('mood','energetic')}\n"
        f"Visual style: {creative.get('visual_style','photorealistic')}\n"
        f"Atmosphere: {creative.get('atmosphere','')}"
        f"{bible_context}\n"
        f"Platform: {creative.get('aspect_ratio','4:5')}\n"
        f"Avoid: {', '.join((creative.get('avoid') or []) + ([forbidden_additions] if forbidden_additions else []))}"
    )

    raw = await _acall_gemini(system, context, temperature=0.72, agent_name="image_prompter")
    r = _extract_json(raw)

    # ── Extract from cd_integration schema ───────────────────────────────────
    primary = r.get("primary_output") or {}
    bg_prompt = str(primary.get("prompt") or r.get("prompt") or "").strip()
    model_preference = str(
        r.get("recommended_model") or primary.get("model") or r.get("model_preference") or ""
    ).strip()
    neg_from_schema = str(primary.get("negative_prompt") or r.get("negative_prompt") or "").strip()
    params = primary.get("parameters") or {}
    draft = r.get("draft_variant") or {}

    # Fallback if primary prompt missing or too short
    if not bg_prompt or len(bg_prompt) < 20:
        logger.warning("[image_prompter] cd_integration prompt missing, running fallback")
        fallback_system = (
            "You are a Senior Art Director. Describe the background hero image for this ad poster.\n"
            "Keep the actual subject from the user's brief in the scene.\n"
            "Apply creative treatment: lighting, color, composition, mood.\n"
            "ZERO text or letters in the image. Bottom half must be naturally dark.\n"
            "Return plain text only — 60-100 words, no JSON."
        )
        fallback_user = (
            f"User's brief: \"{triage.get('original_prompt', '')}\"\n"
            f"Mood: {creative.get('mood','energetic')} | Style: {creative.get('visual_style','photorealistic')}\n"
            "Describe the background scene."
        )
        bg_prompt = await _acall_gemini(fallback_system, fallback_user,
                                        temperature=0.5, agent_name="image_prompter")
        bg_prompt = bg_prompt.strip().strip('"').strip("'")
        if bg_prompt in ("{}", "{", "}", "null", "none", "") or len(bg_prompt) < 15:
            bg_prompt = ""

    # Sanitize — strip any text/typography keywords that leaked through
    _TEXT_LEAK = re.compile(
        r"\b(crisp\s+sharp\s+text|readable\s+typography|graphic\s+design|"
        r"high\s+contrast\s+text|bold\s+typography|text\s+overlay|"
        r"typography|legible|calligraph\w*|lettering|signage)\b",
        re.IGNORECASE,
    )
    bg_prompt = _TEXT_LEAK.sub("", bg_prompt).strip().strip(",").strip()
    bg_prompt = re.sub(r",\s*,", ",", bg_prompt)
    bg_prompt = re.sub(r"\s{2,}", " ", bg_prompt)

    # Hard negative — always block text regardless of model
    _HARD_NEG = (
        "text, words, letters, numbers, typography, captions, labels, watermark, "
        "logo text, brand name, headline, subtitle, written words, fonts, script, "
        "calligraphy, signage, UI overlay, HUD, interface elements, blurry, low quality"
    )
    # Merge with schema negative (which has model-specific negatives)
    if neg_from_schema and neg_from_schema not in ("{}", "null"):
        base_negative = f"{_HARD_NEG}, {neg_from_schema}"
    else:
        base_negative = _HARD_NEG
    if forbidden_additions:
        base_negative = f"{base_negative}, {forbidden_additions}"

    # Smart fallback prompt
    industry = triage.get("industry", "general")
    mood_val = creative.get("mood", "energetic")
    style_val = creative.get("visual_style", "photorealistic")
    _smart_fallback = (
        f"cinematic {industry} scene, {mood_val} atmosphere, {style_val} style, "
        f"dramatic lighting, deep shadows in bottom half, no text, clean background"
    )

    return {
        "background_prompt": bg_prompt or _smart_fallback,
        "negative_prompt":   base_negative,
        "model_preference":  model_preference or "flux_pro",
        "parameters":        params,           # steps, guidance, aspect_ratio from schema
        "draft_variant":     draft,            # flux_schnell version for fast iteration
        "translation_notes": r.get("translation_notes", ""),
        "recommendation_reason": r.get("recommendation_reason", ""),
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
            triage["original_prompt"] = safe_prompt  # pass through for image_prompter context
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

            # ── Stage 4: Layout Planner (Gemini-powered, full-bleed positions) ──
            t = time.time()
            elements = await _agent_layout_planner(triage, creative, copy, aspect_ratio=aspect_ratio)
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

            # cd_integration schema extras — steps/guidance/draft for generate_stream to use
            brief["_img_parameters"]        = img.get("parameters", {})
            brief["_img_draft_variant"]     = img.get("draft_variant", {})
            brief["_img_translation_notes"] = img.get("translation_notes", "")
            brief["_img_recommendation"]    = img.get("recommendation_reason", "")

            # gemini_prompt_engine compatibility
            brief["visual_concept"] = img["background_prompt"]
            brief["mood"]           = creative.get("mood", "")
            brief["lighting"]       = "cinematic dramatic lighting"
            brief["camera"]         = "professional photography"

            # Platform / routing + triage-recommended dimensions
            brief["platform"]             = triage.get("platform", "instagram_portrait")
            brief["creative_type"]        = triage.get("creative_type", "ad")
            brief["goal"]                 = triage.get("goal", "brand_awareness")
            brief["recommended_width"]    = triage.get("recommended_width", 1080)
            brief["recommended_height"]   = triage.get("recommended_height", 1350)

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

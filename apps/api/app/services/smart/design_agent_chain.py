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


# ── Module-level Gemini client singleton ─────────────────────────────────────
_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


# Per-agent max tokens (tuned to actual output sizes)
_AGENT_MAX_TOKENS = {
    "triage":           300,
    "brand_intel":      250,
    "creative_director":350,
    "copy_writer":      700,
    "image_prompter":   500,
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
            pass
    logger.warning("[design_chain] _extract_json failed on: %r", text[:200])
    return {"_parse_error": True}


# ── Async Gemini caller ───────────────────────────────────────────────────────
async def _acall_gemini(
    system: str,
    user: str,
    temperature: float = 0.7,
    agent_name: str = "unknown",
) -> str:
    t0 = time.time()
    try:
        client = _get_gemini_client()
        from google.genai import types

        max_tokens = _AGENT_MAX_TOKENS.get(agent_name, 500)

        # Use async interface
        resp = await client.aio.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[{"role": "user", "parts": [{"text": user}]}],
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        result = resp.text or "{}"
        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info("[design_chain][%s] %dms parsed=%s", agent_name, elapsed_ms, "true")
        return result

    except RuntimeError as e:
        # GEMINI_API_KEY not set
        logger.warning("[design_chain][%s] config error: %s", agent_name, e)
        return "{}"
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        # Distinguish quota vs timeout vs other
        err_type = type(e).__name__
        if "ResourceExhausted" in err_type or "quota" in str(e).lower():
            logger.error("[design_chain][%s] Gemini QUOTA EXCEEDED: %s", agent_name, e)
        elif "DeadlineExceeded" in err_type or "timeout" in str(e).lower():
            logger.error("[design_chain][%s] Gemini TIMEOUT after %dms: %s", agent_name, elapsed_ms, e)
        else:
            logger.warning("[design_chain][%s] Gemini call failed (%dms): %s", agent_name, elapsed_ms, e)
        return "{}"


# ── Individual agents (all async) ─────────────────────────────────────────────

async def _agent_triage(prompt: str) -> Dict:
    system = (
        "You are a marketing strategist AI. Classify a design request.\n"
        'Return ONLY valid JSON: {"creative_type":"ad|poster|social_post|banner|story|thumbnail",'
        '"platform":"instagram|instagram_story|linkedin|twitter|print|default",'
        '"goal":"product_launch|brand_awareness|sale_promotion|event|app_download|lead_gen",'
        '"audience":"b2b|b2c|youth|professional|general",'
        '"brand_hint":"brand or product name or empty",'
        '"industry":"saas|food|fashion|fitness|real_estate|healthcare|finance|education|tech|general",'
        '"is_festival":false,"festival_name":""}'
    )
    raw = await _acall_gemini(system, "Design request: " + prompt, temperature=0.3, agent_name="triage")
    r = _extract_json(raw)
    defaults = {
        "creative_type": "poster", "platform": "instagram",
        "goal": "brand_awareness", "audience": "general",
        "brand_hint": "", "industry": "general",
        "is_festival": False, "festival_name": "",
    }
    # Only apply non-None LLM values
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
        'Return ONLY valid JSON: {"theme":"word","mood":"word",'
        '"visual_style":"photorealistic|illustration|3d_render|graphic_flat|editorial",'
        '"layout_archetype":"hero_top_features_bottom|split_left_right|full_bleed|minimal_centered|grid",'
        '"hero_occupies":"top_60|top_50|full_bleed|center_50",'
        '"atmosphere":"brief description","avoid":["elements"]}'
    )
    context = (
        f"Prompt: {prompt}\nBrand: {brand.get('brand_name','')} Tone: {brand.get('tone','')}\n"
        f"Industry: {triage.get('industry','')} Platform: {triage.get('platform','')}\n"
        f"Primary color: {palette.get('primary','#6C63FF')}"
    )
    raw = await _acall_gemini(system, context, temperature=0.8, agent_name="creative_director")
    r = _extract_json(raw)
    return {
        "theme":            r.get("theme", "bold"),
        "mood":             r.get("mood", "energetic"),
        "visual_style":     r.get("visual_style", "photorealistic"),
        "layout_archetype": r.get("layout_archetype", "hero_top_features_bottom"),
        "hero_occupies":    r.get("hero_occupies", "top_60"),
        "atmosphere":       r.get("atmosphere", ""),
        "avoid":            r.get("avoid") if isinstance(r.get("avoid"), list) else [],
        "palette":          palette,
    }


async def _agent_copy_writer(
    triage: Dict,
    brand: Dict,
    creative: Dict,
    prompt: str,
) -> Dict:
    platform = triage.get("platform", "instagram")
    hl_max = {"instagram": 30, "instagram_story": 20, "linkedin": 50, "default": 40}.get(platform, 40)
    festival_hint = ""
    if triage.get("is_festival") and triage.get("festival_name"):
        festival_hint = f"\nFestival context: {triage['festival_name']} — include cultural warmth."

    system = (
        f"You are a world-class Ad Copywriter. Platform: {platform}. "
        f"Tone: {brand.get('tone','bold')}. Goal: {triage.get('goal','brand_awareness')}. "
        f"HEADLINE max {hl_max} chars ALL CAPS.{festival_hint}\n"
        'Return ONLY valid JSON: {"brand_name":"","headline":"ALL CAPS",'
        '"subheadline":"sentence case","body":"1-2 sentences",'
        '"cta":"2-4 WORDS","cta_url":"","tagline":"",'
        '"features":[{"icon":"emoji","title":"name","desc":"one line"},'
        '{"icon":"emoji","title":"name","desc":"one line"},'
        '{"icon":"emoji","title":"name","desc":"one line"},'
        '{"icon":"emoji","title":"name","desc":"one line"}]}'
    )
    context = (
        f"Request: {prompt}\nTheme: {creative.get('theme','')} Mood: {creative.get('mood','')}\n"
        f"Industry: {triage.get('industry','')} Audience: {triage.get('audience','general')}"
    )
    raw = await _acall_gemini(system, context, temperature=0.85, agent_name="copy_writer")
    r = _extract_json(raw)

    # Validate features: must be list of dicts with "title" key
    raw_features = r.get("features")
    if not isinstance(raw_features, list):
        raw_features = []
    features = [f for f in raw_features if isinstance(f, dict) and f.get("title")][:4]
    while len(features) < 4:
        n = len(features) + 1
        features.append({"icon": "⭐", "title": f"Feature {n}", "desc": "Key benefit"})

    headline = str(r.get("headline") or "MAKE IT HAPPEN").upper()
    # Word-boundary trim if over limit
    if len(headline) > hl_max:
        headline = headline[:hl_max].rsplit(" ", 1)[0]

    return {
        "brand_name":  str(r.get("brand_name") or brand.get("brand_name", "") or ""),
        "headline":    headline,
        "subheadline": str(r.get("subheadline") or "The fastest way to get results"),
        "body":        str(r.get("body") or ""),
        "cta":         str(r.get("cta") or "GET STARTED").upper(),
        "cta_url":     str(r.get("cta_url") or ""),
        "tagline":     str(r.get("tagline") or brand.get("tagline", "") or ""),
        "features":    features,
    }


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
) -> Dict:
    festival_hint = ""
    if triage.get("is_festival") and triage.get("festival_name"):
        festival_hint = f"\nFestival: {triage['festival_name']} — use authentic cultural scene."

    hero_pct = {"top_60": 0.60, "top_50": 0.50}.get(creative.get("hero_occupies", "top_60"), 0.60)
    dark_zone_pct = int((1.0 - hero_pct) * 100)

    system = (
        "You are an Ideogram V3 / Flux Pro background scene generator for poster ads.\n"
        "CRITICAL: Generate ONLY the hero background — NO TEXT in the image.\n"
        f"Bottom {dark_zone_pct}% must be naturally darker (text will overlay here).{festival_hint}\n"
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
        f"Avoid: {', '.join(creative.get('avoid') or [])}"
    )
    raw = await _acall_gemini(system, context, temperature=0.75, agent_name="image_prompter")
    r = _extract_json(raw)
    return {
        "background_prompt": str(r.get("prompt") or f"cinematic {triage.get('industry','product')} scene, dramatic lighting, no text"),
        "negative_prompt":   str(r.get("negative_prompt") or "text, words, letters, watermark, blurry"),
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

            # ── Stage 2: Brand Intel + Creative Director (PARALLEL) ──────────
            t = time.time()
            brand, creative = await asyncio.gather(
                _agent_brand_intel(triage, brand_kit, safe_prompt),
                _agent_creative_director(triage, {"brand_name": "", "tone": "bold",
                    "primary_color": (brand_kit or {}).get("primary_color", "#6C63FF"),
                    "font_style": (brand_kit or {}).get("font_style", "bold_tech")}, safe_prompt),
            )
            agent_times["brand_creative_parallel"] = round(time.time() - t, 2)

            # Rebuild creative with real brand (re-run is cheap; palette is local)
            # Only re-run creative director if brand changed significantly from placeholder
            if brand.get("primary_color") != "#6C63FF" or brand.get("tone") != "bold":
                t = time.time()
                creative = await _agent_creative_director(triage, brand, safe_prompt)
                agent_times["creative_director_refined"] = round(time.time() - t, 2)

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
            t = time.time()
            copy, img = await asyncio.gather(
                _agent_copy_writer(triage, brand, creative, safe_prompt),
                _agent_image_prompter(triage, creative, {"brand_name": brand.get("brand_name", "")}),
            )
            agent_times["copy_image_parallel"] = round(time.time() - t, 2)

            # ── Stage 4: Layout Planner (pure Python, instant) ───────────────
            t = time.time()
            elements = _agent_layout_planner(creative, copy, aspect_ratio=aspect_ratio)
            agent_times["layout_planner"] = round(time.time() - t, 3)

            # ── Assemble final brief ─────────────────────────────────────────
            brief["triage"]    = triage
            brief["brand"]     = brand
            brief["creative"]  = creative
            brief["copy_blocks"] = copy
            brief["ad_copy"]   = {
                "brand_name":  copy["brand_name"],
                "headline":    copy["headline"],
                "subheadline": copy["subheadline"],
                "body":        copy["body"],
                "cta":         copy["cta"],
                "cta_url":     copy["cta_url"],
                "tagline":     copy["tagline"],
                "features":    copy["features"],
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

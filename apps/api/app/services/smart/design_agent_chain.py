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

from app.config.loader import config as beast_config

logger = logging.getLogger(__name__)

# Import enhanced Brand Intelligence Agent
try:
    from app.services.agents.brand_intelligence_agent import brand_intel_agent
    _BRAND_INTEL_AGENT_AVAILABLE = True
except ImportError as e:
    logger.warning("[design_chain] Enhanced brand_intel_agent not available: %s", e)
    _BRAND_INTEL_AGENT_AVAILABLE = False

# Import Design Director Agent
try:
    from app.services.smart.design_director import design_director_agent
    _DESIGN_DIRECTOR_AVAILABLE = True
except ImportError as e:
    logger.warning("[design_chain] design_director not available: %s", e)
    _DESIGN_DIRECTOR_AVAILABLE = False

# Import Cultural Intelligence Layer
try:
    from app.services.smart.cultural_intelligence import CulturalIntelligence
    _CULTURAL_INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    logger.warning("[design_chain] cultural_intelligence not available: %s", e)
    _CULTURAL_INTELLIGENCE_AVAILABLE = False

# Import Motion Designer Agent
try:
    from app.services.smart.motion_designer import generate_static_motion_hints
    _MOTION_DESIGNER_AVAILABLE = True
except ImportError as e:
    logger.warning("[design_chain] motion_designer not available: %s", e)
    _MOTION_DESIGNER_AVAILABLE = False

# ── Hex color validator ──────────────────────────────────────────────────────
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_QUOTED_TEXT_RE = re.compile(r"""['"]([^'"]{1,200})['"]""")


def _safe_hex(value: object, fallback: str) -> str:
    s = str(value or "").strip()
    return s if _HEX_RE.match(s) else fallback


def _extract_explicit_texts(prompt: str) -> Dict[str, str]:
    """
    Deterministically preserve quoted copy from the raw user prompt.

    This avoids losing explicit poster words when triage JSON is incomplete.
    First quoted phrase -> headline, second -> subheadline, third -> CTA.
    """
    matches = [m.strip() for m in _QUOTED_TEXT_RE.findall(prompt or "") if m and m.strip()]
    result = {
        "explicit_headline": "",
        "explicit_subheadline": "",
        "explicit_cta": "",
    }
    if matches:
        result["explicit_headline"] = matches[0]
    if len(matches) > 1:
        result["explicit_subheadline"] = matches[1]
    if len(matches) > 2:
        result["explicit_cta"] = matches[2]
    return result


def _aspect_ratio_label(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "4:5"
    ratio = width / height
    if abs(ratio - 1.0) <= 0.08:
        return "1:1"
    if ratio >= 1.7:
        return "16:9"
    if ratio >= 1.45:
        return "3:2"
    if ratio >= 1.2:
        return "4:3"
    if ratio <= 0.60:
        return "9:16"
    if ratio <= 0.72:
        return "3:4"
    return "4:5"


def _request_strategy(triage: Dict, prompt: str, brand: Optional[Dict] = None) -> Dict[str, str]:
    prompt_lower = (prompt or "").lower()
    industry = str(triage.get("industry") or "general").lower()
    goal = str(triage.get("goal") or "brand_awareness").lower()
    tone = str((brand or {}).get("tone") or "").lower()

    is_fashion = industry == "fashion" or any(
        token in prompt_lower for token in ("fashion", "couture", "runway", "collection", "model", "editorial", "vogue")
    )
    is_luxury = tone in ("luxury", "elegant") or any(
        token in prompt_lower for token in ("luxury", "premium", "elegant", "opulent", "high-end", "exclusive")
    )

    if is_fashion or is_luxury:
        return {
            "font_style": "elegant_serif" if is_luxury else "luxury_display",
            "tone": "luxury" if is_luxury else "elegant",
            "layout_archetype": "hero_dominant",
            "hero_occupies": "center_50",
            "visual_style": "editorial",
            "detail_budget": "Use 90-120 words, one hero subject, and no more than two environmental motifs.",
            "creative_guardrails": (
                "Commercial fashion taste only. Keep the hero subject dominant and desirable. "
                "If the user did not request a specific location, choose a proven editorial backdrop such as a refined runway set, "
                "premium architectural courtyard, sculptural studio backdrop, or luxury boutique facade. "
                "Do not let scenery overpower the garment."
            ),
            "image_guardrails": (
                "Hero fashion model must occupy roughly 45-60% of frame height with a crisp garment silhouette. "
                "Background must remain secondary, elegant, and uncluttered. Seasonal cues should be subtle and premium, "
                "not theme-park literal."
            ),
            "copy_guardrails": (
                "Prefer restrained editorial copy. If headline and subheadline already communicate the idea, body copy can be empty. "
                "CTA, if used, should feel premium rather than salesy."
            ),
            "negative_guardrails": "tiny subject, distant model, overpowering architecture, busy background, cluttered set, costume fantasy",
        }

    if industry == "food":
        return {
            "font_style": "clean_sans",
            "tone": "energetic" if goal == "sale_promotion" else "professional",
            "layout_archetype": "hero_dominant",
            "hero_occupies": "center_50",
            "visual_style": "photorealistic",
            "detail_budget": "Use 70-100 words, appetizing close-up detail, and one or two supporting props max.",
            "creative_guardrails": "Make the food itself the obvious hero. Avoid over-designed fantasy scenes unless the user explicitly asked for them.",
            "image_guardrails": "Food should dominate the frame. Plate, steam, garnish, and lighting should increase appetite immediately.",
            "copy_guardrails": "Headline should be punchy and appetizing. Keep supporting copy short.",
            "negative_guardrails": "tiny dish, messy table, cluttered props, confusing background",
        }

    return {
        "font_style": "bold_tech",
        "tone": "professional",
        "layout_archetype": "full_bleed",
        "hero_occupies": "top_60",
        "visual_style": "photorealistic",
        "detail_budget": "Use only as much detail as strengthens the hero visual and readability.",
        "creative_guardrails": "Choose commercially strong, non-generic visuals that support the message first.",
        "image_guardrails": "Keep one clear hero subject and preserve clean copy space.",
        "copy_guardrails": "Let the strongest message lead. Avoid filler copy.",
        "negative_guardrails": "",
    }


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
    "reconcile":        400,
    "char_guard":       600,
}

_COPY_SPACE_PROMPT_HINTS_OLD = {
    # OLD APPROACH (for compositor overlay) - DEPRECATED
    "top": "preserve clean negative space in the upper third for headline overlay",
    "bottom": "preserve clean negative space in the lower third for headline and CTA overlay",
    "left": "preserve clean negative space on the left side for headline and supporting copy",
    "right": "preserve clean negative space on the right side for headline and supporting copy",
    "center": "preserve a clean central copy-safe area for headline overlay",
}

def _build_native_text_instructions(headline: str, cta: str, copy_space: str, brand_name: str = "") -> str:
    """
    Build Ideogram native text rendering instructions.
    Instead of "preserve space", we tell Ideogram EXACTLY what text to render and how.

    Returns prompt snippet like:
    "Bold headline text 'BEAST MODE' in upper third area, large impactful sans-serif typography,
    white text with thick black outline, highly legible. CTA button 'SHOP NOW' at bottom center."
    """
    if not headline or not headline.strip():
        return ""

    # Text position mapping
    position_map = {
        "top": "in the upper third area",
        "bottom": "in the lower third area",
        "left": "on the left side",
        "right": "on the right side",
        "center": "in the center area",
    }
    position = position_map.get(copy_space, "in the upper area")

    # Build headline instruction
    headline_clean = headline.strip()[:60]  # Max 60 chars for prompt clarity
    text_parts = []

    # Main headline
    text_parts.append(
        f"Bold headline text '{headline_clean}' {position}, large impactful sans-serif typography, "
        f"white text with thick black outline for maximum legibility and contrast"
    )

    # CTA if exists
    if cta and cta.strip():
        cta_clean = cta.strip()[:30]
        cta_position = "at bottom center" if copy_space != "bottom" else "below headline"
        text_parts.append(
            f"CTA text '{cta_clean}' {cta_position}, medium-sized bold typography"
        )

    # Brand name if exists (small at top)
    if brand_name and brand_name.strip():
        brand_clean = brand_name.strip()[:40]
        text_parts.append(
            f"Small brand name '{brand_clean}' at top"
        )

    return ". ".join(text_parts)
_TEXT_NEGATIVE_TERMS = [
    "text",
    "words",
    "letters",
    "typography",
    "captions",
    "labels",
    "watermark",
]


def _infer_body_copy_policy(triage: Dict, strategy: Dict, copy: Dict) -> str:
    goal = str(triage.get("goal") or "brand_awareness").lower()
    headline = str(copy.get("headline") or "").strip()
    subheadline = str(copy.get("subheadline") or "").strip()
    if (
        strategy.get("font_style") in ("elegant_serif", "luxury_display")
        and headline
        and subheadline
        and goal != "sale_promotion"
    ):
        return "minimal"
    if goal in ("sale_promotion", "lead_gen", "event"):
        return "supporting"
    return "balanced"


def _backdrop_candidates_for_request(
    triage: Dict,
    brand: Dict,
    creative: Dict,
    strategy: Dict,
) -> List[Dict]:
    industry = str(triage.get("industry") or "general").lower()
    prompt_lower = str(triage.get("original_prompt") or "").lower()
    tone = str(brand.get("tone") or strategy.get("tone") or "").lower()

    is_fashion = industry == "fashion" or any(
        token in prompt_lower for token in ("fashion", "couture", "runway", "collection", "model", "editorial")
    )
    is_luxury = tone in ("luxury", "elegant") or any(
        token in prompt_lower for token in ("luxury", "premium", "opulent", "exclusive", "high-end")
    )
    is_food = industry == "food" or any(
        token in prompt_lower for token in ("restaurant", "dessert", "food", "cafe", "menu", "dish", "chef")
    )
    is_beauty = industry in ("healthcare", "general") and any(
        token in prompt_lower for token in ("beauty", "skincare", "serum", "perfume", "cosmetic", "makeup")
    )
    is_fitness = industry == "fitness" or any(
        token in prompt_lower for token in ("gym", "fitness", "workout", "athlete", "training", "sport")
    )
    is_tech = industry in ("tech", "saas", "finance", "education") or any(
        token in prompt_lower for token in ("app", "software", "dashboard", "device", "tech", "startup", "platform")
    )

    if is_fashion or is_luxury:
        return [
            {
                "id": "sculptural_studio",
                "label": "Sculptural studio set",
                "direction": (
                    "Use a refined editorial studio with sculptural shadow planes, premium materials, and one controlled "
                    "seasonal accent so the garment stays dominant and aspirational."
                ),
                "copy_space": "top",
                "hero_placement": "centered and large",
                "subject_priority": 10,
                "readability": 10,
                "brand_fit": 10,
                "novelty": 8,
                "supports_sale": 7,
                "supports_editorial": 10,
                "environment_dominance": 3,
                "vertical_friendly": 10,
                "font_style": "elegant_serif" if is_luxury else "luxury_display",
            },
            {
                "id": "controlled_runway",
                "label": "Controlled runway reveal",
                "direction": (
                    "Stage the hero in a polished runway-like reveal with disciplined lighting, shallow audience hints, "
                    "and a clean upper band reserved for headline impact."
                ),
                "copy_space": "top",
                "hero_placement": "centered with forward motion",
                "subject_priority": 9,
                "readability": 9,
                "brand_fit": 9,
                "novelty": 8,
                "supports_sale": 7,
                "supports_editorial": 9,
                "environment_dominance": 4,
                "vertical_friendly": 9,
                "font_style": "luxury_display",
            },
            {
                "id": "courtyard_editorial",
                "label": "Architectural courtyard editorial",
                "direction": (
                    "Place the hero in a premium courtyard or heritage architectural frame, but keep the set softened and "
                    "secondary so the subject silhouette still reads first."
                ),
                "copy_space": "top",
                "hero_placement": "center-lower with clean vertical axis",
                "subject_priority": 7,
                "readability": 8,
                "brand_fit": 8,
                "novelty": 9,
                "supports_sale": 5,
                "supports_editorial": 8,
                "environment_dominance": 6,
                "vertical_friendly": 8,
                "font_style": "elegant_serif",
            },
            {
                "id": "boutique_facade",
                "label": "Luxury boutique facade",
                "direction": (
                    "Use a premium storefront or boutique facade with one strong window glow and negative space on the side, "
                    "so the message feels commercial and upscale without turning into a literal catalog shot."
                ),
                "copy_space": "right",
                "hero_placement": "left-third anchor",
                "subject_priority": 8,
                "readability": 9,
                "brand_fit": 8,
                "novelty": 7,
                "supports_sale": 8,
                "supports_editorial": 7,
                "environment_dominance": 5,
                "vertical_friendly": 8,
                "font_style": "elegant_serif",
            },
        ]

    if is_food:
        return [
            {
                "id": "hero_counter_closeup",
                "label": "Hero counter close-up",
                "direction": (
                    "Push into an appetizing close-up on the signature dish or dessert with glossy textures, steam or chill, "
                    "and only one or two premium supporting props."
                ),
                "copy_space": "top",
                "hero_placement": "large foreground hero",
                "subject_priority": 10,
                "readability": 9,
                "brand_fit": 10,
                "novelty": 7,
                "supports_sale": 9,
                "supports_editorial": 7,
                "environment_dominance": 2,
                "vertical_friendly": 9,
                "font_style": "clean_sans",
            },
            {
                "id": "chef_pass",
                "label": "Chef's pass moment",
                "direction": (
                    "Set the dish at the kitchen pass with controlled warmth, sharp plating detail, and a slight sense of service "
                    "motion to create appetite plus credibility."
                ),
                "copy_space": "top",
                "hero_placement": "mid-frame with shallow depth",
                "subject_priority": 9,
                "readability": 8,
                "brand_fit": 9,
                "novelty": 8,
                "supports_sale": 8,
                "supports_editorial": 7,
                "environment_dominance": 4,
                "vertical_friendly": 8,
                "font_style": "clean_sans",
            },
            {
                "id": "signature_tabletop",
                "label": "Signature tabletop still life",
                "direction": (
                    "Build a premium tabletop set with one hero dish, restrained garnish, tactile surfaces, and negative space "
                    "that makes pricing or promo copy easy to read."
                ),
                "copy_space": "right",
                "hero_placement": "left-third hero plate",
                "subject_priority": 9,
                "readability": 10,
                "brand_fit": 8,
                "novelty": 6,
                "supports_sale": 10,
                "supports_editorial": 6,
                "environment_dominance": 3,
                "vertical_friendly": 8,
                "font_style": "clean_sans",
            },
            {
                "id": "storefront_launch",
                "label": "Storefront launch reveal",
                "direction": (
                    "For openings or events, show a clean restaurant frontage or interior reveal with one hero food cue, keeping "
                    "the promo feel energetic but still design-led."
                ),
                "copy_space": "bottom",
                "hero_placement": "upper-center focal area",
                "subject_priority": 7,
                "readability": 8,
                "brand_fit": 8,
                "novelty": 7,
                "supports_sale": 9,
                "supports_editorial": 5,
                "environment_dominance": 5,
                "vertical_friendly": 8,
                "font_style": "clean_sans",
            },
        ]

    if is_beauty:
        return [
            {
                "id": "mirror_vanity",
                "label": "Mirror vanity glow",
                "direction": (
                    "Use a polished vanity or mirrored pedestal with controlled reflections, one beauty hero, and luxurious light "
                    "falloff that keeps the composition clean."
                ),
                "copy_space": "top",
                "hero_placement": "center-lower pedestal",
                "subject_priority": 9,
                "readability": 9,
                "brand_fit": 9,
                "novelty": 8,
                "supports_sale": 7,
                "supports_editorial": 9,
                "environment_dominance": 3,
                "vertical_friendly": 9,
                "font_style": "elegant_serif",
            },
            {
                "id": "clinical_luxe_lab",
                "label": "Clinical luxe lab",
                "direction": (
                    "Blend clean laboratory precision with luxury materials so the product feels credible, elevated, and visually sharp "
                    "without losing warmth."
                ),
                "copy_space": "right",
                "hero_placement": "left-third anchor",
                "subject_priority": 9,
                "readability": 10,
                "brand_fit": 8,
                "novelty": 7,
                "supports_sale": 8,
                "supports_editorial": 8,
                "environment_dominance": 3,
                "vertical_friendly": 8,
                "font_style": "elegant_serif",
            },
            {
                "id": "liquid_pedestal",
                "label": "Liquid pedestal set",
                "direction": (
                    "Anchor the product on a sculpted pedestal with fluid reflections or luminous liquid accents that feel premium "
                    "rather than fantasy-heavy."
                ),
                "copy_space": "top",
                "hero_placement": "center hero object",
                "subject_priority": 10,
                "readability": 8,
                "brand_fit": 9,
                "novelty": 8,
                "supports_sale": 7,
                "supports_editorial": 8,
                "environment_dominance": 4,
                "vertical_friendly": 9,
                "font_style": "elegant_serif",
            },
            {
                "id": "spa_stone_scene",
                "label": "Spa stone restraint",
                "direction": (
                    "Use a spa-inspired stone or mineral set with restrained organic cues so the product feels calm, premium, and "
                    "instantly legible."
                ),
                "copy_space": "left",
                "hero_placement": "right-third pedestal",
                "subject_priority": 8,
                "readability": 9,
                "brand_fit": 8,
                "novelty": 6,
                "supports_sale": 7,
                "supports_editorial": 7,
                "environment_dominance": 4,
                "vertical_friendly": 8,
                "font_style": "elegant_serif",
            },
        ]

    if is_fitness:
        return [
            {
                "id": "hero_training_bay",
                "label": "Hero training bay",
                "direction": (
                    "Keep the athlete or product dominant inside a disciplined training bay with directional light, subtle motion cues, "
                    "and plenty of readable negative space."
                ),
                "copy_space": "top",
                "hero_placement": "center hero with active stance",
                "subject_priority": 10,
                "readability": 9,
                "brand_fit": 9,
                "novelty": 7,
                "supports_sale": 8,
                "supports_editorial": 6,
                "environment_dominance": 3,
                "vertical_friendly": 9,
                "font_style": "bold_tech",
            },
            {
                "id": "graphic_gym_floor",
                "label": "Graphic gym floor",
                "direction": (
                    "Use a bold gym floor or training lane graphic as the base plane so the visual feels energetic, branded, and "
                    "easy to layer copy onto."
                ),
                "copy_space": "bottom",
                "hero_placement": "upper hero lane",
                "subject_priority": 8,
                "readability": 10,
                "brand_fit": 8,
                "novelty": 7,
                "supports_sale": 9,
                "supports_editorial": 5,
                "environment_dominance": 4,
                "vertical_friendly": 8,
                "font_style": "bold_tech",
            },
            {
                "id": "stadium_tunnel",
                "label": "Stadium tunnel release",
                "direction": (
                    "Frame the hero in a tunnel or dramatic entry corridor that amplifies anticipation while keeping the subject "
                    "front and center."
                ),
                "copy_space": "top",
                "hero_placement": "center with depth",
                "subject_priority": 9,
                "readability": 8,
                "brand_fit": 8,
                "novelty": 8,
                "supports_sale": 7,
                "supports_editorial": 6,
                "environment_dominance": 5,
                "vertical_friendly": 9,
                "font_style": "bold_tech",
            },
            {
                "id": "performance_studio",
                "label": "Performance studio",
                "direction": (
                    "Use a controlled performance studio with fog, rim light, and a single training prop to keep the message "
                    "clean and high-energy."
                ),
                "copy_space": "right",
                "hero_placement": "left-third anchor",
                "subject_priority": 9,
                "readability": 9,
                "brand_fit": 7,
                "novelty": 7,
                "supports_sale": 8,
                "supports_editorial": 6,
                "environment_dominance": 3,
                "vertical_friendly": 8,
                "font_style": "bold_tech",
            },
        ]

    if is_tech:
        return [
            {
                "id": "device_light_stage",
                "label": "Device light stage",
                "direction": (
                    "Present the product or interface on a disciplined light stage with crisp edge lighting, minimal environment, "
                    "and copy-safe space built into the composition."
                ),
                "copy_space": "right",
                "hero_placement": "left-third object focus",
                "subject_priority": 10,
                "readability": 10,
                "brand_fit": 9,
                "novelty": 7,
                "supports_sale": 8,
                "supports_editorial": 6,
                "environment_dominance": 2,
                "vertical_friendly": 8,
                "font_style": "bold_tech",
            },
            {
                "id": "abstract_signal_plane",
                "label": "Abstract signal plane",
                "direction": (
                    "Use a controlled abstract signal or data-light environment behind the hero so the image feels modern without "
                    "turning into generic neon wallpaper."
                ),
                "copy_space": "left",
                "hero_placement": "right-third anchor",
                "subject_priority": 8,
                "readability": 9,
                "brand_fit": 8,
                "novelty": 8,
                "supports_sale": 7,
                "supports_editorial": 6,
                "environment_dominance": 4,
                "vertical_friendly": 8,
                "font_style": "bold_tech",
            },
            {
                "id": "premium_workspace",
                "label": "Premium workspace hero",
                "direction": (
                    "Show the hero in a premium workspace or executive desk environment with restraint, useful depth, and one strong "
                    "brand color accent."
                ),
                "copy_space": "top",
                "hero_placement": "center-lower focal plane",
                "subject_priority": 8,
                "readability": 9,
                "brand_fit": 8,
                "novelty": 6,
                "supports_sale": 8,
                "supports_editorial": 5,
                "environment_dominance": 4,
                "vertical_friendly": 8,
                "font_style": "bold_tech",
            },
            {
                "id": "architectural_minimal",
                "label": "Architectural minimal set",
                "direction": (
                    "Use a minimal architectural set with sharp light geometry and quiet premium materials so the product reads as "
                    "high-value and modern."
                ),
                "copy_space": "top",
                "hero_placement": "center hero object",
                "subject_priority": 9,
                "readability": 9,
                "brand_fit": 8,
                "novelty": 7,
                "supports_sale": 7,
                "supports_editorial": 6,
                "environment_dominance": 3,
                "vertical_friendly": 9,
                "font_style": "bold_tech",
            },
        ]

    return [
        {
            "id": "studio_gradient",
            "label": "Studio gradient stage",
            "direction": (
                "Keep the hero on a clean studio gradient or shadowed stage so the message stays readable and the subject remains "
                "the first thing people notice."
            ),
            "copy_space": "top",
            "hero_placement": "center-lower focal area",
            "subject_priority": 9,
            "readability": 10,
            "brand_fit": 8,
            "novelty": 6,
            "supports_sale": 8,
            "supports_editorial": 5,
            "environment_dominance": 2,
            "vertical_friendly": 9,
            "font_style": strategy.get("font_style", "bold_tech"),
        },
        {
            "id": "graphic_shadow_set",
            "label": "Graphic shadow set",
            "direction": (
                "Use graphic shadows, one strong surface, and a controlled accent color to create depth without clutter or stock-photo energy."
            ),
            "copy_space": "right",
            "hero_placement": "left-third anchor",
            "subject_priority": 8,
            "readability": 10,
            "brand_fit": 8,
            "novelty": 8,
            "supports_sale": 8,
            "supports_editorial": 6,
            "environment_dominance": 3,
            "vertical_friendly": 8,
            "font_style": strategy.get("font_style", "bold_tech"),
        },
        {
            "id": "architectural_frame",
            "label": "Architectural frame",
            "direction": (
                "Frame the hero with restrained architecture or premium built form, but keep the structure quiet so the focal subject still wins."
            ),
            "copy_space": "top",
            "hero_placement": "center focal axis",
            "subject_priority": 7,
            "readability": 8,
            "brand_fit": 7,
            "novelty": 7,
            "supports_sale": 6,
            "supports_editorial": 6,
            "environment_dominance": 5,
            "vertical_friendly": 8,
            "font_style": strategy.get("font_style", "bold_tech"),
        },
        {
            "id": "lifestyle_context",
            "label": "Lifestyle context scene",
            "direction": (
                "Use a believable lifestyle context with one decisive focal subject and enough negative space that the copy can still lead."
            ),
            "copy_space": "bottom",
            "hero_placement": "upper-center hero",
            "subject_priority": 8,
            "readability": 8,
            "brand_fit": 7,
            "novelty": 6,
            "supports_sale": 7,
            "supports_editorial": 5,
            "environment_dominance": 4,
            "vertical_friendly": 8,
            "font_style": strategy.get("font_style", "bold_tech"),
        },
    ]


def _score_backdrop_direction(candidate: Dict, triage: Dict, strategy: Dict, copy: Dict) -> Dict:
    goal = str(triage.get("goal") or "brand_awareness").lower()
    platform = str(triage.get("platform") or "instagram_portrait").lower()
    text_load = len(str(copy.get("headline") or "")) + len(str(copy.get("subheadline") or ""))
    readability_pressure = 2 if text_load >= 24 else 0
    sale_bonus = candidate.get("supports_sale", 0) if goal in ("sale_promotion", "lead_gen", "event") else 0
    editorial_bonus = candidate.get("supports_editorial", 0) if strategy.get("visual_style") == "editorial" else 0
    vertical_bonus = candidate.get("vertical_friendly", 0) if "portrait" in platform or "story" in platform else 0
    clutter_penalty = max(int(candidate.get("environment_dominance", 5)) - int(candidate.get("subject_priority", 5)), 0)
    center_copy_penalty = readability_pressure if str(candidate.get("copy_space") or "") == "center" else 0

    score_breakdown = {
        "subject_priority": int(candidate.get("subject_priority", 0)) * 2,
        "readability": int(candidate.get("readability", 0)) * 2 + readability_pressure,
        "brand_fit": int(candidate.get("brand_fit", 0)) * 2,
        "novelty": int(candidate.get("novelty", 0)),
        "sale_bonus": int(sale_bonus),
        "editorial_bonus": int(editorial_bonus),
        "vertical_bonus": int(vertical_bonus // 2),
        "clutter_penalty": -int(clutter_penalty),
        "center_copy_penalty": -int(center_copy_penalty),
    }
    score_total = sum(score_breakdown.values())
    ranked = dict(candidate)
    ranked["score_breakdown"] = score_breakdown
    ranked["score_total"] = score_total
    return ranked


def _build_design_room(triage: Dict, brand: Dict, creative: Dict, copy: Dict) -> Dict:
    strategy = _request_strategy(triage, triage.get("original_prompt", ""), brand)
    candidates = _backdrop_candidates_for_request(triage, brand, creative, strategy)
    ranked_candidates = sorted(
        (_score_backdrop_direction(candidate, triage, strategy, copy) for candidate in candidates),
        key=lambda item: item.get("score_total", 0),
        reverse=True,
    )
    winner = ranked_candidates[0] if ranked_candidates else {}
    copy_space = str(winner.get("copy_space") or "bottom")
    body_copy_policy = _infer_body_copy_policy(triage, strategy, copy)
    headline = str(copy.get("headline") or "").strip()
    subheadline = str(copy.get("subheadline") or "").strip()
    discussion = [
        {
            "speaker": "creative_director",
            "message": (
                f"Use the {winner.get('label', 'selected backdrop').lower()}. "
                f"{winner.get('direction', '')} Keep the hero {winner.get('hero_placement', 'clear and dominant')}."
            ).strip(),
        },
        {
            "speaker": "copy_writer",
            "message": (
                f"Keep the {copy_space} copy-safe zone clean for "
                f"{('headline ' + repr(headline)) if headline else 'the main message'}"
                f"{(' and subheadline ' + repr(subheadline)) if subheadline else ''}. "
                f"Body copy policy: {body_copy_policy}."
            ),
        },
        {
            "speaker": "layout_planner",
            "message": (
                f"Reserve the {copy_space} third for typography, avoid placing text over the hero focal plane, "
                f"and use a {winner.get('font_style', strategy.get('font_style', 'bold_tech'))} feel."
            ),
        },
    ]
    summary = (
        f"Winner: {winner.get('label', 'fallback backdrop')} with score {winner.get('score_total', 0)}. "
        f"Prioritize {winner.get('hero_placement', 'hero clarity')}, preserve {copy_space} copy space, "
        f"and keep the composition commercially strong before decorative detail."
    )
    return {
        "strategy": strategy,
        "copy_space": copy_space,
        "font_style": winner.get("font_style", strategy.get("font_style", "bold_tech")),
        "body_copy_policy": body_copy_policy,
        "winner": winner,
        "candidates": ranked_candidates,
        "discussion": discussion,
        "summary": summary,
    }


def _format_design_room_context(design_room: Optional[Dict]) -> str:
    if not design_room:
        return ""
    winner = design_room.get("winner") or {}
    lines = [
        f"Design room consensus: {design_room.get('summary', '')}",
        f"Chosen backdrop: {winner.get('label', '')}",
        f"Backdrop direction: {winner.get('direction', '')}",
        f"Preferred copy space: {design_room.get('copy_space', 'bottom')}",
        f"Typography vibe: {design_room.get('font_style', 'bold_tech')}",
        f"Body copy policy: {design_room.get('body_copy_policy', 'balanced')}",
    ]
    for note in design_room.get("discussion", [])[:3]:
        speaker = str(note.get("speaker") or "").strip()
        message = str(note.get("message") or "").strip()
        if speaker and message:
            lines.append(f"{speaker}: {message}")
    top_candidates = design_room.get("candidates") or []
    if top_candidates:
        ranking = "; ".join(
            f"{candidate.get('label', '')} ({candidate.get('score_total', 0)})"
            for candidate in top_candidates[:3]
        )
        lines.append(f"Taste ranking: {ranking}")
    return "\n".join(line for line in lines if line.strip())


def _designer_wrap_hint(text: str, max_chars_per_line: int, max_lines: int = 3) -> str:
    words = [word for word in str(text or "").split() if word]
    if not words or max_chars_per_line <= 0:
        return str(text or "").strip()

    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars_per_line or len(lines) >= max_lines - 1:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    if len(lines) > max_lines:
        head = lines[: max_lines - 1]
        tail = " ".join(lines[max_lines - 1 :])
        lines = head + [tail]
    return "\n".join(line.strip() for line in lines if line.strip())


def _build_typography_direction(
    triage: Dict,
    brand: Dict,
    creative: Dict,
    copy: Dict,
    design_room: Dict,
) -> Dict:
    prompt_lower = str(triage.get("original_prompt") or "").lower()
    industry = str(triage.get("industry") or "general").lower()
    goal = str(triage.get("goal") or "brand_awareness").lower()
    copy_space = str(design_room.get("copy_space") or "bottom").lower()
    font_style = str(design_room.get("font_style") or brand.get("font_style") or "bold_tech")

    is_event = goal == "event" or any(
        token in prompt_lower for token in ("festival", "concert", "gig", "party", "live", "dj", "music")
    )
    is_luxury = font_style in ("elegant_serif", "luxury_display")
    is_food = industry == "food"

    align = "center"
    if copy_space == "left":
        align = "left"
    elif copy_space == "right":
        align = "right"

    direction = {
        "copy_alignment": align,
        "brand_position": "top_left" if copy_space in ("top", "left") else "top_center",
        "headline_font": "bebas_neue",
        "subheadline_font": "montserrat_bold",
        "body_font": "montserrat_bold",
        "cta_font": "bebas_neue",
        "tagline_font": "montserrat_bold",
        "headline_effect": "shadow_cutout",
        "subheadline_effect": "soft_shadow",
        "body_effect": "soft_shadow",
        "cta_treatment": "pill",
        "copy_space": copy_space,
        "headline_max_chars_per_line": 14,
        "headline_max_lines": 2,
        "subheadline_max_chars_per_line": 18,
        "subheadline_max_lines": 2,
        "body_max_chars_per_line": 28,
        "body_max_lines": 3,
        "cta_max_chars_per_line": 16,
        "show_body": True,
        "show_accent_rule": False,
        "headline_wrap_hint": _designer_wrap_hint(copy.get("headline", ""), 14, 2),
        "subheadline_wrap_hint": _designer_wrap_hint(copy.get("subheadline", ""), 18, 2),
        "body_wrap_hint": _designer_wrap_hint(copy.get("body", ""), 28, 3),
        "cta_wrap_hint": _designer_wrap_hint(copy.get("cta", ""), 16, 2),
    }

    if is_luxury:
        direction.update({
            "headline_font": "playfair",
            "subheadline_font": "raleway_bold",
            "body_font": "raleway_bold",
            "cta_font": "inter_bold",
            "tagline_font": "raleway_bold",
            "headline_effect": "soft_shadow",
            "subheadline_effect": "minimal",
            "body_effect": "minimal",
            "cta_treatment": "ghost",
            "headline_max_chars_per_line": 12,
            "headline_max_lines": 3,
            "subheadline_max_chars_per_line": 16,
            "body_max_chars_per_line": 26,
            "show_body": str(design_room.get("body_copy_policy") or "") != "minimal",
            "show_accent_rule": False,
        })
    elif is_food:
        direction.update({
            "headline_font": "montserrat_black",
            "subheadline_font": "montserrat_bold",
            "body_font": "montserrat_bold",
            "cta_font": "montserrat_black",
            "headline_effect": "soft_shadow",
            "subheadline_effect": "soft_shadow",
            "body_effect": "minimal",
            "cta_treatment": "pill",
            "headline_max_chars_per_line": 16,
            "subheadline_max_chars_per_line": 20,
            "body_max_chars_per_line": 24,
            "show_accent_rule": False,
        })
    elif is_event:
        direction.update({
            "headline_font": "anton",
            "subheadline_font": "montserrat_black",
            "body_font": "montserrat_bold",
            "cta_font": "anton",
            "tagline_font": "montserrat_bold",
            "headline_effect": "glow",
            "subheadline_effect": "shadow_cutout",
            "body_effect": "soft_shadow",
            "cta_treatment": "pill",
            "headline_max_chars_per_line": 12,
            "headline_max_lines": 2,
            "subheadline_max_chars_per_line": 14,
            "body_max_chars_per_line": 26,
            "show_accent_rule": False,
        })

    if goal in ("sale_promotion", "lead_gen") and not is_luxury:
        direction["show_body"] = True
        direction["cta_treatment"] = "pill"

    direction["headline_wrap_hint"] = _designer_wrap_hint(
        copy.get("headline", ""),
        int(direction["headline_max_chars_per_line"]),
        int(direction["headline_max_lines"]),
    )
    direction["subheadline_wrap_hint"] = _designer_wrap_hint(
        copy.get("subheadline", ""),
        int(direction["subheadline_max_chars_per_line"]),
        int(direction["subheadline_max_lines"]),
    )
    direction["body_wrap_hint"] = _designer_wrap_hint(
        copy.get("body", ""),
        int(direction["body_max_chars_per_line"]),
        int(direction["body_max_lines"]),
    )
    direction["cta_wrap_hint"] = _designer_wrap_hint(
        copy.get("cta", ""),
        int(direction["cta_max_chars_per_line"]),
        2,
    )
    return direction

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

## CAMERA & LENS REFERENCES (Worth 50 other modifiers!)
CAMERA MODELS BY USE CASE:
  Portrait: Leica M11 | Hasselblad X2D | Sony A7R V
  Fashion: Phase One IQ4 | Fujifilm GFX 100S
  Street: Leica Q3 | Sony A7 IV | Ricoh GR III
  Product: Hasselblad H6D-400c | Phase One XT | Cambo Actus
  Cinematic: ARRI Alexa 35 | RED V-RAPTOR | Sony VENICE 2

LENS SPECS THAT WORK:
  Bokeh: 85mm f/1.2 | 105mm f/1.4
  Wide: 24mm f/1.4 | 35mm f/1.4
  Telephoto: 200mm f/2.8
  Macro: 100mm macro, 1:1 ratio

USAGE: "Shot on Hasselblad X2D, 85mm f/1.4" → massive quality signal

## FLUX PRO POWER MODIFIERS (Premium only)
  - "[Color] Pantone [code]" → model understands Pantone references precisely
  - "hyper-detailed [material]" → glass/fabric/metal texture rendering
  - "subsurface scattering" → realistic skin (not plastic)
  - "chromatic aberration, subtle" → lens authenticity
  - "[photographer name] photography" → Annie Leibovitz | Roger Deakins | Steve McCurry

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

## QUALITY STACK (Top Tier Signals - use max 5)
✅ USE THESE (Professional signals):
  "award-winning commercial photography"
  "published in [Vogue/WIRED/Wallpaper*/Kinfolk]"
  "[Photographer name] photography" (Annie Leibovitz, Steve McCurry, Roger Deakins)
  "medium format photography"
  "color graded by [reference]"

❌ NEVER USE (Generic noise):
  "hyperrealistic" | "8K" | "trending on artstation" | "masterpiece" | "best quality" | "ultra detailed"

## INDIA MARKET PROMPTS (Cultural Authenticity)
FACES (dignified, specific):
  "Indian {gender}, {age} years old, {skin_tone}, {region} aesthetic, {expression}, {styling}"
  Skin tones: warm brown | medium brown | deep brown | golden brown
  Regions: South Indian | North Indian | Bengali | Punjabi | Marathi
  Styling: contemporary urban | traditional | fusion
  FORBIDDEN: "exotic" | "dusky" | "ethnic" (colonial/othering language)

SETTINGS (authentic):
  Modern: "Contemporary Mumbai apartment, floor-to-ceiling windows, city skyline, clean lines, warm afternoon light"
  Heritage: "Haveli interior, Rajasthan, carved sandstone arches, jali screens, colored glass shadows, antique brass"
  Festival: "Diwali courtyard, clay diyas in rows, marigold garlands, rangoli pattern, families in soft focus"
  Street: "Colaba Causeway/Linking Road, colorful stalls, monsoon-wet streets, golden evening light, authentic crowd"

## NEGATIVE PROMPTS (Model-Specific Artifact Targeting)
BASE (all models): "text, words, letters, signs, watermark, typography, UI overlay, captions"
FLUX portrait add: "plastic skin, smooth skin, overexposed highlights, blown-out whites, lens distortion, unnatural poses, merged hands, extra fingers"
FLUX product add: "floating elements, merged objects, inconsistent shadows"
IDEOGRAM add: "photorealistic, lens blur, noise, photography, camera artifacts"
HUNYUAN add: "harsh lighting, overexposed skin, cartoon, anime, illustration"
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
    # Fix Gemini double-quoted key bug: ""key": → "key":
    # Happens when previous value is empty string "" and Gemini concatenates closing " with opening "
    text = re.sub(r'""([a-zA-Z_][a-zA-Z0-9_]*)"\s*:', r'"\1":', text)
    # Try full parse first (model returned clean JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Regex: find outermost {...} (handles surrounding prose)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidate = match.group()
        # Apply same double-quote key fix on the candidate
        candidate = re.sub(r'""([a-zA-Z_][a-zA-Z0-9_]*)"\s*:', r'"\1":', candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Try to repair truncated JSON: close open strings/objects/arrays
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


# ── BEAST-LEVEL TRIAGE KNOWLEDGE BASES ────────────────────────────────────────

_CULTURAL_MOMENTS_DB = {
    # Indian Festivals
    "diwali": {"type": "seasonal_festival", "keywords": ["celebration", "lights", "prosperity", "fortune"], "palette_override": True},
    "holi": {"type": "seasonal_festival", "keywords": ["color", "joy", "spring", "playful"], "palette_override": True},
    "navratri": {"type": "seasonal_festival", "keywords": ["dance", "energy", "devotion", "vibrant"], "palette_override": True},
    "durga_puja": {"type": "seasonal_festival", "keywords": ["goddess", "power", "tradition", "grand"], "palette_override": True},
    "eid": {"type": "seasonal_festival", "keywords": ["togetherness", "peace", "prayer", "festive"], "palette_override": True},
    "raksha_bandhan": {"type": "seasonal_festival", "keywords": ["sibling", "bond", "protection", "tradition"], "palette_override": False},
    "onam": {"type": "seasonal_festival", "keywords": ["harvest", "unity", "floral", "kerala"], "palette_override": False},
    "pongal": {"type": "seasonal_festival", "keywords": ["harvest", "gratitude", "prosperity", "tamil"], "palette_override": False},
    "baisakhi": {"type": "seasonal_festival", "keywords": ["harvest", "punjab", "energy", "celebration"], "palette_override": False},
    "ugadi": {"type": "seasonal_festival", "keywords": ["new_year", "fresh_start", "tradition", "south"], "palette_override": False},
    "bihu": {"type": "seasonal_festival", "keywords": ["harvest", "assam", "dance", "spring"], "palette_override": False},
    "ganesh_chaturthi": {"type": "seasonal_festival", "keywords": ["new_beginnings", "wisdom", "devotion", "grand"], "palette_override": True},

    # Global Festivals
    "christmas": {"type": "seasonal_festival", "keywords": ["joy", "giving", "family", "festive"], "palette_override": True},
    "new_year": {"type": "seasonal_festival", "keywords": ["fresh_start", "celebration", "resolution", "optimism"], "palette_override": False},
    "valentine": {"type": "seasonal_festival", "keywords": ["romance", "love", "passion", "connection"], "palette_override": True},
    "women_day": {"type": "seasonal_festival", "keywords": ["empowerment", "strength", "equality", "celebration"], "palette_override": False},

    # Global Events
    "world_cup": {"type": "global_moment", "keywords": ["passion", "competition", "pride", "energy"], "palette_override": False},
    "olympics": {"type": "global_moment", "keywords": ["excellence", "unity", "achievement", "glory"], "palette_override": False},
    "ipl": {"type": "global_moment", "keywords": ["cricket", "excitement", "energy", "india"], "palette_override": False},
    "super_bowl": {"type": "global_moment", "keywords": ["sports", "entertainment", "grand", "american"], "palette_override": False},

    # Industry Moments
    "sale_season": {"type": "industry_moment", "keywords": ["urgency", "deals", "limited_time", "excitement"], "palette_override": False},
    "black_friday": {"type": "industry_moment", "keywords": ["massive_deals", "urgency", "shopping", "excitement"], "palette_override": False},
    "cyber_monday": {"type": "industry_moment", "keywords": ["online_deals", "tech", "urgency", "digital"], "palette_override": False},
    "independence_day": {"type": "seasonal_festival", "keywords": ["patriotic", "pride", "freedom", "national"], "palette_override": True},
}

_EMOTION_LIBRARY = {
    # Primary emotions with trigger patterns
    "urgency": ["sale", "limited", "today", "now", "hurry", "ends", "last_chance", "flash", "24h", "asap"],
    "desire": ["luxury", "premium", "exclusive", "indulge", "crave", "want", "dream", "perfect"],
    "trust": ["proven", "certified", "guarantee", "safe", "reliable", "authentic", "verified", "expert"],
    "curiosity": ["discover", "reveal", "secret", "new", "unlock", "find_out", "explore", "learn"],
    "pride": ["achieve", "accomplish", "winner", "best", "champion", "elite", "master", "pro"],
    "nostalgia": ["classic", "vintage", "remember", "tradition", "heritage", "timeless", "original"],
    "aspiration": ["transform", "become", "upgrade", "elevate", "level_up", "grow", "advance", "next_level"],
    "belonging": ["community", "together", "join", "family", "connect", "tribe", "belong", "we"],
    "exclusivity": ["exclusive", "members", "vip", "limited", "private", "select", "invite", "elite"],
    "joy": ["happy", "fun", "celebrate", "smile", "enjoy", "delight", "cheerful", "bright"],
    "calm": ["peace", "relax", "serene", "tranquil", "harmony", "zen", "soothing", "gentle"],
    "power": ["strong", "bold", "fierce", "unstoppable", "dominant", "force", "mighty", "conquer"],
    "rebellion": ["break", "disrupt", "rebel", "challenge", "different", "unconventional", "dare"],
    "warmth": ["cozy", "comfort", "nurture", "care", "home", "embrace", "tender", "loving"],
    "awe": ["amazing", "stunning", "breathtaking", "spectacular", "magnificent", "extraordinary"],
    "fomo": ["missing_out", "everyone", "trending", "viral", "popular", "hottest", "everyone_is"],
    "excitement": ["thrill", "adventure", "dynamic", "energetic", "electrifying", "pumped", "fired_up"],
}

_PSYCHOGRAPHIC_MAP = {
    # Industry + Tone → Psychographic
    ("fitness", "bold"): "achiever",
    ("fitness", "energetic"): "achiever",
    ("fashion", "luxury"): "status-seeker",
    ("fashion", "elegant"): "status-seeker",
    ("tech", "professional"): "achiever",
    ("saas", "professional"): "pragmatist",
    ("food", "playful"): "belonging-seeker",
    ("food", "professional"): "value-seeker",
    ("real_estate", "professional"): "security-seeker",
    ("finance", "professional"): "security-seeker",
    ("healthcare", "professional"): "security-seeker",
    ("education", "professional"): "pragmatist",
    ("general", "playful"): "explorer",
    ("general", "energetic"): "explorer",
    ("general", "minimal"): "creative",
    ("general", "bold"): "achiever",
}

_ATTENTION_BUDGET_MAP = {
    # Platform → Seconds
    "instagram_story": 2,
    "tiktok_story": 0.5,
    "instagram_portrait": 2,
    "instagram_square": 2,
    "facebook_landscape": 3,
    "linkedin": 5,
    "youtube_thumbnail": 1,
    "twitter": 2,
    "pinterest": 3,
    "print_flyer": 10,
    "print_a4": 10,
    "banner_leaderboard": 1,
    "banner_rectangle": 2,
    "default": 2,
}

_PIPELINE_ROUTING_RULES = {
    # Complexity markers → pipeline mode
    "fast_path_keywords": ["simple", "quick", "basic", "minimal", "clean", "single"],
    "premium_keywords": ["campaign", "launch", "complex", "multiple", "professional", "festival", "cultural"],
    "urgency_keywords": ["urgent", "asap", "today", "now", "immediately", "rush", "emergency"],
}


def _detect_cultural_moment(prompt: str) -> Optional[Dict]:
    """Detect cultural/seasonal moments from prompt."""
    prompt_lower = prompt.lower()

    for moment_key, moment_data in _CULTURAL_MOMENTS_DB.items():
        if moment_key in prompt_lower:
            return {
                "type": moment_data["type"],
                "name": moment_key.replace("_", " ").title(),
                "palette_override": moment_data["palette_override"],
                "keywords": moment_data["keywords"],
            }

    return None


def _detect_emotion_target(prompt: str, goal: str) -> str:
    """Detect primary emotional target from prompt and goal."""
    prompt_lower = prompt.lower()

    # Score each emotion
    scores = {}
    for emotion, triggers in _EMOTION_LIBRARY.items():
        score = sum(1 for trigger in triggers if trigger in prompt_lower)
        if score > 0:
            scores[emotion] = score

    # Goal-based defaults
    goal_emotion_map = {
        "sale_promotion": "urgency",
        "product_launch": "curiosity",
        "brand_awareness": "aspiration",
        "event": "excitement",
        "lead_gen": "curiosity",
        "app_download": "desire",
    }

    if scores:
        # Return highest scoring emotion
        return max(scores.items(), key=lambda x: x[1])[0]
    else:
        # Fallback to goal-based emotion
        return goal_emotion_map.get(goal, "aspiration")


def _detect_psychographic(industry: str, tone: str, prompt: str) -> str:
    """Detect audience psychographic from industry, tone, and prompt context."""
    # Try exact mapping first
    key = (industry, tone)
    if key in _PSYCHOGRAPHIC_MAP:
        return _PSYCHOGRAPHIC_MAP[key]

    # Fallback: industry-based defaults
    industry_defaults = {
        "fitness": "achiever",
        "fashion": "status-seeker",
        "tech": "achiever",
        "saas": "pragmatist",
        "food": "value-seeker",
        "real_estate": "security-seeker",
        "finance": "security-seeker",
        "healthcare": "security-seeker",
        "education": "pragmatist",
    }

    return industry_defaults.get(industry, "explorer")


def _detect_pipeline_mode(prompt: str, industry: str, cultural_moment: Optional[Dict], brand_hint: str) -> str:
    """Intelligent pipeline routing based on complexity signals."""
    prompt_lower = prompt.lower()

    # Crisis mode - urgent keywords
    if any(keyword in prompt_lower for keyword in _PIPELINE_ROUTING_RULES["urgency_keywords"]):
        return "crisis"

    # Premium mode triggers
    premium_triggers = 0

    # Cultural sensitivity
    if cultural_moment and cultural_moment.get("palette_override"):
        premium_triggers += 1

    # Complex keywords
    if any(keyword in prompt_lower for keyword in _PIPELINE_ROUTING_RULES["premium_keywords"]):
        premium_triggers += 1

    # Known brand (database lookup will happen)
    if brand_hint and len(brand_hint) > 2:
        premium_triggers += 1

    # Long prompt = complex requirement
    if len(prompt) > 200:
        premium_triggers += 1

    # Industry complexity
    if industry in ("fashion", "finance", "healthcare"):
        premium_triggers += 1

    if premium_triggers >= 3:
        return "premium"

    # Fast path triggers
    if any(keyword in prompt_lower for keyword in _PIPELINE_ROUTING_RULES["fast_path_keywords"]):
        if premium_triggers == 0:
            return "fast_path"

    # Default: standard
    return "standard"


def _detect_cultural_context(industry: str, prompt: str) -> str:
    """Detect cultural/geographic context from industry and prompt."""
    prompt_lower = prompt.lower()

    # Tier-1 metro markers
    metro_markers = ["mumbai", "delhi", "bangalore", "pune", "hyderabad", "chennai", "kolkata", "metro", "urban", "city"]
    if any(marker in prompt_lower for marker in metro_markers):
        return "tier1_metro"

    # Tier-2 India markers
    tier2_markers = ["tier2", "tier-2", "small_city", "town", "regional", "local", "indian"]
    if any(marker in prompt_lower for marker in tier2_markers):
        return "tier2_india"

    # Western markers
    western_markers = ["global", "international", "western", "us", "uk", "europe", "america"]
    if any(marker in prompt_lower for marker in western_markers):
        return "western"

    # Default: tier1_metro (Indian market default)
    return "tier1_metro"


def _detect_device_context(platform: str) -> str:
    """Detect device context from platform."""
    mobile_platforms = ["instagram_story", "tiktok_story", "instagram_portrait", "instagram_square"]
    desktop_platforms = ["linkedin", "banner_leaderboard", "banner_rectangle"]

    if platform in mobile_platforms:
        return "mobile-first"
    elif platform in desktop_platforms:
        return "desktop-work"
    elif platform == "youtube_thumbnail":
        return "large-screen-tv"
    else:
        return "mobile-first"  # Default


# ── Individual agents (all async) ─────────────────────────────────────────────

async def _agent_triage(prompt: str) -> Dict:
    """
    BEAST-LEVEL TRIAGE AGENT — Military-grade request intelligence.

    Phase 1: Basic Classification (LLM)
    Phase 2: Cultural Intelligence (Heuristic)
    Phase 3: Audience Intelligence (Heuristic)
    Phase 4: Emotional Target (Heuristic)
    Phase 5: Pipeline Routing (Heuristic)

    Output: Comprehensive triage package with 20+ fields.
    """

    # ── PHASE 1: LLM-Based Basic Classification ──────────────────────────────────
    system = (
        "You are a senior marketing strategist AND platform expert with 15+ years at Wieden+Kennedy.\n"
        "Your job: decode what the client ACTUALLY needs, even from a poorly written brief.\n"
        "\n"
        "== PLATFORM FORMAT KNOWLEDGE ==\n"
        f"{_PLATFORM_FORMATS_KB}\n"
        "== END KNOWLEDGE ==\n"
        "\n"
        "CRITICAL RULES:\n"
        "1. If user quoted specific text (e.g. 'headline: TRANSFORM'), extract it EXACTLY to explicit_headline\n"
        "2. Infer industry from context: 'gym'→fitness, 'cafe'→food, 'app launch'→saas\n"
        "3. Detect festivals: 'Diwali sale'→is_festival=true, festival_name='diwali'\n"
        "4. Use INFERENCE RULES to pick the correct platform\n"
        "5. Brand hint: extract brand/product name if mentioned\n"
        "\n"
        "Return ONLY valid JSON:\n"
        '{\n'
        '  "creative_type": "ad|poster|social_post|banner|story|thumbnail",\n'
        '  "platform": "instagram_portrait|instagram_square|instagram_story|facebook_landscape|twitter|linkedin|youtube_thumbnail|pinterest|tiktok_story|print_flyer|print_a4|banner_leaderboard|banner_rectangle|banner_half_page|default",\n'
        '  "goal": "product_launch|brand_awareness|sale_promotion|event|app_download|lead_gen",\n'
        '  "audience": "b2b|b2c|youth|professional|general",\n'
        '  "brand_hint": "brand or product name if mentioned, else empty",\n'
        '  "industry": "saas|food|fashion|fitness|real_estate|healthcare|finance|education|tech|general",\n'
        '  "tone": "professional|playful|luxury|energetic|minimal|bold|elegant",\n'
        '  "explicit_headline": "exact quoted headline text or empty",\n'
        '  "explicit_cta": "exact quoted CTA text or empty",\n'
        '  "explicit_subheadline": "exact quoted subheadline or empty",\n'
        '  "is_festival": false,\n'
        '  "festival_name": ""\n'
        '}'
    )

    raw = await _acall_gemini(system, "Design request: " + prompt, temperature=0.3, agent_name="triage")
    r = _extract_json(raw)

    # Base defaults
    triage = {
        "creative_type": "poster",
        "platform": "instagram_portrait",
        "goal": "brand_awareness",
        "audience": "general",
        "brand_hint": "",
        "industry": "general",
        "tone": "professional",
        "explicit_headline": "",
        "explicit_cta": "",
        "explicit_subheadline": "",
        "is_festival": False,
        "festival_name": "",
    }

    # Merge LLM output
    for k, v in r.items():
        if v is not None and not k.startswith("_"):
            triage[k] = v

    # Extract explicit texts (fallback if LLM missed quoted text)
    explicit_text = _extract_explicit_texts(prompt)
    for key, value in explicit_text.items():
        if value and not str(triage.get(key) or "").strip():
            triage[key] = value

    # ── PHASE 2: Cultural Moment Detection ───────────────────────────────────────
    cultural_moment = _detect_cultural_moment(prompt)
    if not cultural_moment and triage.get("is_festival") and triage.get("festival_name"):
        # LLM detected festival, build cultural moment object
        festival_key = triage["festival_name"].lower().replace(" ", "_")
        festival_data = _CULTURAL_MOMENTS_DB.get(festival_key)
        if festival_data:
            cultural_moment = {
                "type": festival_data["type"],
                "name": triage["festival_name"],
                "palette_override": festival_data["palette_override"],
                "keywords": festival_data["keywords"],
            }

    triage["cultural_moment"] = cultural_moment

    # ── PHASE 3: Emotional Target ────────────────────────────────────────────────
    emotion_target = _detect_emotion_target(prompt, triage["goal"])
    triage["emotion_target"] = emotion_target

    # ── PHASE 4: Audience Intelligence ───────────────────────────────────────────
    psychographic = _detect_psychographic(triage["industry"], triage["tone"], prompt)
    cultural_context = _detect_cultural_context(triage["industry"], prompt)
    device_context = _detect_device_context(triage["platform"])
    attention_budget = _ATTENTION_BUDGET_MAP.get(triage["platform"], 2)

    # Age range inference (basic heuristic)
    age_range = [18, 45]  # Default
    if "youth" in triage["audience"] or "gen-z" in prompt.lower() or "young" in prompt.lower():
        age_range = [18, 25]
    elif "b2b" in triage["audience"] or "professional" in triage["audience"]:
        age_range = [25, 45]
    elif "senior" in prompt.lower() or "mature" in prompt.lower():
        age_range = [45, 65]

    triage["audience_intelligence"] = {
        "age_range": age_range,
        "psychographic": psychographic,
        "cultural_context": cultural_context,
        "device_context": device_context,
        "attention_budget_seconds": attention_budget,
    }

    # ── PHASE 5: Pipeline Routing ────────────────────────────────────────────────
    pipeline_mode = _detect_pipeline_mode(prompt, triage["industry"], cultural_moment, triage["brand_hint"])

    # Urgency classification
    urgency_map = {
        "crisis": "critical",
        "premium": "premium",
        "standard": "standard",
        "fast_path": "draft",
    }
    urgency = urgency_map.get(pipeline_mode, "standard")

    triage["pipeline_mode"] = pipeline_mode
    triage["urgency"] = urgency
    triage["quality_passes"] = 1  # Default (Quality Critic will decide if 2nd pass needed)

    # ── PHASE 6: Platform Dimensions ─────────────────────────────────────────────
    dims = _PLATFORM_DIMS.get(triage["platform"], _PLATFORM_DIMS["default"])
    triage["recommended_width"] = dims[0]
    triage["recommended_height"] = dims[1]

    return triage


async def _agent_brand_intel(
    triage: Dict,
    brand_kit: Optional[Dict],
    prompt: str,
) -> Dict:
    """Enhanced brand intelligence with full palette system, typography DNA, visual equity."""
    if _BRAND_INTEL_AGENT_AVAILABLE:
        try:
            # Use enhanced Brand Intelligence Agent (Phase 1-7)
            result = await brand_intel_agent.extract(prompt, triage, brand_kit)
            return result.get("brand_intelligence", result)
        except Exception as e:
            logger.warning("[design_chain] Enhanced brand_intel failed (%s), falling back to basic", e)

    # Fallback: Basic brand intel (legacy)
    defaults = _request_strategy(triage, prompt)
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
        "font_style":      r.get("font_style", defaults["font_style"]),
        "tone":            r.get("tone", defaults["tone"]),
        "tagline":         r.get("tagline", ""),
        "logo_url":        "",
    }
    if result["font_style"] == "bold_tech" and defaults["font_style"] != "bold_tech":
        result["font_style"] = defaults["font_style"]
    if result["tone"] == "professional" and defaults["tone"] != "professional":
        result["tone"] = defaults["tone"]
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

    strategy = _request_strategy(triage, prompt, brand)
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

    # ── BEAST CONFIG: Auto-detect aesthetic from industry + keywords ──────────
    aesthetic_id = beast_config.detect_aesthetic_by_industry(industry)
    # Override if prompt has specific aesthetic keywords
    keyword_aesthetic = beast_config.detect_aesthetic_by_keywords(prompt)
    if keyword_aesthetic and keyword_aesthetic != "ai_native":
        aesthetic_id = keyword_aesthetic

    aesthetic_data = beast_config.get_aesthetic(aesthetic_id) or {}
    aesthetic_direction = aesthetic_data.get("visual_direction", {})
    aesthetic_prompt_lang = aesthetic_data.get("prompt_language", {})

    # Inject aesthetic into creative guardrails
    if aesthetic_direction:
        logger.info(f"[creative_director] Aesthetic: {aesthetic_id} (trend: {aesthetic_data.get('trend_strength', 0)})")

    # Extract generation profile for cultural/generational alignment
    generation_profile_id = triage.get("generation_profile", "mass_market_india")
    gen_profile = beast_config.get_generation_profile(generation_profile_id) or {}
    gen_aesthetic = gen_profile.get("aesthetic_preference", {})

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
        f"- Commercial taste guardrails: {strategy['creative_guardrails']}\n"
        f"- Detail budget: {strategy['detail_budget']}\n"
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
        '"composition_archetype":"hero_dominant|split_60_40|typographic_led|frame_within_frame|dynamic_diagonal|asymmetric_grid|full_bleed"}}'
    )
    # Beast-level context enrichment
    emotion_target = triage.get("emotion_target", "aspiration")
    cultural_moment = triage.get("cultural_moment")
    audience_intel = triage.get("audience_intelligence", {})
    psychographic = audience_intel.get("psychographic", "general")
    attention_budget = audience_intel.get("attention_budget_seconds", 2)

    cultural_context = ""
    if cultural_moment:
        cultural_context = (
            f"\n🎯 CULTURAL MOMENT: {cultural_moment['name']} ({cultural_moment['type']})\n"
            f"   Keywords: {', '.join(cultural_moment['keywords'])}\n"
            f"   Palette Override: {'YES — use festival colors' if cultural_moment.get('palette_override') else 'NO — keep brand colors'}"
        )

    # Aesthetic vocabulary for Gemini
    aesthetic_hint = ""
    if aesthetic_direction:
        color_palette = aesthetic_direction.get("color_palette", [])
        lighting = aesthetic_direction.get("lighting_style", "")
        composition = aesthetic_direction.get("composition", "")
        aesthetic_hint = (
            f"\n🎨 AESTHETIC CODE ({aesthetic_id.upper()}, trend strength: {aesthetic_data.get('trend_strength', 0)}/10):\n"
            f"   Colors: {', '.join(color_palette[:4]) if color_palette else 'Use brand colors'}\n"
            f"   Lighting: {lighting}\n"
            f"   Composition: {composition}\n"
        )

    gen_hint = ""
    if gen_aesthetic:
        preferred_styles = gen_aesthetic.get("preferred_visual_styles", [])
        forbidden_styles = gen_aesthetic.get("avoid", [])
        if preferred_styles or forbidden_styles:
            gen_hint = (
                f"\n👥 GENERATION PROFILE ({generation_profile_id.replace('_', ' ').title()}):\n"
                f"   Preferred: {', '.join(preferred_styles[:3]) if preferred_styles else 'Any'}\n"
                f"   Avoid: {', '.join(forbidden_styles[:3]) if forbidden_styles else 'None'}\n"
            )

    context = (
        f"Brief: {prompt}\n"
        f"Brand: {brand.get('brand_name','')} | Tone: {brand.get('tone','')} | Industry: {industry}\n"
        f"Platform: {platform} | Goal: {goal} | Audience: {triage.get('audience','general')}\n"
        f"Primary color: {palette.get('primary','#6C63FF')} | Secondary: {palette.get('secondary','#4FACFE')}\n"
        f"\n🎯 BEAST-LEVEL INTELLIGENCE:\n"
        f"   Target Emotion: {emotion_target.upper()} — Your creative direction MUST trigger this emotion\n"
        f"   Psychographic: {psychographic} — Design for this mindset\n"
        f"   Attention Budget: {attention_budget}s — You have THIS LONG to make impact{cultural_context}{aesthetic_hint}{gen_hint}\n"
        f"\nCreative guardrails: {strategy['creative_guardrails']}"
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
    for forbidden in [s.strip() for s in strategy["negative_guardrails"].split(",") if s.strip()]:
        if forbidden not in creative_bible["forbidden_elements"]:
            creative_bible["forbidden_elements"].append(forbidden)

    # ── BEAST MODE: Enrich Creative Bible with Cultural Intelligence ──────────
    if _CULTURAL_INTELLIGENCE_AVAILABLE:
        try:
            creative_bible = CulturalIntelligence.enrich_with_cultural_context(
                creative_bible=creative_bible,
                industry=industry,
                audience=triage.get("audience", "general"),
                platform=platform
            )
            logger.info(f"[creative_director] Cultural Intelligence: {creative_bible.get('cultural_intelligence', {}).get('aesthetic_direction')}")
        except Exception as e:
            logger.warning(f"[creative_director] Cultural Intelligence enrichment failed: {e}")

    layout_archetype = str(r.get("layout_archetype") or strategy["layout_archetype"])
    hero_occupies = str(r.get("hero_occupies") or strategy["hero_occupies"])
    visual_style = str(r.get("visual_style") or strategy["visual_style"])
    if strategy["font_style"] in ("elegant_serif", "luxury_display"):
        if layout_archetype not in ("hero_dominant", "frame_within_frame", "asymmetric_grid", "full_bleed"):
            layout_archetype = strategy["layout_archetype"]
        if hero_occupies not in ("center_50", "top_50", "full_bleed"):
            hero_occupies = strategy["hero_occupies"]
        if visual_style == "photorealistic":
            visual_style = strategy["visual_style"]

    return {
        "theme":            r.get("theme", "bold"),
        "mood":             r.get("mood", "energetic"),
        "visual_style":     visual_style,
        "layout_archetype": layout_archetype,
        "hero_occupies":    hero_occupies,
        "atmosphere":       r.get("atmosphere", ""),
        "avoid":            r.get("avoid") if isinstance(r.get("avoid"), list) else [],
        "palette":          palette,
        "creative_bible":   creative_bible,
        "detail_budget":    strategy["detail_budget"],
        "image_guardrails": strategy["image_guardrails"],
    }


async def _agent_copy_writer(
    triage: Dict,
    brand: Dict,
    creative: Dict,
    prompt: str,
) -> Dict:
    strategy = _request_strategy(triage, prompt, brand)
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

    # Beast-level intelligence injection
    emotion_target = triage.get("emotion_target", "aspiration")
    cultural_moment = triage.get("cultural_moment")
    audience_intel = triage.get("audience_intelligence", {})
    psychographic = audience_intel.get("psychographic", "general")

    festival_hint = ""
    if cultural_moment:
        festival_hint = f"\nCultural Moment: {cultural_moment['name']} — weave in {', '.join(cultural_moment['keywords'][:2])}."
    elif triage.get("is_festival") and triage.get("festival_name"):
        festival_hint = f"\nFestival context: {triage['festival_name']} — include cultural warmth."

    # Creative Bible injection — copy must align with the locked emotional territory
    bible = creative.get("creative_bible") or {}
    bible_hint = ""
    if bible.get("emotional_territory"):
        bible_hint += f'\nCreative Bible — emotional territory: "{bible["emotional_territory"]}"'
        bible_hint += " — every word of copy must evoke this feeling."
    if bible.get("forbidden_elements"):
        bible_hint += f'\nForbidden: avoid themes of: {", ".join(bible["forbidden_elements"][:3])}'

    # Psychographic copy hints
    psycho_map = {
        "achiever": "Use performance, results, transformation language.",
        "value-seeker": "Emphasize savings, smart choice, ROI.",
        "status-seeker": "Use exclusivity, premium, elevated status language.",
        "security-seeker": "Use trust, safety, reliability language.",
        "explorer": "Use adventure, discovery, new experience language.",
    }
    psycho_hint = f"\nPsychographic: {psychographic} — {psycho_map.get(psychographic, '')}"
    emotion_hint = f"\nTarget Emotion: {emotion_target.upper()} — trigger this emotion in headline."

    system = (
        f"You are a world-class Ad Copywriter (Ogilvy / Leo Burnett level).\n"
        f"Platform: {platform}. Tone: {brand.get('tone','bold')}. "
        f"Goal: {triage.get('goal','brand_awareness')}. Industry: {triage.get('industry','general')}.\n"
        f"Think deeply about what this business needs. Write copy that converts.\n"
        f"Commercial copy guardrails: {strategy['copy_guardrails']}\n"
        f"HEADLINE max {hl_max} chars ALL CAPS.{festival_hint}{explicit_hint}{bible_hint}{psycho_hint}{emotion_hint}\n"
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
    design_room: Optional[Dict] = None,
    design_decree: Optional[Dict] = None,
    variant: str = "safe",  # "safe" | "bold" | "disruptive"
) -> List[Dict]:
    """
    Gemini-powered layout agent — thinks about optimal element placement
    for a full-bleed poster (hero image fills 100% canvas, text overlaid).
    Returns normalized Fabric.js element list (x/y/w/h in 0.0–1.0 range).

    NEW: Supports 3 variants via variant parameter:
    - safe: Proven composition, minimal risk, commercial-first
    - bold: Strong execution, branded distinctiveness, confident
    - disruptive: Breaks conventions intentionally, attention-maximizing
    """
    palette = creative.get("palette", {})
    pri = _safe_hex(palette.get("primary"), "#6C63FF")
    txt = _safe_hex(palette.get("text_primary"), "#FFFFFF")
    sec = _safe_hex(palette.get("text_secondary"), "#CCCCDD")

    has_brand    = bool(str(copy.get("brand_name") or "").strip())
    has_sub      = bool(str(copy.get("subheadline") or "").strip())
    has_body     = bool(str(copy.get("body") or "").strip())
    has_cta      = bool(str(copy.get("cta") or "").strip())
    has_tagline  = bool(str(copy.get("tagline") or "").strip())
    headline_len = len(str(copy.get("headline") or ""))
    design_room_context = _format_design_room_context(design_room)
    preferred_copy_space = str((design_room or {}).get("copy_space") or "").strip()
    preferred_font_style = str((design_room or {}).get("font_style") or "").strip()
    chosen_backdrop = str(((design_room or {}).get("winner") or {}).get("label") or "").strip()

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
        "4. Body copy: optional, below subheadline, keep it short and readable\n"
        "5. CTA button: pinned near bottom, y=0.80–0.86\n"
        "6. Tagline: very bottom, y=0.91–0.95\n"
        "7. NOTHING exceeds y=0.97\n"
        "8. Landscape (16:9): text left-aligned x=0.05–0.50, hero fills right\n"
        "9. Story (9:16): generous vertical spacing, bigger fonts\n"
        "10. Font choice: prefer bebas_neue/anton for headlines, montserrat_bold for body\n"
        "11. If a preferred copy-safe zone is provided, honor it unless readability becomes impossible\n"
        "\n"
        "Return ONLY a raw JSON array (no object wrapper, no prose, no markdown). Start with `[` and end with `]`.\n"
        "Each element:\n"
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
        f"Body: {copy.get('body','')}\n"
        f"CTA: {copy.get('cta','')}\n"
        f"Tagline: {copy.get('tagline','')}\n"
        f"Mood: {creative.get('mood','')}\n"
        f"Accent color: {pri}\n"
        f"Has brand: {has_brand}, Has sub: {has_sub}, Has body: {has_body}, Has CTA: {has_cta}, Has tagline: {has_tagline}\n"
        f"Preferred copy space: {preferred_copy_space or 'unspecified'}\n"
        f"Preferred font vibe: {preferred_font_style or 'unspecified'}\n"
        f"Chosen backdrop: {chosen_backdrop or 'unspecified'}\n"
        f"{design_room_context}"
    )

    raw = await _acall_gemini(system, context, temperature=0.3, agent_name="layout_planner")

    # Parse — expect JSON array
    raw = raw.strip()
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    def _try_parse_elements(s: str) -> Optional[List]:
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list) and parsed:
                return parsed
            # Gemini sometimes wraps: {"elements": [...]} or {"layout": [...]}
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list) and v:
                        return v
        except Exception:
            pass
        return None

    elements = _try_parse_elements(raw)
    if elements:
        logger.info("[layout_planner] Gemini placed %d elements", len(elements))
        return elements

    # Try extracting [...] from prose wrapper
    arr_match = re.search(r"\[[\s\S]*\]", raw)
    if arr_match:
        elements = _try_parse_elements(arr_match.group())
        if elements:
            logger.info("[layout_planner] Gemini placed %d elements (extracted)", len(elements))
            return elements

    # Fallback: deterministic full-bleed layout
    logger.warning("[layout_planner] Gemini failed, using deterministic full-bleed layout")
    return _layout_fallback(copy, creative, aspect_ratio, copy_space=preferred_copy_space or "bottom")


def _score_layout_variant(
    elements: List[Dict],
    variant_type: str,
    creative_bible: Dict,
    design_decree: Optional[Dict] = None,
) -> float:
    """
    Simple jury scorer for layout variants.
    Returns score 0.0-10.0 based on hierarchy, readability, brand fit.

    Scoring:
    - safe: High brand fit, proven patterns (7.5-8.5 baseline)
    - bold: Strong execution, visual tension (7.0-9.0 range)
    - disruptive: Attention-maximizing, risk-taking (6.5-9.5 range)
    """
    if not elements:
        return 0.0

    score = 5.0  # Base score

    # Check hierarchy (headline should exist and be prominent)
    headline_found = any(e.get("id") == "headline" for e in elements)
    cta_found = any(e.get("id") in ["cta_button", "cta"] for e in elements)

    if headline_found:
        score += 1.5
    if cta_found:
        score += 1.0

    # Check y-positions (nothing should exceed 0.97)
    max_y = max((e.get("bounds", {}).get("y", 0) + e.get("bounds", {}).get("h", 0)) for e in elements)
    if max_y <= 0.97:
        score += 1.0
    else:
        score -= 1.0  # Penalty for overflow

    # Variant-specific scoring
    if variant_type == "safe":
        # Prefer centered layouts, proven patterns
        headline_el = next((e for e in elements if e.get("id") == "headline"), None)
        if headline_el:
            x = headline_el.get("bounds", {}).get("x", 0.5)
            # Centered headline gets bonus (x close to 0.05 for full-width centered)
            if 0.03 <= x <= 0.07:
                score += 1.0
        score += 0.5  # Safe baseline bonus

    elif variant_type == "bold":
        # Prefer asymmetry, visual tension
        headline_el = next((e for e in elements if e.get("id") == "headline"), None)
        if headline_el:
            x = headline_el.get("bounds", {}).get("x", 0.5)
            w = headline_el.get("bounds", {}).get("w", 0.9)
            # Asymmetric positioning gets bonus
            if x < 0.30 or x > 0.30:
                score += 0.8
            # Larger headline bonus
            if w > 0.80:
                score += 0.5

    elif variant_type == "disruptive":
        # Prefer unconventional, high impact
        cta_el = next((e for e in elements if e.get("id") in ["cta_button", "cta"]), None)
        if cta_el:
            y = cta_el.get("bounds", {}).get("y", 0.82)
            # Unconventional CTA placement bonus
            if y < 0.75 or y > 0.90:
                score += 1.0
        score += 0.3  # Risk-taking baseline

    # Cap score at 10.0
    return min(score, 10.0)


def _layout_fallback(copy: Dict, creative: Dict, aspect_ratio: float, copy_space: str = "bottom") -> List[Dict]:
    """Deterministic full-bleed layout — all elements on image, nothing below."""
    palette = creative.get("palette", {})
    pri = _safe_hex(palette.get("primary"), "#6C63FF")
    txt = _safe_hex(palette.get("text_primary"), "#FFFFFF")
    sec = _safe_hex(palette.get("text_secondary"), "#CCCCDD")

    elements: List[Dict] = []
    copy_space = str(copy_space or "bottom").lower()
    headline_x = 0.05
    headline_w = 0.90
    headline_y = 0.52
    sub_y = 0.67
    body_y = 0.74
    cta_x = 0.10
    cta_w = 0.80
    text_align = "center"

    if copy_space == "top":
        headline_y = 0.12
        sub_y = 0.26
        body_y = 0.34
    elif copy_space == "left":
        headline_x = 0.06
        headline_w = 0.42
        headline_y = 0.30
        sub_y = 0.47
        body_y = 0.56
        cta_x = 0.06
        cta_w = 0.36
        text_align = "left"
    elif copy_space == "right":
        headline_x = 0.52
        headline_w = 0.42
        headline_y = 0.30
        sub_y = 0.47
        body_y = 0.56
        cta_x = 0.58
        cta_w = 0.30
        text_align = "right"

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
            "bounds": {"x": headline_x, "y": headline_y, "w": headline_w, "h": 0.14},
            "style": {"font": "bebas_neue", "size_role": "headline", "color": txt, "align": text_align},
            "content": headline, "locked": False})

    # Subheadline at 67%
    sub = str(copy.get("subheadline") or "")
    if sub:
        elements.append({"id": "subheadline", "type": "text",
            "bounds": {"x": headline_x, "y": sub_y, "w": headline_w, "h": 0.06},
            "style": {"font": "montserrat_bold", "size_role": "subheadline", "color": sec, "align": text_align},
            "content": sub, "locked": False})

    body = str(copy.get("body") or "")
    if body:
        elements.append({"id": "body_text", "type": "text",
            "bounds": {"x": headline_x, "y": body_y, "w": headline_w, "h": 0.10},
            "style": {"font": "montserrat_bold", "size_role": "body", "color": sec, "align": text_align},
            "content": body, "locked": False})

    # CTA at 80%
    cta = str(copy.get("cta") or "")
    if cta:
        elements.append({"id": "cta_button", "type": "shape",
            "bounds": {"x": cta_x, "y": 0.80, "w": cta_w, "h": 0.08},
            "style": {"fill": pri, "radius": 40, "opacity": 1.0}, "content": "", "locked": False})
        elements.append({"id": "cta_text", "type": "text",
            "bounds": {"x": cta_x, "y": 0.80, "w": cta_w, "h": 0.08},
            "style": {"font": "bebas_neue", "size_role": "cta", "color": txt, "align": text_align},
            "content": cta, "locked": False})

    # Tagline at 91%
    tagline = str(copy.get("tagline") or "")
    if tagline:
        elements.append({"id": "tagline", "type": "text",
            "bounds": {"x": 0.05, "y": 0.91, "w": 0.90, "h": 0.04},
            "style": {"font": "montserrat_bold", "size_role": "tagline", "color": sec, "align": "center"},
            "content": tagline, "locked": False})

    return elements


def _infer_copy_space(elements: List[Dict]) -> str:
    headline_el = next(
        (
            el for el in elements
            if isinstance(el, dict)
            and el.get("id") in ("headline", "subheadline", "cta_text")
            and isinstance(el.get("bounds"), dict)
        ),
        None,
    )
    if not headline_el:
        return "bottom"

    bounds = headline_el.get("bounds") or {}
    x = float(bounds.get("x", 0.05) or 0.05)
    y = float(bounds.get("y", 0.52) or 0.52)
    w = float(bounds.get("w", 0.9) or 0.9)

    if y <= 0.35:
        return "top"
    if y >= 0.68:
        return "bottom"
    if x <= 0.16 and w <= 0.60:
        return "left"
    if x >= 0.28 and w <= 0.60:
        return "right"
    return "center"


def _remove_copy_text_from_prompt(prompt: str, values: List[str]) -> str:
    cleaned = prompt or ""
    for value in values:
        val = str(value or "").strip()
        if not val:
            continue
        cleaned = re.sub(re.escape(f'"{val}"'), "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(re.escape(f"'{val}'"), "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(re.escape(val), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    return cleaned.strip(" ,.")


def _ensure_text_negatives(negative_prompt: str) -> str:
    terms = [t.strip() for t in str(negative_prompt or "").split(",") if t.strip()]
    seen = {t.lower() for t in terms}
    for term in _TEXT_NEGATIVE_TERMS:
        if term.lower() not in seen:
            terms.append(term)
            seen.add(term.lower())
    return ", ".join(terms)


def _sync_layout_elements(copy: Dict, creative: Dict, elements: List[Dict], aspect_ratio: float) -> List[Dict]:
    base = [dict(el) for el in elements if isinstance(el, dict)] if isinstance(elements, list) else []
    fallback = _layout_fallback(copy, creative, aspect_ratio)
    by_id = {str(el.get("id")): el for el in base if el.get("id")}
    fallback_by_id = {str(el.get("id")): el for el in fallback if el.get("id")}

    desired_text = {
        "brand_name": str(copy.get("brand_name") or "").strip().upper(),
        "headline": str(copy.get("headline") or "").strip(),
        "subheadline": str(copy.get("subheadline") or "").strip(),
        "body_text": str(copy.get("body") or "").strip(),
        "cta_text": str(copy.get("cta") or "").strip(),
        "tagline": str(copy.get("tagline") or "").strip(),
    }

    for element_id, content in desired_text.items():
        if not content:
            continue
        target = by_id.get(element_id)
        if target is None and element_id in fallback_by_id:
            target = dict(fallback_by_id[element_id])
            base.append(target)
            by_id[element_id] = target
        if target is not None:
            target["content"] = content

    if desired_text["cta_text"] and "cta_button" not in by_id and "cta_button" in fallback_by_id:
        base.append(dict(fallback_by_id["cta_button"]))

    if desired_text["brand_name"] and "brand_bar" not in by_id and "brand_bar" in fallback_by_id:
        base.append(dict(fallback_by_id["brand_bar"]))

    return base


def _apply_typography_direction_to_elements(
    elements: List[Dict],
    typography_direction: Optional[Dict],
    copy: Dict,
) -> List[Dict]:
    direction = typography_direction or {}
    align = str(direction.get("copy_alignment") or "center")
    content_overrides = {
        "headline": str(direction.get("headline_wrap_hint") or copy.get("headline") or "").strip(),
        "subheadline": str(direction.get("subheadline_wrap_hint") or copy.get("subheadline") or "").strip(),
        "body_text": str(direction.get("body_wrap_hint") or copy.get("body") or "").strip(),
        "cta_text": str(direction.get("cta_wrap_hint") or copy.get("cta") or "").strip(),
    }
    font_overrides = {
        "brand_name": str(direction.get("headline_font") or "bebas_neue"),
        "headline": str(direction.get("headline_font") or "bebas_neue"),
        "subheadline": str(direction.get("subheadline_font") or "montserrat_bold"),
        "body_text": str(direction.get("body_font") or "montserrat_bold"),
        "cta_text": str(direction.get("cta_font") or "bebas_neue"),
        "tagline": str(direction.get("tagline_font") or direction.get("body_font") or "montserrat_bold"),
    }
    effect_overrides = {
        "headline": str(direction.get("headline_effect") or "shadow_cutout"),
        "subheadline": str(direction.get("subheadline_effect") or "soft_shadow"),
        "body_text": str(direction.get("body_effect") or "soft_shadow"),
        "cta_text": str(direction.get("cta_treatment") or "pill"),
    }

    result: List[Dict] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        updated = dict(element)
        style = dict(updated.get("style") or {})
        element_id = str(updated.get("id") or "")
        if element_id in font_overrides:
            style["font"] = font_overrides[element_id]
        if updated.get("type") == "text":
            style["align"] = "center" if element_id == "brand_name" else align
        if element_id in effect_overrides:
            style["effect"] = effect_overrides[element_id]
        updated["style"] = style
        if element_id in content_overrides and content_overrides[element_id]:
            updated["content"] = content_overrides[element_id]
        result.append(updated)
    return result


def _agent_reconcile_outputs(
    triage: Dict,
    creative: Dict,
    copy: Dict,
    img: Dict,
    elements: List[Dict],
    aspect_ratio: float,
    design_room: Optional[Dict] = None,
    typography_direction: Optional[Dict] = None,
) -> Dict:
    strategy = _request_strategy(triage, triage.get("original_prompt", ""), {"tone": creative.get("mood", "")})
    copy_final = dict(copy)
    explicit_headline = str(triage.get("explicit_headline") or "").strip()
    explicit_subheadline = str(triage.get("explicit_subheadline") or "").strip()
    explicit_cta = str(triage.get("explicit_cta") or "").strip()

    if explicit_headline:
        copy_final["headline"] = explicit_headline.upper()
    if explicit_subheadline:
        copy_final["subheadline"] = explicit_subheadline
    if explicit_cta:
        copy_final["cta"] = explicit_cta.upper()
    body_copy_policy = str((design_room or {}).get("body_copy_policy") or "").strip().lower()
    if (
        strategy["font_style"] in ("elegant_serif", "luxury_display")
        and explicit_headline
        and explicit_subheadline
        and str(triage.get("goal") or "brand_awareness") != "sale_promotion"
    ):
        copy_final["body"] = ""
        notes = ["editorial_body_suppressed"]
    else:
        notes: List[str] = []
    if body_copy_policy == "minimal" and str(copy_final.get("body") or "").strip():
        copy_final["body"] = ""
        notes.append("body_trimmed_for_design")
    img_final = dict(img)
    preferred_copy_space = str((design_room or {}).get("copy_space") or "").strip()
    copy_space = preferred_copy_space or _infer_copy_space(elements)

    bg_prompt = _remove_copy_text_from_prompt(
        str(img_final.get("background_prompt") or ""),
        [copy_final.get("headline"), copy_final.get("subheadline"), copy_final.get("cta")],
    )
    chosen_direction = str(((design_room or {}).get("winner") or {}).get("direction") or "").strip()
    if chosen_direction and chosen_direction.lower() not in bg_prompt.lower():
        bg_prompt = f"{chosen_direction}. {bg_prompt}".strip(". ")

    # NATIVE TEXT RENDERING: Include actual text in Ideogram prompt (not "preserve space")
    # This tells Ideogram to render text AS PART of image generation, not compositor overlay
    native_text_instructions = _build_native_text_instructions(
        headline=copy_final.get("headline", ""),
        cta=copy_final.get("cta", ""),
        copy_space=copy_space,
        brand_name=copy_final.get("brand_name", "")
    )
    if native_text_instructions:
        bg_prompt = f"{bg_prompt}. {native_text_instructions}".strip(". ")
        notes.append(f"native_text:enabled copy_space:{copy_space}")
    if strategy["image_guardrails"].lower() not in bg_prompt.lower():
        bg_prompt = f"{bg_prompt}. {strategy['image_guardrails']}".strip(". ")
    img_final["background_prompt"] = bg_prompt
    img_final["negative_prompt"] = _ensure_text_negatives(str(img_final.get("negative_prompt") or ""))
    if strategy["negative_guardrails"]:
        img_final["negative_prompt"] = _ensure_text_negatives(
            f"{img_final['negative_prompt']}, {strategy['negative_guardrails']}"
        )

    params = dict(img_final.get("parameters") or {})
    params.setdefault(
        "aspect_ratio",
        _aspect_ratio_label(
            int(triage.get("recommended_width") or 1080),
            int(triage.get("recommended_height") or 1350),
        ),
    )
    img_final["parameters"] = params

    draft_variant = dict(img_final.get("draft_variant") or {})
    if draft_variant:
        draft_params = dict(draft_variant.get("parameters") or {})
        draft_params.setdefault("aspect_ratio", params["aspect_ratio"])
        draft_variant["parameters"] = draft_params
        img_final["draft_variant"] = draft_variant

    synced_elements = _sync_layout_elements(copy_final, creative, elements, aspect_ratio)
    synced_elements = _apply_typography_direction_to_elements(synced_elements, typography_direction, copy_final)

    design_updates = {
        "has_feature_grid": bool(copy_final.get("features")),
        "has_cta_button": bool(str(copy_final.get("cta") or "").strip()),
        "copy_space": copy_space,
        "font_style": str((design_room or {}).get("font_style") or strategy["font_style"]),
        "headline_font": str((typography_direction or {}).get("headline_font") or ""),
        "subheadline_font": str((typography_direction or {}).get("subheadline_font") or ""),
        "body_font": str((typography_direction or {}).get("body_font") or ""),
        "cta_font": str((typography_direction or {}).get("cta_font") or ""),
        "copy_alignment": str((typography_direction or {}).get("copy_alignment") or "center"),
        "headline_effect": str((typography_direction or {}).get("headline_effect") or ""),
        "subheadline_effect": str((typography_direction or {}).get("subheadline_effect") or ""),
        "body_effect": str((typography_direction or {}).get("body_effect") or ""),
        "cta_treatment": str((typography_direction or {}).get("cta_treatment") or ""),
        "brand_position": str((typography_direction or {}).get("brand_position") or ""),
        "show_accent_rule": bool((typography_direction or {}).get("show_accent_rule")),
    }
    if explicit_headline or explicit_subheadline or explicit_cta:
        notes.append("explicit_copy_locked")
    winner_id = str(((design_room or {}).get("winner") or {}).get("id") or "").strip()
    if winner_id:
        notes.append(f"taste_winner:{winner_id}")

    return {
        "copy": copy_final,
        "image": img_final,
        "elements": synced_elements,
        "poster_design": design_updates,
        "copy_space": copy_space,
        "notes": notes,
    }


async def _agent_image_prompter(
    triage: Dict,
    creative: Dict,
    copy: Dict,
    design_room: Optional[Dict] = None,
    prompt_dna: Optional[Dict] = None,
) -> Dict:
    strategy = _request_strategy(triage, triage.get("original_prompt", ""), {"tone": creative.get("mood", "")})

    # Beast-level intelligence extraction
    emotion_target = triage.get("emotion_target", "aspiration")
    cultural_moment = triage.get("cultural_moment")
    audience_intel = triage.get("audience_intelligence", {})
    attention_budget = audience_intel.get("attention_budget_seconds", 2)

    # Full-bleed: image fills 100% canvas, text overlaid. Bottom 50% must be dark.
    festival_hint = ""
    if cultural_moment:
        festival_hint = (
            f"\nCultural Moment: {cultural_moment['name']} — authentic {cultural_moment['type']} visuals. "
            f"Visual keywords: {', '.join(cultural_moment['keywords'][:3])}."
        )
    elif triage.get("is_festival") and triage.get("festival_name"):
        festival_hint = f"\nFestival context: {triage['festival_name']} — weave in authentic cultural visual elements."

    attention_hint = f"\nAttention Budget: {attention_budget}s — image must make impact IMMEDIATELY. Hero subject must dominate."

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
    design_room_context = _format_design_room_context(design_room)
    chosen_backdrop = str(((design_room or {}).get("winner") or {}).get("direction") or "").strip()

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
        "You are a SENIOR PROMPT ENGINEER — you speak BOTH languages: human creative intention AND diffusion model attention weights.\n"
        "Task: Translate Creative Director's brief into beast-level, model-optimized image prompts.\n"
        "\n"
        "== KNOWLEDGE BASE ==\n"
        f"{_IMAGE_PROMPT_ENGINEER_KB}\n"
        "== END KNOWLEDGE BASE ==\n"
        "\n"
        "🎯 9-STEP BUILD PROCESS (MANDATORY):\n"
        "\n"
        "STEP 1: SUBJECT CORE\n"
        "  → Extract main subject from brief. 2-3 sentences with HYPER-SPECIFIC physical attributes.\n"
        "  → Example: 'Indian woman, 28 years old, sari in deep magenta silk, carrying woven basket'\n"
        "\n"
        "STEP 2: ENVIRONMENT/SETTING\n"
        "  → NOT 'outdoors' — 'narrow street in Mumbai Colaba market, monsoon-wet cobblestones reflecting orange streetlight'\n"
        "\n"
        "STEP 3: LIGHTING (MOST CRITICAL)\n"
        "  → Source: sun/studio/neon/natural\n"
        "  → Direction: from upper-left/backlit/frontal/below\n"
        "  → Quality: hard/soft/diffused/harsh\n"
        "  → Color temp: warm 3200K/neutral 5600K/cool 8000K\n"
        "  → Shadows: deep/subtle/absent\n"
        "\n"
        "STEP 4: CAMERA/LENS (Worth 50 other modifiers!)\n"
        "  → 'Shot on [camera from KB] + [lens spec from KB]'\n"
        "  → Pick based on industry: Portrait→Hasselblad X2D, Product→Phase One XT, etc.\n"
        "\n"
        "STEP 5: COMPOSITION\n"
        "  → Translate CD archetype: hero-dominant→'subject centered, full-frame', diagonal→'subject angled 45°'\n"
        "\n"
        "STEP 6: COLOR PALETTE TRANSLATION\n"
        "  → Convert hex to descriptive: #F4A62A→'warm amber gold accent, like diya flame illumination'\n"
        "\n"
        "STEP 7: STYLE REGISTER\n"
        "  → Map CD aesthetic to model vocab: 'brutalism×luxury'→'raw concrete, architectural negative space, expensive materials'\n"
        "\n"
        "STEP 8: QUALITY STACK\n"
        "  → Add 3-5 APPROVED quality signals (NOT generic 'hyperrealistic/8K' noise)\n"
        "  → Use: 'medium format photography', '[photographer name] style', 'published in Vogue'\n"
        "\n"
        "STEP 9: FINAL ASSEMBLY & VALIDATION\n"
        "  → Combine all elements per model template\n"
        "  → Validate: subject first, bottom 50% dark, zero text keywords, model-appropriate length\n"
        "  → Draft variant: ≤60 words flux_schnell version\n"
        "\n"
        "CRITICAL RULES:\n"
        "  - Subject ALWAYS first (not mood words)\n"
        "  - Specificity > adjectives ('worn leather, brass buttons' NOT 'detailed jacket')\n"
        "  - Use Camera/Lens references from KB (massive quality boost)\n"
        "  - For India market: Use cultural authenticity prompts from KB (NO 'exotic/dusky/ethnic')\n"
        "  - Negative prompts: Model-specific artifact targeting (NOT generic)\n"
        "  - If backdrop direction provided: treat as locked unless contradicts user brief\n"
        f"Commercial taste guardrails: {strategy['image_guardrails']}\n"
        f"Detail budget: {strategy['detail_budget']}\n"
        f"{festival_hint}{attention_hint}{dna_hint}\n"
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
        f"Avoid: {', '.join((creative.get('avoid') or []) + ([forbidden_additions] if forbidden_additions else []))}\n"
        f"Commercial taste guardrails: {strategy['image_guardrails']}\n"
        f"Chosen backdrop direction: {chosen_backdrop or 'not specified'}\n"
        f"{design_room_context}"
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
            f"Chosen backdrop direction: {chosen_backdrop or 'not specified'}\n"
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
        f"{chosen_backdrop}. " if chosen_backdrop else ""
    ) + (
        f"cinematic {industry} scene, {mood_val} atmosphere, {style_val} style, "
        f"dramatic lighting, deep shadows in bottom half, no text, clean background"
    )

    return {
        "background_prompt": bg_prompt or _smart_fallback,
        "negative_prompt":   base_negative,
        "model_preference":  model_preference or "flux_2_pro",
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
            resolved_width = width
            resolved_height = height

            # ── Stage 1: Triage (serial — everything depends on it) ──────────
            t = time.time()
            triage = await _agent_triage(safe_prompt)
            triage["original_prompt"] = safe_prompt  # pass through for image_prompter context
            agent_times["triage"] = round(time.time() - t, 2)
            if width == 1024 and height == 1024:
                resolved_width = int(triage.get("recommended_width") or width)
                resolved_height = int(triage.get("recommended_height") or height)
            aspect_ratio = resolved_width / max(resolved_height, 1)

            # ── Stage 2: Brand Intel first, then Creative Director with real brand ─
            # Sequential (not parallel) — saves 1 Gemini call vs old double-CD pattern,
            # and Creative Director gets accurate brand colors/tone from the start.
            t = time.time()
            brand = await _agent_brand_intel(triage, brand_kit, safe_prompt)
            agent_times["brand_intel"] = round(time.time() - t, 2)

            t = time.time()
            creative = await _agent_creative_director(triage, brand, safe_prompt)
            agent_times["creative_director"] = round(time.time() - t, 2)
            creative["aspect_ratio"] = _aspect_ratio_label(resolved_width, resolved_height)

            palette = creative.get("palette", {})

            # ── Stage 2b: Design Director — Visual System Decree ───────────
            # Issues composition law, grid system, type scale, color rules
            # This decree is NON-NEGOTIABLE for all downstream agents
            design_decree = None
            if _DESIGN_DIRECTOR_AVAILABLE:
                try:
                    t = time.time()
                    design_decree = await design_director_agent(
                        creative_bible=creative.get("creative_bible", {}),
                        brand_palette={
                            "primary_color": _safe_hex(palette.get("primary"), "#6C63FF"),
                            "secondary_color": _safe_hex(palette.get("secondary"), "#4FACFE"),
                            "accent_color": _safe_hex(palette.get("accent"), "#00D4FF"),
                        },
                        platform=triage.get("platform", "instagram"),
                        aspect_ratio=aspect_ratio,
                        triage=triage,
                        industry=triage.get("industry", "general"),
                        gemini_client=_get_gemini_client()
                    )
                    agent_times["design_director"] = round(time.time() - t, 2)
                    logger.info(f"[design_chain] Design Director decree: {design_decree.get('composition_law')}")
                except Exception as e:
                    logger.warning(f"[design_chain] Design Director failed: {e}, continuing without decree")
                    design_decree = None

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

            # ── Stage 3: Copy Writer ────────────────────────────────────────
            # Extract bucket-specific DNA (active when run_count >= 5)
            bucket_key = triage.get("industry", "general")
            bucket_dna: Dict = {}
            if prompt_dna and isinstance(prompt_dna, dict):
                bucket_dna = prompt_dna.get(bucket_key, prompt_dna.get("typography", {})) or {}

            t = time.time()
            copy = await _agent_copy_writer(triage, brand, creative, safe_prompt)
            agent_times["copy_writer"] = round(time.time() - t, 2)

            # ── Stage 3b: Character limit guard (fires only when over limit) ─
            t = time.time()
            copy = await _enforce_char_limits(copy, triage.get("platform", "instagram"))
            agent_times["char_guard"] = round(time.time() - t, 3)

            # ── Stage 3c: Structured design room + backdrop taste scorer ───
            t = time.time()
            design_room = _build_design_room(triage, brand, creative, copy)
            agent_times["design_room"] = round(time.time() - t, 3)

            t = time.time()
            typography_direction = _build_typography_direction(triage, brand, creative, copy, design_room)
            agent_times["typography_director"] = round(time.time() - t, 3)

            # ── Stage 4: Image Prompter + Layout Planner (PARALLEL or MULTI-VARIANT) ────────
            # Multi-variant logic: Generate 3 layout variants for PREMIUM+ tiers
            tier = str(triage.get("tier", "standard")).lower()
            enable_multi_variant = tier in ["premium", "ultra"] and design_decree is not None

            t = time.time()
            if enable_multi_variant:
                # PREMIUM/ULTRA: Generate 3 variants in parallel
                logger.info("[design_chain] Multi-variant mode: generating 3 layout variants")
                img, safe_layout, bold_layout, disruptive_layout = await asyncio.gather(
                    _agent_image_prompter(triage, creative, copy, design_room=design_room, prompt_dna=bucket_dna),
                    _agent_layout_planner(triage, creative, copy, aspect_ratio=aspect_ratio, design_room=design_room, design_decree=design_decree, variant="safe"),
                    _agent_layout_planner(triage, creative, copy, aspect_ratio=aspect_ratio, design_room=design_room, design_decree=design_decree, variant="bold"),
                    _agent_layout_planner(triage, creative, copy, aspect_ratio=aspect_ratio, design_room=design_room, design_decree=design_decree, variant="disruptive"),
                )

                # Score all 3 variants
                creative_bible = creative.get("creative_bible", {})
                safe_score = _score_layout_variant(safe_layout, "safe", creative_bible, design_decree)
                bold_score = _score_layout_variant(bold_layout, "bold", creative_bible, design_decree)
                disruptive_score = _score_layout_variant(disruptive_layout, "disruptive", creative_bible, design_decree)

                # Pick best variant (highest score)
                variants = [
                    {"type": "safe", "elements": safe_layout, "score": safe_score},
                    {"type": "bold", "elements": bold_layout, "score": bold_score},
                    {"type": "disruptive", "elements": disruptive_layout, "score": disruptive_score},
                ]
                best_variant = max(variants, key=lambda v: v["score"])
                elements = best_variant["elements"]

                logger.info(
                    f"[design_chain] Variant scores: safe={safe_score:.1f}, bold={bold_score:.1f}, "
                    f"disruptive={disruptive_score:.1f} → winner: {best_variant['type']}"
                )

                # Store variant info in brief for debugging
                brief["_layout_variants"] = {
                    "enabled": True,
                    "winner": best_variant["type"],
                    "scores": {
                        "safe": safe_score,
                        "bold": bold_score,
                        "disruptive": disruptive_score,
                    },
                }
            else:
                # FAST/STANDARD: Single safe variant only
                img, elements = await asyncio.gather(
                    _agent_image_prompter(triage, creative, copy, design_room=design_room, prompt_dna=bucket_dna),
                    _agent_layout_planner(triage, creative, copy, aspect_ratio=aspect_ratio, design_room=design_room, design_decree=design_decree, variant="safe"),
                )
                brief["_layout_variants"] = {"enabled": False, "winner": "safe"}

            agent_times["image_layout_parallel"] = round(time.time() - t, 3)

            # ── Assemble final brief ─────────────────────────────────────────
            t = time.time()
            reconcile = _agent_reconcile_outputs(
                triage, creative, copy, img, elements, aspect_ratio,
                design_room=design_room,
                typography_direction=typography_direction,
            )
            copy = reconcile["copy"]
            img = reconcile["image"]
            elements = reconcile["elements"]
            brief["poster_design"].update(reconcile.get("poster_design", {}))
            brief["_reconcile"] = {
                "copy_space": reconcile.get("copy_space", "bottom"),
                "notes": reconcile.get("notes", []),
            }
            brief["_design_room"] = design_room
            brief["_typography_direction"] = typography_direction
            brief["scores"]["backdrop"] = {
                "winner_id": ((design_room.get("winner") or {}).get("id") or ""),
                "winner_score": ((design_room.get("winner") or {}).get("score_total") or 0),
                "candidates": [
                    {
                        "id": candidate.get("id", ""),
                        "label": candidate.get("label", ""),
                        "score_total": candidate.get("score_total", 0),
                    }
                    for candidate in (design_room.get("candidates") or [])[:4]
                ],
            }
            agent_times["reconcile"] = round(time.time() - t, 3)

            brief["triage"]         = triage
            brief["brand"]          = brand
            brief["creative"]       = creative
            brief["creative_bible"] = creative.get("creative_bible", {})
            brief["design_decree"]  = design_decree or {}
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
            brief["resolved_width"]       = resolved_width
            brief["resolved_height"]      = resolved_height

            brief["_elapsed"]      = round(time.time() - t0, 2)
            brief["_agent_times"]  = agent_times

            # Motion Designer: Add motion hints for video/story platforms
            if _MOTION_DESIGNER_AVAILABLE:
                platform = triage.get("platform", "")
                if platform in ["instagram_story", "tiktok_story", "instagram_reel", "tiktok"]:
                    try:
                        t_motion = time.time()
                        motion_hints = await generate_static_motion_hints(
                            triage=triage,
                            creative_bible=creative.get("creative_bible", {}),
                            layout={"elements": elements}
                        )
                        brief["motion_hints"] = motion_hints
                        agent_times["motion_designer"] = round(time.time() - t_motion, 2)
                        logger.info("[design_chain] motion hints added for %s (%.2fs)", platform, agent_times["motion_designer"])
                    except Exception as e:
                        logger.warning("[design_chain] motion_designer failed: %s", e)
                        brief["motion_hints"] = None

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

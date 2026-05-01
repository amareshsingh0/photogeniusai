"""
Per-Model Prompt Formatter — Gap 4 of Ad Quality Upgrade.

Problem: same enriched prompt goes to every model. Each model has different
strengths and parsing behaviour:
  - GPT Image 2   → understands structured creative briefs, exact quoted text,
                     paragraph format. Instruction-following is ChatGPT-level.
  - Imagen/Google → _distill_for_imagen() already runs INSIDE _call_google().
                     Do NOT apply an extra layer here — it would double-distill.
  - Flux 2 Flex   → natural language scene description with camera physics.
                     Hates designer-brief vocab ("lockup", "locked across", etc.)
  - WaveSpeed     → pass through as-is; provider handles artistic intent well.

Wire-up: called in generate_stream.py AFTER sanitize + anchor + model selection,
BEFORE multi_client.generate(). Only active when _simple_payload exists (i.e.
simple_engine ran and produced structured output).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Models that need special formatting at the generate_stream level.
# Google/Imagen models are excluded — _distill_for_imagen runs inside _call_google().
_GPT_MODELS     = {"gpt_image_2"}
_FLUX_MODELS    = {"flux_2_flex", "flux_2_pro", "flux_kontext", "flux_kontext_max",
                   "flux_2_dev", "flux_2_turbo", "flux_2_max", "flux_fill"}
_GOOGLE_MODELS  = {"gemini_3_imagen", "gemini_3_1_imagen", "imagen_4_base",
                   "imagen_4_ultra", "imagen_4_fast", "imagen_3"}
_WAVESPEED_PASS = {"wan_2_7", "grok_2_imagine", "hunyuan_image"}

# Designer-brief words Flux renders literally or misinterprets as composition
# instructions ("locked across the top third" → Flux may tile the text).
_FLUX_STRIP = re.compile(
    r"\b(?:locked\s+across|lockup|locking|anchored\s+to|"
    r"upper\s+third|lower\s+third|top\s+third|bottom\s+third|"
    r"safe[\s-]zone|bleed\s+margin|"
    r"color\s+block|gradient\s+overlay|cream\s+ribbon)\b",
    re.IGNORECASE,
)


def format_prompt_for_model(
    base_prompt: str,
    model_key: str,
    simple_payload: Optional[Dict[str, Any]],
) -> str:
    """Return a model-optimised prompt string.

    Args:
        base_prompt:     The already-sanitised, anchor-prepended prompt from
                         generate_stream.py (what would normally go to every model).
        model_key:       Canonical model key (e.g. 'gpt_image_2', 'flux_2_flex').
        simple_payload:  Dict returned by simple_engine.enrich() — contains
                         prompt, ad_copy, visual, campaign_type, etc.
                         None when simple_engine did not run (fallback path).

    Returns:
        Formatted prompt string ready for multi_client.generate().
    """
    if not simple_payload:
        # simple_engine didn't run — no structured data to work with.
        return base_prompt

    if model_key in _GPT_MODELS:
        return _format_for_gpt(base_prompt, simple_payload)

    if model_key in _FLUX_MODELS:
        return _format_for_flux(base_prompt, simple_payload)

    if model_key in _GOOGLE_MODELS:
        # _distill_for_imagen runs inside _call_google() — pass through untouched.
        return base_prompt

    if model_key in _WAVESPEED_PASS:
        # WaveSpeed (wan_2_7, grok_2_imagine) handles artistic prompts well as-is.
        return base_prompt

    # Unknown / future models — pass through.
    return base_prompt


# ─────────────────────────────────────────────────────────────────────────────
# GPT Image 2 formatter
# ─────────────────────────────────────────────────────────────────────────────

def _format_for_gpt(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Creative-brief paragraph format for GPT Image 2.

    GPT Image 2 is ChatGPT under the hood — it understands structured English
    instructions as well as or better than raw image prompts. We send it a
    short creative brief + the base visual prompt + explicit typography block.
    This consistently improves text accuracy and layout quality.
    """
    ad_copy: Optional[Dict] = payload.get("ad_copy")
    visual:  Optional[Dict] = payload.get("visual")
    campaign_type:       str = payload.get("campaign_type", "general")
    copywriting_formula: str = payload.get("copywriting_formula", "simple")
    subject_category:    str = payload.get("subject_category", "general")

    sections: list[str] = []

    # --- Brief header ---
    if campaign_type and campaign_type != "general":
        sections.append(
            f"Create a professional {campaign_type.replace('_', ' ')} image "
            f"for the {subject_category.replace('_', ' ')} category."
        )

    # --- Base visual scene (strip the affirmative anchor — GPT doesn't need it) ---
    scene = re.sub(
        r"^\s*ONE single unified (?:image|photograph)[^.]*\.\s*",
        "",
        base_prompt,
        flags=re.IGNORECASE,
    ).strip()
    if scene:
        sections.append(scene)

    # --- Structured copy block ---
    if ad_copy:
        headline   = (ad_copy.get("headline") or "").strip()
        subhead    = (ad_copy.get("subhead") or "").strip()
        cta        = (ad_copy.get("cta") or "").strip()
        benefits   = [b for b in (ad_copy.get("benefit_lines") or []) if b]
        signals    = [s for s in (ad_copy.get("trust_signals") or []) if s]
        tagline    = (ad_copy.get("emotional_tagline") or "").strip()
        brand_name = (ad_copy.get("brand_name") or "").strip()

        copy_lines: list[str] = []
        if headline:
            copy_lines.append(f'HEADLINE: "{headline}"')
        if subhead:
            copy_lines.append(f'SUBHEADLINE: "{subhead}"')
        if benefits:
            copy_lines.extend(f'BENEFIT: "{b}"' for b in benefits[:3])
        if signals:
            copy_lines.append(f'TRUST: "{signals[0]}"')
        if tagline:
            copy_lines.append(f'TAGLINE: "{tagline}"')
        if cta:
            copy_lines.append(f'CTA BUTTON: "{cta}"')
        if brand_name:
            copy_lines.append(f'BRAND NAME: "{brand_name}"')

        if copy_lines:
            sections.append(
                "TEXT TO RENDER ON IMAGE (copy exactly as written, correct spelling):\n"
                + "\n".join(copy_lines)
            )

    # --- Visual direction ---
    if visual:
        mood     = (visual.get("mood") or "").strip()
        palette  = (visual.get("color_palette") or "").strip()
        lighting = (visual.get("lighting") or "").strip()
        typo     = (visual.get("typography_style") or "").strip()

        visual_parts: list[str] = []
        if mood:
            visual_parts.append(f"Mood: {mood}")
        if palette:
            visual_parts.append(f"Color palette: {palette}")
        if lighting:
            visual_parts.append(f"Lighting: {lighting}")
        if typo:
            visual_parts.append(f"Typography style: {typo}")

        if visual_parts:
            sections.append("VISUAL DIRECTION: " + " | ".join(visual_parts))

    # --- Typography quality instruction (always last for GPT) ---
    sections.append(
        "Ensure all on-image text is perfectly legible, correctly spelled, "
        "and rendered with professional typographic hierarchy. "
        "Single unified composition — no multiple panels or variants."
    )

    result = "\n\n".join(s for s in sections if s)
    logger.info("[formatter][gpt_image_2] %d→%d chars", len(base_prompt), len(result))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Flux formatter
# ─────────────────────────────────────────────────────────────────────────────

def _format_for_flux(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Natural-language scene description for Flux models.

    Flux (FLUX.1) is a diffusion model trained on photographic captions — not
    design briefs. It works best with:
      - Natural scene description (camera, lens, light physics)
      - Minimal layout/structural language ("locked across", "lower third" → bad)
      - Text in quotes preserved (Flux CAN render short text strings)

    We strip designer-brief vocab that Flux misinterprets as literal text to
    render on the image, while keeping camera + lighting + scene details.
    """
    ad_copy: Optional[Dict] = payload.get("ad_copy")

    # Strip layout/composition jargon that confuses Flux
    cleaned = _FLUX_STRIP.sub("", base_prompt)
    cleaned = re.sub(r"  +", " ", cleaned).strip()

    # If text is needed and ad_copy has a headline, append a simple text hint
    if ad_copy:
        headline = (ad_copy.get("headline") or "").strip()
        cta      = (ad_copy.get("cta") or "").strip()
        if headline and f'"{headline}"' not in cleaned:
            cleaned += f' Text overlay: "{headline}"'
            if cta:
                cleaned += f' with "{cta}" button below.'

    logger.info("[formatter][flux] %d→%d chars", len(base_prompt), len(cleaned))
    return cleaned

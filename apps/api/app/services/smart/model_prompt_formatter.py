"""
Per-Model Prompt Formatter  -  Gap 4 of Ad Quality Upgrade.

Problem: same enriched prompt goes to every model. Each model has different
strengths and parsing behaviour:
  - GPT Image 2   -> understands structured creative briefs, exact quoted text,
                     paragraph format. Instruction-following is ChatGPT-level.
  - Imagen/Google -> _distill_for_imagen() already runs INSIDE _call_google().
                     Do NOT apply an extra layer here  -  it would double-distill.
  - Flux 2 Flex   -> natural language scene description with camera physics.
                     Hates designer-brief vocab ("lockup", "locked across", etc.)
  - WaveSpeed     -> pass through as-is; provider handles artistic intent well.

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
# Google/Imagen models are excluded  -  _distill_for_imagen runs inside _call_google().
_GPT_MODELS     = {"gpt_image_2"}
_FLUX_MODELS    = {"flux_2_flex", "flux_2_pro", "flux_kontext", "flux_kontext_max",
                   "flux_2_dev", "flux_2_turbo", "flux_2_max", "flux_fill"}
_GOOGLE_MODELS  = {"gemini_3_imagen", "gemini_3_1_imagen", "imagen_4_base",
                   "imagen_4_ultra", "imagen_4_fast", "imagen_3"}
_WAVESPEED_PASS = {"wan_2_7", "grok_2_imagine", "hunyuan_image"}

# Designer-brief words Flux renders literally or misinterprets as composition
# instructions ("locked across the top third" -> Flux may tile the text).
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
        simple_payload:  Dict returned by simple_engine.enrich()  -  contains
                         prompt, ad_copy, visual, campaign_type, etc.
                         None when simple_engine did not run (fallback path).

    Returns:
        Formatted prompt string ready for multi_client.generate().
    """
    if not simple_payload:
        # simple_engine didn't run  -  no structured data to work with.
        return base_prompt

    if model_key in _GPT_MODELS:
        return _format_for_gpt(base_prompt, simple_payload)

    if model_key in _FLUX_MODELS:
        return _format_for_flux(base_prompt, simple_payload)

    if model_key in _GOOGLE_MODELS:
        # Build a pre-distilled scene prompt from structured data so it
        # SURVIVES _distill_for_imagen() in _call_google() without losing
        # the headline/subhead/CTA quoted strings.
        return _format_for_imagen(base_prompt, simple_payload)

    if model_key in _WAVESPEED_PASS:
        # WaveSpeed models (wan_2_7, grok_2_imagine, hunyuan_image) cannot
        # reliably render multi-element text. Strip text-rendering expectations
        # and send a pure scene description.
        return _format_for_wavespeed(base_prompt, simple_payload)

    # Unknown / future models  -  pass through.
    return base_prompt


# ----------------------------------------------------------------------
# GPT Image 2 formatter
# ----------------------------------------------------------------------

def _guess_icon(benefit: str) -> str:
    """Map a benefit label to a simple icon hint GPT Image 2 can render."""
    b = benefit.lower()
    if any(w in b for w in ("light", "weight", "feather", "airy")):
        return "feather icon"
    if any(w in b for w in ("blur", "smooth", "glow", "radiant", "spark", "finish", "flawless", "set")):
        return "sparkle icon"
    if any(w in b for w in ("lasting", "long", "hour", "day", "wear", "24")):
        return "clock icon"
    if any(w in b for w in ("natural", "organic", "vegan", "plant", "leaf", "gentle", "clean")):
        return "leaf icon"
    if any(w in b for w in ("oil", "control", "matte", "moisture", "hydrat", "droplet")):
        return "droplet icon"
    if any(w in b for w in ("protect", "shield", "derm", "safe", "test", "spf")):
        return "shield icon"
    if any(w in b for w in ("cover", "pore", "imperfect", "blemish", "conceal")):
        return "circle-dot icon"
    return "simple line-art icon"


def _format_for_gpt(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Sectioned imperative template for GPT Image 2.

    Research (PDF page 13) prescribes this exact format:
      1. Persona prefix ("Act as a world-class advertising art director...")
      2. PRIMARY COMMAND: <one sentence describing the deliverable>
      3. TEXT ELEMENTS TO RENDER (USE EXACTLY THESE STRINGS): key/value list
      4. VISUAL AND LAYOUT INSTRUCTIONS: bullet list of placements

    GPT Image 2 is built to parse imperative sectioned commands, not narrative
    prose. ASCII output only - no unicode symbols (provider/log encoding safety).
    """
    ad_copy: Optional[Dict] = payload.get("ad_copy") or {}
    visual:  Optional[Dict] = payload.get("visual") or {}
    campaign_type:    str = payload.get("campaign_type", "general")
    subject_category: str = payload.get("subject_category", "general")
    intent:           str = (payload.get("intent") or "").strip()

    headline   = (ad_copy.get("headline") or "").strip()
    subhead    = (ad_copy.get("subhead") or "").strip()
    cta        = (ad_copy.get("cta") or "").strip()
    benefits   = [b for b in (ad_copy.get("benefit_lines") or []) if b]
    signals    = [s for s in (ad_copy.get("trust_signals") or []) if s]
    tagline    = (ad_copy.get("emotional_tagline") or "").strip()
    brand_name = (ad_copy.get("brand_name") or "").strip()

    mood        = (visual.get("mood") or "").strip()
    palette     = (visual.get("color_palette") or "").strip()
    lighting    = (visual.get("lighting") or "").strip()
    composition = (visual.get("composition") or "").strip()
    background  = (visual.get("background") or "").strip()
    typo        = (visual.get("typography_style") or "").strip()

    persona_specialty = {
        "beauty":      "luxury beauty and cosmetics campaigns",
        "tech":        "premium consumer electronics campaigns",
        "food":        "gourmet food and beverage campaigns",
        "fashion":     "high-end fashion editorial campaigns",
        "health":      "wellness and fitness brand campaigns",
        "real_estate": "luxury real estate marketing",
        "education":   "premium education brand campaigns",
    }.get(subject_category, "premium brand advertising campaigns")

    camp_label = campaign_type.replace("_", " ") if campaign_type != "general" else "advertisement"
    cat_label  = subject_category.replace("_", " ") if subject_category != "general" else "consumer"
    intent_phrase = intent.replace("_", " ") if intent and intent != "general" else camp_label

    sections: list[str] = []

    # Persona prefix
    sections.append(
        "Act as a world-class advertising art director specializing in "
        f"{persona_specialty}."
    )

    # PRIMARY COMMAND
    subject_phrase = f"the {cat_label} category" if cat_label != "consumer" else "a consumer brand"
    if brand_name:
        subject_phrase = f"the brand {brand_name} in {subject_phrase}"
    sections.append(
        "PRIMARY COMMAND:\n"
        f"Generate a single, cohesive image of a polished {intent_phrase} for "
        f"{subject_phrase}. Single unified composition - no panels, no variants, "
        "no collage. Render as a finished print-ready advertisement."
    )

    # TEXT ELEMENTS TO RENDER (key/value list)
    text_lines: list[str] = []
    if brand_name:
        text_lines.append(f'- BRAND_NAME: "{brand_name}"')
    if headline:
        text_lines.append(f'- HERO_HEADLINE: "{headline}"')
    if subhead:
        text_lines.append(f'- SUBHEADLINE: "{subhead}"')
    if benefits:
        labels_json = ", ".join(f'"{b}"' for b in benefits[:5])
        text_lines.append(f"- ICON_LABELS: [{labels_json}]")
    if tagline:
        text_lines.append(f'- EMOTIONAL_TAGLINE: "{tagline}"')
    if cta:
        text_lines.append(f'- CALL_TO_ACTION: "{cta}"')
    if signals:
        trust_json = ", ".join(f'"{s}"' for s in signals[:5])
        text_lines.append(f"- TRUST_STRIP_ITEMS: [{trust_json}]")

    if text_lines:
        sections.append(
            "TEXT ELEMENTS TO RENDER:\n"
            "USE EXACTLY THESE STRINGS, CORRECT SPELLING:\n"
            + "\n".join(text_lines)
        )

    # VISUAL AND LAYOUT INSTRUCTIONS
    layout_lines: list[str] = []

    comp_default = (
        "Vertical or square aspect, suitable for Instagram feed. "
        "Text hierarchy on the left or center-left; hero product on the right or center-right."
        if subject_category in ("beauty", "fashion", "health")
        else "Single unified composition with clear visual hierarchy."
    )
    layout_lines.append(f"- COMPOSITION: {composition or comp_default}")

    if background:
        layout_lines.append(f"- PRODUCT: A high-resolution product photograph. {background}")
    else:
        layout_lines.append(
            f"- PRODUCT: A high-resolution product photograph of the {intent_phrase} "
            "with premium commercial-photography lighting."
        )

    if brand_name:
        layout_lines.append(
            f'- LOGO PLACEMENT: Place the brand wordmark "{brand_name}" in the top-left corner '
            "in a small, refined, brand-appropriate typeface."
        )

    if campaign_type in ("product_launch", "announcement"):
        layout_lines.append(
            '- LAUNCH BADGE: Above the headline, a small "NEW LAUNCH" label with thin '
            "horizontal rules on either side, in small-caps or light tracking."
        )

    if headline:
        layout_lines.append(
            "- HEADLINE PLACEMENT: Center the HERO_HEADLINE in the upper-middle text region, "
            "in large bold uppercase condensed sans-serif. Dominant text element."
        )

    if subhead:
        layout_lines.append(
            "- SUBHEADLINE PLACEMENT: Place the SUBHEADLINE directly below the HERO_HEADLINE "
            "in an elegant italic or script font for premium high-low contrast."
        )

    if benefits and len(benefits) >= 2:
        icon_pairs = ", ".join(
            f'"{b}" with a {_guess_icon(b)}' for b in benefits[:5]
        )
        layout_lines.append(
            "- ICON ROW PLACEMENT: Below the subheadline (or below the product photo), "
            f"arrange {len(benefits[:5])} small circular icon badges horizontally. "
            "Each circle contains a minimal line-art icon and a 1-2 line label below it. "
            f"Suggested pairings: {icon_pairs}."
        )

    if tagline:
        layout_lines.append(
            "- TAGLINE PLACEMENT: A small, elegant line of text below the icons "
            "(or above the CTA), centered, in clean sans-serif."
        )

    if cta:
        layout_lines.append(
            "- CTA PLACEMENT: At the bottom-center, render the CALL_TO_ACTION as either an elegant "
            "script-style line of text or a prominent pill-shaped button in the brand accent color."
        )

    if signals:
        layout_lines.append(
            "- TRUST STRIP PLACEMENT: A thin full-width horizontal band at the very bottom of the "
            "image, containing the TRUST_STRIP_ITEMS separated by vertical pipes or thin dividers, "
            "in small-caps or tracked sans-serif."
        )

    style_parts: list[str] = []
    if mood:
        style_parts.append(mood)
    if palette:
        style_parts.append(f"palette of {palette}")
    if lighting:
        style_parts.append(lighting)
    if typo:
        style_parts.append(f"typography: {typo}")
    style_parts.append("premium commercial photography quality")
    layout_lines.append("- STYLE AND TONE: " + ", ".join(style_parts) + ".")

    sections.append("VISUAL AND LAYOUT INSTRUCTIONS:\n" + "\n".join(layout_lines))

    # Final non-negotiable directives
    sections.append(
        "QUALITY REQUIREMENTS: All text must be perfectly legible and correctly spelled - "
        "no garbled letters, no extra characters, no fragmented words. "
        "Render every element listed above. Single unified image, no multiple panels."
    )

    result = "\n\n".join(s for s in sections if s)
    logger.info("[formatter][gpt_image_2] %d->%d chars", len(base_prompt), len(result))
    return result


# ----------------------------------------------------------------------
# Flux formatter
# ----------------------------------------------------------------------

def _format_for_flux(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Natural-language scene description for Flux models.

    Flux (FLUX.1) is a diffusion model trained on photographic captions  -  not
    design briefs. It works best with:
      - Natural scene description (camera, lens, light physics)
      - Minimal layout/structural language ("locked across", "lower third" -> bad)
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

    logger.info("[formatter][flux] %d->%d chars", len(base_prompt), len(cleaned))
    return cleaned


# ----------------------------------------------------------------------
# Google Imagen formatter
# ----------------------------------------------------------------------
# Imagen models (Imagen 3 / 4 / Gemini Imagen) have a sentence-level distiller
# (_distill_for_imagen in multi_provider_client.py) that runs INSIDE _call_google.
# That distiller drops any sentence with 2+ designer-brief vocab matches and
# extracts max 3 quoted strings as text-to-render.
#
# Strategy: build a PRE-DISTILLED prompt from structured data so it survives
# distillation cleanly. We feed Imagen exactly what it can handle:
#   - One natural-language scene sentence (no designer vocab)
#   - Up to 3 quoted text strings (headline, subhead, CTA  -  in that priority)
# Icon badges, trust strips, layout zones  -  Imagen cannot render them; do not
# include them in the prompt or they become visual clutter / garbled text.
#
# This is universal: works for beauty / food / events / sales / wishes  -  any
# subject. Fields come from Haiku's structured output, not from category templates.

# Designer-brief vocabulary to scrub from Haiku's prompt before sending to Imagen.
# Matches the patterns in _distill_for_imagen but applied PRE-distillation so the
# scene sentence we send is clean from the start.
_IMAGEN_DESIGNER_VOCAB = re.compile(
    r"\b(?:locked\s+across|lockup|anchored\s+to|"
    r"upper\s+third|lower\s+third|top\s+third|bottom\s+third|middle\s+third|"
    r"top[\s-]left|top[\s-]right|bottom[\s-]left|bottom[\s-]right|"
    r"center[\s-]left|center[\s-]right|"
    r"safe[\s-]zone|bleed\s+margin|gutter|safe\s+margin|"
    r"color\s+block|gradient\s+overlay|cream\s+ribbon|ribbon\s+band|"
    r"pill\s+button|cta\s+pill|chip|badge\s+(?:in|at)|"
    r"\d{1,3}\s*%\s+of\s+(?:poster|frame|height|width|image)|"
    r"sans-?serif|serif\b|condensed\s+sans|elegant\s+serif|display\s+\w+|"
    r"font\s+(?:size|weight|family|hierarchy)|"
    r"tracking|leading|kerning|"
    r"3-plane|three[\s-]plane|foreground[\s-]midground[\s-]background|"
    r"85mm|100mm|f/\d+(?:\.\d+)?|focal\s+length|aperture|depth\s+of\s+field|bokeh|"
    r"key\s+light|fill\s+light|rim[\s-]?light|backlight|backlit|"
    r"three[\s-]?point\s+lighting|softbox|"
    r"icon\s+badge(?:s)?|circular\s+icon|line[\s-]art\s+icon|"
    r"trust\s+strip|trust\s+bar|trust\s+band|trust\s+badge"
    r")\b",
    re.IGNORECASE,
)


def _format_for_imagen(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Top-down descriptive narrative for Google Imagen models.

    Research finding (PDF page 4, page 14): Imagen excels with rich, descriptive
    language. Functional labels ("CTA button", "trust bar", "hero headline")
    "are functional labels that the model has no inherent knowledge of". They
    must be translated to their visual descriptions:

      `Good`  "a prominent solid-colored rectangle at the bottom containing the text 'Shop Now'"
      `Bad`  "a CTA button at the bottom reading 'Shop Now'"

    Strategy: build the prompt entirely from structured `simple_payload` data  - 
    do NOT reuse Haiku's `prompt` field (which still contains functional vocab).
    Walk the layout top-down using only spatial prepositions Imagen understands
    ("at the top", "below it", "on the right", "at the very bottom").

    Layout complexity intentionally stays simple  -  research page 12: Imagen's
    "Max Reliably Produced Complexity = Low  -  simple linear or 2x2 block".
    """
    ad_copy: Dict[str, Any] = payload.get("ad_copy") or {}
    visual:  Dict[str, Any] = payload.get("visual") or {}

    headline      = (ad_copy.get("headline") or "").strip()
    subhead       = (ad_copy.get("subhead") or "").strip()
    cta           = (ad_copy.get("cta") or "").strip()
    benefits      = [b for b in (ad_copy.get("benefit_lines") or []) if b]
    signals       = [s for s in (ad_copy.get("trust_signals") or []) if s]
    tagline       = (ad_copy.get("emotional_tagline") or "").strip()
    brand         = (ad_copy.get("brand_name") or "").strip()

    mood          = (visual.get("mood") or "").strip()
    palette       = (visual.get("color_palette") or "").strip()
    lighting      = (visual.get("lighting") or "").strip()
    background    = (visual.get("background") or "").strip()

    intent: str          = (payload.get("intent") or "").strip()
    campaign_type        = (payload.get("campaign_type") or "general").strip()
    subject_category     = (payload.get("subject_category") or "general").strip()

    # Subject  -  what the image is OF. Pull from intent/category, fallback generic.
    if intent and intent not in ("general", ""):
        subject_phrase = intent.replace("_", " ")
    elif subject_category and subject_category != "general":
        subject_phrase = f"{subject_category.replace('_', ' ')} product"
    else:
        subject_phrase = "product"

    sentences: list[str] = []

    # -- 1. Opening framing (mood + category + subject) ----------------------------------------------------------------------
    mood_word = mood.split(",")[0].strip() if mood else "polished"
    if campaign_type and campaign_type not in ("general", ""):
        camp = campaign_type.replace("_", " ")
        opener = f"A {mood_word} {camp} advertisement"
    else:
        opener = f"A {mood_word} commercial advertisement"
    if brand:
        opener += f" for {brand}"
        if subject_phrase and subject_phrase.lower() not in brand.lower():
            opener += f" {subject_phrase}"
    elif subject_phrase:
        opener += f" for {subject_phrase}"
    sentences.append(opener + ".")

    # -- 2. Background / scene base ----------------------------------------------------------------------
    if background:
        bg_clean = _IMAGEN_DESIGNER_VOCAB.sub("", background).strip()
        if bg_clean:
            sentences.append(f"The background is {bg_clean}.")

    # -- 3. Top-down spatial walk-through ----------------------------------------------------------------------
    # Top-left: brand mark (if brand exists)
    if brand:
        sentences.append(
            f"At the very top-left, a small clean rectangle contains the text \"{brand}\"."
        )

    # Upper-center: headline
    if headline:
        sentences.append(
            f"Centered in the upper portion, a large bold line of text reads \"{headline}\"."
        )

    # Just below headline: subheadline (italic/script described visually)
    if subhead:
        sentences.append(
            f"Just beneath it, in elegant italic script, a smaller line reads \"{subhead}\"."
        )

    # Hero product on the right (only describe if we have category context)
    if subject_category in ("beauty", "food", "fashion", "tech", "health"):
        sentences.append(
            f"On the right side of the image is a high-resolution photograph of the {subject_phrase}."
        )

    # Below product / mid-band: benefit row (max 4  -  Imagen complexity ceiling)
    if benefits and len(benefits) >= 2:
        labels = ", ".join(f'"{b}"' for b in benefits[:4])
        sentences.append(
            f"Below the product image, {len(benefits[:4])} small circles arranged horizontally, "
            f"each containing a simple line drawing and a label: {labels}."
        )

    # Tagline: small line of text (single sentence, no functional label)
    if tagline:
        # Truncate if extremely long  -  Imagen renders clearer with terse strings
        tagline_short = tagline[:120].rstrip(",.;: ")
        sentences.append(
            f"Beneath that, a small line of text reads \"{tagline_short}\"."
        )

    # Bottom-center: CTA (rectangle, not "button")
    if cta:
        sentences.append(
            f"At the very bottom, centered and prominent, a small solid-colored rectangle "
            f"contains the text \"{cta}\"."
        )

    # Above bottom: trust banner (max 4 items)
    if signals:
        signal_labels = ", ".join(f'"{s}"' for s in signals[:4])
        sentences.append(
            f"Just above it, a thin horizontal banner contains {len(signals[:4])} small icons "
            f"each labeled with one of: {signal_labels}."
        )

    # -- 4. Closing aesthetic anchor (palette + lighting) ----------------------------------------------------------------------
    closing_parts: list[str] = []
    if palette:
        palette_clean = _IMAGEN_DESIGNER_VOCAB.sub("", palette).strip().rstrip(",.;:")
        if palette_clean:
            closing_parts.append(f"{palette_clean} palette")
    if lighting:
        light_clean = _IMAGEN_DESIGNER_VOCAB.sub("", lighting).strip().rstrip(",.;:")
        if light_clean:
            closing_parts.append(f"{light_clean}")
    closing_parts.append("premium commercial photography style, single unified composition")
    sentences.append(", ".join(closing_parts).capitalize() + ".")

    result = " ".join(s for s in sentences if s).strip()
    # Final scrub  -  guarantee no functional vocab leaked through.
    result = _IMAGEN_DESIGNER_VOCAB.sub("", result)
    result = re.sub(r"  +", " ", result).strip()

    logger.info(
        "[formatter][imagen] %d->%d chars (sentences=%d)",
        len(base_prompt), len(result), len(sentences),
    )
    return result


# ----------------------------------------------------------------------
# WaveSpeed formatter (wan_2_7, grok_2_imagine, hunyuan_image)
# ----------------------------------------------------------------------
# These models render visual scenes beautifully but cannot reliably produce
# multi-element on-image text. Layout / icon / trust-strip instructions just
# add noise. Send a pure photographic scene and skip text-rendering hints.

def _format_for_wavespeed(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Scene-only prompt for WaveSpeed models (wan_2_7 etc.)."""
    visual: Dict[str, Any] = payload.get("visual") or {}
    ad_copy: Dict[str, Any] = payload.get("ad_copy") or {}

    # Strip the affirmative anchor and designer vocab; keep scene intact.
    scene = re.sub(
        r"^\s*ONE single unified (?:image|photograph)[^.]*\.\s*",
        "",
        base_prompt,
        flags=re.IGNORECASE,
    ).strip()
    scene = _IMAGEN_DESIGNER_VOCAB.sub("", scene)
    scene = re.sub(r"  +", " ", scene).strip()

    parts: list[str] = []
    if scene:
        parts.append(scene)

    # Add only the headline as a single text hint  -  wan_2_7 sometimes
    # renders short text. No subhead, no benefits, no trust strip.
    headline = (ad_copy.get("headline") or "").strip()
    if headline and f'"{headline}"' not in scene:
        parts.append(f'Bold text reading "{headline}" placed prominently.')

    palette = (visual.get("color_palette") or "").strip()
    if palette and "palette" not in palette.lower():
        parts.append(f"Color tones of {palette}.")

    result = " ".join(parts).strip()
    logger.info("[formatter][wavespeed] %d->%d chars", len(base_prompt), len(result))
    return result

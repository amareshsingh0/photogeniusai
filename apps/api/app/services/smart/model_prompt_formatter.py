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
        # Build a pre-distilled scene prompt from structured data so it
        # SURVIVES _distill_for_imagen() in _call_google() without losing
        # the headline/subhead/CTA quoted strings.
        return _format_for_imagen(base_prompt, simple_payload)

    if model_key in _WAVESPEED_PASS:
        # WaveSpeed models (wan_2_7, grok_2_imagine, hunyuan_image) cannot
        # reliably render multi-element text. Strip text-rendering expectations
        # and send a pure scene description.
        return _format_for_wavespeed(base_prompt, simple_payload)

    # Unknown / future models — pass through.
    return base_prompt


# ─────────────────────────────────────────────────────────────────────────────
# GPT Image 2 formatter
# ─────────────────────────────────────────────────────────────────────────────

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
    """ChatGPT-level creative brief for GPT Image 2.

    GPT Image 2 (gpt-image-2) is the same model powering ChatGPT Images.
    ChatGPT internally expands user prompts into detailed structured briefs
    before calling the model — that's why ChatGPT output quality is higher.
    This function replicates that expansion: explicit layout zones, icon badge
    specs, trust strip, composition guides, and mixed-typography instructions.
    """
    ad_copy: Optional[Dict] = payload.get("ad_copy") or {}
    visual:  Optional[Dict] = payload.get("visual") or {}
    campaign_type:    str = payload.get("campaign_type", "general")
    subject_category: str = payload.get("subject_category", "general")

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

    sections: list[str] = []

    # ── 1. Creative brief header ──────────────────────────────────────────────
    camp_label = campaign_type.replace("_", " ")
    cat_label  = subject_category.replace("_", " ")
    quality_ref = {
        "beauty":       "Estée Lauder / Charlotte Tilbury / Glossier",
        "tech":         "Apple / Sony / Samsung",
        "food":         "Ottolenghi editorial / Bon Appétit",
        "fashion":      "Vogue editorial / Zara campaign",
        "health":       "Headspace / Nike Training",
        "real_estate":  "Sotheby's / premium real estate",
        "education":    "Coursera / Harvard Extension",
    }.get(subject_category, "Apple / Nike / premium brand")

    header = (
        f"Create a world-class, print-ready {camp_label} advertisement "
        f"for the {cat_label} industry. "
        f"Quality target: {quality_ref} campaign level. "
        "Single unified composition — ONE image, no panels, no variants, no collage."
    )
    sections.append(header)

    # ── 2. Visual scene (Haiku's prompt — anchor stripped) ───────────────────
    scene = re.sub(
        r"^\s*ONE single unified (?:image|photograph)[^.]*\.\s*",
        "",
        base_prompt,
        flags=re.IGNORECASE,
    ).strip()
    if scene:
        sections.append(f"VISUAL SCENE:\n{scene}")

    # ── 3. Text & layout elements ─────────────────────────────────────────────
    layout_lines: list[str] = []

    if brand_name:
        layout_lines.append(
            f'Brand mark — top-left corner: render "{brand_name}" as an elegant '
            f'brand wordmark/logo in the brand typography style.'
        )

    is_launch = campaign_type in ("product_launch", "announcement")
    if is_launch:
        layout_lines.append(
            '"NEW LAUNCH" label — small, elegant, with thin horizontal rules on each side, '
            "positioned just above the main headline. Use small-caps or light tracking."
        )

    if headline:
        layout_lines.append(
            f'Hero headline — large, bold, commanding: "{headline}" '
            f"— uppercase bold condensed sans-serif, prominently sized, "
            f"primary focal point for the text area."
        )

    if subhead:
        layout_lines.append(
            f'Subheadline — elegant italic or script style below the headline: "{subhead}" '
            f"— use a contrasting script or italic font to pair with the bold headline."
        )

    # Product intro line (derived from brand + campaign type)
    if brand_name and is_launch:
        prod_type = cat_label.title() if cat_label != "general" else "Product"
        layout_lines.append(
            f'Product introduction — small regular weight text: '
            f'"Introducing {brand_name}" followed by a styled product-category badge.'
        )

    if benefits and len(benefits) >= 2:
        icon_items = " | ".join(
            f'"{b}" ({_guess_icon(b)})' for b in benefits[:5]
        )
        layout_lines.append(
            f"Feature icon badges row — render {len(benefits[:5])} items arranged "
            f"horizontally in a row. Each item: a small circle with a minimal line-art "
            f"icon inside + 2-line label text below. Items: {icon_items}."
        )
    elif benefits:
        for b in benefits:
            layout_lines.append(f'Benefit point: "{b}"')

    if tagline:
        layout_lines.append(
            f'Emotional tagline — small, elegant, centered below the icons: "{tagline}"'
        )

    if cta:
        layout_lines.append(
            f'Call-to-action: "{cta}" — style as elegant script text, a pill button, '
            f"or a prominently styled action label with a decorative element (heart ♡, arrow)."
        )

    if signals:
        trust_bar_text = " | ".join(signals[:5])
        layout_lines.append(
            f"Bottom trust strip — a thin horizontal band running across the full bottom edge "
            f"of the image, slightly lighter background than main, small-caps or tracking text: "
            f'"{trust_bar_text}"'
        )

    # Top-right trust badge (if signals available and beauty/health category)
    if signals and subject_category in ("beauty", "health", "food"):
        badge_text = signals[0] if len(signals) == 1 else f"Trusted by thousands"
        layout_lines.append(
            f'Optional trust badge — small circular badge top-right corner with text: '
            f'"{badge_text}" arranged around a central heart or checkmark icon.'
        )

    if layout_lines:
        sections.append(
            "TEXT & LAYOUT ELEMENTS "
            "(render each exactly as described — correct spelling, professional execution):\n"
            + "\n".join(f"• {line}" for line in layout_lines)
        )

    # ── 4. Visual direction ───────────────────────────────────────────────────
    visual_parts: list[str] = []
    if mood:
        visual_parts.append(f"Mood: {mood}")
    if palette:
        visual_parts.append(f"Color palette: {palette}")
    if lighting:
        visual_parts.append(f"Lighting: {lighting}")
    if background:
        visual_parts.append(f"Background: {background}")
    if composition:
        visual_parts.append(f"Composition: {composition}")
    if typo:
        visual_parts.append(f"Typography style: {typo}")
    if visual_parts:
        sections.append("VISUAL DIRECTION: " + " | ".join(visual_parts))

    # ── 5. Final quality & typography instruction ─────────────────────────────
    comp_hint = (
        "Composition: text hierarchy on left or center-left, hero product/subject on right "
        "or center-right — classic beauty-ad split layout."
        if subject_category in ("beauty", "fashion", "health")
        else "Single unified composition with clear visual hierarchy."
    )
    sections.append(
        "TYPOGRAPHY REQUIREMENTS: Use mixed typography — bold condensed uppercase sans-serif "
        "for the hero headline (large, prominent, commanding). Pair with elegant italic or "
        "script font for the subheadline and CTA (creates the premium high-low contrast). "
        "Small clean sans-serif for body copy, benefits, and trust strip. "
        "All text perfectly legible, correctly spelled, no garbled letters, no extra characters. "
        f"{comp_hint} "
        "Render as a finished, professional, print-ready advertisement. "
        "Premium commercial photography / design quality."
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


# ─────────────────────────────────────────────────────────────────────────────
# Google Imagen formatter
# ─────────────────────────────────────────────────────────────────────────────
# Imagen models (Imagen 3 / 4 / Gemini Imagen) have a sentence-level distiller
# (_distill_for_imagen in multi_provider_client.py) that runs INSIDE _call_google.
# That distiller drops any sentence with 2+ designer-brief vocab matches and
# extracts max 3 quoted strings as text-to-render.
#
# Strategy: build a PRE-DISTILLED prompt from structured data so it survives
# distillation cleanly. We feed Imagen exactly what it can handle:
#   - One natural-language scene sentence (no designer vocab)
#   - Up to 3 quoted text strings (headline, subhead, CTA — in that priority)
# Icon badges, trust strips, layout zones — Imagen cannot render them; do not
# include them in the prompt or they become visual clutter / garbled text.
#
# This is universal: works for beauty / food / events / sales / wishes — any
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
    """Pre-distilled prompt for Google Imagen models.

    Imagen renders text via quoted strings (max 3) plus a clean scene
    description. Layout / icon / trust-strip instructions are stripped by
    Imagen's internal distiller and waste tokens. Build the right prompt
    upstream so the distiller has nothing to fight.
    """
    ad_copy: Dict[str, Any] = payload.get("ad_copy") or {}
    visual:  Dict[str, Any] = payload.get("visual") or {}

    # Strip the affirmative anchor — _call_google handles its own framing.
    scene = re.sub(
        r"^\s*ONE single unified (?:image|photograph)[^.]*\.\s*",
        "",
        base_prompt,
        flags=re.IGNORECASE,
    ).strip()

    # Scrub designer-brief vocab from the scene so the distiller doesn't
    # nuke whole sentences. We do this PRE-distillation so the scene survives.
    scene = _IMAGEN_DESIGNER_VOCAB.sub("", scene)
    scene = re.sub(r"  +", " ", scene)
    scene = re.sub(r"\s+([,.;:])", r"\1", scene)
    scene = re.sub(r"([,.;])\s*\1+", r"\1", scene).strip()

    # Pick max 3 priority quoted strings. Order matters — Imagen's distiller
    # renders the FIRST quoted string biggest, second smaller, third smallest.
    headline = (ad_copy.get("headline") or "").strip()
    subhead  = (ad_copy.get("subhead") or "").strip()
    cta      = (ad_copy.get("cta") or "").strip()
    brand    = (ad_copy.get("brand_name") or "").strip()

    priority_texts: list[str] = []
    if headline:
        priority_texts.append(headline)
    if subhead:
        priority_texts.append(subhead)
    if cta:
        priority_texts.append(cta)
    elif brand and len(priority_texts) < 3:
        priority_texts.append(brand)
    priority_texts = priority_texts[:3]

    # Append a tight "the image shows the text..." block so the distiller's
    # quoted-string extractor finds them in priority order.
    parts: list[str] = []
    if scene:
        parts.append(scene)

    # Light visual cue from structured data — palette + lighting only. These
    # SURVIVE distillation when phrased as natural sentences (no "palette:").
    palette  = (visual.get("color_palette") or "").strip()
    lighting = (visual.get("lighting") or "").strip()
    mood     = (visual.get("mood") or "").strip()
    if palette and "palette" not in palette.lower():
        parts.append(f"Color tones of {palette}.")
    if lighting and not _IMAGEN_DESIGNER_VOCAB.search(lighting):
        parts.append(f"Lit with {lighting}.")
    if mood:
        parts.append(f"Overall {mood} mood.")

    # Quoted strings — natural phrasing, not labels. Distiller picks these up.
    if priority_texts:
        text_phrases = []
        for i, t in enumerate(priority_texts):
            if i == 0:
                text_phrases.append(f'the words "{t}" rendered prominently')
            elif i == 1:
                text_phrases.append(f'with "{t}" beneath')
            else:
                text_phrases.append(f'and a small "{t}"')
        parts.append("The image shows " + ", ".join(text_phrases) + ".")

    result = " ".join(parts).strip()
    logger.info(
        "[formatter][imagen] %d→%d chars (texts=%d)",
        len(base_prompt), len(result), len(priority_texts),
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# WaveSpeed formatter (wan_2_7, grok_2_imagine, hunyuan_image)
# ─────────────────────────────────────────────────────────────────────────────
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

    # Add only the headline as a single text hint — wan_2_7 sometimes
    # renders short text. No subhead, no benefits, no trust strip.
    headline = (ad_copy.get("headline") or "").strip()
    if headline and f'"{headline}"' not in scene:
        parts.append(f'Bold text reading "{headline}" placed prominently.')

    palette = (visual.get("color_palette") or "").strip()
    if palette and "palette" not in palette.lower():
        parts.append(f"Color tones of {palette}.")

    result = " ".join(parts).strip()
    logger.info("[formatter][wavespeed] %d→%d chars", len(base_prompt), len(result))
    return result

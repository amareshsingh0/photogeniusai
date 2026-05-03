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
# Ad-intent detector (shared by GPT + Imagen formatters)
# ----------------------------------------------------------------------
# Round 3: not every prompt is an ad. "car on mars", "portrait of a woman",
# "anime cat in a forest" are pure scenes - they have NO ad copy, NO brand,
# NO CTA. For these, the ad-template formatters were forcing "advertisement"
# language and breaking the output. Detect ad-intent and branch accordingly.

def _is_ad_intent(payload: Dict[str, Any]) -> bool:
    """True only when the request is a STRUCTURED AD (vs scene/portrait/typographic-scene).

    A "neon sign with text", "graffiti on wall", "book cover", "billboard with one
    word", "coffee cup with slogan" all have a `headline` quoted text but they are
    NOT structured ads - they are scenes whose subject happens to include text.
    Real ads have multiple ad signals: brand + CTA, benefits/trust lists, an
    explicit campaign, or a formal copywriting formula.

    Strong ad signals (any one triggers AD MODE):
      - benefit_lines or trust_signals populated
      - explicit campaign_type (product_launch / sale / event / etc.)
      - formal copywriting formula (AIDA / PAS / BAB)
      - brand_name AND (cta OR emotional_tagline)
      - >=2 text element types beyond just `headline`

    Otherwise => SCENE MODE (which now handles in-scene text via the
    typographic-scene recipe).
    """
    ad_copy = payload.get("ad_copy") or {}
    has_lists = bool(ad_copy.get("benefit_lines") or ad_copy.get("trust_signals"))
    has_brand = bool((ad_copy.get("brand_name") or "").strip())
    has_cta   = bool((ad_copy.get("cta") or "").strip())
    has_tagln = bool((ad_copy.get("emotional_tagline") or "").strip())
    has_subh  = bool((ad_copy.get("subhead") or "").strip())

    extra_text_types = sum([has_subh, has_brand, has_cta, has_tagln])

    campaign = (payload.get("campaign_type") or "general").strip().lower()
    formula  = (payload.get("copywriting_formula") or "simple").strip().lower()

    if has_lists:                                  return True
    if has_brand and (has_cta or has_tagln):       return True
    if extra_text_types >= 2:                      return True
    if campaign not in ("", "general"):            return True
    if formula in ("aida", "pas", "bab"):          return True
    return False


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


def _format_for_gpt_scene(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Photographer/cinematographer brief for non-ad GPT Image 2 prompts.

    Covers two sub-cases:
      a) PURE SCENE - no text (car on mars, portrait, landscape, anime, fantasy)
      b) TYPOGRAPHIC SCENE - text IS the subject (neon sign, graffiti, book
         cover, billboard, T-shirt slogan, carved sign, embroidered patch)

    For (b) we inject a TEXT IN SCENE section that names the text material/font
    style so models know to render the text as a physical object integrated
    into the scene, not as overlaid graphics.
    """
    visual: Dict[str, Any] = payload.get("visual") or {}
    ad_copy: Dict[str, Any] = payload.get("ad_copy") or {}
    intent: str = (payload.get("intent") or "").strip()
    subject_category: str = payload.get("subject_category", "general")

    # Strip the affirmative anchor - GPT does not need it.
    scene = re.sub(
        r"^\s*ONE single unified (?:image|photograph)[^.]*\.\s*",
        "",
        base_prompt,
        flags=re.IGNORECASE,
    ).strip()

    headline = (ad_copy.get("headline") or "").strip()
    typo_style = (visual.get("typography_style") or "").strip()
    is_typographic_scene = bool(headline)

    # Category-specific photographer persona.
    if is_typographic_scene:
        # Typographic scene specialist - typographer + photographer hybrid.
        persona = (
            "world-class typographic designer and photographer who specializes "
            "in physical signage, sculptural lettering, and integrated environmental type"
        )
    else:
        persona = {
            "portrait":             "world-class portrait photographer in the style of Annie Leibovitz",
            "photorealism_portrait":"world-class portrait photographer in the style of Annie Leibovitz",
            "anime":                "world-class anime art director in the studio Ghibli tradition",
            "vector":               "world-class vector illustrator and graphic designer",
            "artistic":             "world-class fine-art digital painter",
            "photorealism":         "world-class commercial photographer and cinematographer",
        }.get(subject_category, "world-class commercial photographer and cinematographer")

    sections: list[str] = [f"Act as a {persona}."]

    # Primary command.
    command_subject = intent.replace("_", " ") if intent and intent not in ("general", "scene") else "scene"
    sections.append(
        "PRIMARY COMMAND:\n"
        f"Generate a single, polished, high-fidelity image of the following {command_subject}. "
        "Single unified composition - no panels, no variants, no collage."
    )

    # Scene description - directly from Haiku.
    if scene:
        sections.append(f"SCENE DESCRIPTION:\n{scene}")

    # TEXT IN SCENE - only for typographic scenes. Explicitly tells the model
    # the text is a PHYSICAL object in the scene with material + font style.
    if is_typographic_scene:
        text_lines = [f'- PRIMARY TEXT: "{headline}"']
        if typo_style:
            text_lines.append(f"- TYPOGRAPHY MATERIAL/STYLE: {typo_style}")
        else:
            text_lines.append(
                "- TYPOGRAPHY MATERIAL/STYLE: Match the material implied by the scene "
                "(e.g. glowing neon tubes for a neon sign, painted brushstrokes for graffiti, "
                "embossed metal for a plaque, foil-stamped for a book cover). Render text as a "
                "physical object integrated into the scene, not as overlaid 2D graphics."
            )
        # Optional secondary text from subhead if present (rare in scene mode).
        subhead = (ad_copy.get("subhead") or "").strip()
        if subhead:
            text_lines.append(f'- SECONDARY TEXT: "{subhead}" (smaller, supporting hierarchy)')
        sections.append("TEXT IN SCENE (render as a physical object, correct spelling):\n" + "\n".join(text_lines))

    # Visual direction (light/palette/mood/composition) as bullets.
    visual_lines: list[str] = []
    if visual.get("lighting"):      visual_lines.append(f"- LIGHTING: {visual['lighting']}")
    if visual.get("color_palette"): visual_lines.append(f"- PALETTE: {visual['color_palette']}")
    if visual.get("mood"):          visual_lines.append(f"- MOOD: {visual['mood']}")
    if visual.get("composition"):   visual_lines.append(f"- COMPOSITION: {visual['composition']}")
    if visual.get("background"):    visual_lines.append(f"- BACKGROUND: {visual['background']}")
    if visual_lines:
        sections.append("VISUAL DIRECTION:\n" + "\n".join(visual_lines))

    # Quality block - swap text-legibility emphasis when it's a typographic scene.
    if is_typographic_scene:
        sections.append(
            "QUALITY REQUIREMENTS: Photorealistic material rendering of the text "
            "(real glass/metal/paint/wood/fabric/light), correct spelling, accurate "
            "lighting and shadows on the lettering, the text fully integrated into the "
            "scene's lighting and perspective. No garbled letters, no extra characters."
        )
    else:
        sections.append(
            "QUALITY REQUIREMENTS: Photorealistic detail, cinematic lighting, "
            "high dynamic range, sharp focus on the subject with natural depth-of-field "
            "fall-off, accurate shadows and reflections, no garbled artifacts, "
            "no distorted anatomy, single unified scene."
        )

    result = "\n\n".join(s for s in sections if s)
    mode = "typographic-scene" if is_typographic_scene else "scene"
    logger.info("[formatter][gpt_image_2][%s] %d->%d chars", mode, len(base_prompt), len(result))
    return result


def _format_for_gpt(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Sectioned imperative template for GPT Image 2.

    Research (PDF page 13) prescribes this exact format for ADS:
      1. Persona prefix ("Act as a world-class advertising art director...")
      2. PRIMARY COMMAND: <one sentence describing the deliverable>
      3. TEXT ELEMENTS TO RENDER (USE EXACTLY THESE STRINGS): key/value list
      4. VISUAL AND LAYOUT INSTRUCTIONS: bullet list of placements

    GPT Image 2 is built to parse imperative sectioned commands, not narrative
    prose. ASCII output only - no unicode symbols (provider/log encoding safety).

    Round 3: branches into SCENE MODE (photographer persona) when the request
    is a pure scene/portrait with no ad copy.
    """
    if not _is_ad_intent(payload):
        return _format_for_gpt_scene(base_prompt, payload)

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
    # Note: top-left/top-right/etc REMOVED - Imagen needs spatial words.
    # The formatter constructs "At the very top-left, ..." sentences and the
    # strip was nuking the position word, leaving "At the very , ..." garbage.
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


def _format_for_imagen_scene(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Scene descriptor for Google Imagen on non-ad prompts.

    Two sub-cases handled:
      a) PURE SCENE - no on-image text. Sends Haiku's enriched scene with light
         designer-vocab scrub.
      b) TYPOGRAPHIC SCENE - text is a physical subject (neon sign, graffiti).
         Ensures the text string is quoted in the prompt so Imagen's distiller
         picks it up as text-to-render, with material context.
    """
    visual: Dict[str, Any] = payload.get("visual") or {}
    ad_copy: Dict[str, Any] = payload.get("ad_copy") or {}

    # Strip the affirmative anchor and scrub designer-brief vocab.
    scene = re.sub(
        r"^\s*ONE single unified (?:image|photograph)[^.]*\.\s*",
        "",
        base_prompt,
        flags=re.IGNORECASE,
    ).strip()
    scene = _IMAGEN_DESIGNER_VOCAB.sub("", scene)
    scene = re.sub(r"  +", " ", scene)
    scene = re.sub(r"\s+([,.;:])", r"\1", scene)
    scene = re.sub(r"([,.;])\s*\1+", r"\1", scene).strip()

    parts: list[str] = []
    if scene:
        parts.append(scene)

    # Typographic scene - ensure the text is quoted (distiller extracts up to
    # 3 quoted strings) AND inject typography material context so the rendering
    # is a physical object, not floating overlay graphics.
    headline = (ad_copy.get("headline") or "").strip()
    typo_style = (visual.get("typography_style") or "").strip()
    if headline:
        text_already_quoted = f'"{headline}"' in scene or f"'{headline}'" in scene
        if not text_already_quoted:
            parts.append(f'The image shows the text "{headline}" rendered prominently.')
        if typo_style:
            parts.append(
                f'The lettering is {typo_style}, physically integrated into the scene with '
                "matching lighting, shadows, and perspective."
            )
        else:
            parts.append(
                "The lettering is a physical object in the scene "
                "with material consistent with the setting."
            )

    # Light visual reinforcement from structured fields.
    palette  = (visual.get("color_palette") or "").strip()
    lighting = (visual.get("lighting") or "").strip()
    mood     = (visual.get("mood") or "").strip()
    if palette and "palette" not in palette.lower():
        clean = _IMAGEN_DESIGNER_VOCAB.sub("", palette).strip().rstrip(",.;:")
        if clean:
            parts.append(f"Color tones of {clean}.")
    if lighting and not _IMAGEN_DESIGNER_VOCAB.search(lighting):
        clean = lighting.strip().rstrip(",.;:")
        if clean:
            parts.append(f"Lit with {clean}.")
    if mood:
        parts.append(f"Overall {mood} mood.")

    parts.append(
        "Photorealistic, high-fidelity, single unified composition, "
        "premium photography quality."
    )

    result = " ".join(p for p in parts if p).strip()
    mode = "typographic-scene" if headline else "scene"
    logger.info("[formatter][imagen][%s] %d->%d chars", mode, len(base_prompt), len(result))
    return result


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

    Round 3: branches into SCENE MODE (preserves Haiku's rich photoreal prompt)
    when the request is a pure scene/portrait with no ad copy.
    """
    if not _is_ad_intent(payload):
        return _format_for_imagen_scene(base_prompt, payload)

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

    # Subject  -  what the image is OF. Pull from category first (more concrete),
    # then a clean intent if it's not a generic word like "ad"/"poster"/"general".
    # Reject filler intents that produce garbage like "photograph of the ad".
    _GENERIC_INTENTS = {"ad", "advertisement", "poster", "banner", "creative",
                        "image", "graphic", "design", "general", "story", "post"}
    if subject_category and subject_category not in ("", "general"):
        cat_clean = subject_category.replace("_", " ")
        # Avoid "beauty product" duplication when category already concrete
        subject_phrase = cat_clean if cat_clean.endswith(("product", "good", "item", "service")) else f"{cat_clean} product"
    elif intent and intent not in _GENERIC_INTENTS:
        subject_phrase = intent.replace("_", " ")
    else:
        subject_phrase = "product"

    sentences: list[str] = []

    # -- 1. Opening framing (mood + category + subject) ----------------------------------------------------------------------
    mood_word = mood.split(",")[0].strip() if mood else "polished"
    # Pick correct article (a/an) based on first vowel of mood_word.
    article = "an" if mood_word and mood_word[0].lower() in "aeiou" else "a"
    if campaign_type and campaign_type not in ("general", ""):
        camp = campaign_type.replace("_", " ")
        opener = f"{article.capitalize()} {mood_word} {camp} advertisement"
    else:
        opener = f"{article.capitalize()} {mood_word} commercial advertisement"
    # Append brand and subject only when meaningful and non-duplicative.
    sp_lower = subject_phrase.lower().strip()
    brand_lower = brand.lower().strip()
    if brand:
        opener += f" for {brand}"
        # Add subject only if it adds info (not "product", not the brand name).
        if sp_lower and sp_lower != "product" and sp_lower not in brand_lower and brand_lower not in sp_lower:
            opener += f" {subject_phrase}"
    elif subject_phrase and sp_lower != "product":
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

    # Hero product on the right (only describe if we have a CONCRETE category;
    # generic "product" / "ad" produces meaningless "photograph of the ad" text).
    if subject_category in ("beauty", "food", "fashion", "tech", "health") and \
       subject_phrase and subject_phrase.lower() not in ("product", "ad", "advertisement", "general"):
        # Use brand-aware phrasing when brand exists, else just category subject.
        hero_subject = f"{brand} {subject_phrase}".strip() if brand else subject_phrase
        sentences.append(
            f"On the right side of the image is a high-resolution photograph of the {hero_subject}."
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

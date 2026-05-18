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
_GPT_MODELS     = {"gpt_image_2", "gpt_image_2_edit"}
_FLUX_MODELS    = {"flux_2_flex", "flux_2_pro", "flux_kontext", "flux_kontext_max",
                   "flux_2_dev", "flux_2_turbo", "flux_2_max", "flux_fill"}
_GOOGLE_MODELS  = {"gemini_3_imagen", "gemini_3_1_imagen", "imagen_4_base",
                   "imagen_4_ultra", "imagen_4_fast", "imagen_3"}
_WAVESPEED_PASS = {"wan_2_7", "grok_2_imagine", "hunyuan_image"}


# ----------------------------------------------------------------------
# Category -> concrete product noun map
# ----------------------------------------------------------------------
# Imagen + Wan have NO inherent knowledge of category abstractions like
# "alcohol_beverage" or "beauty_cosmetics". They render best when given a
# concrete photograph-able noun (e.g. "premium spirit bottle", "cosmetic
# compact"). Without this map, formatters fell back to "<category> product"
# which Imagen interpreted as e.g. "alcohol_beverage food product" -> chocolate
# dessert (May 4 2026 visual regression for Wan + both Imagen models).
#
# Keys match category_recipes_mined.json (Pitt taxonomy) + manual recipes.
_CATEGORY_PRODUCT_NOUN: Dict[str, str] = {
    # Pitt-mined categories
    "restaurant_cafe":         "gourmet plated dish",
    "chocolate_candy":         "premium chocolate piece",
    "snacks_packaged":         "snack product packaging",
    "seasoning_condiments":    "condiment bottle",
    "pet_care":                "pet food package",
    "alcohol_beverage":        "premium dark glass spirit bottle with elegant label",
    "coffee_tea":              "specialty coffee cup",
    "beverage_soft":           "soft drink bottle or can",
    "automotive":              "premium vehicle",
    "consumer_electronics":    "consumer electronic device",
    "telecom_isp":             "smartphone with network UI",
    "financial_services":      "credit card or banking app screen",
    "education":               "graduation cap and books",
    "security_safety":         "home security device",
    "saas_software":           "laptop screen showing software UI",
    "professional_services":   "professional service scene",
    "beauty_cosmetics":        "luxury cosmetic compact or bottle",
    "healthcare":              "wellness product packaging",
    "fashion_apparel":         "designer clothing or accessory",
    "baby_products":           "baby product package",
    "games_toys":              "game console or toy product",
    "cleaning_products":       "household cleaning bottle",
    "home_improvement":        "modern interior detail",
    "home_appliances":         "home appliance product",
    "travel_hospitality":      "luxury hotel or travel scene",
    "media_entertainment":     "cinematic scene with title treatment",
    "sports_fitness":          "premium athletic gear",
    "retail_shopping":         "shopping bags and product display",
    "gambling_lottery":        "casino chips or lottery ticket",
    "environment_eco":         "natural eco-friendly product",
    "animal_welfare":          "rescued animal portrait",
    "human_rights":            "symbolic human-rights imagery",
    "safety_awareness":        "public safety scene",
    "political_campaign":      "political campaign poster scene",
    "charity_nonprofit":       "charity / nonprofit imagery",
    # Manual recipes (category_recipes.json)
    "medical_pharma":          "medical product packaging",
    "ayurveda_herbal":         "ayurvedic herbal jar with botanicals",
    "packaging_design":        "premium packaging design",
    "religious_spiritual":     "spiritual scene with traditional motifs",
    "books_publishing":        "book cover with title treatment",
    "music_albums":            "music album cover",
    "podcast_audio":           "podcast cover artwork",
    "sports_team":             "sports team athletic gear",
    "movies_streaming":        "movie poster scene",
    "gaming_esports":          "esports scene with gaming gear",
    "dating_app":              "smartphone with dating app UI",
    "crypto_web3":             "crypto wallet or token visual",
    "salon_spa":               "spa product with botanicals",
    "dental_clinic":           "dental clinic product",
    "optical_eyewear":         "premium eyewear product",
    "school_k12":              "school supplies and books",
    "coaching_test_prep":      "study materials with test books",
    "wedding_services":        "wedding floral arrangement",
    "florist_bouquet":         "fresh flower bouquet",
    "bakery_cake":             "artisan cake or pastry",
    "legal_services":          "legal documents and gavel",
    "insurance_finance":       "insurance documents and security symbols",
    "loans_credit":            "credit card or loan documentation",
    "astrology_numerology":    "celestial chart with mystical motifs",
    "yoga_meditation":         "yoga mat with serene scene",
}


def _product_noun(subject_category: str, brand: str = "", recipe_key: str = "") -> str:
    """Return a concrete product noun for the category.

    Resolution order:
      1. recipe_key (from Gemini classifier - most accurate, e.g. 'alcohol_beverage')
      2. subject_category (from Haiku output - sometimes generic like 'entertainment')
      3. fallback "premium product"

    Why recipe_key wins: Haiku's subject_category enum is broader/looser than the
    Gemini-classified category_key. For "AlcShip alcohol poster", classifier sets
    category_key='alcohol_beverage' (perfect match in noun map), but Haiku may
    set subject_category='entertainment' (no match -> "premium entertainment
    product" garbage). Always prefer the classifier's key when available.
    """
    # Try recipe_key first - it's the Gemini-classified category and matches
    # the _CATEGORY_PRODUCT_NOUN map keys directly.
    if recipe_key and recipe_key not in ("", "general"):
        noun = _CATEGORY_PRODUCT_NOUN.get(recipe_key)
        if noun:
            return noun
    # Then try Haiku's subject_category
    if subject_category and subject_category not in ("", "general"):
        noun = _CATEGORY_PRODUCT_NOUN.get(subject_category)
        if noun:
            return noun
        # Soft fallback: humanize the key
        return f"premium {subject_category.replace('_', ' ')} product"
    return "premium product"

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
        # Edit-mode (gpt_image_2_edit) has a fundamentally different prompt
        # contract than generation-mode per OpenAI's cookbook: 3-sentence
        # Replace/Preserve/Match pattern with single text line, vs the
        # full sectioned ad-brief used for /v1/images/generations. Route
        # based on model variant.
        if model_key == "gpt_image_2_edit":
            return _format_for_gpt_edit(base_prompt, simple_payload)
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
            "portrait":               "world-class portrait photographer in the style of Annie Leibovitz",
            "photorealism_portrait":  "world-class portrait photographer in the style of Annie Leibovitz",
            "anime":                  "world-class anime art director in the studio Ghibli tradition",
            "vector":                 "world-class vector illustrator and graphic designer",
            "artistic":               "world-class fine-art digital painter",
            "photorealism":           "world-class commercial photographer and cinematographer",
            "photorealism_food":      "world-class food photographer in the tradition of David Loftus and Bon Appetit editorial",
            "photorealism_fashion":   "world-class editorial fashion photographer (Vogue / Harper's Bazaar tradition)",
            "photorealism_landscape": "world-class landscape photographer in the tradition of Ansel Adams and Marc Adamus",
            "photorealism_product":   "world-class commercial product photographer specializing in studio packshots",
            "interior_arch":          "world-class architectural and interior photographer (Dezeen / ArchDaily editorial tradition)",
            "multiperson":            "world-class group-portrait photographer who specializes in capturing authentic human interaction",
            "character_consistency":  "world-class character designer producing a model sheet — same identity, varied poses, consistent style",
            "image_to_image":         "world-class image-edit specialist preserving subject identity while transforming the scene as requested",
            "multi_reference":        "world-class composite-image specialist who blends multiple references into one cohesive scene",
            "editing":                "world-class image-edit specialist applying a precise, region-scoped modification",
        }.get(subject_category, "world-class commercial photographer and cinematographer")

    sections: list[str] = [f"Act as a {persona}."]

    # Primary command.
    command_subject = intent.replace("_", " ") if intent and intent not in ("general", "scene") else "scene"
    sections.append(
        "PRIMARY COMMAND:\n"
        f"Generate a single, polished, high-fidelity image of the following {command_subject}. "
        "Single unified composition - no panels, no variants, no collage."
    )

    # Reference handling (May 17 2026) — see _format_for_gpt for rationale.
    ref_roles_payload_s = payload.get("reference_roles") or {}
    n_people_ref_s   = int(ref_roles_payload_s.get("people")   or 0) if isinstance(ref_roles_payload_s, dict) else 0
    n_products_ref_s = int(ref_roles_payload_s.get("products") or 0) if isinstance(ref_roles_payload_s, dict) else 0
    ref_caps_s = payload.get("reference_captions") or {}
    if not isinstance(ref_caps_s, dict):
        ref_caps_s = {}
    if n_people_ref_s or n_products_ref_s:
        ref_bits_s: list[str] = []
        people_caps_s = ref_caps_s.get("people") or []
        product_caps_s = ref_caps_s.get("products") or []
        invariants_s: list[str] = []
        for i, cap in enumerate(people_caps_s):
            if not cap or not cap.strip():
                continue
            label = "person in image 1" if len(people_caps_s) == 1 else f"person in image {i+1}"
            invariants_s.append(
                f"- PRESERVE the {label}: {cap.strip()} "
                f"IGNORE its pose, expression, gaze, hands, outfit, hairstyling, and background."
            )
        for i, cap in enumerate(product_caps_s):
            if not cap or not cap.strip():
                continue
            offset = len(people_caps_s)
            invariants_s.append(
                f"- PRESERVE the product in image {offset + i + 1}: {cap.strip()} "
                f"IGNORE its background and lighting; integrate into the new scene."
            )
        if invariants_s:
            ref_bits_s.extend(invariants_s)
        if n_people_ref_s == 1:
            ref_bits_s.append(
                "- The PERSON reference is an IDENTITY ANCHOR ONLY (face, skin tone, hair, "
                "general build). Do NOT copy pose, expression, hands, body angle, outfit, "
                "or background. Invent a fresh pose and action that fits the scene below."
            )
            ref_bits_s.append(
                "- Wardrobe and accessories follow this prompt — render any glasses, "
                "sunglasses, cap, hat, dress, watch, jewelry, or other items mentioned, "
                "regardless of what the reference person wore."
            )
        elif n_people_ref_s >= 2:
            ref_bits_s.append(
                f"- The {n_people_ref_s} PERSON references are IDENTITY ANCHORS ONLY. "
                "Match each face; invent a NEW group composition with fresh poses and "
                "outfits per this prompt."
            )
        if n_products_ref_s >= 1:
            ref_bits_s.append(
                "- PRODUCT reference(s) define exact packaging/label/color/shape; "
                "placement and lighting come from this prompt."
            )
        sections.append("REFERENCE IMAGE HANDLING:\n" + "\n".join(ref_bits_s))

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


def _format_for_gpt_edit(base_prompt: str, payload: Dict[str, Any]) -> str:
    """Edit-mode formatter for gpt-image-2 /v1/images/edits.

    Different contract than generation-mode (_format_for_gpt). Per OpenAI's
    official cookbook (image-gen-models-prompting-guide):

    1. **3-sentence structure**: Replace [change]. Preserve [locked elements].
       Match [physical realism / lighting / perspective].
    2. **Reference each input by index**: "Image 1: ... Image 2: ...".
    3. **Text rendering**: put literal text in quotes, ALL CAPS for emphasis,
       "no extra words, no duplicate text, no reflow", "ensure text appears
       once and is perfectly legible". Brand names: spell letter-by-letter
       for accuracy.
    4. **No "reserve 35% blank copy space" instruction** - the model treats
       it as "leave area empty" and fails to render text in the reserved
       zone (the blank-bottom-half failure mode for multi-reference ads).
    5. **Reduce text strings**: 1-2 max for edit mode. Multi-line headline +
       subhead + CTA + footer all together overwhelms the parser and the
       reserved space stays blank when rendering fails.
    6. **Skip non-Latin script** for now: transliterated Hindi ("Zara
       Muskuraiye") + English subhead combo is unreliable; community guides
       and OpenAI docs don't validate it. We send the headline as-given but
       constrain to a SINGLE primary line.

    This produces ~1500-2500 char prompts vs ~5000+ for the generation-mode
    template, which matches the playbook length (50-150 word range).
    """
    ad_copy: Dict[str, Any] = payload.get("ad_copy") or {}
    visual:  Dict[str, Any] = payload.get("visual") or {}

    headline   = (ad_copy.get("headline") or "").strip()
    subhead    = (ad_copy.get("subhead") or "").strip()
    cta        = (ad_copy.get("cta") or "").strip()
    brand_name = (ad_copy.get("brand_name") or "").strip()
    tagline    = (ad_copy.get("emotional_tagline") or "").strip()

    mood        = (visual.get("mood") or "").strip()
    palette     = (visual.get("color_palette") or "").strip()
    lighting    = (visual.get("lighting") or "").strip()
    background  = (visual.get("background") or "").strip()

    ref_roles_payload = payload.get("reference_roles") or {}
    if not isinstance(ref_roles_payload, dict):
        ref_roles_payload = {}
    n_people   = int(ref_roles_payload.get("people")   or 0)
    n_products = int(ref_roles_payload.get("products") or 0)
    n_logos    = int(ref_roles_payload.get("logos")    or 0)

    ref_captions_payload = payload.get("reference_captions") or {}
    if not isinstance(ref_captions_payload, dict):
        ref_captions_payload = {}
    people_caps  = ref_captions_payload.get("people")   or []
    product_caps = ref_captions_payload.get("products") or []
    logo_caps    = ref_captions_payload.get("logos")    or []

    sections: list[str] = []

    # ---- SECTION 1: REPLACE / COMPOSE INSTRUCTION ---------------------
    # State what the new image should depict in ONE concise sentence.
    # Build it from depicted_subject + scene cues, no design jargon.
    depicted_subject = (visual.get("depicted_subject") or "").strip()
    scene_bits: list[str] = []
    if depicted_subject:
        scene_bits.append(depicted_subject)
    elif n_people and n_products:
        scene_bits.append("the person holding/using the product in a polished commercial scene")
    elif n_products:
        scene_bits.append("the product as the hero of a polished commercial scene")
    elif n_people:
        scene_bits.append("the person in a polished commercial scene")
    if background:
        scene_bits.append(f"set against {background}")
    if mood:
        scene_bits.append(f"with a {mood} mood")
    compose_sentence = "Compose a single cohesive advertisement image showing " + ", ".join(scene_bits) + "."
    sections.append(compose_sentence)

    # ---- SECTION 2: REFERENCE IMAGE INDEX + ROLES ---------------------
    # OpenAI cookbook prescribes "Image 1: ... Image 2: ..." indexing.
    ref_lines: list[str] = []
    idx = 1
    for cap in people_caps[:n_people or len(people_caps)]:
        cap = (cap or "").strip()
        if cap:
            ref_lines.append(f"Image {idx} is the PERSON whose identity must be preserved: {cap}")
            idx += 1
    for cap in product_caps[:n_products or len(product_caps)]:
        cap = (cap or "").strip()
        if cap:
            ref_lines.append(f"Image {idx} is the PRODUCT whose packaging/shape/colors must be preserved exactly: {cap}")
            idx += 1
    for cap in logo_caps[:n_logos or len(logo_caps)]:
        cap = (cap or "").strip()
        if cap:
            ref_lines.append(f"Image {idx} is the LOGO/WORDMARK to render verbatim with correct spelling: {cap}")
            idx += 1
    if ref_lines:
        sections.append("\n".join(ref_lines))

    # ---- SECTION 3: PRESERVE LIST (per cookbook "repeat preserve list") -
    preserve_lines: list[str] = []
    if n_people:
        preserve_lines.append(
            "Preserve from the person reference ONLY the face, skin tone, hair color and length, "
            "and general build. Invent a fresh natural pose, expression, and outfit that fits the "
            "scene; do NOT copy the reference's pose, gaze, hand position, clothing, or background."
        )
    if n_products:
        preserve_lines.append(
            "Preserve the product's exact packaging, label typography, shape, and colors. "
            "Place it naturally into the new scene with lighting/angle dictated by this prompt."
        )
    if n_logos:
        if brand_name:
            # Letter-by-letter brand-name spelling per cookbook tip for tricky words.
            spelled = " ".join(list(brand_name))
            preserve_lines.append(
                f'Preserve the logo wordmark verbatim with correct spelling "{brand_name}" '
                f"(letters: {spelled}). Place it naturally in the layout, do NOT distort, "
                f"crop, or re-style the logo."
            )
        else:
            preserve_lines.append(
                "Preserve the logo wordmark verbatim with correct spelling. Do NOT distort, "
                "crop, or re-style the logo."
            )
    if preserve_lines:
        sections.append("Preserve list: " + " ".join(preserve_lines))

    # ---- SECTION 4: TEXT TO RENDER (1 primary line, optional small CTA) -
    # Per cookbook: quotes + ALL CAPS hint + "no extra words, no duplicate
    # text, text appears once, perfectly legible". Edit mode = max 1-2 strings.
    text_lines: list[str] = []
    # Pick the ONE primary text. Prefer headline, fall back to tagline.
    primary_text = headline or tagline

    # Detect if ANY text string contains non-Latin script. gpt-image-2 renders
    # Devanagari (Hindi/Marathi), Bengali, Tamil, Telugu, Kannada, Malayalam,
    # Gurmukhi (Punjabi), Gujarati, CJK, Arabic, etc. at 95%+ accuracy when
    # the prompt gives the actual native characters (not transliteration).
    # The Devanagari unicode block is U+0900-U+097F; we use a broad "any
    # non-ASCII char" check which covers ALL non-Latin scripts in one pass.
    def _has_non_latin(s: str) -> bool:
        return any(ord(c) > 127 for c in (s or ""))

    multilingual_hint = ""
    if _has_non_latin(primary_text) or _has_non_latin(cta) or _has_non_latin(brand_name):
        multilingual_hint = (
            " IMPORTANT: the text above contains native-script characters "
            "(such as Devanagari for Hindi/Marathi, Bengali, Tamil, Telugu, "
            "Kannada, Malayalam, Gurmukhi/Punjabi, Gujarati, CJK, Arabic, "
            "or similar). Render every character EXACTLY as given in the "
            "native script with correct conjuncts, matras/diacritics, and "
            "letter shapes - do NOT romanize, transliterate, or substitute "
            "Latin letters. Use a font that supports the script; the rendered "
            "text must be readable to a native speaker."
        )

    if primary_text:
        text_lines.append(
            f'Render this exact text ONCE in the image, in clear bold sans-serif: "{primary_text}". '
            "No extra words. No duplicate text. No reflow. The text must appear exactly once and be "
            "perfectly legible. Place the text on a clean uncluttered area of the canvas; do NOT "
            "leave the area blank if rendering is uncertain - shrink the text or move it before "
            "omitting it." + multilingual_hint
        )
    # CTA only if it's a clear short action verb AND we have headroom.
    if cta and primary_text and len(cta) <= 30:
        text_lines.append(
            f'Also render a small call-to-action button at the bottom-right with the exact text: "{cta}". '
            "Same rule: no extra words, appears once, legible."
        )
    elif cta and not primary_text:
        # No headline but a CTA -> treat CTA as the single text element.
        text_lines.append(
            f'Render this exact text ONCE on the image as a short button: "{cta}". '
            "No extra words, no duplicate text, perfectly legible." + multilingual_hint
        )
    if text_lines:
        sections.append("Text rendering:\n" + "\n".join(text_lines))
    else:
        # When we have NO text, tell the model explicitly so it doesn't
        # invent placeholder text on its own.
        sections.append("Text rendering: do not render any text on the image except the logo wordmark already covered above.")

    # ---- SECTION 5: MATCH (physical realism) --------------------------
    match_bits: list[str] = []
    if lighting:
        match_bits.append(f"lighting: {lighting}")
    if palette:
        match_bits.append(f"color palette: {palette}")
    match_bits.append("photorealistic skin texture and natural shadows")
    match_bits.append("premium commercial photography quality, sharp focus on the hero element")
    sections.append("Match: " + "; ".join(match_bits) + ".")

    # ---- SECTION 6: HARD CONSTRAINTS (cookbook style) ----------------
    sections.append(
        "Constraints: single unified image, no panels, no collage, no grid, no variants. "
        "No watermarks. No extra logos or trademarks beyond the one provided. "
        "No placeholder text like '[Brand]' or 'Lorem Ipsum'. No floating quotation marks. "
        "Final output must read as a finished print-ready advertisement, not a draft."
    )

    result = "\n\n".join(s for s in sections if s)
    logger.info("[formatter][gpt_image_2_edit] %d->%d chars (edit mode)", len(base_prompt), len(result))
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

    # Phase-1 strategy fields (May 3 2026 - 4-Phase Ad Creator Brain)
    target_audience: str = (payload.get("target_audience") or "").strip()
    objective:       str = (payload.get("objective") or "awareness").strip().lower()

    headline   = (ad_copy.get("headline") or "").strip()
    subhead    = (ad_copy.get("subhead") or "").strip()
    cta        = (ad_copy.get("cta") or "").strip()
    benefits   = [b for b in (ad_copy.get("benefit_lines") or []) if b]
    signals    = [s for s in (ad_copy.get("trust_signals") or []) if s]
    tagline    = (ad_copy.get("emotional_tagline") or "").strip()
    brand_name = (ad_copy.get("brand_name") or "").strip()
    # Per-text typography (May 4 framework expansion)
    headline_typo = (ad_copy.get("headline_typography") or "").strip()
    subhead_typo  = (ad_copy.get("subhead_typography") or "").strip()
    cta_typo      = (ad_copy.get("cta_typography") or "").strip()
    legal_disclaimer = (ad_copy.get("legal_disclaimer") or "").strip()
    # Brand identity layer (May 6 2026)
    brand_emblem = (ad_copy.get("brand_emblem_description") or "").strip()
    website_url  = (ad_copy.get("website_url") or "").strip()
    contact_info = (ad_copy.get("contact_info") or "").strip()
    footer_strip = [str(f).strip() for f in (ad_copy.get("footer_strip") or []) if str(f).strip()]
    lineup_items = [str(l).strip() for l in (ad_copy.get("lineup_items") or []) if str(l).strip()]

    mood        = (visual.get("mood") or "").strip()
    palette     = (visual.get("color_palette") or "").strip()
    psy_intent  = (visual.get("color_psychology_intent") or "").strip()
    lighting    = (visual.get("lighting") or "").strip()
    composition = (visual.get("composition") or "").strip()
    background  = (visual.get("background") or "").strip()
    typo        = (visual.get("typography_style") or "").strip()
    hierarchy   = (visual.get("visual_hierarchy") or "").strip()
    # When Haiku has explicitly set composition or hierarchy, formatter MUST
    # respect her layout (Pattern Catalog: two-column / centered-ornate /
    # schedule-stack / etc) and avoid injecting hardcoded position defaults
    # that contradict it. Computed here so both TEXT_ELEMENTS and
    # VISUAL_AND_LAYOUT sections can use it.
    haiku_set_layout = bool(hierarchy) or bool(composition)
    # Phase-0 concept fields (May 4 framework expansion)
    visual_metaphor = (visual.get("visual_metaphor") or "").strip()
    micro_details   = [str(d).strip() for d in (visual.get("micro_details") or []) if str(d).strip()]

    # Reference image roles (May 17 2026) — when the user supplied people /
    # product refs, GPT Image 2 /edits will otherwise copy the reference's
    # pose/expression/clothing verbatim. Inject explicit identity-only +
    # new-pose + free-styling guidance so the model treats refs as a headshot,
    # not a storyboard, and allows accessory/outfit overrides from the prompt.
    ref_roles_payload = payload.get("reference_roles") or {}
    n_people_ref   = int(ref_roles_payload.get("people")   or 0) if isinstance(ref_roles_payload, dict) else 0
    n_products_ref = int(ref_roles_payload.get("products") or 0) if isinstance(ref_roles_payload, dict) else 0
    ref_captions_payload = payload.get("reference_captions") or {}
    if not isinstance(ref_captions_payload, dict):
        ref_captions_payload = {}

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

    # Objective -> emphasis hint that calibrates what the model should foreground.
    objective_emphasis = {
        "awareness":  "emphasizing brand recall through one bold iconic visual and a confident emotional hook (logo and headline dominate; CTA is secondary or omitted)",
        "conversion": "engineered to drive immediate action with the call-to-action button visually prominent, urgency cues visible (limited-time, discount, badge), and trust signals present near the CTA",
        "engagement": "designed to stop the scroll with a curiosity hook and a single dominant visual that invites the viewer to swipe, comment, or save",
        "education":  "structured to inform clearly with a benefit list visible, supporting evidence near the headline, and trust signals at the bottom",
        "retention":  "tuned to feel exclusive and insider for existing customers, with loyalty/exclusive cues and a personalized warm tone",
    }.get(objective, "engineered for clear brand communication")

    sections: list[str] = []

    # Persona prefix
    sections.append(
        "Act as a world-class advertising art director specializing in "
        f"{persona_specialty}."
    )

    # PHASE 0 - CONCEPT (visual metaphor + micro-details). The single biggest
    # gap between AI slop and real ads. Surfaced FIRST so GPT internalizes the
    # idea before any layout decision.
    concept_bits: list[str] = []
    if visual_metaphor:
        concept_bits.append(f"- VISUAL METAPHOR (the CONCEPT): {visual_metaphor}")
    if micro_details:
        concept_bits.append("- MICRO-DETAILS to render: " + "; ".join(micro_details[:5]))
    if concept_bits:
        sections.append("CREATIVE CONCEPT:\n" + "\n".join(concept_bits))

    # PHASE 1 - STRATEGY brief (audience + objective)
    strategy_bits: list[str] = []
    if target_audience:
        strategy_bits.append(f"- TARGET AUDIENCE: {target_audience}")
    strategy_bits.append(f"- PRIMARY OBJECTIVE: {objective} ({objective_emphasis})")
    if campaign_type and campaign_type != "general":
        strategy_bits.append(f"- CAMPAIGN TYPE: {campaign_type.replace('_', ' ')}")
    sections.append("STRATEGY BRIEF:\n" + "\n".join(strategy_bits))

    # REFERENCE IMAGE HANDLING (only when refs are present) — critical for
    # GPT Image 2 /edits. Without this section, /edits defaults to near-verbatim
    # reproduction of the reference's pose, expression, outfit, and accessories,
    # producing the "face transplanted onto same body" look the user complained
    # about. Force identity-only + scene-driven pose + prompt-driven wardrobe.
    if n_people_ref or n_products_ref:
        ref_bits: list[str] = []

        # Vision-extracted descriptors (May 17 2026 caption pass). When present,
        # these are concrete role-scoped descriptors (face features for people,
        # packaging for products, mark for logos) — Gemini Vision deliberately
        # skipped pose / outfit / background for people refs so we can write
        # explicit "preserve THIS, ignore THAT" invariants. This is the same
        # pattern ChatGPT web uses internally to defeat /edits pose-copy.
        people_caps = ref_captions_payload.get("people") or []
        product_caps = ref_captions_payload.get("products") or []
        logo_caps = ref_captions_payload.get("logos") or []
        invariants: list[str] = []
        for i, cap in enumerate(people_caps):
            if not cap or not cap.strip():
                continue
            label = "person in image 1" if len(people_caps) == 1 else f"person in image {i+1}"
            invariants.append(
                f"- PRESERVE the {label}: {cap.strip()} "
                f"IGNORE everything else about that image — its pose, expression, head tilt, "
                f"gaze, hand position, body angle, outfit, jewelry, makeup, hairstyling, and "
                f"background MUST NOT carry over into the output."
            )
        for i, cap in enumerate(product_caps):
            if not cap or not cap.strip():
                continue
            offset = len(people_caps)
            label = f"product in image {offset + i + 1}"
            invariants.append(
                f"- PRESERVE the {label}: {cap.strip()} "
                f"IGNORE its background, surface, lighting, and any hands or props in that "
                f"image — place the product in the new scene as described below."
            )
        for i, cap in enumerate(logo_caps):
            if not cap or not cap.strip():
                continue
            offset = len(people_caps) + len(product_caps)
            label = f"logo in image {offset + i + 1}"
            invariants.append(
                f"- PRESERVE the {label}: {cap.strip()} "
                f"Render the wordmark verbatim with correct spelling; place naturally in the new layout."
            )
        if invariants:
            ref_bits.append(
                "PRESERVE-vs-IGNORE INVARIANTS (these are the only attributes from each "
                "reference that should carry into the output — everything else must be "
                "regenerated fresh from the scene description):"
            )
            ref_bits.extend(invariants)

        if n_people_ref == 1:
            ref_bits.append(
                "- The PERSON reference is an IDENTITY ANCHOR ONLY. Match the face, "
                "skin tone, hair color/length, and general build. Do NOT copy pose, "
                "expression, hand position, body angle, outfit, jewelry, makeup, or "
                "background from the reference image."
            )
            ref_bits.append(
                "- Pose, expression, and action MUST come from this prompt and the "
                "scene description below — invent a fresh natural pose that fits the "
                "ad's action (e.g. holding the product, mid-laugh, looking off-camera, "
                "interacting with the scene). Treat the reference like a passport "
                "photo, not a storyboard frame."
            )
            ref_bits.append(
                "- Wardrobe and accessories are FULLY OVERRIDABLE by this prompt. If "
                "the prompt mentions a dress, outfit, glasses, sunglasses, cap, hat, "
                "watch, jewelry, scarf, or any item, render THAT item — ignore what "
                "the reference person was wearing. If the prompt is silent on outfit, "
                "choose something appropriate to the scene (do not default to the "
                "reference's clothes)."
            )
        elif n_people_ref >= 2:
            ref_bits.append(
                f"- The {n_people_ref} PERSON references are IDENTITY ANCHORS ONLY. "
                "Match each face/skin tone/hair, but invent a NEW group composition "
                "with fresh poses, interactions, and expressions suited to the scene. "
                "Do NOT preserve any reference's original pose or outfit."
            )
            ref_bits.append(
                "- Wardrobe and accessories follow this prompt, not the references."
            )
        if n_products_ref == 1:
            ref_bits.append(
                "- The PRODUCT reference defines the exact item: packaging, label "
                "typography, colors, shape, branding must all match. Placement, "
                "angle, lighting, and surrounding scene are dictated by this prompt."
            )
        elif n_products_ref >= 2:
            ref_bits.append(
                f"- The {n_products_ref} PRODUCT references are a lineup — feature "
                "all variants together with matching packaging fidelity, but arrange "
                "and light them per this prompt."
            )
        sections.append("REFERENCE IMAGE HANDLING (read carefully):\n" + "\n".join(ref_bits))

    # PRIMARY COMMAND
    subject_phrase = f"the {cat_label} category" if cat_label != "consumer" else "a consumer brand"
    if brand_name:
        subject_phrase = f"the brand {brand_name} in {subject_phrase}"
    sections.append(
        "PRIMARY COMMAND:\n"
        f"Generate a single, cohesive image of a polished {intent_phrase} for "
        f"{subject_phrase}, {objective_emphasis}. Single unified composition - "
        "no panels, no variants, no collage. Render as a finished print-ready advertisement."
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
    if legal_disclaimer:
        text_lines.append(f'- LEGAL_DISCLAIMER: "{legal_disclaimer}"')
    if brand_emblem:
        # Position is decided by Haiku's COMPOSITION/HIERARCHY (centered-above-
        # wordmark for ornate symmetric, top-left for Z-pattern, beside model
        # for two-column lifestyle, etc). Don't hardcode a position here.
        if haiku_set_layout:
            text_lines.append(
                f"- BRAND_EMBLEM (small decorative crest, place at the position implied by the "
                f"layout pattern in COMPOSITION/HIERARCHY below — typically directly above the wordmark): {brand_emblem}"
            )
        else:
            text_lines.append(
                f"- BRAND_EMBLEM (small decorative crest above the wordmark or in the top-left corner): {brand_emblem}"
            )
    if website_url:
        text_lines.append(f'- WEBSITE_URL (small text in CTA strip): "{website_url}"')
    if contact_info:
        text_lines.append(f'- CONTACT_INFO (footer band): "{contact_info}"')
    if footer_strip:
        footer_json = ", ".join(f'"{f}"' for f in footer_strip[:4])
        text_lines.append(
            f"- FOOTER_BADGE_STRIP (horizontal row of small icon+label pairs at the very bottom): [{footer_json}]. "
            "Each renders as a small icon followed by the label text in a tinted footer band spanning the full width."
        )
    if lineup_items:
        lineup_json = "; ".join(f'"{l}"' for l in lineup_items[:8])
        text_lines.append(
            f"- LINEUP_SCHEDULE (vertically stacked row pills, ONE row per entry, in the central content area): [{lineup_json}]. "
            "Render each as a horizontal pill with the date in a small accent box on the LEFT, the name/title as bold text in the MIDDLE, "
            "and the time on the RIGHT. Use a small icon at the far right of each row matching the event type "
            "(praying-hands, harmonium, diya, flute, temple, mic, etc). EACH ROW IS A SEPARATE LINE — do not merge rows. "
            "ALL DATES, NAMES, AND TIMES MUST RENDER VERBATIM AS GIVEN — do not invent, drop, or substitute."
        )

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

    # VISUAL HIERARCHY - Phase 2C of the ad-creator framework. Names the
    # eye-travel pattern and element positions so the model knows where each
    # text element + the hero photo go.
    # IMPORTANT (May 8 2026): when Haiku provided a hierarchy, TRUST IT — do
    # not also inject the Z-pattern default below; that confuses the image
    # model when Haiku picked a different layout pattern (centered-ornate for
    # devotional, two-column for fashion, schedule-stack for lineups, etc).
    # Haiku-decides-layout > formatter-overrides. (`haiku_set_layout` is
    # computed earlier near the field-extraction block so TEXT_ELEMENTS can
    # also use it.)
    if hierarchy:
        layout_lines.append(f"- VISUAL HIERARCHY: {hierarchy}")
    elif not haiku_set_layout:
        # Only fall back to Z-pattern when Haiku gave us NEITHER composition
        # nor hierarchy — i.e. true defaulting case.
        layout_lines.append(
            "- VISUAL HIERARCHY: Z-pattern - brand mark top-left, hero headline "
            "in the upper-right region, supporting copy in the middle, "
            "call-to-action at the bottom-right. Hero product placed on the "
            "right-third Rule-of-Thirds intersection (NOT dead-center)."
        )

    # NEGATIVE SPACE / COPY SPACE - critical for typography legibility.
    layout_lines.append(
        "- NEGATIVE SPACE: Reserve at least 35% of the canvas as clean, "
        "uncluttered copy space (where the headline lockup sits) - either the "
        "upper half, the left third, or wherever the primary text region is "
        "placed. The background DIRECTLY behind every text element must be a "
        "calm, low-contrast surface (solid color, soft gradient, or out-of-"
        "focus area) so each letter reads cleanly with no visual interference."
    )

    # COLOR PSYCHOLOGY - Phase 2A. Tells the model WHY this palette was chosen.
    if palette and psy_intent:
        layout_lines.append(
            f"- COLOR PSYCHOLOGY: Use the palette {palette} - chosen to signal "
            f"{psy_intent}. Color choices must reinforce this emotional intent."
        )
    elif palette:
        layout_lines.append(f"- COLOR PALETTE: {palette}")

    # PRODUCT line - prefer Haiku's depicted_subject (concrete noun from user
    # prompt) over the generic intent_phrase. Eliminates "a sale ad" type
    # nonsense reaching the model.
    depicted_subject = (visual.get("depicted_subject") or "").strip()
    product_anchor = depicted_subject or intent_phrase
    if background:
        layout_lines.append(f"- PRODUCT: A high-resolution product photograph of {product_anchor}. {background}")
    else:
        layout_lines.append(
            f"- PRODUCT: A high-resolution product photograph of {product_anchor} "
            "with premium commercial-photography lighting."
        )

    if brand_name:
        # When Haiku set composition/hierarchy, trust her placement words; only
        # default to top-left corner when Haiku gave us no layout guidance.
        if haiku_set_layout:
            layout_lines.append(
                f'- LOGO PLACEMENT: Render the brand wordmark "{brand_name}" at the position '
                "implied by the COMPOSITION and VISUAL HIERARCHY above (centered for ornate/"
                "symmetric layouts, top-left for Z-pattern, beside the model in two-column "
                "lifestyle, etc), in a small refined brand-appropriate typeface."
            )
        else:
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
        # Per-element typography (Phase 4E framework expansion). When Haiku
        # provided headline_typography, use it verbatim; else fall back.
        head_style = headline_typo or "large bold uppercase condensed sans-serif, pure white or brand accent color, tight tracking"
        if haiku_set_layout:
            layout_lines.append(
                "- HEADLINE PLACEMENT: Render the HERO_HEADLINE at the position implied by the "
                f"COMPOSITION and VISUAL HIERARCHY above, styled as: {head_style}. Dominant text "
                "element. The background DIRECTLY behind these letters must be a clean uncluttered "
                "surface so every character is fully legible and crisp."
            )
        else:
            layout_lines.append(
                "- HEADLINE PLACEMENT: Center the HERO_HEADLINE in the upper-middle text region, "
                f"styled as: {head_style}. Dominant text element. "
                "The background DIRECTLY behind these letters must be a clean uncluttered "
                "surface so every character is fully legible and crisp."
            )

    if subhead:
        sub_style = subhead_typo or "clean sans-serif body weight, lighter color than headline, wide tracking, medium size"
        layout_lines.append(
            "- SUBHEADLINE PLACEMENT: Place the SUBHEADLINE directly below the HERO_HEADLINE, "
            f"styled as: {sub_style}. High-low contrast with the headline."
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
        cta_style = cta_typo or "bold sans-serif white text on a prominent pill-shaped button in the 10% accent color"
        cta_position = (
            "at the position implied by the COMPOSITION and VISUAL HIERARCHY above"
            if haiku_set_layout
            else "at the bottom-center"
        )
        layout_lines.append(
            f"- CTA PLACEMENT: Render the CALL_TO_ACTION {cta_position}, "
            f"styled as: {cta_style}. The button MUST be the highest-contrast element on the canvas - "
            "use the 10% accent color from the palette. Place it on a calm surface so it reads "
            "instantly from a thumbnail. The CTA is the conversion engine - make it impossible to miss."
        )

    if signals:
        layout_lines.append(
            "- TRUST STRIP PLACEMENT: A thin full-width horizontal band at the very bottom of the "
            "image, containing the TRUST_STRIP_ITEMS separated by vertical pipes or thin dividers, "
            "in small-caps or tracked sans-serif."
        )

    # LEGAL DISCLAIMER (Phase 4D) - mandatory for regulated categories.
    if legal_disclaimer:
        layout_lines.append(
            f'- LEGAL DISCLAIMER: At the very bottom edge, on a thin 10%-opacity dark gradient bar '
            f'spanning the full width, render in tiny pure-white sans-serif: "{legal_disclaimer}". '
            "Must be legible but unobtrusive. Required by platform compliance."
        )

    # TYPOGRAPHY (Phase 2B) - explicit max-2-fonts directive.
    if typo:
        layout_lines.append(
            f"- TYPOGRAPHY: {typo}. Use a MAXIMUM of 2 distinct fonts in the "
            "entire image (1 display for headlines + 1 body for everything "
            "else). Never mix 3 or more font families - that is amateur."
        )
    else:
        layout_lines.append(
            "- TYPOGRAPHY: Pair one bold display font for the headline with "
            "one clean sans-serif for body and small text. MAX 2 fonts total."
        )

    style_parts: list[str] = []
    if mood:
        style_parts.append(mood)
    if lighting:
        style_parts.append(lighting)
    style_parts.append("premium commercial photography quality")
    layout_lines.append("- STYLE AND TONE: " + ", ".join(style_parts) + ".")

    sections.append("VISUAL AND LAYOUT INSTRUCTIONS:\n" + "\n".join(layout_lines))

    # Final non-negotiable directives. Detect if any rendered text string
    # contains native (non-Latin) script characters - gpt-image-2 renders
    # Devanagari (Hindi/Marathi), Bengali, Tamil, Telugu, Kannada, Malayalam,
    # Gurmukhi (Punjabi), Gujarati, CJK, Arabic and similar at 95%+ accuracy
    # WHEN given the actual native characters (not Latin transliteration).
    # Any non-ASCII char on any text field flips on the explicit hint.
    def _txt(*vals: str) -> bool:
        return any(ord(c) > 127 for v in vals if v for c in v)
    has_native = _txt(
        headline, subhead, cta, brand_name, tagline,
        " ".join(benefits) if benefits else "",
        " ".join(signals) if signals else "",
        legal_disclaimer,
    )
    if any(_txt(item) for item in lineup_items):
        has_native = True

    quality_block = (
        "QUALITY REQUIREMENTS: All text must be perfectly legible and correctly spelled - "
        "no garbled letters, no extra characters, no fragmented words. "
        "Render every element listed above. Single unified image, no multiple panels."
    )
    if has_native:
        quality_block += (
            " The text above contains native-script characters (Devanagari for "
            "Hindi/Marathi, Bengali, Tamil, Telugu, Kannada, Malayalam, "
            "Gurmukhi/Punjabi, Gujarati, CJK, Arabic, or similar). Render every "
            "character EXACTLY in the native script with correct conjuncts, "
            "matras/diacritics, and letter shapes - do NOT romanize, "
            "transliterate, or substitute Latin letters. Pick a font that "
            "supports the script; rendered text must be readable to a native "
            "speaker."
        )
    sections.append(quality_block)

    result = "\n\n".join(s for s in sections if s)
    logger.info("[formatter][gpt_image_2] %d->%d chars native_script=%s", len(base_prompt), len(result), has_native)
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
    Round 4: rebuild from structured payload for AD intent (research-grade
    template) instead of just stripping the Haiku output.
    """
    ad_copy: Optional[Dict] = payload.get("ad_copy") or {}
    visual:  Optional[Dict] = payload.get("visual") or {}

    # Pure scene (no ad copy) - just clean Haiku's prompt and return.
    if not _is_ad_intent(payload):
        cleaned = _FLUX_STRIP.sub("", base_prompt)
        cleaned = re.sub(r"  +", " ", cleaned).strip()
        logger.info("[formatter][flux/scene] %d->%d chars", len(base_prompt), len(cleaned))
        return cleaned

    # AD MODE - construct a Flux-native ad prompt from structured data.
    headline = (ad_copy.get("headline") or "").strip()
    subhead  = (ad_copy.get("subhead") or "").strip()
    cta      = (ad_copy.get("cta") or "").strip()
    brand    = (ad_copy.get("brand_name") or "").strip()
    legal_disclaimer = (ad_copy.get("legal_disclaimer") or "").strip()
    visual_metaphor  = (visual.get("visual_metaphor") or "").strip()
    micro_details    = [str(d).strip() for d in (visual.get("micro_details") or []) if str(d).strip()]

    mood       = (visual.get("mood") or "polished").split(",")[0].strip()
    palette    = (visual.get("color_palette") or "").strip()
    psy_intent = (visual.get("color_psychology_intent") or "").strip()
    lighting   = (visual.get("lighting") or "").strip()
    background = (visual.get("background") or "").strip()
    hierarchy  = (visual.get("visual_hierarchy") or "").strip()
    subject_category = (payload.get("subject_category") or "general").strip()
    target_audience  = (payload.get("target_audience") or "").strip()
    objective        = (payload.get("objective") or "awareness").strip().lower()

    parts: list[str] = []

    # Scene opener (photographic, not designer) + audience tone.
    # PRIMARY: Haiku's visual.depicted_subject - the concrete noun extracted
    # from user's prompt. Falls back to _product_noun() lookup only if Haiku
    # didn't fill the field (e.g. for non-ad content).
    recipe_key = (payload.get("_recipe_key") or "").strip()
    depicted_subject = (visual.get("depicted_subject") or "").strip()
    if depicted_subject:
        product_noun = depicted_subject
    else:
        product_noun = _product_noun(subject_category, brand, recipe_key)
    # Strip leading article ("a/an/the") - opener adds its own
    product_noun = re.sub(r"^(?:a|an|the)\s+", "", product_noun, flags=re.IGNORECASE).strip()
    # Always lead with the concrete depicted subject; brand goes in text slot
    # only (handled later in text_bits). Avoids "for brand Cake" -> Flux
    # rendering an actual cake.
    if brand:
        opener = f'A {mood} commercial photograph of a {product_noun} with "{brand}" wordmark on the product label'
    else:
        opener = f"A {mood} commercial photograph of a {product_noun}"
    if target_audience:
        ta = target_audience.split(",")[0].split(";")[0].strip()
        if ta and len(ta) <= 80:
            opener += f" aimed at {ta}"
    parts.append(opener)

    # VISUAL METAPHOR (Phase 0B) - core concept that elevates the ad
    if visual_metaphor:
        vm_clean = _FLUX_STRIP.sub("", visual_metaphor).strip().rstrip(",.;:")
        if vm_clean:
            parts.append(f"the scene shows {vm_clean}")

    # MICRO-DETAILS (Phase 0C) - Flux excels at concrete texture rendering
    if micro_details:
        parts.append("with details: " + ", ".join(d.rstrip(".,;:") for d in micro_details[:5]))

    # Objective-specific emphasis
    if objective == "conversion":
        parts.append("composed to drive immediate action with the call-to-action visually dominant")
    elif objective == "awareness":
        parts.append("composed around one bold iconic visual for brand recall")
    elif objective == "engagement":
        parts.append("composed as a single scroll-stopping shot with curiosity-driving framing")

    # Background environment (Flux loves scene physics)
    if background:
        bg_clean = _FLUX_STRIP.sub("", background).strip()
        if bg_clean:
            parts.append(f"set against {bg_clean}")

    # Lighting (Flux excels at light physics)
    if lighting:
        lt_clean = _FLUX_STRIP.sub("", lighting).strip()
        if lt_clean:
            parts.append(f"lit with {lt_clean}")
    else:
        parts.append("lit with soft diffused studio lighting from the upper left")

    parts.append("captured on an 85mm lens at f/4 with shallow background falloff, sharp on the product, ultra-detailed, photorealistic")

    # NEGATIVE SPACE - Flux understands "leave room" well in natural language
    parts.append(
        "with a large clean uncluttered area on one side of the frame for the text, "
        "the surface behind every word kept calm and low-contrast for crisp legibility"
    )

    # Visual hierarchy - Flux respects positional cues. Strip designer vocab.
    if hierarchy:
        h_clean = _FLUX_STRIP.sub("", hierarchy).strip().rstrip(",.;:")
        if h_clean and len(h_clean) <= 200:
            parts.append(f"composition follows a {h_clean}")

    # Text rendering - keep text strings short, in quotes (Flux 2 renders 1-3 short strings well)
    text_bits: list[str] = []
    if brand:
        text_bits.append(f'the brand mark "{brand}" in a small refined typeface in the top corner')
    if headline:
        text_bits.append(f'a large bold headline reading "{headline}" in the clean text area')
    if subhead and len(subhead.split()) <= 8:
        text_bits.append(f'a smaller line beneath reading "{subhead}"')
    if cta:
        text_bits.append(f'a prominent button at the bottom reading "{cta}"')
    if legal_disclaimer:
        text_bits.append(f'tiny white text at the very bottom edge on a dark band reading "{legal_disclaimer}"')

    if text_bits:
        parts.append("Text on the image: " + "; ".join(text_bits) + ".")

    # Palette + color psychology intent (Phase 2A)
    if palette:
        # Strip percent breakdowns - Flux renders them literally
        pal_clean = re.sub(r"\s*\d{1,3}\s*%", "", palette).strip().rstrip(",.;:")
        if pal_clean:
            if psy_intent:
                parts.append(f"Palette: {pal_clean} - signaling {psy_intent}")
            else:
                parts.append(f"Palette: {pal_clean}")

    # Quality anchors
    parts.append("8k, commercial advertising photography, single unified composition")

    cleaned = ". ".join(p.rstrip(".") for p in parts if p) + "."
    cleaned = _FLUX_STRIP.sub("", cleaned)
    cleaned = re.sub(r"  +", " ", cleaned).strip()

    logger.info("[formatter][flux/ad] %d->%d chars", len(base_prompt), len(cleaned))
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
    legal_disclaimer = (ad_copy.get("legal_disclaimer") or "").strip()

    mood          = (visual.get("mood") or "").strip()
    palette       = (visual.get("color_palette") or "").strip()
    psy_intent    = (visual.get("color_psychology_intent") or "").strip()
    visual_metaphor = (visual.get("visual_metaphor") or "").strip()
    micro_details   = [str(d).strip() for d in (visual.get("micro_details") or []) if str(d).strip()]
    lighting      = (visual.get("lighting") or "").strip()
    background    = (visual.get("background") or "").strip()
    hierarchy     = (visual.get("visual_hierarchy") or "").strip()

    intent: str          = (payload.get("intent") or "").strip()
    campaign_type        = (payload.get("campaign_type") or "general").strip()
    subject_category     = (payload.get("subject_category") or "general").strip()
    target_audience      = (payload.get("target_audience") or "").strip()
    objective            = (payload.get("objective") or "awareness").strip().lower()

    # Subject - use the curated _CATEGORY_PRODUCT_NOUN map for a CONCRETE
    # photograph-able noun (e.g. "premium spirit bottle"). Falls back to
    # category-derived phrase, then to generic "premium product".
    # Imagen + Wan rendered chocolate/dessert when given just "alcohol_beverage
    # food product" (May 4 2026 visual regression) - the noun map fixes that.
    # PRIMARY source for the depicted subject is Haiku's visual.depicted_subject
    # field - extracted from the user's actual prompt nouns. This is scalable
    # across any brand x product combo without hardcoded maps.
    # FALLBACK chain: depicted_subject -> _product_noun(recipe_key) -> _product_noun(subject_category) -> "premium product"
    depicted_subject = (visual.get("depicted_subject") or "").strip()
    recipe_key = (payload.get("_recipe_key") or "").strip()
    if depicted_subject:
        subject_phrase = depicted_subject
    else:
        subject_phrase = _product_noun(subject_category, brand, recipe_key)
        if not subject_phrase or subject_phrase.strip() in ("", "product"):
            subject_phrase = "premium product"
    # Strip any leading article from depicted_subject - downstream sentences
    # add their own article ("for a {subject}", "depicted is a {subject}").
    # Without this strip we get "a a glossy bottle..." double-article (May 4 fix).
    subject_phrase = re.sub(r"^(?:a|an|the)\s+", "", subject_phrase, flags=re.IGNORECASE).strip()

    sentences: list[str] = []

    # -- 0. BRAND/PRODUCT disambiguation (GPT-style separation) -------------
    # Imagen confuses brand-noun homonyms with the depicted object ("Cake"
    # detergent -> rendered actual cake). Borrow GPT formatter's explicit
    # BRAND_NAME vs PRODUCT separation: state the brand role + product role
    # as 2 distinct facts UPFRONT so Imagen's text encoder treats them as
    # different things.
    if brand and subject_phrase and subject_phrase != "premium product":
        sentences.append(
            f'The brand name is "{brand}" - this is a wordmark printed on the product label only. '
            f'The actual product depicted in the photograph is a {subject_phrase}.'
        )

    # -- 1. Opening framing (mood + category + subject + audience tone) -----
    mood_word = mood.split(",")[0].strip() if mood else "polished"
    # Pick correct article (a/an) based on first vowel of mood_word.
    article = "an" if mood_word and mood_word[0].lower() in "aeiou" else "a"
    if campaign_type and campaign_type not in ("general", ""):
        camp = campaign_type.replace("_", " ")
        opener = f"{article.capitalize()} {mood_word} {camp} advertisement"
    else:
        opener = f"{article.capitalize()} {mood_word} commercial advertisement"
    # Build opener: depicted subject is the visual anchor, brand is text-only.
    # Since depicted_subject already contains the concrete noun (extracted by
    # Haiku from user prompt), we always lead with the subject. Brand goes in
    # a separate disambiguation sentence below + the wordmark text slot. This
    # works for ANY brand/product combo without hardcoded homonym lists.
    sp_lower = subject_phrase.lower().strip()
    if subject_phrase and sp_lower not in ("", "product", "premium product"):
        opener += f" featuring {subject_phrase}"
    elif brand:
        opener += f" for {brand}"

    # Audience tone - woven in as adjective phrase, not as a separate sentence
    # (keeps Imagen narrative natural). Truncate long audience to first phrase.
    if target_audience:
        ta = target_audience.split(",")[0].split(";")[0].strip()
        if ta and len(ta) <= 80:
            opener += f" aimed at {ta}"
    sentences.append(opener + ".")

    # NOTE (May 4 2026 fix): visual_metaphor + micro_details are INTENTIONALLY
    # SKIPPED for Imagen. Reason: Imagen has a weak text encoder and confuses
    # narrative scene words with text-to-render. Long descriptions like
    # "scene shows bottle on weathered ship deck..." caused Imagen to render
    # garbled text ("BolAbd Frogs", "Lab Testor", "Prestriction" in the
    # DiaCare test). Imagen does best with terse opener + 3 quoted strings.
    # The metaphor + details still flow to GPT/Flux/Wan formatters.

    # Objective hint - tells Imagen what to emphasize without structural words.
    if objective == "conversion":
        sentences.append("The composition foregrounds the call-to-action prominently with urgency cues nearby for immediate response.")
    elif objective == "awareness":
        sentences.append("The composition is built around one bold iconic visual and a confident emotional anchor that builds brand recall.")
    elif objective == "engagement":
        sentences.append("The composition uses a single dominant scroll-stopping visual and a curiosity hook to invite interaction.")
    elif objective == "education":
        sentences.append("The composition presents clear supporting information arranged hierarchically with trust signals visible.")

    # -- 2. HERO PRODUCT (moved up, May 5 2026) -----------------------------
    # CRITICAL: hero product MUST come before background. Imagen's distiller
    # caps prompts at 100 words sentence-aware. Earlier order put product
    # sentence at position 9+ - regularly cut off, leaving Imagen with only
    # background description -> renders the background AS the main subject
    # (e.g. "stained plate" became the visual hero instead of detergent bottle).
    # Now product sentence lands within first 60 words, always survives.
    if subject_phrase and subject_phrase != "premium product":
        sentences.append(
            f"The main visual subject is a high-resolution photograph of {subject_phrase}, occupying the right two-thirds of the image."
        )

    # -- 3. Background / scene base -----------------------------------------
    if background:
        bg_clean = _IMAGEN_DESIGNER_VOCAB.sub("", background).strip()
        if bg_clean:
            sentences.append(f"The setting around the product is {bg_clean}.")

    # NEGATIVE SPACE: explicit copy-space sentence so Imagen reserves a clean
    # zone for the headline. Wording carefully avoids structural nouns like
    # "line of text", "headline", "caption" that Imagen renders LITERALLY on
    # the canvas (see Apr 24 2026 bug log on multi_provider_client.py).
    sentences.append(
        "A large clean uncluttered area covers at least one third of the image "
        "with a calm low-detail surface so every word reads cleanly and crisply."
    )

    # -- 3. Top-down spatial walk-through ----------------------------------------------------------------------
    # PRIORITY ORDER for Imagen: brand -> headline -> CTA. Distiller caps at
    # 3 literals (May 4 2026 - Imagen mangles 4+ strings). Subhead + tagline
    # SKIPPED for Imagen because they were rendering garbled
    # ("Pharmacist Recommended" -> "Prestriction"). Headline + CTA carry the
    # full message; the visual metaphor + product photo carry the rest.

    # Top-left: brand mark (if brand exists) - LITERAL 1
    if brand:
        sentences.append(
            f"At the very top-left, a small clean rectangle contains the text \"{brand}\"."
        )

    # Upper-center: headline - LITERAL 2
    if headline:
        sentences.append(
            f"Centered in the upper portion, a large bold line of text reads \"{headline}\"."
        )

    # Below headline: SHORT subhead - LITERAL 3 (May 5 2026: distiller cap
    # bumped to 4 with adaptive guard - subheads <=30 chars survive, longer
    # ones still get dropped to avoid spelling mangling).
    if subhead and len(subhead) <= 30:
        sentences.append(
            f"Just below the headline, a smaller line of text reads \"{subhead}\"."
        )

    # Bottom-center: CTA (rectangle, not "button") - LITERAL 4 (mandatory)
    if cta:
        sentences.append(
            f"At the very bottom, centered and prominent, a small solid-colored rectangle "
            f"contains the text \"{cta}\"."
        )

    # Hero product sentence MOVED to position 2 (before background) - see
    # comment block earlier in this function. Don't re-add here.

    # Below product / mid-band: benefit row (max 4 - Imagen complexity ceiling)
    if benefits and len(benefits) >= 2:
        labels = ", ".join(f'"{b}"' for b in benefits[:4])
        sentences.append(
            f"Below the product image, {len(benefits[:4])} small circles arranged horizontally, "
            f"each containing a simple line drawing and a label: {labels}."
        )

    # SUBHEAD + TAGLINE INTENTIONALLY OMITTED for Imagen.
    # Reason: Imagen distiller takes first 3 quoted literals. We need brand +
    # headline + CTA in those 3 slots. Including subhead/tagline pushed CTA
    # to slot 4+, which got dropped, AND subhead got mangled into garbage
    # ("BolAbd Frogs"). Headline + CTA carry the message; subhead removal is
    # net positive for visual quality.

    # Above bottom: trust banner (max 4 items)
    if signals:
        signal_labels = ", ".join(f'"{s}"' for s in signals[:4])
        sentences.append(
            f"Just above it, a thin horizontal banner contains {len(signals[:4])} small icons "
            f"each labeled with one of: {signal_labels}."
        )

    # LEGAL DISCLAIMER (Phase 4D framework expansion) - mandatory for
    # regulated categories. Imagen renders short bottom-edge text reasonably.
    if legal_disclaimer and len(legal_disclaimer) <= 80:
        sentences.append(
            f'At the very bottom edge, a thin dark band contains tiny pure-white text reading "{legal_disclaimer}".'
        )

    # -- 4. Closing aesthetic anchor (palette + lighting + color psychology) -
    closing_parts: list[str] = []
    if palette:
        palette_clean = _IMAGEN_DESIGNER_VOCAB.sub("", palette).strip().rstrip(",.;:")
        if palette_clean:
            # Weave color-psychology intent into the palette mention so Imagen
            # picks colors that reinforce the emotion. Carefully avoid the
            # word "palette" inside structural-trigger zones.
            if psy_intent:
                closing_parts.append(f"{palette_clean} colors signaling {psy_intent}")
            else:
                closing_parts.append(f"{palette_clean} palette")
    if lighting:
        light_clean = _IMAGEN_DESIGNER_VOCAB.sub("", lighting).strip().rstrip(",.;:")
        if light_clean:
            closing_parts.append(f"{light_clean}")
    closing_parts.append("premium commercial photography style, single unified composition")
    sentences.append(", ".join(closing_parts).capitalize() + ".")

    # Visual hierarchy hint - placed AFTER the spatial walk-through so Imagen
    # has already heard the layout. Prepend "with" to keep it as adjectival
    # framing (avoids structural noun trigger). Strip designer vocab patterns.
    if hierarchy:
        h_clean = _IMAGEN_DESIGNER_VOCAB.sub("", hierarchy).strip().rstrip(",.;:")
        if h_clean and len(h_clean) <= 180:
            sentences.append(f"Composition follows a {h_clean}.")

    result = " ".join(s for s in sentences if s).strip()
    # Final scrub  -  guarantee no functional vocab leaked through.
    result = _IMAGEN_DESIGNER_VOCAB.sub("", result)
    # Strip markdown chars + stray brackets BEFORE distill picks up literals.
    # Imagen renders #, *, _, `, ~, [, ], <, > LITERALLY when adjacent to text.
    # The "#" and "[Shop Now]" leak (May 5 2026 bug) was Imagen interpreting
    # styling words; this is a defense-in-depth strip in case any of these
    # chars made it from ad_copy fields into the formatted sentences.
    result = re.sub(r"[#*`_~\[\]<>]+", "", result)
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
    """Scene-first prompt for WaveSpeed models (wan_2_7 / grok_2_imagine / hunyuan).

    Round 4: research-recommended starting template (PDF page 14):
        /imagine prompt: [Highly detailed, commercial photography style]
        A <category> advertisement for ... <full descriptive narrative> ...

    These models render scenes beautifully but text rendering is hit-or-miss.
    Strategy: build a full descriptive scene narrative + at most 1 short
    headline string (Wan 2.7 renders 1-2 word strings reliably, longer breaks).
    """
    visual:  Dict[str, Any] = payload.get("visual") or {}
    ad_copy: Dict[str, Any] = payload.get("ad_copy") or {}

    headline = (ad_copy.get("headline") or "").strip()
    brand    = (ad_copy.get("brand_name") or "").strip()
    cta      = (ad_copy.get("cta") or "").strip()

    mood       = (visual.get("mood") or "polished").split(",")[0].strip()
    palette    = (visual.get("color_palette") or "").strip()
    psy_intent = (visual.get("color_psychology_intent") or "").strip()
    lighting   = (visual.get("lighting") or "").strip()
    background = (visual.get("background") or "").strip()
    hierarchy  = (visual.get("visual_hierarchy") or "").strip()
    visual_metaphor = (visual.get("visual_metaphor") or "").strip()
    micro_details   = [str(d).strip() for d in (visual.get("micro_details") or []) if str(d).strip()]
    subject_category = (payload.get("subject_category") or "general").strip()
    target_audience  = (payload.get("target_audience") or "").strip()
    objective        = (payload.get("objective") or "awareness").strip().lower()

    # PURE SCENE - no ad copy: clean Haiku's prompt, return.
    if not _is_ad_intent(payload):
        scene = re.sub(
            r"^\s*ONE single unified (?:image|photograph)[^.]*\.\s*",
            "",
            base_prompt,
            flags=re.IGNORECASE,
        ).strip()
        scene = _IMAGEN_DESIGNER_VOCAB.sub("", scene)
        scene = re.sub(r"  +", " ", scene).strip()
        logger.info("[formatter][wavespeed/scene] %d->%d chars", len(base_prompt), len(scene))
        return scene

    # AD MODE - terse, product-noun-first prompt. Wan locks onto the FIRST
    # concrete noun it sees; if you bury the product under "advertisement
    # scene featuring the AlcShip alcohol_beverage" it will pick whatever
    # noun catches its parser (chocolate balls, dessert, etc - May 4 2026
    # regression). Lead with a concrete photograph-able product noun from
    # _CATEGORY_PRODUCT_NOUN.
    # Prefer Gemini classifier's recipe_key over Haiku's subject_category
    # (classifier is more accurate - sees full prompt including platform/brand).
    recipe_key = (payload.get("_recipe_key") or "").strip()
    # PRIMARY: Haiku's visual.depicted_subject - extracted from user's actual
    # prompt nouns, scalable to any brand/product combo without hardcoded maps.
    depicted_subject = (visual.get("depicted_subject") or "").strip()
    if depicted_subject:
        product_noun = depicted_subject
    else:
        product_noun = _product_noun(subject_category, brand, recipe_key)
    # Strip leading article so opener "of a {noun}" doesn't become "of a a..."
    product_noun = re.sub(r"^(?:a|an|the)\s+", "", product_noun, flags=re.IGNORECASE).strip()
    parts: list[str] = []

    # Opener: ALWAYS lead with the concrete depicted subject. Wan's parser
    # locks onto the first concrete noun it sees, so we make sure that's the
    # product, not the brand name. Brand appears as wordmark text only.
    if brand:
        parts.append(f'Premium commercial photograph of {product_noun} with "{brand}" wordmark printed on the label')
    else:
        parts.append(f"Premium commercial photograph of {product_noun}")

    # Mood as adjective (after the subject is anchored)
    if mood and mood != "polished":
        parts.append(mood)

    # VISUAL METAPHOR - Wan respects short scene directives. Cap at 120 chars.
    if visual_metaphor:
        vm_clean = _IMAGEN_DESIGNER_VOCAB.sub("", visual_metaphor).strip().rstrip(",.;:")
        if vm_clean and len(vm_clean) <= 120:
            parts.append(vm_clean)

    # MICRO-DETAILS - up to 3 most distinctive (Wan starts ignoring after 3-4 details)
    if micro_details:
        parts.append(", ".join(d.rstrip(".,;:") for d in micro_details[:3]))

    # Background - keep terse
    if background:
        bg_clean = _IMAGEN_DESIGNER_VOCAB.sub("", background).strip().rstrip(",.;:")
        if bg_clean and len(bg_clean) <= 120:
            parts.append(bg_clean)

    # Lighting - keep terse
    if lighting:
        lt_clean = _IMAGEN_DESIGNER_VOCAB.sub("", lighting).strip().rstrip(",.;:")
        if lt_clean and len(lt_clean) <= 100:
            parts.append(lt_clean)
    else:
        parts.append("dramatic studio lighting")

    parts.append("ultra-sharp focus, cinematic depth, 8k photorealistic")

    # Negative space - SHORT version (Wan ignores long directives)
    parts.append("clean uncluttered area on one side for text")

    # Text strings - Wan can render up to 2 short strings (1-4 words each)
    # if explicitly framed as separate visual regions. May 5 2026 fix: was
    # only rendering 1 string (headline), CTA was dropped. Now: headline at
    # top, CTA at bottom, framed as 2 distinct text regions.
    headline_short = headline and len(headline.split()) <= 4
    cta_short = cta and len(cta.split()) <= 3
    if headline_short and cta_short:
        # Both fit - render as 2 text regions
        parts.append(
            f'with the text "{headline}" appearing prominently in the upper text area '
            f'and the text "{cta}" appearing on a colored bar in the lower text area'
        )
    elif headline_short:
        parts.append(f'with the words "{headline}" displayed prominently')
    elif cta_short:
        # Headline too long - just render CTA
        parts.append(f'with the words "{cta}" displayed prominently')

    # Brand text only if brand exists and headline absent (avoid duplication)
    if brand and not headline_short:
        parts.append(f'with "{brand}" wordmark visible on the product')

    # Palette - keep brief
    if palette:
        pal_clean = re.sub(r"\s*\d{1,3}\s*%", "", palette).strip().rstrip(",.;:")
        if pal_clean and len(pal_clean) <= 80:
            parts.append(f"{pal_clean} tones")

    parts.append("single unified composition, no collage, no panels")

    result = ", ".join(p.rstrip(",.") for p in parts if p) + "."
    result = _IMAGEN_DESIGNER_VOCAB.sub("", result)
    result = re.sub(r"  +", " ", result).strip()

    logger.info("[formatter][wavespeed/ad] %d->%d chars (product=%r)",
                len(base_prompt), len(result), product_noun[:40])
    return result

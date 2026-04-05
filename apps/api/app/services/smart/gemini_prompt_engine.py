"""
Gemini Prompt Engine v2 — Bucket-aware + Model-specific + Validator + Critic

Architecture:
  DEFAULT PATH  (all buckets, all tiers):
    Stage A: bucket-specific system prompt → Creative Brief JSON
    Stage B: model-specific system prompt  → generation params JSON
    Validator: schema + budget + bucket-rule check

  HARD BUCKET PATH (anime, typography, editing, architecture — premium/ultra only):
    Stage A: bucket-specific brief
    Stage B: model-specific params
    Critic:  specialist review → targeted refinements
    Stage B2: re-generate params with critic notes injected
    Validator: final check

Fallback chain:
  Gemini fail → heuristic_brief + heuristic_params (never crash)

Feature flags (env):
  GEMINI_API_KEY       → enables Gemini (falls back to heuristic if absent)
  USE_GEMINI_ENGINE    → set false to force heuristic (default true)
"""

from __future__ import annotations

import colorsys
import json
import logging
import os
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Hex → Natural Language Color Translation (APEX model-native syntax)
# Models respond better to descriptive color language than raw hex codes.
# ══════════════════════════════════════════════════════════════════════════════

_HEX_NL_MAP: Dict[str, str] = {
    # Reds / Oranges
    "#FF0000": "pure red", "#CC0000": "deep crimson", "#FF4444": "vivid coral red",
    "#FF6B00": "vivid deep orange", "#FF7700": "bright amber orange",
    "#FF9933": "saffron gold", "#E8593C": "deep burnt orange",
    "#FF5733": "warm vermillion", "#D44000": "rich terracotta",
    # Yellows / Golds
    "#FFD700": "bright gold", "#FFC107": "amber gold", "#C9A84C": "antique gold",
    "#F59E0B": "warm amber", "#FBBF24": "golden yellow",
    # Greens
    "#00FF00": "pure lime green", "#22C55E": "vivid emerald green",
    "#138808": "deep forest green", "#16A34A": "rich green",
    "#059669": "teal green", "#10B981": "fresh mint green",
    # Blues / Cyans
    "#0000FF": "pure blue", "#2563EB": "vivid royal blue",
    "#4FACFE": "bright azure blue", "#00D4FF": "electric cyan",
    "#0EA5E9": "bright sky blue", "#38BDF8": "light cerulean",
    "#0F3460": "deep midnight blue", "#1E40AF": "rich cobalt blue",
    # Purples / Violets
    "#6C63FF": "electric violet", "#7C3AED": "deep purple",
    "#8B5CF6": "soft lavender purple", "#A855F7": "bright amethyst",
    "#6D28D9": "rich indigo violet", "#4C1D95": "deep plum",
    # Pinks / Magentas
    "#FF00FF": "pure magenta", "#EC4899": "vivid hot pink",
    "#F43F5E": "bold rose red", "#FB7185": "soft coral pink",
    # Neutrals / Darks
    "#000000": "pure black", "#0A0A0A": "near-black",
    "#0A0A1A": "near-black midnight navy", "#1A1A2E": "deep midnight navy",
    "#111827": "charcoal black", "#1F2937": "dark slate",
    "#374151": "dark grey", "#6B7280": "medium grey",
    "#9CA3AF": "light grey", "#D1D5DB": "soft silver",
    "#F3F4F6": "near-white", "#FFFFFF": "pure white",
    # Brand-typical
    "#0F172A": "very dark navy", "#1E293B": "dark slate navy",
    "#312E81": "deep indigo", "#4F46E5": "vivid indigo",
}

# Hue→color name mapping for HSV-based fallback
_HUE_NAMES = [
    (15,  "red"), (45, "orange"), (65, "yellow"), (80, "yellow-green"),
    (150, "green"), (185, "teal"), (210, "cyan"), (240, "blue"),
    (265, "indigo"), (285, "violet"), (330, "purple"), (345, "pink"), (360, "red"),
]


def _hex_to_natural(hex_color: str) -> str:
    """
    Convert a hex color to a natural language description that models understand.
    Priority: exact map → HSV-based description.
    """
    if not hex_color:
        return ""
    h = hex_color.upper().strip()
    if not h.startswith("#"):
        h = "#" + h
    # Normalise 3-char shorthand
    if len(h) == 4:
        h = "#" + h[1]*2 + h[2]*2 + h[3]*2
    if len(h) != 7:
        return hex_color  # can't parse — return as-is

    # Exact map lookup
    exact = _HEX_NL_MAP.get(h)
    if exact:
        return exact

    # HSV-based description
    try:
        r = int(h[1:3], 16) / 255.0
        g = int(h[3:5], 16) / 255.0
        b = int(h[5:7], 16) / 255.0
        hue_f, sat, val = colorsys.rgb_to_hsv(r, g, b)
        hue = int(hue_f * 360)

        # Determine lightness adjective
        if val < 0.20:
            lightness = "very dark"
        elif val < 0.45:
            lightness = "dark"
        elif val < 0.65:
            lightness = "medium"
        elif val < 0.85:
            lightness = "bright"
        else:
            lightness = "light"

        # Determine saturation adjective
        if sat < 0.12:
            # Achromatic
            if val < 0.15:
                return "near-black"
            elif val > 0.92:
                return "near-white"
            else:
                return f"{lightness} grey"

        sat_adj = "muted " if sat < 0.40 else ("vivid " if sat > 0.75 else "")

        # Find hue name
        color_name = "colour"
        for threshold, name in _HUE_NAMES:
            if hue <= threshold:
                color_name = name
                break

        return f"{lightness} {sat_adj}{color_name}".strip()
    except Exception:
        return hex_color

# ── Feature flags (read at call time via property, not import time) ────────────
def _is_gemini_enabled() -> bool:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    flag = os.getenv("USE_GEMINI_ENGINE", "true").strip().lower()
    return bool(key) and flag not in ("false", "0", "no", "off")

# Module-level alias kept for legacy imports
USE_GEMINI_ENGINE: bool = _is_gemini_enabled()

# Model name (env-configurable, no deploy required for upgrade)
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")

# Buckets that get a critic agent on premium/ultra
_HARD_BUCKETS = {"anime", "typography", "editing", "interior_arch", "character_consistency"}

# ══════════════════════════════════════════════════════════════════════════════
# STAGE A — Bucket-specific Creative Brief system prompts
# ══════════════════════════════════════════════════════════════════════════════

_CREATIVE_AMPLIFIER = """
CORE DIRECTIVE — IMAGINATION + SITUATION FIRST:

You are a visionary creative director with the imagination of Alejandro Jodorowsky, the composition sense of Stanley Kubrick, the color instinct of Wes Anderson, and the surrealist depth of Salvador Dalí.

STEP 1 — READ THE SITUATION:
Before anything else, detect what situation/context is embedded in the prompt:
- Is it a FESTIVAL? (Diwali, Holi, Eid, Christmas, Navratri, Ganesh Chaturthi, Durga Puja, Lohri, Pongal, Baisakhi, Onam, Rakhi, Valentine's Day, New Year, Black Friday, Thanksgiving, Halloween, etc.)
- Is it an OCCASION? (Wedding, birthday, anniversary, graduation, baby shower, retirement, etc.)
- Is it a SEASON? (Monsoon, summer, winter, spring, harvest time, etc.)
- Is it a CONTENT TYPE? (YouTube thumbnail, Instagram post, poster, billboard, banner, flyer, etc.)
- Is it a CAMPAIGN TYPE? (Product launch, sale, discount offer, brand awareness, political, charity, etc.)

STEP 2 — MATCH EMOTION TO SITUATION:
Every situation has a DOMINANT EMOTION. Lock that in first:
- Diwali → warmth + prosperity + togetherness
- Holi → pure joy + freedom + color explosion
- Wedding → grandeur + love + emotional depth
- Sale/Offer → urgency + excitement + FOMO
- Product launch → desire + anticipation + premium
- Birthday → happiness + surprise + playfulness
- Monsoon → romantic melancholy + freshness + relief
- Thumbnail → curiosity + shock + "I MUST click this"
- Poster → bold storytelling + instant readability at distance

STEP 3 — BUILD THE VISUAL AROUND THE EMOTION:
- Color palette must AMPLIFY the emotion (not just look pretty)
- Composition must SERVE the message (ad = clean zones for text, photo = full bleed)
- Every element earns its place — if it doesn't add to the emotion, remove it
- Find ONE unexpected creative twist that makes this unforgettable

NEVER produce generic, predictable, stock-photo-level descriptions.
ALWAYS ask: "If someone sees this for 2 seconds, what do they FEEL?"
"""

_BRIEF_SYSTEM_BY_BUCKET: Dict[str, str] = {

    # ── Photorealism (generic) ─────────────────────────────────────────────
    "photorealism": _CREATIVE_AMPLIFIER + """You are a world-class commercial photographer and retoucher.
Convert the raw prompt into a precise Creative Brief JSON.

Rules:
- Camera must be a real body + lens (Sony A7R5 + 85mm f/1.2, Nikon Z9 + 24-70mm f/2.8, etc.)
- Lighting: exact position, modifier, color temperature (5600K golden rim, 4200K soft box camera-left)
- Skin/surface: subsurface scattering, pore detail, specular highlight description
- Color palette: max 4 values (hex or precise tone names)
- style_refs: 2-3 real photographer names or ad campaigns (never generic)
- avoid: be specific about what ruins this exact image type

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Portrait sub-bucket ────────────────────────────────────────────────
    "photorealism_portrait": _CREATIVE_AMPLIFIER + """You are a world-class portrait photographer (Annie Leibovitz level).
Focus on: catchlights in eyes, skin subsurface scattering, hair strand separation,
jaw shadow definition, expression micro-details, background bokeh quality.
Camera: must specify body + prime lens (85mm f/1.2 or 135mm f/1.8 preferred).
Lighting: describe 3-point or Rembrandt or butterfly setup precisely.

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Product sub-bucket ─────────────────────────────────────────────────
    "photorealism_product": _CREATIVE_AMPLIFIER + """You are a senior commercial product photographer.
Focus on: hero shot angle, surface material callout (matte/gloss/metallic/frosted glass),
shadow control (hard shadow vs diffused), lifestyle vs studio isolation,
prop selection for brand story, color accuracy for packaging.
Lighting: describe exactly (side-lit for texture, top-lit for beverages, etc.)

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Food sub-bucket ────────────────────────────────────────────────────
    "photorealism_food": _CREATIVE_AMPLIFIER + """You are a food photographer and stylist (Bon Appétit level).
Focus on: hero element placement, steam/condensation/drip detail,
macro texture on the food surface, depth of field on the hero bite,
color vibrancy of fresh ingredients, plating composition (rule of odds),
warm vs cool toning choice.

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Fashion sub-bucket ─────────────────────────────────────────────────
    "photorealism_fashion": _CREATIVE_AMPLIFIER + """You are a fashion photographer (Vogue editorial level).
Focus on: garment texture and drape, model pose energy, fabric movement,
editorial vs commercial distinction, location mood vs studio control,
color story alignment with the clothing, beauty lighting for skin.

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Landscape sub-bucket ───────────────────────────────────────────────
    "photorealism_landscape": _CREATIVE_AMPLIFIER + """You are a landscape and nature photographer (National Geographic level).
Focus on: golden/blue hour timing, atmospheric depth (foreground/mid/background layers),
weather mood (storm light, mist, clear), water motion (long exposure vs frozen),
leading lines, scale indicator (human figure or landmark).

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Anime ──────────────────────────────────────────────────────────────
    "anime": _CREATIVE_AMPLIFIER + """You are a senior anime art director (Studio Ghibli / MAPPA / Ufotable level).
Focus on:
- Character: eye shape style, hair volume/flow, expression intensity, outfit material
- Linework: weight variation (thick outline vs fine detail lines)
- Color: cel shading vs gradient, shadow color (not just dark — use purple/blue shadows)
- Pose: dynamic energy level, weight distribution, foreshortening
- Background: detail level (Ghibli lush vs MAPPA minimal), perspective type
- Consistency anchors: lock down physical features precisely to prevent drift

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Typography ─────────────────────────────────────────────────────────
    "typography": _CREATIVE_AMPLIFIER + """You are a senior Art Director at a top-tier ad agency (Wieden+Kennedy / Ogilvy level).
You specialize in creating PROFESSIONAL POSTER, AD, and MARKETING VISUALS with pixel-perfect text hierarchy.

CRITICAL RULES:
1. GENERATE COMPLETE AD COPY with ALL fields filled — this directly drives the poster renderer:
   - brand_name: the brand/app/product name if mentioned, else infer something fitting
   - headline: 1-5 ALL CAPS punchy words (e.g., "NOW LIVE!", "DIWALI SALE", "50% OFF")
   - subheadline: 5-12 word supporting claim
   - body: 1-2 sentence description of what the product/service/event IS
   - cta: action button text (e.g., "GET STARTED", "SHOP NOW", "CLAIM OFFER")
   - cta_url: website/app store URL if relevant (infer something realistic like www.brandname.com)
   - features: ALWAYS generate 4 features with emoji icon, title, and one-line desc
     e.g. {"icon":"✅","title":"Task Management","desc":"Organize and prioritize tasks"}
   - tagline: optional closing line (e.g., "No credit card required · Free 7-day trial")
2. poster_design: ALWAYS fill all fields — this drives colors, layout, fonts
   - accent_color: vivid brand color hex (NOT gray, NOT white — must be vibrant)
   - bg_color: dark or deep color for the panel sections
   - font_style: bold_tech | elegant_serif | expressive_display | clean_sans
   - layout: hero_top_features_bottom for most ads
3. The background image (from Ideogram) will be used as the HERO visual only (top 55%).
   visual_concept MUST describe a REALISTIC, RELEVANT scene matching the product/brand:
   - SaaS/App → laptop/phone showing a clean dashboard UI, modern office, team working
   - Diwali/festival → warm lights, diyas, rangoli, celebration scene
   - Food/restaurant → appetizing food shot, kitchen, plating
   - Fitness → athlete in action, gym equipment
   - Fashion → model wearing the product, editorial setting
   NEVER generate abstract art, fractals, or unrelated imagery for product ads.
4. All text will be composited by our renderer ON TOP — Ideogram DOES NOT need to render text.
   Keep the scene CLEAN — no text, no overlays, no watermarks in the image.

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."],
  "ad_copy": {
    "brand_name": "Brand or product name (can be empty if not mentioned)",
    "headline": "EXACT HEADLINE TEXT (1-5 words, ALL CAPS for impact)",
    "subheadline": "Exact supporting message (5-12 words)",
    "body": "1-2 sentence description of the product/offer/event (can be empty)",
    "cta": "Action button text (2-4 words)",
    "cta_url": "URL or handle if mentioned (e.g. www.brand.com, @BrandApp)",
    "tagline": "Optional bottom tagline or legal line (can be empty string)",
    "features": [
      {"icon": "emoji or unicode symbol", "title": "Feature name", "desc": "One-line description"},
      {"icon": "emoji or unicode symbol", "title": "Feature name", "desc": "One-line description"},
      {"icon": "emoji or unicode symbol", "title": "Feature name", "desc": "One-line description"},
      {"icon": "emoji or unicode symbol", "title": "Feature name", "desc": "One-line description"}
    ]
  },
  "poster_design": {
    "layout": "hero_top_features_bottom | split_left_right | centered_minimal | full_bleed_text",
    "accent_color": "#HEXCODE — primary brand/action color",
    "bg_color": "#HEXCODE — background fill color",
    "text_color_primary": "#HEXCODE — main text color",
    "text_color_secondary": "#HEXCODE — secondary/body text color",
    "font_style": "bold_tech | elegant_serif | expressive_display | clean_sans",
    "has_feature_grid": true,
    "has_cta_button": true,
    "hero_occupies": "top_60 | center_50 | full_bleed | left_half"
  }
}""",

    # ── Artistic ───────────────────────────────────────────────────────────
    "artistic": _CREATIVE_AMPLIFIER + """You are an art director with MFA in fine arts and 15 years of creative work.
Focus on:
- Medium specificity: impasto oil, loose watercolor wash, charcoal rough, digital matte painting
- Brushwork: visible strokes vs smooth blending, palette knife texture, wet-on-wet
- Color theory: complementary tension, split-complementary harmony, analogous warmth
- Art movement reference: impressionism, brutalism, vaporwave, surrealism, art nouveau
- Composition: golden ratio, visual weight balance, negative space intentionality
- Emotional register: what feeling does this evoke in 3 words?

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Vector / Icon ──────────────────────────────────────────────────────
    "vector": """You are a brand identity designer (Pentagram / Wolff Olins level).
Focus on:
- Geometry: describe shapes mathematically (circle + square overlap, triangular forms, etc.)
- Color: MAXIMUM 3 colors with hex values. Justify each color choice.
- Scalability: must work at 16px favicon AND 1600px billboard — no fine details
- Negative space: describe intentional white space usage
- Style: flat vs minimal gradient (justify), icon grid alignment (24px or 48px base)
- Logo type: wordmark / lettermark / symbol / combination — specify
- Brand personality: 3 adjectives that the mark should communicate

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Interior / Architecture ────────────────────────────────────────────
    "interior_arch": """You are a senior architectural visualization specialist (Zaha Hadid / MVRDV level).
Focus on:
- Materials: precise callouts (brushed concrete, warm oak veneer, matte black powder-coated steel,
  honed Calacatta marble, aged brass hardware)
- Lighting: HDRI sky type, artificial warm spots (2700K pendants), ambient occlusion depth
- Camera: height (eye-level 1.6m / bird's eye / worm's eye), lens (24mm wide vs 50mm standard)
- Render style: photorealistic vs clay render vs atmospheric haze
- Scale: human figure present? or pure architecture?
- Time of day: affects natural light angle and mood completely

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Character Consistency ──────────────────────────────────────────────
    "character_consistency": """You are a character design lead for AAA games / film VFX.
Focus on LOCKING DOWN every physical descriptor precisely:
- Face: exact eye color + shape, nose type, jaw structure, skin tone (Fitzpatrick scale 1-6)
- Hair: exact color (hex), length, texture (wavy/straight/coily), style name
- Build: height category, body type descriptor
- Outfit: every piece named + material + color (hex) + any graphic/logo
- Consistency anchors: 3-4 unique identifiers that must appear in EVERY generation
These anchors prevent character drift across multiple generations.

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",

    # ── Editing / Inpainting ───────────────────────────────────────────────
    "editing": """You are a photo retouching and compositing expert (ILM / Framestore level).
Focus on SURGICAL precision:
- What to PRESERVE: lighting direction, cast shadows, perspective angle, color temperature,
  grain/noise level, existing background elements outside the edit zone
- What to CHANGE: describe only the target edit — nothing else
- Edge quality: seamless blend (soft gradient mask) vs hard cut (geometric mask)
- Color match: new element must match existing scene's color grading
- Physics: new element must obey existing light source direction and intensity

Return ONLY valid JSON:
{
  "visual_concept": "...",
  "subject": "...",
  "setting": "...",
  "lighting": "...",
  "camera": "...",
  "composition": "...",
  "mood": "...",
  "color_palette": "...",
  "texture_detail": "...",
  "style_refs": ["...", "..."],
  "avoid": ["...", "..."]
}""",
}

# ══════════════════════════════════════════════════════════════════════════════
# STAGE B — Model-specific params system prompts
# ══════════════════════════════════════════════════════════════════════════════

_PARAMS_SYSTEM_BY_MODEL: Dict[str, str] = {

    "flux_2_pro": """You are a Flux 2 Pro prompt engineer.
Flux 2 Pro rules:
- Natural descriptive SENTENCES, NOT comma-tag lists
- Camera and lens terms boost output quality significantly (always include)
- 80-120 words sweet spot — longer degrades coherence
- No special tokens, no LoRA triggers, no model-specific syntax
- Start with the subject, then scene, then lighting, then camera, then mood
- negative_prompt: Flux ignores it mostly but still include for pipeline use

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "flux_2_max": """You are a Flux 2 Max prompt engineer.
Flux 2 Max rules:
- Rich, dense descriptive language — this model handles 150-200 words well
- Texture and material descriptions get extra attention from this model
- Lighting descriptions translate directly to output — be very precise
- Sentences preferred over tags, but short clauses work too
- Style references in the prompt boost quality (name photographers/directors)

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "flux_schnell": """You are a Flux Schnell prompt engineer.
Flux Schnell rules:
- SHORT and PUNCHY — max 50 words (model runs 4-8 steps, long prompts hurt)
- Most important visual elements FIRST (early tokens weighted more heavily)
- Use comma-separated descriptors, not full sentences
- Skip lighting nuance — keep it to 1-2 words (golden hour, soft light)
- No negative prompt needed (Schnell largely ignores it)

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "flux_2_dev": """You are a Flux 2 Dev prompt engineer.
Flux 2 Dev rules:
- Painterly and artistic language works best with this model
- Emphasize mood, color, and texture over technical camera specs
- Medium length: 80-100 words
- Art movement references strongly influence output
- Can handle both sentence and tag formats

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "flux_2_turbo": """You are a Flux 2 Turbo prompt engineer.
Flux 2 Turbo rules:
- Similar to Schnell but slightly more detailed — max 70 words
- Prioritize key subject + lighting + style
- Comma-separated format works best
- Speed-optimized model: keep prompts focused

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "flux_kontext": """You are a Flux Kontext prompt engineer.
Flux Kontext rules:
- For EDITING: use instruction-style language ("Keep the background unchanged. Replace X with Y.")
- For CONSISTENCY: anchor the reference first ("Same person as reference image. Now show them...")
- Be explicit about what NOT to change — this model is very instruction-literal
- Max 100 words, instruction-first ordering

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "flux_kontext_max": """You are a Flux Kontext Max prompt engineer.
Same instruction-style as Kontext but supports more detail.
For complex edits: describe the preservation list AND the change list separately.
Up to 150 words. More detail = better output for this model tier.

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "ideogram_turbo": """You are an Ideogram V3 Turbo background scene generator for poster/ad hero images.

CRITICAL: Generate ONLY the hero background scene — NO text, NO words, NO UI labels.
PosterCompositor will add all text/headlines/CTAs on top.

RULES:
1. NO TEXT whatsoever — zero words, letters, numbers in the image
2. Focus on the scene atmosphere: lighting, colors, composition, mood
3. Bottom portion should be darker/cleaner to allow text overlay naturally
4. Match the brief's visual_concept exactly

Max 80 words. Scene description only.

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "ideogram_quality": """You are an Ideogram V3 Quality background scene generator for poster/ad hero images.

CRITICAL: You are generating ONLY the hero background image — NOT the full poster.
A separate renderer (PosterCompositor) will composite all text, headlines, CTAs, and feature cards on top.

YOUR ONLY JOB: Create a stunning, cinematic BACKGROUND SCENE that matches the brief's visual_concept.

RULES:
1. NO TEXT in the image — absolutely zero text, words, letters, numbers, watermarks, UI overlays
2. Focus 100% on the scene: lighting, atmosphere, composition, colors, depth
3. The bottom ~45% of the image should be darker/simpler (text will go here) — use gradient/depth naturally
4. Match the visual_concept EXACTLY — if it says "laptop showing dashboard", generate that scene
5. Cinematic quality: dramatic lighting, high detail, professional photography or render style
6. Leave clean visual space in the center/bottom for text compositing

PRODUCT TYPE GUIDANCE:
- SaaS/Tech app → Realistic laptop/phone on a clean desk showing app UI, soft bokeh background, ambient office lighting
- Festival/Event → Rich cultural scene with atmospheric lighting, bokeh lights, vibrant colors
- Fashion → Model in editorial setting, clean background, dramatic lighting
- Food → Hero product shot, soft bokeh, warm lighting, appetizing presentation
- Fitness → Athlete in action, dynamic pose, cinematic lighting

Up to 120 words. Scene description only — no text, no UI labels in the output.

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "hunyuan_image": """You are a Hunyuan Image prompt engineer (anime specialist).
Hunyuan rules:
- Anime vocabulary responds strongly: use studio names (Ghibli, MAPPA, KyoAni style)
- Character archetypes: specify (shonen protagonist, kuudere, magical girl, etc.)
- Japanese aesthetic terms: moe, bishoujo, ikemen — use if appropriate
- Dynamic pose language: "leaping forward", "wind-swept hair", "dramatic backlit"
- Max 100 words, character-first ordering

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "recraft_v4": """You are a Recraft V4 prompt engineer.
Recraft V4 rules:
- Geometric description: describe shapes explicitly (circle overlapping rectangle, etc.)
- Max 3 colors — list hex values directly in prompt
- Clean, minimal language — no prose, no metaphors
- Flat design preferred unless gradient justified
- Max 60 words

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "recraft_v4_svg": """You are a Recraft V4 SVG prompt engineer.
SVG-specific rules:
- Think like a vector illustrator: describe SHAPES not photos
- Max 3 colors with hex values in the prompt itself
- No gradients, no textures, no photographic elements
- Scalability first: works at 16px favicon AND 1600px billboard
- Negative space: describe intentional white space
- Max 60 words

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",
}

# ══════════════════════════════════════════════════════════════════════════════
# Bucket-specific negative prompts
# ══════════════════════════════════════════════════════════════════════════════

_NEGATIVE_BY_BUCKET: Dict[str, str] = {
    "photorealism": (
        "blurry, low quality, deformed, bad anatomy, watermark, plastic skin, "
        "oversaturated, fake HDR, AI artifacts, uncanny valley, oversmoothed skin, "
        "bad hands, extra fingers, distorted face, lens flare, overexposed"
    ),
    "photorealism_portrait": (
        "blurry, plastic skin, oversmoothed, bad eyes, asymmetric face, "
        "extra fingers, bad hands, double chin artifact, skin texture gone, "
        "watermark, overexposed, unnatural catchlights, dead eyes"
    ),
    "photorealism_product": (
        "blurry, dirty surface, scratched, damaged, distorted shape, "
        "wrong color, bad label, floating object, uneven lighting, "
        "reflection artifacts, overexposed highlights, cheap feel"
    ),
    "photorealism_food": (
        "unappetizing, moldy, burnt, soggy, bad plating, dirty plate, "
        "wrong colors, overexposed, plastic-looking food, fake-looking steam, "
        "blurry hero element, cluttered background"
    ),
    "photorealism_fashion": (
        "bad proportions, distorted clothing, wrinkled mess, bad skin, "
        "overexposed, unnatural pose, dead eyes, plastic hair, "
        "wrong fabric texture, bad hands, extra limbs"
    ),
    "photorealism_landscape": (
        "overprocessed HDR, fake colors, blown highlights, muddy shadows, "
        "distracting foreground clutter, flat boring sky, oversaturated, "
        "lens distortion, plastic-looking water, bad horizon line"
    ),
    "anime": (
        "realistic photo, 3D render, western cartoon style, low quality, "
        "off-model proportions, inconsistent art style, bad hands, extra fingers, "
        "deformed face, western comic book style, blurry linework, muddy colors"
    ),
    "typography": (
        "illegible text, distorted letters, blurry text, low contrast, "
        "cluttered background behind text, overlapping text elements, "
        "pixelated, wrong font style, unreadable, spelling errors, cut-off text"
    ),
    "artistic": (
        "photorealistic, CGI render, 3D model look, stock photo aesthetic, "
        "overprocessed digital noise, flat lifeless colors, generic clip art, "
        "corporate bland, oversmoothed"
    ),
    "vector": (
        "photorealistic, gradients unless specified, texture, film grain, "
        "shadows, 3D depth effect, too many colors, raster artifacts, "
        "blurry edges, hand-drawn imprecision, complex details that break at small sizes"
    ),
    "interior_arch": (
        "distorted perspective, impossible geometry, flickering light artifacts, "
        "oversaturated, cartoon style, sketch look, unwanted people, "
        "furniture clipping, uneven proportions, bad reflections"
    ),
    "character_consistency": (
        "different person, changed eye color, different hair, wrong outfit, "
        "inconsistent skin tone, bad hands, extra limbs, morphed facial features, "
        "character drift, off-model, different build"
    ),
    "editing": (
        "hard visible seam, color mismatch, wrong lighting direction, "
        "changed perspective, altered background, removed shadows, "
        "blurry blend edge, scale mismatch, unrealistic composite"
    ),
    # NOTE: "fast" is a tier, not a bucket — kept only for heuristic_params compat
    # Do NOT route bucket="fast" through the engine
}

_DEFAULT_NEGATIVE = (
    "blurry, low quality, deformed, bad anatomy, watermark, signature, "
    "text artifacts, overexposed, underexposed, grainy, noisy, ugly, "
    "poorly drawn, bad proportions, disfigured, mutation"
)

# ══════════════════════════════════════════════════════════════════════════════
# Critic agent system prompts — HARD BUCKETS only, premium/ultra tier
# ══════════════════════════════════════════════════════════════════════════════

_CRITIC_SYSTEM_BY_BUCKET: Dict[str, str] = {
    "anime": """You are a senior anime production reviewer.
Review this generation prompt for anime image quality. Check:
1. Character consistency anchors — are unique identifiers locked down?
2. Art style specificity — is a real studio/director referenced?
3. Pose energy — is dynamic movement described?
4. Color cel shading — is shadow color non-generic?
5. Background detail level — does it match the style?

Return a JSON with specific improvements ONLY (not praise):
{"issues": ["...", "..."], "refined_prompt_additions": "...", "refined_negative_additions": "..."}""",

    "typography": """You are a senior typographer and graphic design reviewer.
Review this generation prompt for typography quality. Check:
1. Text in image — is it wrapped in double quotes for Ideogram?
2. Font style — is it specific (bold condensed sans vs thin serif)?
3. Background — is it simple enough for legibility?
4. Contrast — is color contrast described for readability?
5. Layout zones — is text placement non-overlapping with the hero visual?

Return a JSON with specific improvements ONLY:
{"issues": ["...", "..."], "refined_prompt_additions": "...", "refined_negative_additions": "..."}""",

    "editing": """You are a senior compositing and retouching reviewer.
Review this editing prompt for precision. Check:
1. Preservation list — what MUST stay unchanged? Is it explicit?
2. Change target — is the edit described surgically (not broadly)?
3. Lighting match — is the new element's lighting direction specified?
4. Edge blend — is seamless vs hard-cut specified?
5. Color match — is color grading consistency mentioned?

Return a JSON with specific improvements ONLY:
{"issues": ["...", "..."], "refined_prompt_additions": "...", "refined_negative_additions": "..."}""",

    "interior_arch": """You are a senior architectural visualization reviewer.
Review this archviz prompt for quality. Check:
1. Material callouts — are surface materials named precisely (not just "wood")?
2. Lighting setup — is HDRI type and artificial light temp specified?
3. Camera height — is eye-level or dramatic angle specified?
4. Scale — is there a human figure for scale reference?
5. Render style — photorealistic vs clay vs atmospheric?

Return a JSON with specific improvements ONLY:
{"issues": ["...", "..."], "refined_prompt_additions": "...", "refined_negative_additions": "..."}""",

    "character_consistency": """You are a senior character design reviewer.
Review this character prompt for consistency anchors. Check:
1. Eye color + shape — locked down precisely?
2. Hair — color (hex), texture, and style all specified?
3. Skin tone — Fitzpatrick scale or precise description?
4. Outfit — every piece named with material + color?
5. 3-4 unique identifiers — present and distinctive enough to prevent drift?

Return a JSON with specific improvements ONLY:
{"issues": ["...", "..."], "refined_prompt_additions": "...", "refined_negative_additions": "..."}""",
}

# ══════════════════════════════════════════════════════════════════════════════
# JSON schema validator
# ══════════════════════════════════════════════════════════════════════════════

_REQUIRED_BRIEF_FIELDS = {"visual_concept", "subject", "lighting", "camera", "mood"}
_REQUIRED_PARAMS_FIELDS = {"prompt", "negative_prompt"}
_MAX_PROMPT_TOKENS = 250   # rough word limit
_MIN_PROMPT_WORDS = 8


def _validate_brief(brief: Dict) -> list[str]:
    """Return list of issues with a brief dict. Empty = valid."""
    issues = []
    for f in _REQUIRED_BRIEF_FIELDS:
        if not brief.get(f):
            issues.append(f"Missing required field: {f}")
    if brief.get("camera", "") in ("", "standard", "default", "camera"):
        issues.append("Camera too generic — needs real body + lens spec")
    if brief.get("lighting", "") in ("", "natural", "good lighting"):
        issues.append("Lighting too vague — needs position + temperature")
    return issues


def _validate_params(params: Dict, bucket: str, has_ad_copy: bool = False) -> list[str]:
    """Return list of issues with params dict. Empty = valid."""
    issues = []
    for f in _REQUIRED_PARAMS_FIELDS:
        if not params.get(f):
            issues.append(f"Missing required field: {f}")
    prompt = params.get("prompt", "")
    word_count = len(prompt.split())
    if word_count < _MIN_PROMPT_WORDS:
        issues.append(f"Prompt too short ({word_count} words, min {_MIN_PROMPT_WORDS})")
    if word_count > _MAX_PROMPT_TOKENS:
        issues.append(f"Prompt too long ({word_count} words, max {_MAX_PROMPT_TOKENS})")
    # Skip double-quote check when PosterCompositor handles text overlay (has_ad_copy=True)
    if bucket == "typography" and not has_ad_copy and '"' not in prompt:
        issues.append("Typography bucket: text in image must be wrapped in double quotes")
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> Dict:
    """
    Extract first JSON object from LLM response.
    Handles: markdown fences, prose prefix/suffix, multiple JSON objects.
    Returns {} on parse failure (never raises).
    """
    if not text or not text.strip():
        return {}
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # Try direct parse (model returned clean JSON)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    # Regex: find outermost {...} — handles prose wrapper like "Here is the JSON: {...}"
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    logger.warning("[gemini-engine] _extract_json failed: %r", text[:200])
    return {}


def _resolve_brief_system(bucket: str) -> str:
    """Pick the most specific matching brief system prompt."""
    if bucket in _BRIEF_SYSTEM_BY_BUCKET:
        return _BRIEF_SYSTEM_BY_BUCKET[bucket]
    # Try parent bucket (photorealism_portrait → photorealism)
    parent = bucket.split("_")[0]
    return _BRIEF_SYSTEM_BY_BUCKET.get(parent, _BRIEF_SYSTEM_BY_BUCKET["photorealism"])


_MODEL_KEY_ALIASES: Dict[str, str] = {
    # stream_generate.py key  →  _PARAMS_SYSTEM_BY_MODEL key
    "flux_pro":     "flux_2_pro",
    "flux_dev":     "flux_2_dev",
    "flux_schnell": "flux_schnell",
    "flux_kontext": "flux_kontext",
    "flux_kontext_max": "flux_kontext_max",
    "ideogram_quality": "ideogram_quality",
    "ideogram_turbo":   "ideogram_turbo",
    "recraft_v4":       "recraft_v4",
    "recraft_v4_svg":   "recraft_v4_svg",
    "hunyuan_image":    "hunyuan_image",
}


# ══════════════════════════════════════════════════════════════════════════════
# CDI — Creative Director Integration System (Stage B universal upgrade)
# Replaces single-model params prompts with a full multi-variant schema.
# Gemini acts as Creative Director who selects model, writes prompt, maps emotion.
# ══════════════════════════════════════════════════════════════════════════════

_CDI_SYSTEM = """You are a world-class Creative Director and prompt engineer simultaneously.
Your job: take a Creative Brief and produce a complete Creative Director Integration (CDI) schema
that will be used to drive AI image generation at the highest possible quality.

AVAILABLE MODELS (use exact keys):
- flux_pro       → Flux 2 Pro via fal.ai. Best for: cinematic photography, luxury products, editorial beauty, complex lighting, realistic humans. Handles 100-140 word descriptive sentences best.
- flux_dev       → Flux 2 Dev. Best for: artistic/painterly scenes, concept art, expressive styles, moody atmosphere. 80-100 words.
- flux_schnell   → Flux Schnell. Best for: fast drafts, simple scenes. Max 50 words, comma tags.
- ideogram_quality → Ideogram v3 Quality. Best for: text-in-image ads, bold typography, graphic design posters, logos. ONLY model that renders text reliably.
- ideogram_turbo   → Ideogram v3 Turbo. Best for: same as quality but faster, lower detail.
- hunyuan_image    → Hunyuan. Best for: Asian aesthetics, fashion, portraits with East Asian cultural elements.

PROMPT ENGINEERING RULES per model:
flux_pro: Natural SENTENCES (not tag lists). Always include: camera body + lens (e.g. "Shot on Hasselblad X2D 110mm f/2"). Include exact lighting position, film stock or color grade. Subject first, then scene, then light, then camera.
flux_dev: Painterly language. Emotion and texture over camera specs. Art movement references work well.
flux_schnell: SHORT comma tags. Most important element first. Skip lighting nuance.
ideogram_quality/turbo: Quote text in double quotes. Describe typography style explicitly (font family, weight, size role). Dark luxury aesthetics need explicit direction.

TRANSLATION PRINCIPLE:
Every emotion or feeling in the brief MUST translate to a specific photography/visual language term.
Examples:
  "warm confidence" → "backlit amber rim light, skin luminosity, Kodak Vision3 film grade"
  "trustworthy" → "eye-level camera, clean warm background, soft key light 45° camera-left"
  "power" → "low angle, wide lens, dramatic shadow, deep blacks"
  "celebration" → "motion blur on crowd, confetti bokeh, high key fill, peak action moment"
  "luxury" → "shallow DOF, specular highlights on product, marble/leather surface detail"
  "futuristic" → "neon underglow, volumetric fog, blue-cyan color grade, reflective surfaces"

COLOR STRATEGY RULE:
Convert color intentions to exact percentages + hex + lighting/material terms.
"60% dark" → specify as background fill + shadow direction + fill ratio
"30% amber" → specify as rim light color temperature (2700-3200K) + material surface

TEXT HANDLING:
If the brief has headline text, EXCLUDE it from the primary_output (flux) prompt.
State this explicitly in text_handling.
Create an ideogram_variant that renders the text graphically.

PARAMETERS:
steps: 4 (schnell), 20 (dev/ideogram), 28-32 (flux_pro simple), 36-40 (flux_pro complex lighting)
guidance: 2.5-3.0 (creative/loose), 3.5 (balanced), 4.0-4.5 (prompt-adherent)

Return ONLY valid JSON matching this exact schema:
{
  "schema": "cd_integration",
  "creative_brief": {
    "hook": "one-sentence core creative idea",
    "emotion": "precise emotional territory with specific qualifiers (not generic)",
    "platform": "primary format + secondary crop",
    "composition": "named archetype + specific element positions",
    "color_strategy": "3 hex values with % split + what each represents visually"
  },
  "translation_notes": "how the CD's emotional direction maps to specific photography/lighting/color language",
  "text_handling": "whether text is excluded from primary and why, or included",
  "recommended_model": "model key from available list",
  "recommendation_reason": "one sentence: why this model is optimal for this specific visual challenge",
  "primary_output": {
    "model": "model key",
    "prompt": "fully crafted prompt for this model (follow model rules above)",
    "negative_prompt": "specific and relevant, not generic",
    "parameters": {"steps": 32, "guidance": 3.5},
    "prompt_notes": "2-3 sentences explaining the key creative decisions in the prompt"
  },
  "ideogram_variant": {
    "model": "ideogram_quality or ideogram_turbo",
    "prompt": "typography-focused prompt with text in double quotes",
    "negative_prompt": "...",
    "parameters": {"steps": 20, "guidance": 3.0},
    "prompt_notes": "why this typography direction"
  },
  "draft_variant": {
    "model": "flux_schnell",
    "prompt": "short 30-50 word comma-tag version for quick composition check",
    "negative_prompt": "...",
    "parameters": {"steps": 4, "guidance": 3.5},
    "prompt_notes": "what to check in this draft"
  }
}"""

# CDI model key → our internal fal_model_key mapping
_CDI_MODEL_MAP: Dict[str, str] = {
    "flux_pro":         "flux_pro",
    "flux_dev":         "flux_dev",
    "flux_schnell":     "flux_schnell",
    "ideogram_quality": "ideogram_quality",
    "ideogram_turbo":   "ideogram_turbo",
    "hunyuan_image":    "hunyuan_image",
    "flux_kontext":     "flux_kontext",
    # legacy aliases
    "flux_2_pro":       "flux_pro",
    "flux_2_dev":       "flux_dev",
    "flux_schnell_pixazo": "flux_schnell",
}


def _resolve_params_system(model_key: str) -> str:
    """Pick model-specific params prompt. Fallback to flux_2_pro."""
    # Normalize: "Flux 2 Pro" → "flux_2_pro"
    normalized = model_key.lower().replace(" ", "_").replace(".", "_").replace("-", "_")
    # 1. Exact match
    if normalized in _PARAMS_SYSTEM_BY_MODEL:
        return _PARAMS_SYSTEM_BY_MODEL[normalized]
    # 2. Alias table (handles stream_generate "flux_pro" → "flux_2_pro")
    aliased = _MODEL_KEY_ALIASES.get(normalized)
    if aliased and aliased in _PARAMS_SYSTEM_BY_MODEL:
        return _PARAMS_SYSTEM_BY_MODEL[aliased]
    # 3. Longest-key-first prefix match (prevents "flux_kontext" matching "flux_kontext_max")
    for key in sorted(_PARAMS_SYSTEM_BY_MODEL, key=len, reverse=True):
        if normalized.startswith(key) or key.startswith(normalized):
            return _PARAMS_SYSTEM_BY_MODEL[key]
    return _PARAMS_SYSTEM_BY_MODEL["flux_2_pro"]


def _resolve_negative(bucket: str, params_negative: str) -> str:
    """Merge bucket-specific negative with params-returned negative (case-insensitive dedup)."""
    bucket_neg = _NEGATIVE_BY_BUCKET.get(
        bucket,
        _NEGATIVE_BY_BUCKET.get(bucket.split("_")[0], _DEFAULT_NEGATIVE)
    )
    pn = (params_negative or "").strip()
    if pn and pn.strip().lower() != _DEFAULT_NEGATIVE.strip().lower():
        all_terms = [t.strip() for t in (pn + ", " + bucket_neg).split(",")]
        seen: set = set()
        deduped: list = []
        for t in all_terms:
            if t and t.lower() not in seen:
                seen.add(t.lower())
                deduped.append(t)
        return ", ".join(deduped)
    return bucket_neg


# ══════════════════════════════════════════════════════════════════════════════
# Cognitive Aesthetics Constants (PDF: Architecting the Unbeatable Pipeline 2026)
# ══════════════════════════════════════════════════════════════════════════════

# Color psychology table — maps goal signal → color directive injected into brief
_COLOR_PSYCHOLOGY: Dict[str, str] = {
    "urgency":  "Color psychology directive: dominant accent RED or ORANGE — amygdala activation, urgency, CTA conversion. Use warm high-contrast palette.",
    "trust":    "Color psychology directive: dominant tone BLUE — parasympathetic activation, trust, stability. Use cool calm palette.",
    "luxury":   "Color psychology directive: dominant palette BLACK + GOLD or DEEP PURPLE — combined novelty response, exclusivity, premium. Rich jewel tones.",
    "energy":   "Color psychology directive: dominant YELLOW or ELECTRIC ORANGE — serotonin release, high visibility, vitality. Vibrant saturated tones.",
    "wellness": "Color psychology directive: dominant GREEN or SOFT EARTH — minimal stress response, naturalism, health. Muted organic palette.",
    "mystery":  "Color psychology directive: dominant DEEP PURPLE or MIDNIGHT BLUE — novelty + mystery response. High-contrast dramatic lighting.",
}

# creative_type / goal → color psychology goal key
_CREATIVE_TYPE_TO_COLOR_GOAL: Dict[str, str] = {
    "ad": "urgency", "advertisement": "urgency", "marketing": "urgency",
    "sale": "urgency", "promo": "urgency", "promotion": "urgency",
    "cta": "urgency", "ecommerce": "urgency",
    "corporate": "trust", "business": "trust", "linkedin": "trust",
    "professional": "trust", "b2b": "trust",
    "luxury": "luxury", "premium": "luxury", "jewelry": "luxury",
    "fashion_editorial": "luxury", "high_end": "luxury",
    "fitness": "energy", "sport": "energy", "gym": "energy", "energy": "energy",
    "wellness": "wellness", "health": "wellness", "organic": "wellness",
    "nature": "wellness", "eco": "wellness",
    "horror": "mystery", "dark": "mystery", "gothic": "mystery", "thriller": "mystery",
}

# Buckets where "Imperfect by Design" aesthetic is beneficial (film grain, organic imperfection)
# Skip: product (needs pristine), vector (scalable), typography (precision), editing (accuracy)
_IMPERFECT_BY_DESIGN_BUCKETS = {
    "photorealism", "photorealism_portrait", "photorealism_fashion",
    "photorealism_landscape", "photorealism_food",
    "artistic", "anime",
}

# Tiers where Imperfect by Design applies (not fast — too quick for nuance)
_IMPERFECT_TIERS = {"standard", "premium", "ultra", "balanced", "quality"}

# India "Modern Masala" cultural keywords — compiled at import for perf
_INDIA_KEYWORDS = {
    "indian", "india", "desi", "bollywood", "hindi", "saree", "sari", "kurta",
    "punjabi", "bengali", "south indian", "tamil", "gujarati", "rajasthani",
    "masala", "chai", "holi", "diwali", "navratri", "eid", "wedding indian",
    "indian bride", "indian wedding", "mehndi", "dupatta", "lehenga", "dhoti",
    "rangoli", "temple", "mumbai", "delhi", "india gate", "taj mahal",
}
_INDIA_RE = re.compile(
    r"(" + "|".join(re.escape(k) for k in sorted(_INDIA_KEYWORDS, key=len, reverse=True)) + r")",
    re.IGNORECASE,
)

# Explicit color terms — if user already specified colors, skip color psychology injection
_EXPLICIT_COLOR_RE = re.compile(
    r"\b(red|blue|green|purple|gold|black|white|pink|teal|warm|cool|pastel|monochrome|"
    r"crimson|navy|magenta|cyan|amber|ivory|beige|maroon|coral|olive|lavender)\b",
    re.IGNORECASE,
)


def _build_contextual_hints(
    raw_prompt: str,
    creative_type: str,
    capability_bucket: str,
    tier: str,
) -> str:
    """
    Build context hints to inject into Stage A brief:
    1. Color psychology based on creative_type/goal
    2. 'Imperfect by Design' for organic aesthetic buckets on standard+ tiers
    3. India 'Modern Masala' cultural context when Indian subject detected
    """
    hints: list[str] = []
    prompt_lower = raw_prompt.lower()
    # Null-safe: default if None passed
    type_lower = (creative_type or "photo").lower()
    resolved_tier = (tier or "standard").lower().replace("quality", "premium").replace("balanced", "standard")

    # ── 1. Color Psychology ────────────────────────────────────────────────────
    # Skip if user already specified explicit colors in prompt
    if not _EXPLICIT_COLOR_RE.search(raw_prompt):
        color_goal = _CREATIVE_TYPE_TO_COLOR_GOAL.get(type_lower)
        if not color_goal:
            for signal, goal in _CREATIVE_TYPE_TO_COLOR_GOAL.items():
                if signal in prompt_lower:
                    color_goal = goal
                    break
        if color_goal and color_goal in _COLOR_PSYCHOLOGY:
            hints.append(_COLOR_PSYCHOLOGY[color_goal])

    # ── 2. Imperfect by Design ────────────────────────────────────────────────
    if capability_bucket in _IMPERFECT_BY_DESIGN_BUCKETS and resolved_tier in _IMPERFECT_TIERS:
        hints.append(
            "Aesthetic directive (2026 trend): 'Imperfect by Design' — inject subtle analog "
            "imperfections: micro film grain, slight chromatic aberration at edges, organic "
            "light leak or imprecise exposure, tactile texture. Avoid sterile AI perfection. "
            "These imperfections increase engagement and authenticity."
        )

    # ── 3. India 'Modern Masala' cultural context ─────────────────────────────
    if _INDIA_RE.search(raw_prompt):
        hints.append(
            "Cultural context: Indian aesthetic — blend traditional vibrancy "
            "(saffron, turmeric gold, deep sindoor red, marigold, peacock teal) with "
            "hyper-modern photographic execution. 'Modern Masala' kinetic energy: "
            "rich texture + bold color + contemporary composition = maximum engagement."
        )

    return " | ".join(hints)


# ══════════════════════════════════════════════════════════════════════════════
# Main Engine
# ══════════════════════════════════════════════════════════════════════════════

# Per-stage token limits (tuned to actual output sizes)
_STAGE_MAX_TOKENS = {
    "brief":  1500,
    "params":  600,
    "critic":  400,
}

# Tier normalization table — covers all names clients might pass
_TIER_NORM = {
    "fast":     "fast",
    "balanced": "standard",
    "standard": "standard",
    "quality":  "premium",
    "premium":  "premium",
    "ultra":    "ultra",
}


def _translate_brief_colors(brief: Dict) -> Dict:
    """
    Walk the brief dict and translate all hex color values to natural language.
    Modifies a shallow copy — original brief is unchanged.
    This implements APEX's model-native syntax: models respond better to
    "vivid deep orange" than "#FF6B00".
    """
    import copy
    b = copy.copy(brief)

    def _translate_val(v: object) -> object:
        if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7):
            translated = _hex_to_natural(v)
            return translated if translated != v else v
        elif isinstance(v, dict):
            return {kk: _translate_val(vv) for kk, vv in v.items()}
        elif isinstance(v, list):
            return [_translate_val(i) for i in v]
        return v

    # Only translate color-bearing fields to avoid corrupting other data
    color_fields = {
        "color_palette", "brand_colors", "poster_design",
        "accent_color", "bg_color", "text_color_primary", "text_color_secondary",
    }
    for field in color_fields:
        if field in b:
            b[field] = _translate_val(b[field])

    return b


class GeminiPromptEngine:
    """
    Bucket-aware + model-specific prompt engine with validator and optional critic.

    Default path  : brief → params → validate → return
    Hard buckets  : brief → params → critic → refined params → validate → return
    (anime, typography, editing, interior_arch, character_consistency)
    (critic only triggered on premium / ultra tier)

    Falls back to heuristic if GEMINI_API_KEY missing or any call fails.
    """

    def __init__(self):
        self._model_name = _GEMINI_MODEL
        self._client = None   # initialized lazily; see _get_client()

    @property
    def enabled(self) -> bool:
        """Re-evaluated on each access so key rotation / env changes take effect."""
        return _is_gemini_enabled()

    def _get_client(self):
        """Return module-level singleton Gemini client (created once, reused)."""
        global _gemini_client
        if "_gemini_client" not in globals() or _gemini_client is None:
            from google import genai
            key = os.getenv("GEMINI_API_KEY", "").strip()
            globals()["_gemini_client"] = genai.Client(api_key=key)
        return globals()["_gemini_client"]

    async def _call(
        self,
        system: str,
        user: str,
        stage: str = "brief",
        temperature: float = 0.85,
    ) -> str:
        """Single async Gemini call — returns raw text."""
        from google.genai import types
        client = self._get_client()
        max_tokens = _STAGE_MAX_TOKENS.get(stage, 800)
        resp = await client.aio.models.generate_content(
            model=self._model_name,
            contents=[{"role": "user", "parts": [{"text": user}]}],
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )
        return resp.text or ""

    # ── Stage A ───────────────────────────────────────────────────────────────

    async def create_brief(
        self,
        raw_prompt: str,
        creative_type: str = "photo",
        style: str = "photo",
        extra_context: Optional[str] = None,
        bucket: str = "photorealism",
        tier: str = "standard",
    ) -> Dict:
        """Stage A: raw prompt → Creative Brief JSON (bucket-specific system prompt)."""
        if not raw_prompt or len(raw_prompt.strip()) < 3:
            return self._heuristic_brief(raw_prompt or "")
        if not self.enabled:
            return self._heuristic_brief(raw_prompt)

        system = _resolve_brief_system(bucket)
        user_msg = f"Raw prompt: {raw_prompt}"
        if creative_type not in ("photo", ""):
            user_msg += f"\nCreative type: {creative_type}"
        if style and style not in ("Auto", "photo", ""):
            user_msg += f"\nDesired style: {style}"
        if extra_context:
            user_msg += f"\nExtra context: {extra_context}"

        # Inject situational + cognitive context hints (uses real tier, not hardcoded "standard")
        ctx_hints = _build_contextual_hints(raw_prompt, creative_type or "photo", bucket, tier)
        if ctx_hints:
            user_msg += f"\n\nSITUATIONAL DIRECTIVES (follow these precisely):\n{ctx_hints}"

        try:
            raw = await self._call(system, user_msg, stage="brief", temperature=0.90)
            brief = _extract_json(raw)
            brief["_source"] = "gemini"
            brief["_bucket"] = bucket

            # Validate — heuristic fallback if missing critical fields
            issues = _validate_brief(brief)
            if issues:
                logger.warning("[gemini-engine] brief issues %s: %s", bucket, issues)
                # If truly missing required fields, fall back rather than pass garbage downstream
                missing_critical = [i for i in issues if "Missing required field" in i]
                if missing_critical:
                    logger.warning("[gemini-engine] critical brief fields missing, falling back")
                    return self._heuristic_brief(raw_prompt)

            # Typography: must have ad_copy + poster_design for compositor
            if bucket == "typography":
                if not isinstance(brief.get("ad_copy"), dict):
                    brief.setdefault("ad_copy", {})
                if not isinstance(brief.get("poster_design"), dict):
                    brief.setdefault("poster_design", {})

            logger.info("[gemini-engine] brief OK bucket=%s: %s",
                        bucket, brief.get("visual_concept", "")[:60])
            return brief

        except Exception as e:
            logger.warning("[gemini-engine] brief failed (%s), heuristic fallback", e)
            return self._heuristic_brief(raw_prompt)

    # ── Stage B ───────────────────────────────────────────────────────────────



    async def build_params(
        self,
        brief: Dict,
        model_name: str = "flux_pro",
        capability_bucket: str = "photorealism",
        critic_notes: Optional[str] = None,
    ) -> Dict:
        """Stage B: Creative Brief → CDI schema (multi-variant, model-aware, emotion-translated)."""
        if not self.enabled or brief.get("_source") == "heuristic":
            return self._heuristic_params(brief, capability_bucket)

        # Translate hex colors to natural language before sending (APEX model-native syntax)
        brief_clean = {k: v for k, v in brief.items() if not k.startswith("_")}
        brief_clean = _translate_brief_colors(brief_clean)

        # For typography bucket: tell CDI that text will be composited separately
        _has_ad_copy = (
            capability_bucket == "typography"
            and isinstance(brief.get("ad_copy"), dict)
            and bool(brief["ad_copy"].get("headline"))
        )
        ad_hint = ""
        if _has_ad_copy:
            ad_copy = brief["ad_copy"]
            ad_hint = (
                f"\n\nPOSTER MODE: PosterCompositor will render these text layers on top of the image:\n"
                f"  Headline: \"{ad_copy.get('headline','')}\"\n"
                f"  Subheadline: \"{ad_copy.get('subheadline','')}\"\n"
                f"  CTA: \"{ad_copy.get('cta','')}\"\n"
                f"primary_output MUST exclude all text — background scene only.\n"
                f"ideogram_variant should render this as a standalone typographic ad.\n"
                f"Bottom {30}% of the primary image must be darker to allow text legibility."
            )

        if critic_notes:
            ad_hint += f"\n\nCritic refinements to incorporate:\n{critic_notes}"

        brief_str = json.dumps(brief_clean, separators=(",", ":"))
        user_msg = (
            f"Creative Brief:\n{brief_str}\n\n"
            f"Router selected model: {model_name} (you may override with a better choice)\n"
            f"Capability bucket: {capability_bucket}{ad_hint}"
        )

        try:
            raw = await self._call(_CDI_SYSTEM, user_msg, stage="params", temperature=0.85)
            cdi = _extract_json(raw)

            if cdi.get("_parse_error") or not cdi.get("primary_output"):
                raise ValueError("CDI parse failed or missing primary_output")

            primary = cdi["primary_output"]
            prompt = str(primary.get("prompt") or "").strip()
            negative = str(primary.get("negative_prompt") or "").strip()
            cdi_params = primary.get("parameters") or {}

            if not prompt or len(prompt) < 20:
                raise ValueError(f"CDI primary prompt too short: {repr(prompt[:40])}")

            # Resolve model key: CDI recommendation overrides router, mapped to our fal keys
            cdi_model_raw = (cdi.get("recommended_model") or model_name).strip().lower()
            recommended_model = _CDI_MODEL_MAP.get(cdi_model_raw, model_name)

            # For poster mode: override to use background-only model (not ideogram)
            if _has_ad_copy and recommended_model in ("ideogram_quality", "ideogram_turbo"):
                recommended_model = "flux_pro"

            result: Dict = {
                "prompt":            prompt,
                "negative_prompt":   negative,
                "recommended_model": recommended_model,
                "parameters": {
                    "steps":    int(cdi_params.get("steps", 32)),
                    "guidance": float(cdi_params.get("guidance", 3.5)),
                },
                "cdi_schema":           cdi,
                "creative_brief_cdi":   cdi.get("creative_brief", {}),
                "translation_notes":    cdi.get("translation_notes", ""),
                "recommendation_reason": cdi.get("recommendation_reason", ""),
                "prompt_notes":         primary.get("prompt_notes", ""),
                "ideogram_variant":     cdi.get("ideogram_variant"),
                "draft_variant":        cdi.get("draft_variant"),
                "style_notes":          cdi.get("creative_brief", {}).get("emotion", ""),
                "_source":              "cdi",
            }

            logger.info(
                "[gemini-engine] CDI OK model=%s→%s prompt=%d chars",
                model_name, recommended_model, len(prompt),
            )
            return result

        except Exception as e:
            logger.warning("[gemini-engine] CDI failed (%s), heuristic fallback", e)
            return self._heuristic_params(brief, capability_bucket)

    # ── Critic (hard buckets, premium/ultra only) ─────────────────────────────

    async def run_critic(
        self,
        brief: Dict,
        params: Dict,
        bucket: str,
        raw_prompt: str = "",
    ) -> Optional[str]:
        """
        Specialist critic agent for hard buckets.
        Returns critic_notes string to inject into Stage B re-run, or None if skipped/failed.
        """
        critic_system = _CRITIC_SYSTEM_BY_BUCKET.get(bucket)
        if not critic_system or not self.enabled:
            return None

        # Skip critic for typography when compositor handles text (double-quote critique is irrelevant)
        _has_ad_copy = (
            bucket == "typography"
            and isinstance(brief.get("ad_copy"), dict)
            and bool(brief["ad_copy"].get("headline"))
        )
        if bucket == "typography" and _has_ad_copy:
            return None

        try:
            brief_clean = {k: v for k, v in brief.items() if not k.startswith("_")}
            # Compact JSON + original prompt for critic context
            user_msg = (
                f"Original user prompt: {raw_prompt}\n\n"
                f"Creative Brief:\n{json.dumps(brief_clean, separators=(',', ':'))}\n\n"
                f"Generated prompt:\n{params.get('prompt', '')}\n\n"
                f"Negative prompt:\n{params.get('negative_prompt', '')}"
            )
            raw = await self._call(critic_system, user_msg, stage="critic", temperature=0.25)
            critic = _extract_json(raw)

            issues = critic.get("issues") or []
            if not isinstance(issues, list):
                issues = []
            additions = str(critic.get("refined_prompt_additions") or "")
            neg_additions = str(critic.get("refined_negative_additions") or "")

            if not issues and not additions:
                logger.info("[gemini-engine] critic: no issues found for %s", bucket)
                return None

            notes = ""
            if issues:
                notes += f"Issues found: {'; '.join(issues)}. "
            if additions:
                notes += f"Add to prompt: {additions}. "
            if neg_additions:
                notes += f"Add to negative: {neg_additions}."

            logger.info("[gemini-engine] critic %s: %d issues", bucket, len(issues))
            return notes.strip() or None

        except Exception as e:
            logger.warning("[gemini-engine] critic failed (%s), skipping", e)
            return None

    # ── Full pipeline ─────────────────────────────────────────────────────────

    async def enhance(
        self,
        raw_prompt: str,
        model_name: str = "flux_pro",
        capability_bucket: str = "photorealism",
        creative_type: str = "photo",
        style: str = "photo",
        extra_context: Optional[str] = None,
        tier: str = "standard",
    ) -> Dict:
        """
        Full async pipeline: brief → params → [critic → refined params] → validate → return.

        Critic runs only for hard buckets (anime, typography, editing,
        interior_arch, character_consistency) on premium or ultra tier.

        Returns dict compatible with stream_generate.py's separate create_brief/build_params calls.
        """
        resolved_tier = _TIER_NORM.get((tier or "standard").lower(), "standard")

        # Hints are built once here and passed into create_brief (not built again inside)
        hints = _build_contextual_hints(raw_prompt, creative_type or "photo", capability_bucket, resolved_tier)
        full_extra = f"{extra_context} | {hints}".strip(" |") if (extra_context and hints) else (hints or extra_context or "")

        # Stage A
        brief = await self.create_brief(
            raw_prompt, creative_type, style,
            extra_context=full_extra,
            bucket=capability_bucket,
            tier=resolved_tier,
        )

        # Stage B — first pass
        params = await self.build_params(brief, model_name, capability_bucket)

        # Critic — hard buckets, premium/ultra only, both brief AND params must be Gemini
        critic_ran = False
        use_critic = (
            capability_bucket in _HARD_BUCKETS
            and resolved_tier in ("premium", "ultra")
            and self.enabled
            and brief.get("_source") == "gemini"
            and params.get("_source") == "gemini"
        )
        if use_critic:
            critic_notes = await self.run_critic(brief, params, capability_bucket, raw_prompt)
            if critic_notes:
                params = await self.build_params(brief, model_name, capability_bucket, critic_notes)
                critic_ran = True

        final_negative = _resolve_negative(capability_bucket, params.get("negative_prompt", ""))
        # engine_label tracks what actually built the params (not just the brief)
        engine_label = "gemini" if params.get("_source") == "gemini" else "heuristic"

        return {
            "brief": brief,
            "prompt": params.get("prompt", raw_prompt),
            "negative_prompt": final_negative,
            "style_notes": params.get("style_notes", ""),
            "original_prompt": raw_prompt,
            "engine": engine_label,
            "critic_ran": critic_ran,
        }

    # ── Heuristic fallbacks ───────────────────────────────────────────────────

    @staticmethod
    def _heuristic_brief(raw_prompt: str) -> Dict:
        return {
            "visual_concept": raw_prompt,
            "subject": raw_prompt,
            "setting": "",
            "lighting": "natural soft lighting",
            "camera": "85mm f/1.8",
            "composition": "rule of thirds",
            "mood": "professional quality",
            "color_palette": "harmonious tones",
            "texture_detail": "sharp details, high resolution",
            "style_refs": [],
            "avoid": ["blurry", "low quality", "deformed"],
            "_source": "heuristic",
        }

    @staticmethod
    def _heuristic_params(brief: Dict, capability_bucket: str) -> Dict:
        # Sanitize visual_concept — reject JSON failure strings like "{}", "null"
        _vc = brief.get("visual_concept") or brief.get("subject", "")
        _vc = str(_vc).strip()
        if _vc in ("{}", "{", "}", "null", "none") or len(_vc) < 5:
            _vc = brief.get("subject", "") or brief.get("mood", "") or "professional scene"
        parts = [_vc]
        for field in ("lighting", "camera", "composition", "mood", "color_palette", "texture_detail"):
            val = brief.get(field, "")
            if val:
                parts.append(val)

        suffix_map = {
            "photorealism":          "photorealistic, 8K UHD, sharp focus, professional photography, hyperdetailed",
            "typography":            "crisp sharp text, graphic design, high contrast, readable typography",
            "artistic":              "artistic masterpiece, painterly, expressive, vibrant colors",
            "character_consistency": "consistent character, detailed face, sharp focus, professional portrait",
            "vector":                "clean vector art, flat design, scalable illustration",
            "interior_arch":         "architectural visualization, sharp details, professional render",
            "anime":                 "anime style, vibrant colors, detailed illustration, studio quality",
            "editing":               "seamless composite, perfect lighting match, professional retouch",
            "fast":                  "good quality, clean",
        }
        base_bucket = capability_bucket.split("_")[0]
        parts.append(suffix_map.get(capability_bucket, suffix_map.get(base_bucket, "masterful quality")))

        neg = _NEGATIVE_BY_BUCKET.get(
            capability_bucket,
            _NEGATIVE_BY_BUCKET.get(base_bucket, _DEFAULT_NEGATIVE)
        )
        avoid = brief.get("avoid", [])
        if avoid:
            neg = ", ".join(avoid) + ", " + neg

        return {
            "prompt": ", ".join(p for p in parts if p),
            "negative_prompt": neg,
            "style_notes": f"bucket={capability_bucket}",
            "_source": "heuristic",
        }


# Singleton
gemini_prompt_engine = GeminiPromptEngine()

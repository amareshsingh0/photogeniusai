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

import json
import logging
import os
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Feature flags ──────────────────────────────────────────────────────────────
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
USE_GEMINI_ENGINE: bool = (
    bool(_GEMINI_KEY)
    and os.getenv("USE_GEMINI_ENGINE", "true").lower() != "false"
)

# Buckets that get a critic agent on premium/ultra
_HARD_BUCKETS = {"anime", "typography", "editing", "interior_arch", "character_consistency"}

# ══════════════════════════════════════════════════════════════════════════════
# STAGE A — Bucket-specific Creative Brief system prompts
# ══════════════════════════════════════════════════════════════════════════════

_CREATIVE_AMPLIFIER = """
CORE DIRECTIVE — IMAGINATION FIRST:
You are not just a technician. You are a visionary creative director with the imagination of Alejandro Jodorowsky, the composition sense of Stanley Kubrick, the color instinct of Wes Anderson, and the surrealist depth of Salvador Dalí.

Your job is to take even the simplest prompt and ELEVATE it into something extraordinary:
- Find the UNEXPECTED angle — what interpretation would make someone stop scrolling?
- Add ONE surprising element that doesn't break the prompt but makes it unforgettable
- Color palettes should feel emotionally charged, not just "harmonious"
- Lighting should tell a story, not just illuminate
- The viewer should FEEL something — awe, curiosity, longing, exhilaration

NEVER produce generic, predictable, stock-photo-level descriptions.
ALWAYS ask: "What would make this image iconic?"
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
    "typography": """You are a senior graphic designer specializing in type-heavy visuals.
Focus on:
- Font category: serif (editorial, luxury) vs sans-serif (modern, tech) vs display (expressive)
- Hierarchy: headline > subheadline > CTA (size ratios, weight contrast)
- Color: WCAG AA minimum contrast ratio between text and background
- Background: must be simple enough for text legibility (gradients ok if text zone is clean)
- Layout zones: where does text live? top/center/bottom — don't overlap hero visual
- CTA: high contrast, action-oriented color (orange, red, white on dark)
- Any text to appear IN the image: describe it explicitly

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

    "ideogram_turbo": """You are an Ideogram V3 Turbo prompt engineer.
Ideogram rules:
- Any text to APPEAR IN the image: wrap in "double quotes" (critical — this is how Ideogram reads text)
- Specify font style explicitly: bold condensed sans-serif, elegant thin serif, hand-lettered, etc.
- Background must be clean enough for text legibility
- Describe layout: text position, size hierarchy, color contrast
- Max 100 words

Return ONLY valid JSON:
{"prompt": "...", "negative_prompt": "...", "style_notes": "..."}""",

    "ideogram_quality": """You are an Ideogram V3 Quality prompt engineer.
Same rules as Turbo but richer:
- More detail on typography layout (padding, alignment, hierarchy sizes)
- Describe color contrast ratios for text (light text on dark bg, etc.)
- Multiple text elements: label each with position and size hierarchy
- Up to 150 words

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
    "fast": (
        "blurry, low quality, watermark, deformed, bad anatomy"
    ),
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


def _validate_params(params: Dict, bucket: str) -> list[str]:
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
    if bucket == "typography" and '"' not in prompt:
        issues.append("Typography bucket: text in image must be wrapped in double quotes")
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> Dict:
    """Extract first JSON object from LLM response (handles markdown fences)."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    text = re.sub(r"```\s*$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON found in response: {text[:200]}")
    return json.loads(text[start:end])


def _resolve_brief_system(bucket: str) -> str:
    """Pick the most specific matching brief system prompt."""
    if bucket in _BRIEF_SYSTEM_BY_BUCKET:
        return _BRIEF_SYSTEM_BY_BUCKET[bucket]
    # Try parent bucket (photorealism_portrait → photorealism)
    parent = bucket.split("_")[0]
    return _BRIEF_SYSTEM_BY_BUCKET.get(parent, _BRIEF_SYSTEM_BY_BUCKET["photorealism"])


def _resolve_params_system(model_key: str) -> str:
    """Pick model-specific params prompt. Fallback to flux_2_pro."""
    # Normalize: "Flux 2 Pro" → "flux_2_pro"
    normalized = model_key.lower().replace(" ", "_").replace(".", "_").replace("-", "_")
    # Try exact, then try prefix match
    if normalized in _PARAMS_SYSTEM_BY_MODEL:
        return _PARAMS_SYSTEM_BY_MODEL[normalized]
    for key in _PARAMS_SYSTEM_BY_MODEL:
        if key in normalized or normalized in key:
            return _PARAMS_SYSTEM_BY_MODEL[key]
    return _PARAMS_SYSTEM_BY_MODEL["flux_2_pro"]


def _resolve_negative(bucket: str, params_negative: str) -> str:
    """Merge bucket-specific negative with params-returned negative."""
    bucket_neg = _NEGATIVE_BY_BUCKET.get(
        bucket,
        _NEGATIVE_BY_BUCKET.get(bucket.split("_")[0], _DEFAULT_NEGATIVE)
    )
    if params_negative and params_negative.strip() and params_negative != _DEFAULT_NEGATIVE:
        # Merge: params-specific + bucket-specific, deduplicated
        all_terms = [t.strip() for t in (params_negative + ", " + bucket_neg).split(",")]
        seen, deduped = set(), []
        for t in all_terms:
            if t and t not in seen:
                seen.add(t)
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

# India "Modern Masala" cultural keywords
_INDIA_KEYWORDS = {
    "indian", "india", "desi", "bollywood", "hindi", "saree", "sari", "kurta",
    "punjabi", "bengali", "south indian", "tamil", "gujarati", "rajasthani",
    "masala", "chai", "holi", "diwali", "navratri", "eid", "wedding indian",
    "indian bride", "indian wedding", "mehndi", "dupatta", "lehenga", "dhoti",
    "rangoli", "temple", "mumbai", "delhi", "india gate", "taj mahal",
}


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
    type_lower = creative_type.lower()
    resolved_tier = tier.lower().replace("quality", "premium").replace("balanced", "standard")

    # ── 1. Color Psychology ────────────────────────────────────────────────────
    color_goal = _CREATIVE_TYPE_TO_COLOR_GOAL.get(type_lower)
    if not color_goal:
        # Scan prompt for goal signals
        for signal, goal in _CREATIVE_TYPE_TO_COLOR_GOAL.items():
            if signal in prompt_lower:
                color_goal = goal
                break
    if color_goal:
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
    if any(kw in prompt_lower for kw in _INDIA_KEYWORDS):
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
        self._model_name = "gemini-2.5-flash"
        self.enabled = USE_GEMINI_ENGINE

    def _call(self, system: str, user: str) -> str:
        """Single Gemini call — returns raw text."""
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=_GEMINI_KEY)
        resp = client.models.generate_content(
            model=self._model_name,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.95,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )
        return resp.text or ""

    # ── Stage A ───────────────────────────────────────────────────────────────

    def create_brief(
        self,
        raw_prompt: str,
        creative_type: str = "photo",
        style: str = "photo",
        extra_context: Optional[str] = None,
        bucket: str = "photorealism",
    ) -> Dict:
        """Stage A: raw prompt → Creative Brief JSON (bucket-specific system prompt)."""
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

        try:
            raw = self._call(system, user_msg)
            brief = _extract_json(raw)
            brief["_source"] = "gemini"
            brief["_bucket"] = bucket

            # Soft validation — log issues but don't fail
            issues = _validate_brief(brief)
            if issues:
                logger.warning("[gemini-engine] brief issues %s: %s", bucket, issues)

            logger.info("[gemini-engine] brief OK bucket=%s: %s",
                        bucket, brief.get("visual_concept", "")[:60])
            return brief

        except Exception as e:
            logger.warning("[gemini-engine] brief failed (%s), heuristic fallback", e)
            return self._heuristic_brief(raw_prompt)

    # ── Stage B ───────────────────────────────────────────────────────────────

    def build_params(
        self,
        brief: Dict,
        model_name: str = "Flux 2 Pro",
        capability_bucket: str = "photorealism",
        critic_notes: Optional[str] = None,
    ) -> Dict:
        """Stage B: Creative Brief → model-specific generation params JSON."""
        if not self.enabled or brief.get("_source") == "heuristic":
            return self._heuristic_params(brief, capability_bucket)

        brief_clean = {k: v for k, v in brief.items() if not k.startswith("_")}
        brief_str = json.dumps(brief_clean, indent=2)
        system = _resolve_params_system(model_name)

        user_msg = f"Creative Brief:\n{brief_str}\n\nTarget model: {model_name}"
        if critic_notes:
            user_msg += f"\n\nCritic refinements to incorporate:\n{critic_notes}"

        try:
            raw = self._call(system, user_msg)
            params = _extract_json(raw)
            params["_source"] = "gemini"

            # Validate
            issues = _validate_params(params, capability_bucket)
            if issues:
                logger.warning("[gemini-engine] params issues %s: %s", model_name, issues)

            logger.info("[gemini-engine] params OK model=%s", model_name)
            return params

        except Exception as e:
            logger.warning("[gemini-engine] params failed (%s), heuristic fallback", e)
            return self._heuristic_params(brief, capability_bucket)

    # ── Critic (hard buckets, premium/ultra only) ─────────────────────────────

    def run_critic(
        self,
        brief: Dict,
        params: Dict,
        bucket: str,
    ) -> Optional[str]:
        """
        Specialist critic agent for hard buckets.
        Returns critic_notes string to inject into Stage B re-run, or None if skipped/failed.
        """
        critic_system = _CRITIC_SYSTEM_BY_BUCKET.get(bucket)
        if not critic_system or not self.enabled:
            return None

        try:
            brief_clean = {k: v for k, v in brief.items() if not k.startswith("_")}
            user_msg = (
                f"Creative Brief:\n{json.dumps(brief_clean, indent=2)}\n\n"
                f"Generated prompt:\n{params.get('prompt', '')}\n\n"
                f"Negative prompt:\n{params.get('negative_prompt', '')}"
            )
            raw = self._call(critic_system, user_msg)
            critic = _extract_json(raw)

            issues = critic.get("issues", [])
            additions = critic.get("refined_prompt_additions", "")
            neg_additions = critic.get("refined_negative_additions", "")

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

    def enhance(
        self,
        raw_prompt: str,
        model_name: str = "Flux Pro",
        capability_bucket: str = "photorealism",
        creative_type: str = "photo",
        style: str = "photo",
        extra_context: Optional[str] = None,
        tier: str = "standard",
    ) -> Dict:
        """
        Full pipeline: brief → params → [critic → refined params] → validate → return.

        Critic runs only for hard buckets (anime, typography, editing,
        interior_arch, character_consistency) on premium or ultra tier.

        Returns:
          {
            "brief": dict,
            "prompt": str,
            "negative_prompt": str,
            "style_notes": str,
            "original_prompt": str,
            "engine": "gemini" | "heuristic",
            "critic_ran": bool,
          }
        """
        # ── Cognitive aesthetic hints (color psychology + imperfect + cultural) ──
        hints = _build_contextual_hints(raw_prompt, creative_type, capability_bucket, tier)
        if hints:
            extra_context = f"{extra_context} | {hints}".strip(" |") if extra_context else hints

        # Stage A — bucket-aware brief
        brief = self.create_brief(
            raw_prompt, creative_type, style, extra_context, bucket=capability_bucket
        )

        # Stage B — model-specific params (first pass)
        params = self.build_params(brief, model_name, capability_bucket)

        # Critic — hard buckets, premium/ultra only
        critic_ran = False
        resolved_tier = tier.lower().replace("quality", "premium")
        use_critic = (
            capability_bucket in _HARD_BUCKETS
            and resolved_tier in ("premium", "ultra")
            and self.enabled
            and brief.get("_source") == "gemini"
        )
        if use_critic:
            critic_notes = self.run_critic(brief, params, capability_bucket)
            if critic_notes:
                # Stage B2 — refined params with critic notes
                params = self.build_params(brief, model_name, capability_bucket, critic_notes)
                critic_ran = True

        # Merge bucket-specific negative
        final_negative = _resolve_negative(
            capability_bucket, params.get("negative_prompt", "")
        )

        engine_label = "gemini" if self.enabled and brief.get("_source") == "gemini" else "heuristic"

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
        parts = [brief.get("visual_concept") or brief.get("subject", "")]
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

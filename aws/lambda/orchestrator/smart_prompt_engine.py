"""
Smart Prompt Engine
====================
Takes a ClassificationResult from UniversalPromptClassifier and builds
the BEST possible positive + negative prompt for the diffusion pipeline.

Every image type gets tailored quality boosters, style tokens, lighting
directives, and anatomy guards — all chosen automatically.

The user never sees any of this.  They type "a cat on a rooftop at dusk"
and we turn it into a 300-token masterpiece prompt.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .universal_prompt_classifier import ClassificationResult


# ---------------------------------------------------------------------------
# Per-category quality boosters  (appended to every prompt of that type)
# ---------------------------------------------------------------------------

CATEGORY_BOOSTERS: Dict[str, List[str]] = {
    "portrait": [
        "sharp facial features", "professional lighting on face",
        "natural skin tone", "detailed eyes", "authentic expression",
        "high-resolution skin texture",
    ],
    "landscape": [
        "sweeping composition", "rich depth of field",
        "vibrant natural colors", "atmospheric perspective",
        "cinematic framing", "dramatic sky",
    ],
    "nature": [
        "vivid natural colors", "sharp detail on subject",
        "shallow depth of field", "bokeh background",
        "naturalistic lighting", "high dynamic range",
    ],
    "action": [
        "sharp focus on action", "dynamic composition",
        "motion blur where appropriate", "peak-moment capture",
        "dramatic angle", "high shutter speed feel",
    ],
    "product": [
        "clean background", "professional studio lighting",
        "sharp product detail", "attractive color grading",
        "commercial quality", "appealing composition",
    ],
    "fine_art": [
        "gallery-quality composition", "artistic depth",
        "emotionally resonant", "visually striking",
        "unique perspective", "masterful use of light and shadow",
    ],
    "illustration": [
        "clean linework", "vibrant colors", "polished finish",
        "professional grade", "detailed shading", "cohesive color palette",
    ],
    "technical": [
        "crisp clean lines", "accurate proportions",
        "clear labels", "professional layout", "precise details",
    ],
    "scientific": [
        "scientifically accurate", "high resolution",
        "clear detail", "proper magnification",
    ],
    "specialty": [
        "stunning visual effect", "technically perfect",
        "award-winning quality", "breathtaking detail",
    ],
    "graphics": [
        "seamless tiling", "clean edges",
        "rich detail", "vibrant colors", "high resolution",
    ],
    "entertainment": [
        "eye-catching", "visually engaging",
        "modern aesthetic", "trending style",
    ],
    "publishing": [
        "print-ready quality", "striking visual impact",
        "professional design", "high resolution",
    ],
    "historical_film": [
        "authentic period look", "warm film tone",
        "subtle grain texture", "natural color grading",
    ],
    "cultural": [
        "culturally authentic", "respectful representation",
        "vivid detail", "rich color",
    ],
    "ceremonial": [
        "vibrant celebration colors", "joyful atmosphere",
        "detailed cultural elements", "authentic setting",
    ],
    "education": [
        "clear and informative", "pedagogically sound",
        "engaging visual style", "accurate representation",
    ],
}

# ---------------------------------------------------------------------------
# Per-style prompt tokens
# ---------------------------------------------------------------------------

STYLE_TOKENS: Dict[str, List[str]] = {
    "photorealistic": ["photorealistic", "8K UHD", "DSLR quality", "sharp focus", "perfect exposure", "professional photography", "RAW photo"],
    "film_grain_vintage": ["vintage photograph", "film grain", "warm analog tone", "35mm film", "aged color palette", "nostalgic mood", "Kodachrome"],
    "watercolor": ["watercolor painting", "wet-on-wet technique", "soft flowing colors", "visible brush strokes", "translucent washes", "aquarelle style"],
    "oil_painting": ["oil on canvas", "rich impasto texture", "painterly brushwork", "deep saturated colors", "fine art oil painting", "gallery quality"],
    "minimal_flat": ["flat design", "minimal aesthetic", "clean geometric shapes", "vector-style", "limited color palette", "no shadows", "crisp edges"],
    "cyberpunk_neon": ["cyberpunk aesthetic", "neon-lit", "rain-soaked chrome", "holographic displays", "futuristic atmosphere", "electric color palette", "noir lighting"],
    "low_poly": ["low-poly 3D", "geometric faceted", "minimal polygon count", "stylized 3D render", "pastel geometric"],
    "cartoon": ["cel-shaded", "cartoon style", "bold outlines", "flat color fills", "exaggerated proportions", "playful character design"],
    "bw_high_contrast": ["black and white", "high contrast", "dramatic shadows", "noir aesthetic", "monochrome", "silver gelatin print look"],
    "surreal_dreamlike": ["surrealist", "dreamlike atmosphere", "impossible geometry", "ethereal glow", "otherworldly", "magical realism", "Salvador Dali inspired"],
    "pencil_sketch": ["pencil sketch", "graphite drawing", "hand-drawn look", "visible pencil strokes", "white paper background", "fine line detail"],
    "anime": ["anime style", "Japanese animation", "large expressive eyes", "vibrant colors", "dynamic poses", "detailed backgrounds"],
    "impressionist": ["impressionist painting", "visible brushstrokes", "soft focus", "light-filled", "Monet inspired", "plein air style"],
    "cubist": ["cubist style", "geometric fragmentation", "multiple viewpoints", "angular forms", "Picasso inspired"],
    "pop_art": ["pop art style", "bold primary colors", "comic-book influence", "repetitive imagery", "Andy Warhol inspired", "screen-print look"],
    "gothic": ["gothic aesthetic", "dark atmosphere", "dramatic shadows", "ornate details", "medieval darkness", "horror mood"],
    "renaissance": ["Renaissance style", "classical composition", "chiaroscuro lighting", "rich pigments", "old master technique", "sfumato"],
    "art_deco": ["Art Deco style", "geometric luxury", "gold accents", "symmetrical composition", "glamorous 1920s", "ornamental elegance"],
    "pixel_art": ["pixel art", "retro 8-bit style", "chunky pixels", "limited color palette", "game sprite quality"],
    "chibi": ["chibi style", "oversized head", "small body", "cute proportions", "kawaii aesthetic", "adorable character"],
}

# ---------------------------------------------------------------------------
# Per-medium quality tokens
# ---------------------------------------------------------------------------

MEDIUM_TOKENS: Dict[str, List[str]] = {
    "photograph": ["masterpiece", "award-winning photograph", "professional camera", "perfect composition", "stunning detail"],
    "painting": ["masterpiece painting", "museum quality", "rich textures", "expert brushwork", "fine art gallery piece"],
    "illustration": ["professional illustration", "polished digital art", "stunning artwork", "magazine-ready"],
    "3d_render": ["high-end 3D render", "ray-traced", "photorealistic CGI", "cinematic lighting", "detailed textures", "Unreal Engine quality"],
    "drawing": ["detailed hand drawing", "professional sketch", "fine linework", "expert draftsmanship"],
    "vector": ["crisp vector art", "clean scalable design", "precise paths", "professional vector illustration"],
    "diagram": ["clear technical diagram", "professional layout", "accurate annotations", "readable labels"],
    "scientific_image": ["high-resolution scientific image", "accurate representation", "detailed magnification"],
    "digital_pixel": ["pixel-perfect", "retro game aesthetic", "clean pixel boundaries"],
    "mixed": ["stunning mixed-media", "layered composition", "rich visual depth"],
}

# ---------------------------------------------------------------------------
# Negative prompt banks  (per-category additions on top of universal negatives)
# ---------------------------------------------------------------------------

UNIVERSAL_NEGATIVES = [
    "blurry", "low quality", "low resolution", "pixelated", "jpeg artifacts",
    "watermark", "signature", "text overlay", "ugly", "disfigured",
    "deformed", "distorted", "warped", "broken", "corrupted",
    "amateur", "unprofessional", "cheap", "tacky", "overexposed",
    "underexposed", "noisy", "grainy noise", "artifacts",
]

CATEGORY_NEGATIVES: Dict[str, List[str]] = {
    "portrait": [
        "bad anatomy", "extra limbs", "missing limbs", "extra fingers",
        "fewer than 5 fingers", "more than 5 fingers", "deformed hands",
        "malformed hands", "bad proportions", "gross proportions",
        "missing head", "head cut off", "face cut off", "extra heads",
        "merged bodies", "fused limbs", "extra arms", "extra legs",
        "bad face", "asymmetric face", "blurry face",
    ],
    "nature": [
        "unrealistic animal", "deformed creature", "extra limbs on animal",
        "wrong number of legs", "unnatural colors",
    ],
    "product": [
        "cluttered background", "distracting elements", "poor lighting",
        "reflections on product", "shadows on product",
    ],
    "fine_art": [
        "derivative", "generic", "cookie-cutter", "unoriginal",
    ],
    "illustration": [
        "inconsistent style", "mixed media clash", "sloppy linework",
        "uneven coloring", "poor composition",
    ],
    "technical": [
        "inaccurate labels", "overlapping text", "unclear diagram",
        "wrong proportions", "messy layout",
    ],
}

# ---------------------------------------------------------------------------
# Lighting directives per detected lighting type
# ---------------------------------------------------------------------------

LIGHTING_DIRECTIVES: Dict[str, List[str]] = {
    "golden_hour": ["golden hour lighting", "warm amber glow", "long shadows", "soft directional light"],
    "studio": ["studio lighting", "key light and fill light", "controlled environment", "clean background"],
    "natural": ["natural daylight", "soft even lighting", "realistic shadows"],
    "night": ["nighttime atmosphere", "moonlit", "artificial light sources", "deep shadows", "dramatic contrast"],
    "dramatic": ["dramatic lighting", "high contrast", "deep shadows", "single light source", "cinematic mood"],
    "soft": ["soft diffused light", "even illumination", "minimal harsh shadows", "gentle tones"],
    "neon": ["neon-lit environment", "colorful light reflections", "glow effects", "vibrant illumination"],
}

# ---------------------------------------------------------------------------
# Color palette directives
# ---------------------------------------------------------------------------

COLOR_DIRECTIVES: Dict[str, List[str]] = {
    "monochrome": ["monochrome color grading", "silver tones", "classical black and white"],
    "warm": ["warm color temperature", "amber and golden tones", "rich browns and oranges"],
    "cool": ["cool color temperature", "blue and teal tones", "crisp cold palette"],
    "vibrant": ["vibrant saturated colors", "punchy palette", "eye-catching hues"],
    "muted": ["muted desaturated palette", "soft pastel tones", "understated colors"],
    "duotone": ["duotone color treatment", "two dominant colors", "stylized palette"],
    "natural": ["natural color palette", "true-to-life tones", "balanced saturation"],
}

# ---------------------------------------------------------------------------
# People / anatomy guard tokens  (added whenever people are in the scene)
# ---------------------------------------------------------------------------

PEOPLE_GUARDS: Dict[int, List[str]] = {
    1: [
        "single person clearly visible", "complete human figure",
        "head fully visible and unobscured", "correct human anatomy",
        "anatomically correct hands with five fingers",
        "natural human proportions",
    ],
    2: [
        "exactly two distinct people", "both figures complete and separate",
        "both heads fully visible", "no merged or fused bodies",
        "proper spacing between individuals",
        "anatomically correct hands with five fingers each",
    ],
}

PEOPLE_GUARDS_MULTI = [
    "each person has a fully visible head",
    "all people are distinct separate individuals",
    "no merged bodies or shared limbs",
    "anatomically correct hands with five fingers each",
    "proper spacing between all people",
    "every figure has correct human proportions",
    "all faces are clearly visible and unobscured",
]

PEOPLE_NEGATIVES_EXTRA = [
    "extra people", "missing people", "merged bodies", "fused figures",
    "shared limbs", "bodies overlapping incorrectly", "missing heads",
    "heads cut off", "occluded faces", "wrong number of people",
    "conjoined figures", "body horror",
]


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class SmartPromptEngine:
    """
    Builds production-quality prompts from ClassificationResult.

    Usage:
        from .universal_prompt_classifier import UniversalPromptClassifier

        classifier = UniversalPromptClassifier()
        engine     = SmartPromptEngine()

        classification = classifier.classify(user_prompt)
        positive, negative = engine.build_prompts(classification)
    """

    def build_prompts(self, result: ClassificationResult) -> Tuple[str, str]:
        """
        Return (positive_prompt, negative_prompt) ready for the pipeline.
        """
        positive = self._build_positive(result)
        negative = self._build_negative(result)
        return positive, negative

    def recommend_loras(self, classification_result: ClassificationResult) -> List[str]:
        """
        Auto-LoRA selection based on prompt category. Returns up to 3 LoRA names
        to apply (e.g. for SageMaker / two-pass pipeline).

        Rules:
        - If category contains "portrait" or has_people: add "skin_realism_v2"
        - If style is "cinematic" or medium is "photograph": add "cinematic_lighting_v3"
        - Always add "color_harmony_v1" for coherence

        Order: color_harmony_v1 first, then skin_realism_v2 (if applicable), then cinematic_lighting_v3 (if applicable).
        """
        out: List[str] = []
        r = classification_result
        category_lower = (r.category or "").lower()
        style_lower = (r.style or "").lower()
        medium_lower = (r.medium or "").lower()

        # Always add color harmony for coherence (max 3 total)
        out.append("color_harmony_v1")

        if "portrait" in category_lower or r.has_people:
            if "skin_realism_v2" not in out:
                out.append("skin_realism_v2")

        if style_lower == "cinematic" or medium_lower == "photograph":
            if "cinematic_lighting_v3" not in out:
                out.append("cinematic_lighting_v3")

        return out[:3]

    # ------------------------------------------------------------------
    # Positive prompt assembly
    # ------------------------------------------------------------------

    def _build_positive(self, r: ClassificationResult) -> str:
        parts: List[str] = []

        # 1. Original user prompt (always first — highest priority)
        parts.append(r.raw_prompt)

        # 2. Style tokens
        parts.extend(STYLE_TOKENS.get(r.style, STYLE_TOKENS["photorealistic"]))

        # 3. Medium tokens
        parts.extend(MEDIUM_TOKENS.get(r.medium, MEDIUM_TOKENS["photograph"]))

        # 4. Category boosters
        parts.extend(CATEGORY_BOOSTERS.get(r.category, []))

        # 5. Lighting directives
        parts.extend(LIGHTING_DIRECTIVES.get(r.lighting, LIGHTING_DIRECTIVES["natural"]))

        # 6. Color palette directives
        parts.extend(COLOR_DIRECTIVES.get(r.color_palette, []))

        # 7. People / anatomy guards
        if r.has_people and r.person_count > 0:
            if r.person_count in PEOPLE_GUARDS:
                parts.extend(PEOPLE_GUARDS[r.person_count])
            else:
                parts.append(f"exactly {r.person_count} people in the scene")
                parts.extend(PEOPLE_GUARDS_MULTI)

        # 8. Special flags
        if r.has_fantasy:
            parts.extend(["magical atmosphere", "ethereal glow", "fantasy world detail"])
        if r.has_weather:
            parts.extend(["realistic weather effects", "atmospheric particles visible"])
        if r.has_animals:
            parts.extend(["detailed and realistic animal", "natural animal pose"])
        if r.has_text:
            # Text rendering is handled by TypographyEngine post-generation
            parts.append("placeholder for text area, clean space for text")
        if r.has_architecture:
            parts.extend(["architectural detail", "structurally accurate", "realistic building materials"])

        # Deduplicate while preserving order
        seen = set()
        deduped: List[str] = []
        for p in parts:
            key = p.lower().strip()
            if key not in seen and key:
                seen.add(key)
                deduped.append(p)

        return ", ".join(deduped)

    # ------------------------------------------------------------------
    # Negative prompt assembly
    # ------------------------------------------------------------------

    def _build_negative(self, r: ClassificationResult) -> str:
        negatives: List[str] = list(UNIVERSAL_NEGATIVES)

        # Category-specific negatives
        negatives.extend(CATEGORY_NEGATIVES.get(r.category, []))

        # People negatives (always include anatomy guards when people present)
        if r.has_people:
            negatives.extend(PEOPLE_NEGATIVES_EXTRA)
            if r.person_count > 0:
                negatives.append(f"not exactly {r.person_count} people")

        # Style-specific negatives
        if r.style == "photorealistic":
            negatives.extend(["painterly", "illustrated", "cartoon", "CGI look"])
        elif r.style in ("watercolor", "oil_painting", "impressionist"):
            negatives.extend(["photographic", "digital render", "flat colors"])
        elif r.style == "cartoon":
            negatives.extend(["realistic", "photographic", "detailed shading"])
        elif r.style == "pixel_art":
            negatives.extend(["smooth", "anti-aliased", "high resolution textures"])
        elif r.style == "bw_high_contrast":
            negatives.extend(["color", "colored", "saturated"])

        # Medium-specific negatives
        if r.medium == "3d_render":
            negatives.extend(["flat", "2D look", "painted look", "photographic"])
        if r.medium == "vector":
            negatives.extend(["gradient blends", "raster", "photographic detail"])

        # Deduplicate
        seen = set()
        deduped: List[str] = []
        for n in negatives:
            key = n.lower().strip()
            if key not in seen and key:
                seen.add(key)
                deduped.append(n)

        return ", ".join(deduped)

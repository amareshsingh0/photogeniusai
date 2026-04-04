"""
Central Configuration — Single source of truth for the entire smart pipeline.

WHY THIS FILE EXISTS:
  Adding a new style (e.g., "gaming") should require editing ONE file — this one.
  All modules import from here instead of defining their own magic numbers.

STRUCTURE:
  TYPOGRAPHY  — Font sizes, hierarchy ratios, rendering params
  ROLE_COLORS — Per-style text color selection
  FONT_PRIORITY — Per-style font fallback chains
  STYLES      — Unified style registry (effects, design keywords, negatives, flags)
  THEMES      — Creative Director theme definitions (keywords → objects/colors/atmosphere)

MATH:
  All divisors/multipliers are named constants with comments explaining
  the visual math behind them. No unnamed 0.12 or size//8 anywhere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, TypedDict

# ══════════════════════════════════════════════════════════════════════════════
# Paths
# ══════════════════════════════════════════════════════════════════════════════
FONTS_DIR = Path(__file__).parent / "fonts"


# ══════════════════════════════════════════════════════════════════════════════
# Typography Constants
# ══════════════════════════════════════════════════════════════════════════════

class TypographyConfig(TypedDict):
    # Base headline = this fraction of image width. 0.12 = ~123px on 1024.
    headline_size_ratio: float
    min_font_size: int           # Absolute floor (px)
    max_width_ratio: float       # Text block max = this × image width
    shrink_step: int             # Px step when shrinking to fit

    # Hierarchy: multiplier on headline size per role
    hierarchy_headline: float    # 1.0 = full size
    hierarchy_subtitle: float    # 0.60 = 60% of headline
    hierarchy_cta: float         # 0.50 = 50% of headline

    # Max text block height as fraction of image height
    max_height_headline: float   # 0.20 = 20% of image
    max_height_other: float      # 0.12 = 12% of image

    # Shadow layer: offset = max(4, size / offset_divisor)
    shadow_offset_divisor: int   # 8 → ~15px at 123px
    shadow_blur_divisor: int     # 6 → ~20px at 123px
    shadow_alpha: int            # 180 (0-255)

    # Glow layer: radius = max(8, size / glow_radius_divisor)
    glow_radius_divisor: int     # 4 → ~31px at 123px
    glow_alpha_poster: int       # 140 for poster styles
    glow_alpha_normal: int       # 100 for other styles
    glow_extra_stroke: int       # 3px added to stroke for glow spread

    # Stroke: width = max(min, size / divisor)
    stroke_divisor_poster: int   # 14 → ~9px at 123px (bold poster)
    stroke_divisor_normal: int   # 20 → ~6px at 123px (clean other)
    stroke_min_poster: int       # 3px minimum
    stroke_min_normal: int       # 2px minimum

    # Vertical positioning (fraction of image height)
    position_top_margin: float   # 0.05 = 5% from top
    position_bottom_anchor: float  # 0.92 = stack bottom ends at 92%

    # Spacing between stacked text items = max(8, headline_size / spacing_divisor)
    spacing_divisor: int         # 8


TYPOGRAPHY: TypographyConfig = {
    "headline_size_ratio": 0.12,
    "min_font_size": 36,
    "max_width_ratio": 0.90,
    "shrink_step": 2,

    "hierarchy_headline": 1.0,
    "hierarchy_subtitle": 0.60,
    "hierarchy_cta": 0.50,

    "max_height_headline": 0.20,
    "max_height_other": 0.12,

    "shadow_offset_divisor": 8,
    "shadow_blur_divisor": 6,
    "shadow_alpha": 180,

    "glow_radius_divisor": 4,
    "glow_alpha_poster": 140,
    "glow_alpha_normal": 100,
    "glow_extra_stroke": 3,

    "stroke_divisor_poster": 14,
    "stroke_divisor_normal": 20,
    "stroke_min_poster": 3,
    "stroke_min_normal": 2,

    "position_top_margin": 0.05,
    "position_bottom_anchor": 0.92,

    "spacing_divisor": 8,
}

# Helper: hierarchy ratio lookup
HIERARCHY_RATIOS: Dict[str, float] = {
    "headline": TYPOGRAPHY["hierarchy_headline"],
    "subtitle": TYPOGRAPHY["hierarchy_subtitle"],
    "cta": TYPOGRAPHY["hierarchy_cta"],
}


# ══════════════════════════════════════════════════════════════════════════════
# Role Colors — per-style text color by role and background luminance
# Format: (fill_color, stroke_color)
# ══════════════════════════════════════════════════════════════════════════════

# WCAG luminance threshold (sRGB linearized)
LUMINANCE_THRESHOLD = 0.179

# Colors for poster/marketing/banner/social styles
_POSTER_ROLE_COLORS: Dict[str, Dict[str, tuple]] = {
    "headline": {"light_bg": ("white", "#222222"), "dark_bg": ("white", "black")},
    "subtitle": {"light_bg": ("#FF6B00", "black"), "dark_bg": ("#FFD700", "black")},
    "cta":      {"light_bg": ("#FF1744", "white"), "dark_bg": ("#00E5FF", "black")},
}

# Colors for non-poster styles (clean WCAG)
_CLEAN_ROLE_COLORS: Dict[str, tuple] = {
    "light_bg": ("white", "#222222"),
    "dark_bg": ("white", "black"),
}

# Which styles use vibrant poster colors vs clean WCAG
VIBRANT_COLOR_STYLES = {"poster", "marketing", "banner", "social"}


# ══════════════════════════════════════════════════════════════════════════════
# Unified Style Registry
# Each style is ONE dict. Adding a new style = adding ONE entry here.
# ══════════════════════════════════════════════════════════════════════════════

class StyleDef(TypedDict, total=False):
    # Text overlay flags
    uppercase: bool              # Force UPPERCASE text
    poster_mode: bool            # Word-per-line for ≤4 word headlines

    # Design effects (all 0.0-2.0 range)
    color_boost: float
    contrast: float
    sharpness: float
    vignette: float
    warmth: float
    grain: float

    # Prompt assembly
    design_elements: str         # Injected into enhanced prompt
    negative_prompt: str         # Style-specific negatives

    # Layout planner defaults
    bg_default: str              # Default background style
    copy_space_default: str      # Default copy space position

    # Font priority (list of font filenames or system paths)
    fonts: List[str]


STYLES: Dict[str, StyleDef] = {
    "poster": {
        "uppercase": True,
        "poster_mode": True,
        "color_boost": 1.15,
        "contrast": 1.08,
        "sharpness": 1.3,
        "vignette": 0.15,
        "warmth": 0.0,
        "grain": 0.0,
        "design_elements": (
            "vibrant gradient background, smooth abstract shapes, "
            "dynamic lighting, glossy surfaces, bold visual hierarchy, "
            "professional graphic design, eye-catching color palette"
        ),
        "negative_prompt": "photo frame, border, margin, flat design, dull colors, amateur layout",
        "bg_default": "gradient",
        "copy_space_default": "top",
        "fonts": [
            str(FONTS_DIR / "BebasNeue-Regular.ttf"),
            str(FONTS_DIR / "Anton-Regular.ttf"),
            str(FONTS_DIR / "Montserrat-Black.ttf"),
            "C:/Windows/Fonts/impact.ttf",
        ],
    },
    "marketing": {
        "uppercase": True,
        "poster_mode": True,
        "color_boost": 1.15,
        "contrast": 1.08,
        "sharpness": 1.3,
        "vignette": 0.15,
        "warmth": 0.0,
        "grain": 0.0,
        "design_elements": (
            "vibrant gradient background, smooth abstract shapes, "
            "dynamic lighting, glossy surfaces, bold visual hierarchy, "
            "professional graphic design, eye-catching color palette"
        ),
        "negative_prompt": "photo frame, border, margin, flat design, dull colors, amateur layout",
        "bg_default": "gradient",
        "copy_space_default": "top",
        "fonts": [
            str(FONTS_DIR / "BebasNeue-Regular.ttf"),
            str(FONTS_DIR / "Anton-Regular.ttf"),
            str(FONTS_DIR / "Montserrat-Black.ttf"),
        ],
    },
    "editorial": {
        "uppercase": False,
        "poster_mode": False,
        "color_boost": 1.05,
        "contrast": 1.05,
        "sharpness": 1.2,
        "vignette": 0.2,
        "warmth": 0.0,
        "grain": 0.3,
        "design_elements": (
            "elegant minimalist design, refined color palette, "
            "sophisticated layout, editorial quality, magazine-grade finish"
        ),
        "negative_prompt": "amateur, snapshot, poor composition, oversaturated, garish",
        "bg_default": "minimal",
        "copy_space_default": "bottom",
        "fonts": [
            "C:/Windows/Fonts/impact.ttf",
            str(FONTS_DIR / "BebasNeue-Regular.ttf"),
            str(FONTS_DIR / "Montserrat-Bold.ttf"),
        ],
    },
    "cinematic": {
        "uppercase": False,
        "poster_mode": False,
        "color_boost": 1.1,
        "contrast": 1.12,
        "sharpness": 1.15,
        "vignette": 0.3,
        "warmth": 0.4,
        "grain": 0.4,
        "design_elements": (
            "dramatic volumetric lighting, cinematic color grading, "
            "atmospheric depth, film-quality production design"
        ),
        "negative_prompt": "flat lighting, amateur, TV quality, low production value",
        "bg_default": "complex",
        "copy_space_default": "bottom",
        "fonts": [
            str(FONTS_DIR / "Montserrat-Bold.ttf"),
            str(FONTS_DIR / "BebasNeue-Regular.ttf"),
            "C:/Windows/Fonts/arialbd.ttf",
        ],
    },
    "product": {
        "uppercase": False,
        "poster_mode": False,
        "color_boost": 1.0,
        "contrast": 1.03,
        "sharpness": 1.4,
        "vignette": 0.0,
        "warmth": 0.0,
        "grain": 0.0,
        "design_elements": (
            "clean studio backdrop, soft product lighting, "
            "pristine reflective surface, professional packshot quality"
        ),
        "negative_prompt": "background clutter, shadows on product, reflections, fingerprints",
        "bg_default": "solid",
        "copy_space_default": "bottom",
        "fonts": [
            str(FONTS_DIR / "Montserrat-Bold.ttf"),
            str(FONTS_DIR / "Montserrat-Black.ttf"),
        ],
    },
    "social": {
        "uppercase": True,
        "poster_mode": False,
        "color_boost": 1.2,
        "contrast": 1.06,
        "sharpness": 1.2,
        "vignette": 0.1,
        "warmth": 0.2,
        "grain": 0.0,
        "design_elements": (
            "trendy vibrant colors, Instagram-worthy aesthetic, "
            "modern graphic elements, eye-catching visual design"
        ),
        "negative_prompt": "corporate, boring, stock photo, generic, low effort",
        "bg_default": "photo",
        "copy_space_default": "top",
        "fonts": [
            str(FONTS_DIR / "Montserrat-Black.ttf"),
            str(FONTS_DIR / "BebasNeue-Regular.ttf"),
            str(FONTS_DIR / "Anton-Regular.ttf"),
        ],
    },
    "banner": {
        "uppercase": True,
        "poster_mode": True,
        "color_boost": 1.12,
        "contrast": 1.05,
        "sharpness": 1.25,
        "vignette": 0.0,
        "warmth": 0.0,
        "grain": 0.0,
        "design_elements": (
            "wide panoramic layout, bold gradient sweep, "
            "dynamic geometric shapes, professional banner design"
        ),
        "negative_prompt": "cramped layout, tiny elements, poor scaling",
        "bg_default": "gradient",
        "copy_space_default": "left",
        "fonts": [
            str(FONTS_DIR / "BebasNeue-Regular.ttf"),
            str(FONTS_DIR / "Montserrat-Black.ttf"),
            str(FONTS_DIR / "Anton-Regular.ttf"),
        ],
    },
    "photo": {
        "uppercase": False,
        "poster_mode": False,
        "color_boost": 1.05,
        "contrast": 1.04,
        "sharpness": 1.15,
        "vignette": 0.1,
        "warmth": 0.1,
        "grain": 0.0,
        "design_elements": "",
        "negative_prompt": "artificial, fake, plastic skin, oversaturated",
        "bg_default": "photo",
        "copy_space_default": "none",
        "fonts": [
            str(FONTS_DIR / "Montserrat-Bold.ttf"),
            str(FONTS_DIR / "Montserrat-Black.ttf"),
        ],
    },
}

# Fallback style for unknown style names
DEFAULT_STYLE = "photo"

# Font fallback chain (appended after style-specific fonts)
FONT_FALLBACK_CHAIN: List[str] = [
    str(FONTS_DIR / "BebasNeue-Regular.ttf"),
    str(FONTS_DIR / "Anton-Regular.ttf"),
    str(FONTS_DIR / "Montserrat-Bold.ttf"),
    str(FONTS_DIR / "Montserrat-Black.ttf"),
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


# ══════════════════════════════════════════════════════════════════════════════
# Background Prompt Hints
# ══════════════════════════════════════════════════════════════════════════════

BG_PROMPT_HINTS: Dict[str, str] = {
    "gradient": "smooth vibrant gradient background, professional color transition",
    "solid": "clean solid color background, studio backdrop",
    "minimal": "minimal uncluttered background, negative space",
    "photo": "",
    "complex": "detailed rich environment, atmospheric depth",
}

COPY_SPACE_HINTS: Dict[str, str] = {
    "top": "with ample empty space at the top for headline, clean upper third",
    "bottom": "with ample empty space at the bottom for text, clean lower third",
    "center": "with large empty central area for text, subject pushed to edges",
    "left": "with empty space on the left side for text, subject on right",
    "right": "with empty space on the right side for text, subject on left",
}

# Universal quality polish appended to every prompt
QUALITY_POLISH = "masterful quality, professional finish, sharp details"

# Text framing trick
TEXT_FRAMING = "decorative framing elements around the edges, clean center composition"


# ══════════════════════════════════════════════════════════════════════════════
# Creative Director Themes
# ══════════════════════════════════════════════════════════════════════════════

class ThemeDef(TypedDict):
    keywords: List[str]
    label: str
    objects: List[str]
    colors: List[str]
    atmosphere: str


THEMES: Dict[str, ThemeDef] = {
    "summer_beach": {
        "keywords": ["summer", "beach", "tropical", "vacation", "surf", "ocean", "sea", "pool", "swimwear"],
        "label": "Summer Beach",
        "objects": ["palm leaves", "sunglasses", "tropical flowers", "sand texture", "seashells", "ocean waves"],
        "colors": ["vibrant orange", "turquoise", "sunny yellow", "coral pink", "sky blue"],
        "atmosphere": "high-energy vibrant tropical warmth, sun-kissed glow",
    },
    "winter_holiday": {
        "keywords": ["winter", "christmas", "holiday", "snow", "xmas", "new year", "festive"],
        "label": "Winter Holiday",
        "objects": ["snowflakes", "pine branches", "ornaments", "fairy lights", "gift ribbons"],
        "colors": ["deep red", "forest green", "gold", "silver", "icy blue"],
        "atmosphere": "cozy festive warmth, sparkling holiday magic",
    },
    "luxury": {
        "keywords": ["luxury", "premium", "elegant", "exclusive", "high-end", "vip", "gold", "diamond"],
        "label": "Luxury",
        "objects": ["gold accents", "marble texture", "crystal reflections", "silk fabric draping"],
        "colors": ["black", "gold", "champagne", "deep burgundy", "ivory"],
        "atmosphere": "opulent sophistication, rich textures, premium finish",
    },
    "tech": {
        "keywords": ["tech", "digital", "cyber", "futuristic", "neon", "gaming", "ai", "robot", "code"],
        "label": "Technology",
        "objects": ["circuit patterns", "holographic elements", "geometric grids", "data streams", "glowing particles"],
        "colors": ["electric blue", "neon purple", "cyber green", "deep black", "white glow"],
        "atmosphere": "futuristic high-tech energy, digital precision, neon glow",
    },
    "nature": {
        "keywords": ["nature", "forest", "mountain", "garden", "flower", "plant", "botanical", "green", "organic"],
        "label": "Nature",
        "objects": ["leaves", "wildflowers", "vines", "moss", "butterflies", "dew drops"],
        "colors": ["forest green", "earth brown", "soft cream", "wildflower purple", "sky blue"],
        "atmosphere": "fresh natural serenity, organic textures, earthy warmth",
    },
    "food": {
        "keywords": ["food", "restaurant", "chef", "cooking", "recipe", "meal", "cuisine", "dish", "cafe", "bakery"],
        "label": "Food & Culinary",
        "objects": ["fresh herbs", "steam wisps", "wooden cutting board", "ceramic plates", "spice scatter"],
        "colors": ["warm amber", "rich brown", "fresh green", "cream white", "tomato red"],
        "atmosphere": "appetizing warmth, rustic culinary charm, aromatic ambiance",
    },
    "fashion": {
        "keywords": ["fashion", "style", "outfit", "couture", "runway", "model", "vogue", "trend", "clothing"],
        "label": "Fashion",
        "objects": ["fabric swirls", "sparkle accents", "abstract shapes", "geometric frames"],
        "colors": ["blush pink", "ivory", "charcoal", "metallic gold", "deep navy"],
        "atmosphere": "editorial chic, high-fashion sophistication, runway glamour",
    },
    "fitness": {
        "keywords": ["fitness", "gym", "workout", "sport", "athletic", "exercise", "training", "muscle", "yoga"],
        "label": "Fitness",
        "objects": ["dynamic motion lines", "energy bursts", "sweat droplets", "geometric shapes"],
        "colors": ["electric red", "power orange", "steel grey", "black", "neon green"],
        "atmosphere": "explosive energy, raw power, athletic intensity",
    },
    "music": {
        "keywords": ["music", "concert", "dj", "band", "album", "song", "festival", "party", "dance", "club"],
        "label": "Music & Entertainment",
        "objects": ["sound waves", "music notes", "neon lights", "smoke effects", "spotlight beams"],
        "colors": ["neon pink", "electric purple", "deep black", "gold sparkle", "laser green"],
        "atmosphere": "pulsating nightlife energy, concert stage vibes, electrifying",
    },
    "corporate": {
        "keywords": ["business", "corporate", "office", "professional", "company", "startup", "meeting"],
        "label": "Corporate",
        "objects": ["clean geometric lines", "subtle gradients", "abstract network nodes"],
        "colors": ["navy blue", "white", "light grey", "subtle teal", "corporate blue"],
        "atmosphere": "clean professional confidence, trustworthy, modern corporate",
    },
    "romantic": {
        "keywords": ["love", "romance", "valentine", "wedding", "couple", "heart", "romantic", "date"],
        "label": "Romantic",
        "objects": ["rose petals", "soft bokeh lights", "heart shapes", "silk ribbons", "candle glow"],
        "colors": ["blush pink", "deep red", "soft white", "rose gold", "champagne"],
        "atmosphere": "intimate warmth, dreamy soft-focus romance, tender elegance",
    },
    "horror": {
        "keywords": ["horror", "scary", "dark", "spooky", "halloween", "creepy", "ghost", "zombie", "thriller"],
        "label": "Horror",
        "objects": ["fog tendrils", "cracked textures", "cobwebs", "bare branches", "flickering light"],
        "colors": ["blood red", "pitch black", "sickly green", "bone white", "dark purple"],
        "atmosphere": "ominous dread, eerie shadows, unsettling tension",
    },
    "retro": {
        "keywords": ["retro", "vintage", "80s", "90s", "nostalgic", "old school", "classic", "throwback"],
        "label": "Retro/Vintage",
        "objects": ["halftone dots", "VHS scan lines", "cassette tapes", "retro shapes", "film grain"],
        "colors": ["pastel pink", "mint green", "warm yellow", "faded orange", "cream"],
        "atmosphere": "nostalgic warmth, retro-futuristic charm, analog texture",
    },
    "minimalist": {
        "keywords": ["minimal", "minimalist", "clean", "simple", "zen", "modern", "white space"],
        "label": "Minimalist",
        "objects": ["single accent element", "thin geometric lines", "subtle shadow"],
        "colors": ["white", "black", "soft grey", "single accent color"],
        "atmosphere": "serene simplicity, intentional emptiness, refined clarity",
    },
    "sale_promo": {
        "keywords": ["sale", "discount", "offer", "deal", "promo", "clearance", "% off", "buy", "shop", "price"],
        "label": "Sale & Promotion",
        "objects": ["burst shapes", "ribbons", "price tags", "confetti", "shopping bags", "star bursts"],
        "colors": ["bold red", "bright yellow", "hot pink", "electric blue", "white"],
        "atmosphere": "urgent excitement, eye-catching commercial energy, deal-driven",
    },
}

DEFAULT_THEME: ThemeDef = {
    "keywords": [],
    "label": "General",
    "objects": ["subtle gradient elements", "soft abstract shapes"],
    "colors": ["harmonious tones", "balanced palette"],
    "atmosphere": "professional quality, visually appealing, well-composed",
}


# ══════════════════════════════════════════════════════════════════════════════
# Helper: get style config with fallback
# ══════════════════════════════════════════════════════════════════════════════

def get_style(name: str) -> StyleDef:
    """Get style config, falling back to DEFAULT_STYLE if unknown."""
    return STYLES.get(name, STYLES[DEFAULT_STYLE])


def get_effect_preset(style_name: str) -> Dict[str, float]:
    """Extract just the effect values from a style (for DesignEffects)."""
    s = get_style(style_name)
    return {
        k: s.get(k, 0.0)
        for k in ("color_boost", "contrast", "sharpness", "vignette", "warmth", "grain")
    }


# ══════════════════════════════════════════════════════════════════════════════
# Brand Guidelines — configurable per-brand color/tone/font rules
# ══════════════════════════════════════════════════════════════════════════════

class BrandGuidelines(TypedDict, total=False):
    name: str                        # Brand name
    primary_colors: List[str]        # Hex colors e.g. ["#FF6B00", "#1A1A2E"]
    secondary_colors: List[str]      # Accent colors
    forbidden_colors: List[str]      # Colors that must NOT appear
    fonts: List[str]                 # Preferred font names
    tone: str                        # "professional" | "playful" | "luxury" | "casual" | "bold"
    restrictions: List[str]          # Free-text rules e.g. ["no red text on white"]
    min_contrast_ratio: float        # WCAG minimum (default 4.5 for AA)
    logo_safe_zone: float            # Fraction of image reserved for logo (0.0-0.2)


# Default brand (used when no brand is specified)
DEFAULT_BRAND: BrandGuidelines = {
    "name": "PhotoGenius",
    "primary_colors": ["#6366F1", "#8B5CF6"],    # Indigo/violet
    "secondary_colors": ["#F59E0B", "#10B981"],   # Amber/emerald accents
    "forbidden_colors": [],
    "fonts": [],
    "tone": "professional",
    "restrictions": [],
    "min_contrast_ratio": 4.5,
    "logo_safe_zone": 0.0,
}

# Brand registry — add custom brands here
BRAND_REGISTRY: Dict[str, BrandGuidelines] = {
    "default": DEFAULT_BRAND,
}


def get_brand(name: str = "default") -> BrandGuidelines:
    """Get brand guidelines, falling back to default."""
    return BRAND_REGISTRY.get(name, DEFAULT_BRAND)


# ══════════════════════════════════════════════════════════════════════════════
# Capability Routing — keyword → bucket → model (updated monthly)
# ══════════════════════════════════════════════════════════════════════════════
#
# HOW TO UPDATE:
#   1. Run monthly benchmark (same 10 prompts across all models)
#   2. Update BUCKET_MODEL_MAP with new winners
#   3. Never touch BUCKET_KEYWORDS — those are intent signals, not model names
#
# BUCKETS (capability-first, model-agnostic):
#   photorealism        → real photo, product, portrait, skin, 8k
#   typography          → text in image, logo, poster with words, banner headline
#   artistic            → art, painting, illustration, cinematic vibe, fantasy
#   character_consistency → same person, consistent face, reference character
#   vector              → svg, icon, logo, flat design, scalable
#   interior_arch       → room, interior, building, architectural render
#   editing             → fix, edit, replace, remove, inpaint
#   fast                → draft, preview, quick, thumbnail
# ──────────────────────────────────────────────────────────────────────────────

BUCKET_KEYWORDS: Dict[str, List[str]] = {
    "typography": [
        # Direct text/design intent
        "text", "quote", "write", "written", "headline", "title", "caption",
        "font", "logo", "wordmark", "label", "sign saying", "reads", "says",
        "slogan", "tagline", "typography",
        # Poster / Banner / Ad formats
        "poster", "banner", "flyer", "hoarding", "billboard", "brochure",
        "ad creative", "advertisement", "social media post", "instagram post",
        "facebook ad", "google ad", "marketing creative", "promotional",
        "infographic", "thumbnail design",
        # SaaS / Tech / Business design
        "saas", "software ad", "app ad", "tech poster", "product launch",
        "landing page banner", "cta", "call to action",
        # Festival / Occasion ads
        "festival ad", "sale poster", "discount banner", "offer poster",
        "event poster", "invitation design", "greeting card",
    ],
    "vector": [
        "vector", "svg", "icon", "flat design", "scalable", "illustration flat",
        "line art", "minimal logo", "badge", "emblem",
    ],
    "character_consistency": [
        "same person", "same character", "consistent face", "reference face",
        "character sheet", "same model", "portrait series",
    ],
    "editing": [
        "remove", "replace", "fix", "edit", "change background", "inpaint",
        "fill", "extend", "outpaint", "generative fill",
    ],
    "anime": [
        "anime", "manga", "chibi", "waifu", "shonen", "shojo",
        "japanese animation", "anime style", "cartoon anime",
    ],
    "artistic": [
        "painting", "illustration", "artwork", "cartoon",
        "comic", "watercolor", "oil painting", "sketch", "concept art",
        "fantasy", "surreal", "abstract", "vibe", "aesthetic",
        "cinematic feel", "mood", "atmospheric",
    ],
    "interior_arch": [
        "interior", "room", "bedroom", "living room", "kitchen", "bathroom",
        "office design", "architecture", "building", "facade", "render",
        "3d visualization", "floor plan",
    ],
    "fast": [
        "quick", "draft", "preview", "thumbnail", "rough", "sketch quickly",
        "fast", "low quality ok",
    ],
    # photorealism is the DEFAULT bucket (no keywords needed — catch-all)
    "photorealism": [],
}

# ── Model mapping per bucket per tier ─────────────────────────────────────────
# Format: { bucket: { tier: { "model": fal_model_key, "backend": "fal"|"ideogram"|"replicate" } } }
# Update ONLY this section when model rankings change.

BUCKET_MODEL_MAP: Dict[str, Dict[str, Dict]] = {
    # ── Photorealism / Portrait / Product ─────────────────────────────────────
    # Jury ONLY in ultra. ESRGAN applied in backend for standard/premium/ultra.
    "photorealism": {
        "fast":     {"model": "flux_schnell",  "provider": "multi"},
        "standard": {"model": "flux_2_pro",    "provider": "multi"},
        "premium":  {"model": "flux_2_max",    "provider": "multi"},
        "ultra":    {"model": "flux_2_max",    "provider": "multi", "num_images": 3},
    },
    # ── Typography / Text in image / Posters ──────────────────────────────────
    # Ideogram v3: undisputed best for readable text. rendering_speed controls cost.
    "typography": {
        "fast":     {"model": "ideogram_turbo",   "provider": "multi"},
        "standard": {"model": "ideogram_turbo",   "provider": "multi"},
        "premium":  {"model": "ideogram_quality", "provider": "multi"},
        "ultra":    {"model": "ideogram_quality", "provider": "multi", "num_images": 2},
    },
    # ── Artistic / Cinematic / Creative ───────────────────────────────────────
    "artistic": {
        "fast":     {"model": "flux_schnell",  "provider": "multi"},
        "standard": {"model": "flux_2_dev",    "provider": "multi"},
        "premium":  {"model": "flux_2_max",    "provider": "multi"},
        "ultra":    {"model": "flux_2_max",    "provider": "multi", "num_images": 3},
    },
    # ── Anime / Manga / Asian art ─────────────────────────────────────────────
    "anime": {
        "fast":     {"model": "flux_schnell",   "provider": "multi"},
        "standard": {"model": "hunyuan_image",  "provider": "multi"},
        "premium":  {"model": "hunyuan_image",  "provider": "multi"},
        "ultra":    {"model": "hunyuan_image",  "provider": "multi", "num_images": 3},
    },
    # ── Character Consistency / Same-person edits ─────────────────────────────
    "character_consistency": {
        "fast":     {"model": "flux_schnell",     "provider": "multi"},
        "standard": {"model": "flux_kontext",     "provider": "multi"},
        "premium":  {"model": "flux_kontext",     "provider": "multi"},
        "ultra":    {"model": "flux_kontext_max", "provider": "multi", "num_images": 2},
    },
    # ── Image Editing / Inpainting / Outpainting ──────────────────────────────
    "editing": {
        "fast":     {"model": "flux_kontext",     "provider": "multi"},
        "standard": {"model": "flux_kontext",     "provider": "multi"},
        "premium":  {"model": "flux_kontext_max", "provider": "multi"},
        "ultra":    {"model": "flux_kontext_max", "provider": "multi", "num_images": 2},
    },
    # ── Vector / SVG / Icons / Flat Design ───────────────────────────────────
    "vector": {
        "fast":     {"model": "recraft_v4",     "provider": "multi"},
        "standard": {"model": "recraft_v4_svg", "provider": "multi"},
        "premium":  {"model": "recraft_v4_svg", "provider": "multi"},
        "ultra":    {"model": "recraft_v4_svg", "provider": "multi", "num_images": 2},
    },
    # ── Interior Design / Architecture ────────────────────────────────────────
    "interior_arch": {
        "fast":     {"model": "flux_schnell",  "provider": "multi"},
        "standard": {"model": "flux_2_pro",    "provider": "multi"},
        "premium":  {"model": "flux_2_max",    "provider": "multi"},
        "ultra":    {"model": "flux_2_max",    "provider": "multi", "num_images": 2},
    },
    # ── Fast / Draft / Preview ────────────────────────────────────────────────
    "fast": {
        "fast":     {"model": "flux_schnell",  "provider": "multi"},
        "standard": {"model": "flux_2_turbo",  "provider": "multi"},
        "premium":  {"model": "flux_2_pro",    "provider": "multi"},
        "ultra":    {"model": "flux_2_pro",    "provider": "multi", "num_images": 2},
    },
}

# Tier aliases (web quality string → internal tier key)
TIER_ALIASES: Dict[str, str] = {
    "fast":      "fast",
    "balanced":  "standard",
    "quality":   "premium",
    "ultra":     "ultra",
    # GPU tier names (legacy compat)
    "FAST":      "fast",
    "STANDARD":  "standard",
    "PREMIUM":   "premium",
}


_PORTRAIT_KEYWORDS = [
    "portrait", "headshot", "face", "selfie", "person", "man", "woman", "girl",
    "boy", "model", "human", "people", "skin", "close-up", "close up", "profile photo",
]
_PRODUCT_KEYWORDS = [
    "product", "bottle", "can", "package", "cosmetic", "perfume", "cream", "watch",
    "shoe", "sneaker", "bag", "handbag", "packshot", "studio shot", "item",
]
_FOOD_KEYWORDS = [
    "food", "dish", "meal", "recipe", "plate", "restaurant", "chef", "cuisine",
    "dessert", "cake", "coffee", "drink", "beverage", "breakfast", "lunch", "dinner",
]
_FASHION_KEYWORDS = [
    "fashion", "outfit", "clothing", "wear", "dress", "suit", "couture", "runway",
    "street style", "lookbook", "styled", "apparel", "garment",
]
_LANDSCAPE_KEYWORDS = [
    "landscape", "nature", "mountain", "forest", "ocean", "sea", "sky", "sunset",
    "sunrise", "field", "valley", "lake", "river", "waterfall", "scenic", "countryside",
]


def detect_capability_bucket(prompt: str) -> str:
    """
    Detect the capability bucket from the user's raw prompt.

    Returns one of the BUCKET_KEYWORDS keys (or a photorealism sub-bucket),
    defaulting to "photorealism".
    Priority: earlier buckets in the list win (typography > vector > character > ...).
    Sub-buckets returned: photorealism_portrait, photorealism_product,
    photorealism_food, photorealism_fashion, photorealism_landscape.
    """
    prompt_lower = prompt.lower()
    priority_order = [
        "typography",
        "vector",
        "character_consistency",
        "editing",
        "anime",
        "artistic",
        "interior_arch",
        "fast",
    ]
    for bucket in priority_order:
        for kw in BUCKET_KEYWORDS.get(bucket, []):
            if kw in prompt_lower:
                return bucket

    # Photorealism — detect sub-bucket
    for kw in _PORTRAIT_KEYWORDS:
        if kw in prompt_lower:
            return "photorealism_portrait"
    for kw in _PRODUCT_KEYWORDS:
        if kw in prompt_lower:
            return "photorealism_product"
    for kw in _FOOD_KEYWORDS:
        if kw in prompt_lower:
            return "photorealism_food"
    for kw in _FASHION_KEYWORDS:
        if kw in prompt_lower:
            return "photorealism_fashion"
    for kw in _LANDSCAPE_KEYWORDS:
        if kw in prompt_lower:
            return "photorealism_landscape"

    return "photorealism"


def get_model_config(capability_bucket: str, tier: str) -> Dict:
    """
    Get the model config for a given bucket + tier.

    Returns dict with keys: model, backend, and any extra kwargs.
    Falls back gracefully: sub-buckets → photorealism, unknown bucket → photorealism,
    unknown tier → standard.
    """
    resolved_tier = TIER_ALIASES.get(tier, "standard")
    # Sub-buckets (e.g. photorealism_portrait) use the photorealism model map
    base_bucket = capability_bucket.split("_")[0] if capability_bucket.startswith("photorealism_") else capability_bucket
    bucket_map = BUCKET_MODEL_MAP.get(base_bucket, BUCKET_MODEL_MAP["photorealism"])
    return bucket_map.get(resolved_tier, bucket_map.get("standard", {"model": "flux_pro", "backend": "fal"}))

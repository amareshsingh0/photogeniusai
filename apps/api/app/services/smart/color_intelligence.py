"""
Color Intelligence Engine v2 — PhotoGenius AI (hardened)

Derives full brand palettes from a single primary color using:
- HSV-based harmony rules (complementary, triadic, analogous, split-complementary)
- Cultural context overrides (India festivals, luxury, tech, health, etc.)
- Perceptual contrast enforcement (WCAG AA/AAA minimum)
- Tone-aware adjustments (urgent → saturated, minimal → muted, luxury → desaturated + gold)
- Festival auto-detection from prompt text (word-boundary regex, longest-match)

Usage:
  from app.services.smart.color_intelligence import color_intelligence

  palette = color_intelligence.derive_palette("#FF6B35", brand_tone="energetic", industry="food")
  colors  = color_intelligence.festival_palette("diwali")
  fest    = color_intelligence.detect_festival("Diwali sale poster banao")
"""
from __future__ import annotations

import colorsys
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Color math helpers
# ══════════════════════════════════════════════════════════════════════════════

def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Parse hex color to (r, g, b). Returns blue fallback on invalid input."""
    s = (hex_str or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) == 6:
        try:
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        except ValueError:
            pass
    logger.warning("[ColorIntel] Invalid hex %r — using #2563EB fallback", hex_str)
    return (37, 99, 235)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
    )


def _rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Returns (h 0-360, s 0-1, v 0-1)."""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return h * 360, s, v


def _hsv_to_hex(h: float, s: float, v: float) -> str:
    """h in degrees (0-360)."""
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return _rgb_to_hex(int(r * 255), int(g * 255), int(b * 255))


def _luminance(rgb: Tuple[int, int, int]) -> float:
    """WCAG relative luminance (0-1)."""
    def _lin(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * _lin(rgb[0]) + 0.7152 * _lin(rgb[1]) + 0.0722 * _lin(rgb[2])


def _contrast_ratio(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    """WCAG contrast ratio between two RGB colors."""
    l1 = _luminance(rgb1) + 0.05
    l2 = _luminance(rgb2) + 0.05
    return max(l1, l2) / min(l1, l2)


def _ensure_contrast(text_hex: str, bg_hex: str, min_ratio: float = 4.5) -> str:
    """Return text_hex if contrast is sufficient, else white or near-black."""
    # Fast-fail: identical colors always fail contrast
    if text_hex.upper().lstrip("#") == bg_hex.upper().lstrip("#"):
        return "#FFFFFF" if _luminance(_hex_to_rgb(bg_hex)) < 0.5 else "#0F172A"
    text_rgb = _hex_to_rgb(text_hex)
    bg_rgb   = _hex_to_rgb(bg_hex)
    if _contrast_ratio(text_rgb, bg_rgb) >= min_ratio:
        return text_hex
    white_cr = _contrast_ratio((255, 255, 255), bg_rgb)
    black_cr = _contrast_ratio((15, 23, 42),    bg_rgb)
    return "#FFFFFF" if white_cr >= black_cr else "#0F172A"


def _normalize_hex(hex_str: str) -> str:
    """Normalize to uppercase 6-char hex with leading #. Falls back to #2563EB."""
    s = (hex_str or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) == 6 and all(c in "0123456789ABCDEFabcdef" for c in s):
        return "#" + s.upper()
    return "#2563EB"


# ══════════════════════════════════════════════════════════════════════════════
# Festival palettes
# ══════════════════════════════════════════════════════════════════════════════

_FESTIVAL_PALETTES: Dict[str, Dict[str, str]] = {
    "diwali": {
        "primary": "#FF9933", "secondary": "#FFD700", "accent": "#FF4500",
        "bg": "#1A0800", "text_primary": "#FFFFFF", "text_secondary": "#FFD700",
    },
    "holi": {
        "primary": "#FF3366", "secondary": "#00BFFF", "accent": "#FFD700",
        "bg": "#0D0000", "text_primary": "#FFFFFF", "text_secondary": "#FF3366",
    },
    "navratri": {
        "primary": "#FF6B35", "secondary": "#9B59B6", "accent": "#F1C40F",
        "bg": "#0D0D0D", "text_primary": "#FFFFFF", "text_secondary": "#F1C40F",
    },
    "eid": {
        "primary": "#00A693", "secondary": "#C9A84C", "accent": "#E8F4F0",
        "bg": "#0A1628", "text_primary": "#FFFFFF", "text_secondary": "#C9A84C",
    },
    "christmas": {
        "primary": "#CC0000", "secondary": "#006400", "accent": "#FFD700",
        "bg": "#0D1B0D", "text_primary": "#FFFFFF", "text_secondary": "#FFD700",
    },
    "new_year": {
        "primary": "#C9A84C", "secondary": "#1A1A2E", "accent": "#FFD700",
        "bg": "#0D0D1A", "text_primary": "#FFFFFF", "text_secondary": "#C9A84C",
    },
    "black_friday": {
        "primary": "#FF0000", "secondary": "#FFD700", "accent": "#FF4500",
        "bg": "#000000", "text_primary": "#FFFFFF", "text_secondary": "#FFD700",
    },
    "valentine": {
        "primary": "#E91E63", "secondary": "#FF80AB", "accent": "#F8BBD0",
        "bg": "#1A0010", "text_primary": "#FFFFFF", "text_secondary": "#FF80AB",
    },
    "independence_day_india": {
        "primary": "#FF9933", "secondary": "#138808", "accent": "#FFFFFF",
        "bg": "#000080", "text_primary": "#FFFFFF", "text_secondary": "#FFD700",
    },
    "ganesh_chaturthi": {
        "primary": "#FF6B00", "secondary": "#FFD700", "accent": "#8B0000",
        "bg": "#1A0800", "text_primary": "#FFFFFF", "text_secondary": "#FFD700",
    },
    "onam": {
        "primary": "#FF8C00", "secondary": "#FFD700", "accent": "#228B22",
        "bg": "#0A1A00", "text_primary": "#FFFFFF", "text_secondary": "#FFD700",
    },
    "pongal": {
        "primary": "#FF8C00", "secondary": "#32CD32", "accent": "#FFD700",
        "bg": "#0A1000", "text_primary": "#FFFFFF", "text_secondary": "#FFD700",
    },
    "dussehra": {
        "primary": "#FF6B00", "secondary": "#CC0000", "accent": "#FFD700",
        "bg": "#1A0500", "text_primary": "#FFFFFF", "text_secondary": "#FFD700",
    },
    "raksha_bandhan": {
        "primary": "#FF69B4", "secondary": "#FFD700", "accent": "#FF1493",
        "bg": "#1A001A", "text_primary": "#FFFFFF", "text_secondary": "#FFD700",
    },
}

# Festival keyword → palette key.
# NOTE: sorted longest-first at compile time so longer phrases shadow shorter ones.
_FESTIVAL_KEYWORDS: Dict[str, str] = {
    "festival of lights":    "diwali",
    "happy new year":        "new_year",
    "cyber monday":          "black_friday",
    "black friday":          "black_friday",
    "eid mubarak":           "eid",
    "independence day":      "independence_day_india",
    "raksha bandhan":        "raksha_bandhan",
    "rakshabandhan":         "raksha_bandhan",
    "ganesh chaturthi":      "ganesh_chaturthi",
    "february 14":           "valentine",
    "august 15":             "independence_day_india",
    "deepawali":             "diwali",
    "deepavali":             "diwali",
    "navratri":              "navratri",
    "sankranti":             "pongal",
    "dussehra":              "dussehra",
    "valentine":             "valentine",
    "ramadan":               "eid",
    "dandiya":               "navratri",
    "diwali":                "diwali",
    "garba":                 "navratri",
    "gulal":                 "holi",
    "ganpati":               "ganesh_chaturthi",
    "ganesh":                "ganesh_chaturthi",
    "christmas":             "christmas",
    "pongal":                "pongal",
    "lohri":                 "pongal",
    "onam":                  "onam",
    "diyas":                 "diwali",
    "x-mas":                 "christmas",
    "xmas":                  "christmas",
    "holi":                  "holi",
    "rang":                  "holi",   # protected below with word boundary
    "eid":                   "eid",
    "new year":              "new_year",
}

# Compile once: longest keywords first, word-boundary anchored to prevent
# "rang" → "orange", "eid" → "kaleidoscope", "garba" → "garbage" false matches.
_FESTIVAL_RE = re.compile(
    r'\b(?:' + "|".join(
        re.escape(k) for k in sorted(_FESTIVAL_KEYWORDS, key=len, reverse=True)
    ) + r')\b',
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════════════════
# Industry default palettes + alias map
# ══════════════════════════════════════════════════════════════════════════════

_INDUSTRY_DEFAULTS: Dict[str, Dict[str, str]] = {
    "technology":    {"primary": "#2563EB", "secondary": "#1E40AF", "accent": "#06B6D4", "bg": "#0F172A"},
    "saas":          {"primary": "#7C3AED", "secondary": "#4C1D95", "accent": "#A78BFA", "bg": "#0F0A1E"},
    "health":        {"primary": "#10B981", "secondary": "#059669", "accent": "#34D399", "bg": "#0A1A12"},
    "food":          {"primary": "#F97316", "secondary": "#EA580C", "accent": "#FCD34D", "bg": "#1A0800"},
    "fashion":       {"primary": "#BE185D", "secondary": "#9D174D", "accent": "#F9A8D4", "bg": "#0F0010"},
    "finance":       {"primary": "#1E3A5F", "secondary": "#0F2340", "accent": "#C9A84C", "bg": "#0A1020"},
    "education":     {"primary": "#D97706", "secondary": "#B45309", "accent": "#FDE68A", "bg": "#1A1000"},
    "entertainment": {"primary": "#DC2626", "secondary": "#991B1B", "accent": "#FBBF24", "bg": "#0F0000"},
    "real_estate":   {"primary": "#0E7490", "secondary": "#164E63", "accent": "#A5F3FC", "bg": "#020F14"},
    "travel":        {"primary": "#0284C7", "secondary": "#0369A1", "accent": "#7DD3FC", "bg": "#0A1520"},
    "retail":        {"primary": "#DC2626", "secondary": "#B91C1C", "accent": "#FCA5A5", "bg": "#150000"},
    "luxury":        {"primary": "#C9A84C", "secondary": "#8B7536", "accent": "#F5E6A3", "bg": "#050505"},
    "fitness":       {"primary": "#EF4444", "secondary": "#B91C1C", "accent": "#FDE68A", "bg": "#0F0000"},
    "beauty":        {"primary": "#F472B6", "secondary": "#DB2777", "accent": "#FCE7F3", "bg": "#0F0010"},
    "gaming":        {"primary": "#8B5CF6", "secondary": "#6D28D9", "accent": "#22D3EE", "bg": "#0A001A"},
    "generic":       {"primary": "#2563EB", "secondary": "#1E40AF", "accent": "#F59E0B", "bg": "#0F172A"},
}

# Aliases → canonical industry key
_INDUSTRY_ALIASES: Dict[str, str] = {
    "tech":           "technology",
    "software":       "saas",
    "startup":        "saas",
    "fintech":        "finance",
    "banking":        "finance",
    "insurance":      "finance",
    "b2b":            "technology",
    "adtech":         "technology",
    "e-commerce":     "retail",
    "ecommerce":      "retail",
    "shop":           "retail",
    "restaurant":     "food",
    "beverage":       "food",
    "gym":            "fitness",
    "wellness":       "health",
    "healthcare":     "health",
    "pharma":         "health",
    "cosmetics":      "beauty",
    "skincare":       "beauty",
    "apparel":        "fashion",
    "clothing":       "fashion",
    "property":       "real_estate",
    "hospitality":    "travel",
    "hotel":          "travel",
    "media":          "entertainment",
    "music":          "entertainment",
    "film":           "entertainment",
}

# Module-level constant — pre-normalized generic primaries for industry override
_GENERIC_PRIMARIES = frozenset({
    "#2563EB", "#000000", "#FFFFFF", "#FF0000", "#0000FF", "#00FF00",
})

# Tone → saturation multiplier
_TONE_SATURATION: Dict[str, float] = {
    "urgent":       1.20,
    "energetic":    1.15,
    "bold":         1.08,
    "playful":      1.12,
    "professional": 1.00,
    "corporate":    0.95,
    "trustworthy":  0.95,
    "warm":         1.05,
    "elegant":      0.85,
    "luxury":       0.80,
    "minimal":      0.70,
}


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def detect_festival(prompt: str) -> Optional[str]:
    """
    Detect festival/occasion from prompt text using compiled word-boundary regex.
    Longest keywords take precedence (e.g. "eid mubarak" beats "eid").
    Returns palette key or None.
    """
    if not prompt:
        return None
    m = _FESTIVAL_RE.search(prompt)
    return _FESTIVAL_KEYWORDS.get(m.group(0).lower()) if m else None


def detect_cultural_key(text: str) -> Optional[str]:
    """Alias for detect_festival."""
    return detect_festival(text)


def festival_palette(festival_name: str) -> Optional[Dict[str, str]]:
    """Get predefined festival palette dict by name (auto-contrast enforced)."""
    if not festival_name:
        return None
    key = festival_name.lower().strip().replace(" ", "_").replace("-", "_")
    # Try direct lookup; fall back via keyword map
    if key not in _FESTIVAL_PALETTES:
        key = _FESTIVAL_KEYWORDS.get(key.replace("_", " "), key)
    pal = _FESTIVAL_PALETTES.get(key)
    if not pal:
        return None
    return _enforce_festival_contrast(dict(pal))


def _enforce_festival_contrast(pal: Dict[str, str]) -> Dict[str, str]:
    """Run WCAG contrast checks on a festival palette (doesn't change primary/secondary/accent hues)."""
    pal["text_primary"]   = _ensure_contrast(pal.get("text_primary", "#FFFFFF"),   pal["bg"], 7.0)
    pal["text_secondary"] = _ensure_contrast(pal.get("text_secondary", "#FFD700"),  pal["bg"], 4.5)
    return pal


def industry_defaults(industry: str) -> Dict[str, str]:
    """Get default brand colors for industry (supports aliases like 'fintech', 'e-commerce')."""
    key = (industry or "generic").lower().strip()
    key = _INDUSTRY_ALIASES.get(key, key)
    return dict(_INDUSTRY_DEFAULTS.get(key, _INDUSTRY_DEFAULTS["generic"]))


def suggest_harmony(brand_tone: str, creative_type: str = "") -> str:
    """
    Pick best harmony rule for the context.
    creative_type (e.g. 'sale', 'newsletter', 'corporate') refines the result.
    Uses word-boundary matching to avoid 'non-luxury' → 'analogous' false match.
    """
    tone  = (brand_tone   or "").lower()
    ctype = (creative_type or "").lower()

    # Sales/promo content → high-contrast complementary for visual pop
    if re.search(r'\b(?:sale|promo|discount|offer|deal)\b', ctype):
        return "complementary"

    # Luxury / fashion → analogous for smooth transitions.
    # Negative lookbehind (?<!-) prevents "non-luxury" from matching "luxury".
    if re.search(r'(?<!-)(?:luxury|fashion|elegant|premium|couture)(?!-)', tone):
        return "analogous"

    # Festival / high-energy → triadic for maximum vibrancy
    if re.search(r'(?<!-)(?:festival|holi|diwali|energy|playful|vibrant)(?!-)', tone):
        return "triadic"

    # Tech / corporate → split-complementary for authority + accent
    if re.search(r'\b(?:tech|saas|corporate|finance|banking)\b', tone):
        return "split_comp"

    return "complementary"


def derive_palette(
    primary_hex: str = "#2563EB",
    brand_tone: str = "professional",
    industry: str = "generic",
    harmony: str = "complementary",
    prompt_context: str = "",
) -> Dict[str, str]:
    """
    Derive a complete 6-color palette from a primary hex color.

    Priority:
    1. Festival/cultural override (highest) — still WCAG-checked
    2. Industry defaults if primary is a generic placeholder
    3. HSV harmony math from primary_hex

    Returns:
        { primary, secondary, accent, bg, text_primary, text_secondary }
    """
    # Normalize primary_hex early so all downstream code works with valid hex
    primary_hex = _normalize_hex(primary_hex)
    brand_tone  = (brand_tone or "professional").lower()
    industry    = _INDUSTRY_ALIASES.get((industry or "generic").lower(), (industry or "generic").lower())

    # 1. Festival override — highest priority, WCAG-enforced
    if prompt_context:
        fest_key = detect_festival(prompt_context)
        if fest_key and fest_key in _FESTIVAL_PALETTES:
            logger.debug("[ColorIntel] Festival override: %s", fest_key)
            return _enforce_festival_contrast(dict(_FESTIVAL_PALETTES[fest_key]))

    # 2. Industry override for clearly generic primaries
    if primary_hex.upper() in _GENERIC_PRIMARIES:
        ind = _INDUSTRY_DEFAULTS.get(industry, _INDUSTRY_DEFAULTS["generic"])
        original = primary_hex
        primary_hex = ind["primary"]
        logger.info("[ColorIntel] Generic primary %s → industry default %s (%s)", original, primary_hex, industry)

    # 3. Auto-select harmony when caller left it as default
    if harmony == "complementary":
        harmony = suggest_harmony(brand_tone)

    # 4. HSV derivation
    r, g, b = _hex_to_rgb(primary_hex)
    h, s_orig, v = _rgb_to_hsv(r, g, b)

    # Apply tone saturation scaling (save original s for text derivation)
    s_mult = _TONE_SATURATION.get(brand_tone, 1.0)
    s = max(0.0, min(1.0, s_orig * s_mult))

    # Harmony colors
    if harmony == "triadic":
        sec_hex    = _hsv_to_hex(h + 120, s * 0.85, v)
        accent_hex = _hsv_to_hex(h + 240, s * 0.90, min(1.0, v + 0.05))
    elif harmony == "analogous":
        sec_hex    = _hsv_to_hex(h + 30,  s * 0.90, v)
        accent_hex = _hsv_to_hex(h - 30,  s * 0.90, v)
    elif harmony == "split_comp":
        sec_hex    = _hsv_to_hex(h + 150, s * 0.85, v)
        accent_hex = _hsv_to_hex(h + 210, s * 0.90, min(1.0, v + 0.05))
    else:  # complementary
        sec_hex    = _hsv_to_hex(h + 180, s * 0.80, v)
        accent_hex = _hsv_to_hex(h + 30,  min(1.0, s * 1.05), min(1.0, v + 0.10))

    # Background: deep dark desaturated hue
    if brand_tone == "minimal":
        bg_hex = "#F8FAFC"
    elif brand_tone in ("luxury", "elegant"):
        bg_hex = _hsv_to_hex(h, min(0.25, s * 0.15), 0.05)
    else:
        bg_hex = _hsv_to_hex(h, min(0.60, s * 0.30), max(0.04, v * 0.10))

    # Accessible text — use s_orig so text-secondary isn't over-desaturated
    text_primary   = _ensure_contrast("#FFFFFF", bg_hex, min_ratio=7.0)
    text_secondary = _ensure_contrast(
        _hsv_to_hex(h, min(0.35, s_orig * 0.50), min(1.0, v * 1.40)),
        bg_hex, min_ratio=4.5,
    )

    # Accent: visible on bg (button legibility)
    accent_hex = _boost_accent_visibility(accent_hex, bg_hex)

    palette = {
        "primary":        primary_hex,
        "secondary":      sec_hex,
        "accent":         accent_hex,
        "bg":             bg_hex,
        "text_primary":   text_primary,
        "text_secondary": text_secondary,
    }
    logger.debug("[ColorIntel] palette %s (harmony=%s tone=%s)", palette, harmony, brand_tone)
    return palette


def _boost_accent_visibility(accent_hex: str, bg_hex: str) -> str:
    """
    Ensure accent has ≥3.0 contrast on bg.
    Dark backgrounds → boost brightness.
    Light backgrounds → darken accent.
    If all attempts fail → safe high-contrast fallback.
    """
    accent_rgb = _hex_to_rgb(accent_hex)
    bg_rgb     = _hex_to_rgb(bg_hex)
    if _contrast_ratio(accent_rgb, bg_rgb) >= 3.0:
        return accent_hex
    h, s, v = _rgb_to_hsv(*accent_rgb)
    bg_lum = _luminance(bg_rgb)

    if bg_lum > 0.5:
        # Light background: darken the accent
        for drop in (0.15, 0.30, 0.50, 0.70):
            candidate = _hsv_to_hex(h, min(1.0, s + 0.10), max(0.0, v - drop))
            if _contrast_ratio(_hex_to_rgb(candidate), bg_rgb) >= 3.0:
                return candidate
        return "#1E3A5F"  # dark navy — universally readable on light bg
    else:
        # Dark background: boost brightness
        for boost in (0.12, 0.25, 0.40, 0.60):
            candidate = _hsv_to_hex(h, max(0.60, s), min(1.0, v + boost))
            if _contrast_ratio(_hex_to_rgb(candidate), bg_rgb) >= 3.0:
                return candidate
        # Absolute fallback — pick best of bright/dark universal colors
        whites = ("#FFD700", "#FFFFFF", "#F59E0B")
        for fb in whites:
            if _contrast_ratio(_hex_to_rgb(fb), bg_rgb) >= 3.0:
                return fb
        return "#FFFFFF"


def suggest_accent_for_cta(primary_hex: str, bg_hex: str) -> str:
    """Suggest best CTA button color: max-contrast, max-vibrance on bg."""
    rgb = _hex_to_rgb(primary_hex)
    h, s, v = _rgb_to_hsv(*rgb)
    bg_rgb = _hex_to_rgb(bg_hex)
    candidates = [
        _hsv_to_hex(h + 30,  min(1.0, s + 0.10), min(1.0, v + 0.20)),
        _hsv_to_hex(h - 30,  min(1.0, s + 0.10), min(1.0, v + 0.20)),
        _hsv_to_hex(h + 180, 0.95, 0.95),
        "#F59E0B", "#10B981", "#EF4444", "#FFFFFF",
    ]
    best, best_score = "", 0.0
    for c in candidates:
        c_rgb = _hex_to_rgb(c)  # parse once, reuse for both contrast + saturation
        cr = _contrast_ratio(c_rgb, bg_rgb)
        if cr < 3.0:
            continue
        _, sc, _ = _rgb_to_hsv(*c_rgb)
        score = cr * (1 + sc * 0.3)
        if score > best_score:
            best_score, best = score, c
    # If no candidate passed the threshold, guarantee contrast via _boost
    return best if best else _boost_accent_visibility("#F59E0B", bg_hex)


def analyze_palette(palette: Dict[str, str]) -> Dict:
    """
    Quality analysis: harmony, contrast, vibrancy, WCAG level.
    Checks: text_primary/bg, text_secondary/bg, accent/bg.
    """
    warnings: List[str] = []

    text_rgb      = _hex_to_rgb(palette.get("text_primary",   "#FFFFFF"))
    text_sec_rgb  = _hex_to_rgb(palette.get("text_secondary", "#CBD5E1"))
    bg_rgb        = _hex_to_rgb(palette.get("bg",             "#0F172A"))
    primary_rgb   = _hex_to_rgb(palette.get("primary",        "#2563EB"))
    accent_rgb    = _hex_to_rgb(palette.get("accent",         "#F59E0B"))

    # ── Contrast ──────────────────────────────────────────────────────────────
    text_cr     = _contrast_ratio(text_rgb, bg_rgb)
    text_sec_cr = _contrast_ratio(text_sec_rgb, bg_rgb)
    accent_cr   = _contrast_ratio(accent_rgb, bg_rgb)

    contrast_score = min(1.0, text_cr / 7.0)

    if text_cr < 4.5:
        warnings.append(f"text_primary contrast {text_cr:.1f}:1 below WCAG AA (4.5:1)")
    if text_sec_cr < 3.0:
        warnings.append(f"text_secondary contrast {text_sec_cr:.1f}:1 below minimum (3.0:1)")
    if accent_cr < 3.0:
        warnings.append(f"accent contrast {accent_cr:.1f}:1 below button minimum (3.0:1)")

    # ── Vibrancy ──────────────────────────────────────────────────────────────
    # Unpack all HSV at once — avoids 4 separate _rgb_to_hsv calls
    ph, ps, pv = _rgb_to_hsv(*primary_rgb)
    ah, as_, av = _rgb_to_hsv(*accent_rgb)

    vibrancy_score = (ps + as_) / 2
    if vibrancy_score < 0.35:
        warnings.append("Palette too muted — increase saturation for ad impact")

    # ── Harmony ───────────────────────────────────────────────────────────────
    # Grayscale colors (near-zero saturation) pair with everything
    if ps < 0.05 or as_ < 0.05:
        harmony_score = 1.0
    else:
        hue_diff = abs(ph - ah)
        if hue_diff > 180:
            hue_diff = 360 - hue_diff
        # hue_diff=0 means monochromatic → no cross-hue harmony → low score
        if hue_diff < 15:
            harmony_score = 0.20
        else:
            best_dist = min(abs(hue_diff - d) for d in (30, 120, 150, 180))
            harmony_score = max(0.0, 1.0 - best_dist / 90)

    return {
        "harmony_score":    round(harmony_score,  2),
        "contrast_score":   round(contrast_score, 2),
        "vibrancy_score":   round(vibrancy_score, 2),
        "warnings":         warnings,
        "wcag_level":       "AAA" if text_cr >= 7.0 else "AA" if text_cr >= 4.5 else "FAIL",
        "text_contrast":    round(text_cr,     2),
        "secondary_contrast": round(text_sec_cr, 2),
        "accent_contrast":  round(accent_cr,   2),
    }


# ── Module singleton ──────────────────────────────────────────────────────────
class _ColorIntelligence:
    derive_palette         = staticmethod(derive_palette)
    festival_palette       = staticmethod(festival_palette)
    industry_defaults      = staticmethod(industry_defaults)
    detect_festival        = staticmethod(detect_festival)
    detect_cultural_key    = staticmethod(detect_cultural_key)
    suggest_harmony        = staticmethod(suggest_harmony)
    suggest_accent_for_cta = staticmethod(suggest_accent_for_cta)
    analyze_palette        = staticmethod(analyze_palette)


color_intelligence = _ColorIntelligence()

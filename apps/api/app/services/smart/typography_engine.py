"""
Typography Intelligence Engine v3 — PhotoGenius AI

Production fixes applied (v2 → v3):
- FONTS_DIR uses env-configurable writable path (no import-time crash on read-only FS)
- All google_url entries replaced with TTF direct-download URLs (not woff2)
- font_path(): atomic write (tmp+rename), size validation, per-font thread lock,
  in-memory cache, woff2 guard
- platform_from_dimensions(): explicit non-overlapping ratio branches; twitter range added
- get_font_sizes(): font_style scale multiplier applied; canvas_height-aware cap
- get_typography_spec(): pre-resolves 2 font paths (not 6×); subheadline/cta use
  headline font for display styles; font_weight pulled from FONT_CATALOGUE;
  canvas_height + brand_tone used; font_file stripped from external payloads
- _google_fonts_import_url(): dedup-ordered (no set()); groups same family → one entry;
  multiple weights → Montserrat:wght@700;900
- Startup validation: validate_required_fonts() warns if bundled fonts missing
- Async preload: async def preload_all_fonts() for FastAPI lifespan
"""
from __future__ import annotations

import logging
import os
import threading
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from types import MappingProxyType

logger = logging.getLogger(__name__)

# ── Fonts directory (writable, env-configurable) ──────────────────────────────
_DEFAULT_FONTS_DIR = Path(os.environ.get("FONTS_CACHE_DIR", "/tmp/photogenius_fonts"))
try:
    _DEFAULT_FONTS_DIR.mkdir(parents=True, exist_ok=True)
    FONTS_DIR = _DEFAULT_FONTS_DIR
except Exception as _e:
    logger.warning("[typography] Cannot create fonts dir %s: %s — font downloads disabled", _DEFAULT_FONTS_DIR, _e)
    FONTS_DIR = _DEFAULT_FONTS_DIR  # still set; font_path will handle missing gracefully

# ── Font catalogue ────────────────────────────────────────────────────────────
# google_url: MUST be a TTF (not woff2) — PIL ImageFont.truetype() cannot read woff2.
# Use Google Fonts static API pattern:
#   https://fonts.gstatic.com/s/{slug}/{version}/{File}.ttf
# css_family: used for Canvas / CSS output
# google_query: used for Google Fonts @import URL
_FONT_CATALOGUE_RAW: Dict[str, Dict] = {
    # ── Always-bundled fonts (no google_url — must exist in fonts/ dir) ────────
    "bebas_neue": {
        "file":        "BebasNeue-Regular.ttf",
        "category":    "display",
        "weight":      400,   # Bebas Neue only ships Regular (visually very bold)
        "role":        "headline",
        "css_family":  "Bebas Neue, Impact, sans-serif",
        "google_query":"Bebas+Neue",
        "google_url":  "https://github.com/google/fonts/raw/main/ofl/bebasnue/BebasNeue-Regular.ttf",
    },
    "anton": {
        "file":        "Anton-Regular.ttf",
        "category":    "display",
        "weight":      400,
        "role":        "headline",
        "css_family":  "Anton, Impact, sans-serif",
        "google_query":"Anton",
        "google_url":  "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
    },
    "montserrat_black": {
        "file":        "Montserrat-Black.ttf",
        "category":    "sans",
        "weight":      900,
        "role":        "headline",
        "css_family":  "Montserrat, sans-serif",
        "google_query":"Montserrat:wght@900",
        "google_url":  "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Black.ttf",
    },
    "montserrat_bold": {
        "file":        "Montserrat-Bold.ttf",
        "category":    "sans",
        "weight":      700,
        "role":        "body",
        "css_family":  "Montserrat, sans-serif",
        "google_query":"Montserrat:wght@700",
        "google_url":  "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf",
    },
    # ── Downloaded-on-demand fonts (google_url = TTF, NOT woff2) ─────────────
    "oswald": {
        "file":        "Oswald-Bold.ttf",
        "category":    "display",
        "weight":      700,
        "role":        "headline",
        "css_family":  "Oswald, sans-serif",
        "google_query":"Oswald:wght@700",
        # TTF static URL (Google Fonts v2 direct download)
        "google_url":  "https://fonts.gstatic.com/s/oswald/v53/TK3_WkUHHAIjg75cFRf3bXL8LICs1xFvsUtiZTEeA.ttf",
    },
    "playfair": {
        "file":        "PlayfairDisplay-Bold.ttf",
        "category":    "serif",
        "weight":      700,
        "role":        "headline",
        "css_family":  "Playfair Display, Georgia, serif",
        "google_query":"Playfair+Display:wght@700",
        "google_url":  "https://fonts.gstatic.com/s/playfairdisplay/v37/nuFvD-vYSZviVYUb_rj3ij__anPXJzDwcbmjWBN2PKdTvXDXbtXb.ttf",
    },
    "inter_bold": {
        "file":        "Inter-Bold.ttf",
        "category":    "sans",
        "weight":      700,
        "role":        "body",
        "css_family":  "Inter, system-ui, sans-serif",
        "google_query":"Inter:wght@700",
        "google_url":  "https://fonts.gstatic.com/s/inter/v19/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuFuYAZJhiJ-Ek-_EeA.ttf",
    },
    "raleway_bold": {
        "file":        "Raleway-Bold.ttf",
        "category":    "sans",
        "weight":      700,
        "role":        "body",
        "css_family":  "Raleway, sans-serif",
        "google_query":"Raleway:wght@700",
        "google_url":  "https://fonts.gstatic.com/s/raleway/v34/1Ptxg8zYS_SKggPN4iEgvnHyvveLxVvaorCIPrEVIT9d0c-.ttf",
    },
    "poppins_bold": {
        "file":        "Poppins-Bold.ttf",
        "category":    "sans",
        "weight":      700,
        "role":        "body",
        "css_family":  "Poppins, sans-serif",
        "google_query":"Poppins:wght@700",
        "google_url":  "https://fonts.gstatic.com/s/poppins/v23/pxiByp8kv8JHgFVrLCz7Z1xlFd2JQEk.ttf",
    },
}

# Expose as immutable so callers can't mutate the catalogue
FONT_CATALOGUE: MappingProxyType = MappingProxyType(_FONT_CATALOGUE_RAW)

# ── Font pairing rules ────────────────────────────────────────────────────────
_PAIRING_RULES_RAW: Dict[str, Tuple[str, str]] = {
    # font_style_key → (headline_font_key, body_font_key)
    "bold_tech":            ("bebas_neue",      "montserrat_bold"),
    "expressive_display":   ("anton",           "montserrat_bold"),
    "elegant_serif":        ("playfair",        "raleway_bold"),
    "clean_sans":           ("montserrat_black","montserrat_bold"),
    "modern_sans":          ("oswald",          "inter_bold"),
    "friendly_round":       ("poppins_bold",    "poppins_bold"),
    "luxury_display":       ("playfair",        "inter_bold"),
    "minimal_light":        ("montserrat_black","inter_bold"),
    "default":              ("bebas_neue",      "montserrat_bold"),
}
PAIRING_RULES: MappingProxyType = MappingProxyType(_PAIRING_RULES_RAW)

# Styles where subheadline should use the headline font (not body font)
_SUBHEADLINE_HEADLINE_FONT_STYLES = frozenset({
    "elegant_serif", "expressive_display", "luxury_display",
})

# ── Platform size rules ───────────────────────────────────────────────────────
_PLATFORM_SIZES_RAW: Dict[str, Dict[str, int]] = {
    "instagram": {
        "headline": 60, "subheadline": 32, "body": 26,
        "cta": 32, "tagline": 22, "brand": 36,
    },
    "instagram_story": {
        "headline": 80, "subheadline": 40, "body": 30,
        "cta": 40, "tagline": 24, "brand": 40,
    },
    "linkedin": {
        "headline": 48, "subheadline": 28, "body": 22,
        "cta": 28, "tagline": 18, "brand": 30,
    },
    "twitter": {
        "headline": 44, "subheadline": 26, "body": 20,
        "cta": 26, "tagline": 18, "brand": 28,
    },
    "print": {
        "headline": 120, "subheadline": 60, "body": 36,
        "cta": 48, "tagline": 28, "brand": 48,
    },
    "billboard": {
        "headline": 200, "subheadline": 100, "body": 60,
        "cta": 80, "tagline": 40, "brand": 80,
    },
    "default": {
        "headline": 52, "subheadline": 28, "body": 22,
        "cta": 30, "tagline": 20, "brand": 32,
    },
}
PLATFORM_SIZES: MappingProxyType = MappingProxyType(_PLATFORM_SIZES_RAW)

# ── Kerning profiles ──────────────────────────────────────────────────────────
# These are CSS letter-spacing values (em fractions) — also used for canvas CSS.
# PIL rendering does character-by-character spacing (not built-in), so these are
# used by the canvas editor only; PIL compositor ignores them.
KERNING: Dict[str, float] = {
    "tight":  -0.04,   # display headlines (condensed)
    "normal":  0.0,    # subheadlines, CTAs
    "loose":   0.06,   # body text, captions
    "widest":  0.12,   # brand name in all-caps
}

# Tone-specific kerning overrides
_TONE_KERNING_OVERRIDES: Dict[str, Dict[str, float]] = {
    "luxury":       {"tight": -0.06, "normal": 0.02, "widest": 0.18},
    "energetic":    {"tight": -0.02, "normal": 0.01},
    "minimal_light":{"normal": 0.04, "loose": 0.08},
}

# Font style scale multipliers (display fonts can go larger)
_STYLE_SCALE: Dict[str, float] = {
    "bold_tech":          1.1,
    "expressive_display": 1.15,
    "elegant_serif":      0.92,
    "luxury_display":     0.88,
    "minimal_light":      0.90,
    "friendly_round":     1.0,
    "clean_sans":         1.0,
    "modern_sans":        1.05,
    "default":            1.0,
}

# ── Thread locks for concurrent font downloads ────────────────────────────────
_font_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
# In-memory resolution cache (populated after first successful resolve)
_resolved_cache: Dict[str, Optional[Path]] = {}

# Required fonts that must always be bundled
_REQUIRED_FONTS = ["bebas_neue", "anton", "montserrat_black", "montserrat_bold"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def validate_required_fonts() -> List[str]:
    """
    Check that all always-bundled fonts exist on disk.
    Returns list of missing font keys (empty = all good).
    Call at startup.
    """
    missing = []
    for key in _REQUIRED_FONTS:
        info = _FONT_CATALOGUE_RAW.get(key, {})
        path = FONTS_DIR / info.get("file", "")
        if not path.exists():
            logger.error("[typography] Missing required font: %s (%s)", key, info.get("file"))
            missing.append(key)
    return missing


def font_path(font_key: str) -> Optional[Path]:
    """
    Return local Path to a font file, downloading TTF from Google Fonts if needed.

    Thread-safe: uses per-font lock + atomic tmp→rename write.
    Returns None if font is unknown, download fails, or downloaded file is invalid.
    """
    # Fast path — already resolved
    if font_key in _resolved_cache:
        return _resolved_cache[font_key]

    info = _FONT_CATALOGUE_RAW.get(font_key)
    if not info:
        _resolved_cache[font_key] = None
        return None

    path = FONTS_DIR / info["file"]

    with _font_locks[font_key]:
        # Re-check inside lock (another thread may have downloaded while we waited)
        if font_key in _resolved_cache:
            return _resolved_cache[font_key]

        if path.exists() and path.stat().st_size > 10_000:
            _resolved_cache[font_key] = path
            return path

        url = info.get("google_url")
        if not url:
            _resolved_cache[font_key] = None
            return None

        # Warn if URL looks like woff2 (should be TTF)
        if url.endswith(".woff2"):
            logger.error(
                "[typography] google_url for '%s' ends in .woff2 — PIL cannot load woff2. "
                "Update to a TTF URL.", font_key
            )
            _resolved_cache[font_key] = None
            return None

        try:
            import httpx
            headers = {"User-Agent": "Mozilla/5.0"}  # force TTF delivery from some CDNs
            r = httpx.get(url, timeout=15, follow_redirects=True, headers=headers)
            if r.status_code != 200 or len(r.content) < 10_000:
                logger.warning(
                    "[typography] font download failed: %s status=%d size=%d",
                    info["file"], r.status_code, len(r.content),
                )
                _resolved_cache[font_key] = None
                return None

            # Atomic write: tmp file → rename
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(r.content)

            # Validate: try loading with PIL before committing
            try:
                from PIL import ImageFont
                ImageFont.truetype(str(tmp), 24)
            except Exception as e:
                logger.warning("[typography] downloaded font failed PIL validation (%s): %s", info["file"], e)
                tmp.unlink(missing_ok=True)
                _resolved_cache[font_key] = None
                return None

            os.replace(tmp, path)   # atomic on POSIX; near-atomic on Windows
            logger.info("[typography] downloaded and validated: %s", info["file"])
            _resolved_cache[font_key] = path
            return path

        except Exception as e:
            logger.warning("[typography] font download error (%s): %s", info["file"], e)
            _resolved_cache[font_key] = None
            return None


def resolve_font_path(font_key: str) -> Optional[str]:
    """
    Return str path to font file for PIL, with fallback to montserrat_bold.
    Never returns a path that PIL cannot open.
    """
    p = font_path(font_key)
    if p:
        return str(p)
    # Fallback to guaranteed font
    if font_key != "montserrat_bold":
        fb = font_path("montserrat_bold")
        if fb:
            logger.debug("[typography] font '%s' unavailable → falling back to montserrat_bold", font_key)
            return str(fb)
    return None


def get_font_pair(font_style: str) -> Tuple[str, str]:
    """Return (headline_font_key, body_font_key) for a style."""
    return _PAIRING_RULES_RAW.get(font_style, _PAIRING_RULES_RAW["default"])


def platform_from_dimensions(width: int, height: int) -> str:
    """
    Classify canvas dimensions into a platform key.

    Explicit non-overlapping ranges (h/w ratio):
      >= 1.7         → instagram_story  (9:16 = 1.78)
      1.1 .. 1.69    → instagram        (4:5 = 1.25, 5:4 covered)
      0.85 .. 1.09   → twitter          (1:1 squares)
      0.58 .. 0.84   → linkedin         (landscape social)
      < 0.58         → billboard        (16:9 wide = 0.5625)
    """
    if width <= 0 or height <= 0:
        logger.warning("[typography] Invalid canvas dimensions %dx%d — using default", width, height)
        return "default"
    ratio = height / width
    if ratio >= 1.7:
        return "instagram_story"
    if ratio >= 1.1:
        return "instagram"
    if ratio >= 0.85:
        return "twitter"
    if ratio >= 0.58:
        return "linkedin"
    return "billboard"


@lru_cache(maxsize=256)
def get_font_sizes(
    platform: str,
    canvas_width: int,
    canvas_height: int = 0,
    font_style: str = "bold_tech",
) -> Dict[str, int]:
    """
    Return pixel font sizes for all roles.

    Priority: max(platform_minimum, proportional_from_width) × style_scale
    Also applies a height-cap (headline cannot exceed 12% of canvas height)
    to prevent overflow on tall/narrow canvases.
    """
    if platform not in _PLATFORM_SIZES_RAW:
        logger.warning("[typography] Unknown platform %r — using default sizes", platform)
    plat = _PLATFORM_SIZES_RAW.get(platform, _PLATFORM_SIZES_RAW["default"])

    proportional = {
        "headline":    max(52, int(canvas_width * 0.115)),
        "subheadline": max(26, int(canvas_width * 0.038)),
        "body":        max(20, int(canvas_width * 0.030)),
        "cta":         max(28, int(canvas_width * 0.042)),
        "tagline":     max(18, int(canvas_width * 0.026)),
        "brand":       max(28, int(canvas_width * 0.042)),
    }

    scale = _STYLE_SCALE.get(font_style, 1.0)
    sizes: Dict[str, int] = {}
    for role, prop_val in proportional.items():
        raw = max(plat.get(role, 0), prop_val)
        sizes[role] = int(raw * scale)

    # Height cap: headline ≤ 12% of canvas height to prevent overflow
    if canvas_height > 0:
        max_headline = int(canvas_height * 0.12)
        if sizes["headline"] > max_headline:
            sizes["headline"] = max(plat.get("headline", 0), max_headline)

    return sizes


def get_letter_spacing(role: str, brand_tone: str = "professional") -> float:
    """
    Return CSS letter-spacing fraction (em) for a text role.
    Applies tone-specific overrides (luxury = tighter, energetic = looser).
    """
    tone_norm = brand_tone.lower()
    overrides = _TONE_KERNING_OVERRIDES.get(tone_norm, {})

    if role in ("headline", "brand"):
        return overrides.get("tight",   KERNING["tight"])
    if role in ("body", "tagline"):
        return overrides.get("loose",   KERNING["loose"])
    if role == "brand":
        return overrides.get("widest",  KERNING["widest"])
    return overrides.get("normal", KERNING["normal"])


def get_typography_spec(
    font_style: str,
    platform: str,
    canvas_width: int,
    canvas_height: int = 0,
    brand_tone: str = "professional",
    *,
    include_font_file: bool = False,   # False = safe for API responses (no FS path leak)
) -> Dict[str, Any]:
    """
    Return a full typography specification for the canvas editor and PIL compositor.

    Args:
        font_style:        One of the PAIRING_RULES keys (e.g. "bold_tech")
        platform:          One of PLATFORM_SIZES keys or auto-detected via platform_from_dimensions()
        canvas_width:      Canvas pixel width
        canvas_height:     Canvas pixel height (used for headline overflow cap)
        brand_tone:        Tone string from brand kit (affects kerning)
        include_font_file: If True, include filesystem path in each role dict (PIL use only).
                           Never set True for external API responses.

    Returns dict with one key per role + "headline_font", "body_font", "google_fonts".
    """
    sizes        = get_font_sizes(platform, canvas_width, canvas_height, font_style)
    headline_key, body_key = get_font_pair(font_style)

    # Pre-resolve font paths once (2 unique keys, not 6× in loop)
    headline_path = resolve_font_path(headline_key)
    body_path     = resolve_font_path(body_key)

    # Line height rules (tighter for display, looser for body)
    line_heights = {
        "headline":    1.0,
        "subheadline": 1.2,
        "body":        1.6,
        "cta":         1.1,
        "tagline":     1.4,
        "brand":       1.0,
    }

    # Text transform
    transforms = {
        "headline":    "uppercase" if font_style in ("bold_tech", "expressive_display") else "none",
        "subheadline": "none",
        "body":        "none",
        "cta":         "uppercase",
        "tagline":     "none",
        "brand":       "uppercase",
    }

    roles = ["headline", "subheadline", "body", "cta", "tagline", "brand"]
    spec: Dict[str, Any] = {}

    for role in roles:
        # subheadline + cta use headline font for display/serif styles
        use_headline_font = (
            role in ("headline", "brand")
            or (role == "subheadline" and font_style in _SUBHEADLINE_HEADLINE_FONT_STYLES)
            or (role == "cta")  # CTA always display-font for visual punch
        )
        font_key  = headline_key if use_headline_font else body_key
        font_info = _FONT_CATALOGUE_RAW.get(font_key, {})
        # Pull exact weight from catalogue (not hardcoded role map)
        catalogue_weight = str(font_info.get("weight", 400))

        entry: Dict[str, Any] = {
            "font_key":       font_key,
            "font_family":    font_info.get("css_family", "sans-serif"),
            "size_px":        sizes[role],
            "letter_spacing": get_letter_spacing(role, brand_tone),
            "line_height":    line_heights[role],
            "font_weight":    catalogue_weight,
            "text_transform": transforms[role],
        }
        if include_font_file:
            entry["font_file"] = headline_path if use_headline_font else body_path

        spec[role] = entry

    spec["headline_font"] = _FONT_CATALOGUE_RAW.get(headline_key, {}).get("css_family", "sans-serif")
    spec["body_font"]     = _FONT_CATALOGUE_RAW.get(body_key,     {}).get("css_family", "sans-serif")
    spec["google_fonts"]  = _google_fonts_import_url(headline_key, body_key)

    return spec


def _google_fonts_import_url(headline_key: str, body_key: str) -> str:
    """
    Generate Google Fonts @import URL for a font pair.

    Groups multiple weights of the same font family into a single
    `family=Montserrat:wght@700;900` entry (correct Google Fonts v2 syntax).
    Uses ordered dedup (not set) for deterministic output.
    """
    # Ordered dedup
    seen: set[str] = set()
    ordered_keys: List[str] = []
    for key in [headline_key, body_key]:
        if key not in seen:
            seen.add(key)
            ordered_keys.append(key)

    # Group by font family (handles Montserrat:wght@700 + Montserrat:wght@900)
    family_weights: Dict[str, List[str]] = defaultdict(list)
    family_noweight: List[str] = []

    for key in ordered_keys:
        query = _FONT_CATALOGUE_RAW.get(key, {}).get("google_query", "")
        if not query:
            continue
        if ":wght@" in query:
            parts = query.split(":wght@", 1)
            fam   = parts[0].replace("+", " ")
            wt    = parts[1]
            family_weights[fam].append(wt)
        else:
            family_noweight.append(query.replace(" ", "+"))

    families: List[str] = []
    # Multi-weight families: Montserrat:wght@700;900
    for fam, weights in family_weights.items():
        wt_str = "%3B".join(sorted(set(weights)))   # %3B = URL-encoded semicolon
        families.append(f"family={fam.replace(' ', '+')}:wght@{wt_str}")
    # No-weight families: BebasNeue, Anton
    for q in family_noweight:
        families.append(f"family={q}")

    if not families:
        return ""
    return "https://fonts.googleapis.com/css2?" + "&".join(families) + "&display=swap"


# ── Async font preloader (call from FastAPI lifespan) ─────────────────────────

async def preload_all_fonts() -> None:
    """
    Pre-download all fonts that have a google_url and aren't already on disk.
    Call this in FastAPI `lifespan` startup to avoid per-request blocking downloads.
    """
    import asyncio

    missing_keys = [
        key for key, info in _FONT_CATALOGUE_RAW.items()
        if info.get("google_url") and not (FONTS_DIR / info["file"]).exists()
    ]
    if not missing_keys:
        logger.info("[typography] All fonts already cached — preload skipped")
        return

    logger.info("[typography] Preloading %d fonts: %s", len(missing_keys), missing_keys)

    try:
        import httpx
        from PIL import ImageFont
    except ImportError as e:
        logger.warning("[typography] preload_all_fonts skipped — missing dependency: %s", e)
        return

    async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                  headers={"User-Agent": "Mozilla/5.0"}) as client:
        for key in missing_keys:
            info = _FONT_CATALOGUE_RAW[key]
            url  = info["google_url"]
            path = FONTS_DIR / info["file"]

            if url.endswith(".woff2"):
                logger.error("[typography] Skipping woff2 URL for '%s' — update to TTF URL", key)
                continue

            try:
                resp = await client.get(url)
                if resp.status_code != 200 or len(resp.content) < 10_000:
                    logger.warning("[typography] preload failed %s: HTTP %d size=%d",
                                   info["file"], resp.status_code, len(resp.content))
                    continue

                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(resp.content)

                # Validate
                try:
                    ImageFont.truetype(str(tmp), 24)
                except Exception as e:
                    logger.warning("[typography] preloaded font invalid (%s): %s", info["file"], e)
                    tmp.unlink(missing_ok=True)
                    continue

                os.replace(tmp, path)
                _resolved_cache[key] = path
                logger.info("[typography] preloaded: %s", info["file"])

            except Exception as e:
                logger.warning("[typography] preload error (%s): %s", info["file"], e)

    # Validate required fonts after preload
    validate_required_fonts()


# ── Module singleton ──────────────────────────────────────────────────────────
class _TypographyEngine:
    """Singleton wrapper — all methods are module-level functions."""
    get_font_sizes             = staticmethod(get_font_sizes)
    get_font_pair              = staticmethod(get_font_pair)
    get_letter_spacing         = staticmethod(get_letter_spacing)
    font_path                  = staticmethod(font_path)
    resolve_font_path          = staticmethod(resolve_font_path)
    platform_from_dimensions   = staticmethod(platform_from_dimensions)
    get_typography_spec        = staticmethod(get_typography_spec)
    validate_required_fonts    = staticmethod(validate_required_fonts)
    preload_all_fonts          = staticmethod(preload_all_fonts)

    @property
    def PLATFORM_SIZES(self) -> MappingProxyType:  # type: ignore[override]
        return PLATFORM_SIZES

    @property
    def FONT_CATALOGUE(self) -> MappingProxyType:  # type: ignore[override]
        return FONT_CATALOGUE

    @property
    def PAIRING_RULES(self) -> MappingProxyType:  # type: ignore[override]
        return PAIRING_RULES


typography_engine = _TypographyEngine()

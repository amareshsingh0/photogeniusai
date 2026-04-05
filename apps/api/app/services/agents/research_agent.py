"""
Brand Research Agent — Sprint 5B

Scrapes a website URL and extracts brand identity signals:
  - Brand name (og:site_name, title, meta)
  - Logo URL (og:image, link[rel=icon], largest img)
  - Primary + secondary colors (meta theme-color, CSS vars, colorthief dominant)
  - Font guess (body/h1 font-family CSS)
  - Brand tone inference (content analysis)

POST /api/v1/agents/research-brand
Body: { url: str }
Returns: { brand_name, logo_url, primary_color, secondary_color, font_guess, tone, source_url }
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

# ── Optional dependencies (graceful fallback if not installed) ─────────────────
try:
    from bs4 import BeautifulSoup
    _BS4 = True
except ImportError:
    _BS4 = False
    logger.warning("beautifulsoup4 not installed — brand research will be limited")

try:
    from colorthief import ColorThief
    import io
    _COLORTHIEF = True
except ImportError:
    _COLORTHIEF = False
    logger.warning("colorthief not installed — dominant color extraction disabled")


# ── Regex helpers ──────────────────────────────────────────────────────────────
_HEX_RE    = re.compile(r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b')
_CSS_VAR_RE = re.compile(r'--(?:primary|brand|main|accent|color)[^:]*:\s*(#[0-9A-Fa-f]{3,6})', re.I)
_FONT_RE   = re.compile(r'font-family\s*:\s*([^\";}{]+)', re.I)
_RGB_RE    = re.compile(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)')

# Tone keyword mappings
_TONE_KEYWORDS: dict[str, list[str]] = {
    "luxury":       ["luxury", "premium", "exclusive", "elite", "bespoke", "couture", "prestige"],
    "playful":      ["fun", "playful", "delight", "joy", "kids", "colorful", "game", "smile"],
    "energetic":    ["energy", "power", "bold", "dynamic", "sport", "fitness", "fast", "drive"],
    "trustworthy":  ["trust", "secure", "safe", "reliable", "guarantee", "certified", "proven"],
    "casual":       ["simple", "easy", "friendly", "everyday", "casual", "relax", "fresh"],
    "professional": ["professional", "enterprise", "business", "corporate", "solution", "platform"],
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PhotoGeniusBot/1.0; +https://photogenius.ai/bot)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _expand_short_hex(h: str) -> str:
    """Expand #ABC → #AABBCC."""
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return f"#{h.upper()}"


def _infer_tone(text: str) -> str:
    """Infer brand tone from page text content."""
    text_lower = text.lower()
    scores: dict[str, int] = {tone: 0 for tone in _TONE_KEYWORDS}
    for tone, keywords in _TONE_KEYWORDS.items():
        for kw in keywords:
            scores[tone] += text_lower.count(kw)
    best = max(scores, key=lambda t: scores[t])
    return best if scores[best] > 0 else "professional"


def _guess_font(css_text: str) -> str:
    """Extract dominant font-family from inline/embedded CSS."""
    matches = _FONT_RE.findall(css_text)
    for m in matches:
        font = m.strip().strip("'\"").split(",")[0].strip()
        if font and len(font) > 2 and font.lower() not in ("inherit", "initial", "unset", "sans-serif", "serif", "monospace"):
            return font
    return "Inter"


def _extract_colors_from_css(css_text: str) -> list[str]:
    """Extract hex colors from CSS (CSS vars first, then all hex)."""
    colors: list[str] = []

    # Prefer CSS variable patterns (--primary, --brand, --main, --accent)
    for m in _CSS_VAR_RE.finditer(css_text):
        colors.append(_expand_short_hex(m.group(1)))

    # Fall back to all hex colors if we found nothing
    if not colors:
        for m in _HEX_RE.finditer(css_text):
            c = _expand_short_hex(m.group(0))
            # Skip white/black/near-gray
            h = c.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            if max(r, g, b) - min(r, g, b) > 30:  # has hue
                colors.append(c)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in colors:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique[:10]


async def _get_dominant_colors(image_url: str, base_url: str) -> list[str]:
    """Download an image and extract dominant colors via colorthief."""
    if not _COLORTHIEF:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
            resp = await client.get(image_url, follow_redirects=True)
            if resp.status_code != 200:
                return []
        img_bytes = io.BytesIO(resp.content)
        ct = ColorThief(img_bytes)
        palette = ct.get_palette(color_count=3, quality=5)
        return [_rgb_to_hex(*c) for c in palette]
    except Exception as e:
        logger.debug("colorthief error for %s: %s", image_url, e)
        return []


async def research_brand(url: str) -> dict:
    """
    Scrape `url` and return brand identity signals.

    Returns dict with keys:
      brand_name, logo_url, primary_color, secondary_color,
      font_guess, tone, source_url, success, error (if failed)
    """
    if not _BS4:
        return {
            "success": False,
            "error": "beautifulsoup4 not installed on server. Run: pip install beautifulsoup4 colorthief",
            "source_url": url,
        }

    # Normalise URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}", "source_url": url}
            html = resp.text
    except httpx.TimeoutException:
        return {"success": False, "error": "Request timed out", "source_url": url}
    except Exception as e:
        return {"success": False, "error": str(e), "source_url": url}

    soup = BeautifulSoup(html, "html.parser")

    # ── Brand name ────────────────────────────────────────────────────────────
    brand_name = ""
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        brand_name = og_site["content"].strip()
    if not brand_name:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            brand_name = og_title["content"].split("|")[0].split("–")[0].split("-")[0].strip()
    if not brand_name:
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            brand_name = title_tag.string.split("|")[0].split("–")[0].split("-")[0].strip()

    # ── Logo URL ──────────────────────────────────────────────────────────────
    logo_url = ""
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        logo_url = urljoin(base_url, og_image["content"])
    if not logo_url:
        # apple-touch-icon or shortcut icon
        icon = soup.find("link", rel=lambda r: r and any(x in r for x in ("apple-touch-icon", "icon")))
        if icon and icon.get("href"):
            logo_url = urljoin(base_url, icon["href"])
    if not logo_url:
        # Try /favicon.ico
        logo_url = f"{base_url}/favicon.ico"

    # ── Colors ────────────────────────────────────────────────────────────────
    primary_color   = "#6366F1"  # default indigo
    secondary_color = "#8B5CF6"

    # 1. meta theme-color
    theme_meta = soup.find("meta", attrs={"name": "theme-color"})
    if theme_meta and theme_meta.get("content"):
        val = theme_meta["content"].strip()
        if val.startswith("#"):
            primary_color = _expand_short_hex(val)

    # 2. Inline <style> / <link rel=stylesheet> CSS
    css_colors: list[str] = []
    for style_tag in soup.find_all("style"):
        if style_tag.string:
            css_colors.extend(_extract_colors_from_css(style_tag.string))
    if css_colors:
        primary_color   = css_colors[0]
        secondary_color = css_colors[1] if len(css_colors) > 1 else secondary_color

    # 3. colorthief on OG/logo image as fallback
    if not css_colors and logo_url:
        dom_colors = await _get_dominant_colors(logo_url, base_url)
        if dom_colors:
            primary_color   = dom_colors[0]
            secondary_color = dom_colors[1] if len(dom_colors) > 1 else secondary_color

    # ── Font guess ────────────────────────────────────────────────────────────
    font_guess = "Inter"
    for style_tag in soup.find_all("style"):
        if style_tag.string:
            font = _guess_font(style_tag.string)
            if font and font != "Inter":
                font_guess = font
                break

    # ── Tone inference ────────────────────────────────────────────────────────
    page_text = soup.get_text(separator=" ", strip=True)[:5000]
    tone = _infer_tone(page_text)

    return {
        "success":         True,
        "brand_name":      brand_name[:80] if brand_name else "",
        "logo_url":        logo_url,
        "primary_color":   primary_color,
        "secondary_color": secondary_color,
        "font_guess":      font_guess,
        "tone":            tone,
        "source_url":      url,
    }

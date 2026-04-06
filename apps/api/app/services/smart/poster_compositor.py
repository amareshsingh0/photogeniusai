"""
PosterCompositor — PIL-based structured poster builder.

Takes a hero background image + Gemini ad_copy/poster_design JSON
and builds a FULL structured poster with:

  Zone 1 — Brand bar (top strip): brand name
  Zone 2 — Hero image: background scene (top 55-65% of canvas)
  Zone 3 — Headline + subheadline: large bold type
  Zone 4 — Feature grid: 2-col pill/card layout (gated by has_feature_grid)
  Zone 5 — CTA section: pill button + URL (gated by has_cta_button)
  Zone 6 — Footer strip: tagline

Output: base64 JPEG at full resolution (width × computed_height)
"""
from __future__ import annotations

import base64
import io
import logging
import math
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

logger = logging.getLogger(__name__)

MAX_CANVAS_H = 4096
MIN_CANVAS_W  = 512

# Import typography engine — single source of truth for fonts + sizes
from app.services.smart.typography_engine import (
    resolve_font_path,
    get_font_sizes,
    get_font_pair,
    platform_from_dimensions,
)


# ── Font loading with LRU cache (no repeated disk I/O) ───────────────────────

@lru_cache(maxsize=128)
def _load_font_cached(path_str: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path_str, size)


def _font(font_key: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Load font by typography_engine key (e.g. "bebas_neue", "montserrat_bold").
    Falls back through montserrat_bold → PIL default.
    """
    path_str = resolve_font_path(font_key)
    if path_str:
        try:
            return _load_font_cached(path_str, size)
        except Exception as e:
            logger.debug("[compositor] font load failed %s size=%d: %s", font_key, size, e)

    # Fallback: PIL default
    if not getattr(_font, "_warned", False):
        _font._warned = True  # type: ignore[attr-defined]
        logger.warning("[compositor] No usable font for key %r — PIL default used", font_key)
    return ImageFont.load_default()


# ── Color helpers ─────────────────────────────────────────────────────────────

def _parse_hex(hex_str: object, fallback: Tuple[int,int,int] = (255,255,255)) -> Tuple[int,int,int]:
    """Parse #RRGGBB or #RGB. Handles None safely."""
    if not hex_str or not isinstance(hex_str, str):
        return fallback
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c*2 for c in s)
    if len(s) == 6:
        try:
            return (int(s[0:2],16), int(s[2:4],16), int(s[4:6],16))
        except ValueError:
            pass
    return fallback


def _luminance(rgb: Tuple[int,int,int]) -> float:
    def _lin(c: int) -> float:
        s = c / 255.0
        return s/12.92 if s <= 0.04045 else ((s+0.055)/1.055)**2.4
    return 0.2126*_lin(rgb[0]) + 0.7152*_lin(rgb[1]) + 0.0722*_lin(rgb[2])


def _wcag_contrast(fg: Tuple[int,int,int], bg: Tuple[int,int,int]) -> float:
    """WCAG 2.1 contrast ratio."""
    l1, l2 = sorted([_luminance(fg), _luminance(bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _contrast_color(bg: Tuple[int,int,int]) -> Tuple[int,int,int]:
    """Return white or near-black for best WCAG contrast against bg."""
    white = (255, 255, 255)
    black = (15, 15, 20)
    return white if _wcag_contrast(white, bg) >= _wcag_contrast(black, bg) else black


# ── Text helpers ──────────────────────────────────────────────────────────────

def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int,int]:
    if not text:
        return 0, 0
    bbox = draw.textbbox((0,0), text, font=font)
    return bbox[2]-bbox[0], bbox[3]-bbox[1]


def _text_width_multiline(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """Max width across all lines of wrapped text."""
    if not text:
        return 0
    return max(_text_size(draw, line, font)[0] for line in text.split("\n") if line)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    """Word-wrap text to max_w pixels. Force-appends words that are wider than max_w."""
    words = (text or "").split()
    if not words:
        return ""
    lines, cur = [], words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        bbox = draw.textbbox((0,0), test, font=font)
        if (bbox[2]-bbox[0]) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return "\n".join(lines)


def _draw_text_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    canvas_w: int,
    y: int,
    fill: Tuple,
    shadow: bool = False,
    shadow_color: Tuple = (0, 0, 0, 140),
    shadow_offset: int = 3,
) -> None:
    """Draw centered multiline text with optional drop shadow."""
    if not text:
        return
    x = canvas_w // 2
    if shadow:
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            text, font=font, fill=shadow_color, anchor="mt", align="center",
        )
    draw.text((x, y), text, font=font, fill=fill, anchor="mt", align="center")


def _rounded_rect(draw: ImageDraw.ImageDraw, xy: Tuple, radius: int, fill: Tuple) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0,y0,x1,y1], radius=radius, fill=fill)


# ── Gradient fade helper (vectorized, not per-pixel loop) ─────────────────────

def _make_gradient_fade(
    width: int,
    height: int,
    fade_start_frac: float,
    bg_color: Tuple[int,int,int],
) -> Image.Image:
    """
    Returns an RGBA image (same size as hero) where the bottom portion
    fades from transparent to bg_color. Uses resize instead of pixel loop.
    """
    fade_start = int(height * fade_start_frac)
    fade_h = max(1, height - fade_start)

    # 1-px wide gradient, then resize to full width
    grad = Image.new("L", (1, fade_h))
    for py in range(fade_h):
        alpha = int(255 * py / fade_h)
        grad.putpixel((0, py), alpha)
    grad = grad.resize((width, fade_h), Image.Resampling.BILINEAR)

    # Build full-height RGBA: transparent above fade_start, gradient below
    fade_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    color_layer = Image.new("RGBA", (width, fade_h), bg_color + (255,))
    color_layer.putalpha(grad)
    fade_img.paste(color_layer, (0, fade_start), color_layer)
    return fade_img


# ══════════════════════════════════════════════════════════════════════════════
# Main compositor
# ══════════════════════════════════════════════════════════════════════════════

class PosterCompositor:
    """
    Build a structured multi-zone poster from a background image + ad_copy.

    Stateless by design — all state is local to composite().
    """

    def composite(
        self,
        hero_b64: str,
        ad_copy: Dict,
        poster_design: Optional[Dict],
        target_width: int = 1024,
        target_height: int = 1536,
    ) -> str:
        """
        Returns base64 JPEG of the fully composited poster.
        Raises ValueError on bad input (caller should catch).
        """
        # ── Input validation ──────────────────────────────────────────────────
        if not hero_b64:
            raise ValueError("hero_b64 is empty")
        if target_width < MIN_CANVAS_W:
            raise ValueError(f"target_width {target_width} below minimum {MIN_CANVAS_W}")

        # Decode hero image (fail fast, before expensive layout computation)
        try:
            hero_bytes = base64.b64decode(hero_b64)
            hero_img = Image.open(io.BytesIO(hero_bytes))
            hero_img.load()   # force decode now to catch corrupt images early
            hero_img = hero_img.convert("RGBA")
        except Exception as e:
            raise ValueError(f"Invalid hero image data: {e}") from e

        # ── Parse design tokens (all null-safe) ───────────────────────────────
        pd = poster_design or {}
        ad = ad_copy if isinstance(ad_copy, dict) else {}

        accent     = _parse_hex(pd.get("accent_color"),       (108, 99, 255))
        bg_color   = _parse_hex(pd.get("bg_color"),           ( 10, 10, 26))
        txt_pri    = _parse_hex(pd.get("text_color_primary"),  (255,255,255))
        txt_sec    = _parse_hex(pd.get("text_color_secondary"),(200,200,220))
        font_style = pd.get("font_style") or "bold_tech"
        has_features_flag = pd.get("has_feature_grid")
        has_features_flag = has_features_flag if has_features_flag is not None else True
        has_cta_flag = pd.get("has_cta_button")
        has_cta_flag = has_cta_flag if has_cta_flag is not None else True
        hero_zone  = pd.get("hero_occupies") or "top_60"

        accent_text = _contrast_color(accent)
        btn_radius  = target_width // 20
        card_radius = target_width // 30

        # ── Font selection via typography_engine (single source of truth) ───────
        # get_font_pair returns (headline_key, body_key) from PAIRING_RULES
        f_headline, f_body = get_font_pair(font_style)

        W = target_width
        PAD = int(W * 0.055)
        inner_w = W - 2 * PAD

        # ── Extract content (all null-safe) ───────────────────────────────────
        brand_name  = str(ad.get("brand_name")  or "").strip()
        logo_url    = str(ad.get("logo_url")    or "").strip()
        headline    = str(ad.get("headline")    or "").strip().upper()
        subheadline = str(ad.get("subheadline") or "").strip()
        body_text   = str(ad.get("body")        or "").strip()
        cta_text    = str(ad.get("cta")         or "GET STARTED").strip().upper()
        cta_url     = str(ad.get("cta_url")     or "").strip()
        tagline     = str(ad.get("tagline")     or "").strip()

        # Fetch logo image if URL provided (non-fatal)
        logo_img: Optional[Image.Image] = None
        if logo_url:
            try:
                import httpx as _httpx
                _resp = _httpx.get(logo_url, timeout=5.0, follow_redirects=True)
                _resp.raise_for_status()
                logo_img = Image.open(io.BytesIO(_resp.content)).convert("RGBA")
                logger.info("[compositor] logo loaded from %s (%dx%d)", logo_url, logo_img.width, logo_img.height)
            except Exception as _e:
                logger.warning("[compositor] logo fetch failed (%s): %s", logo_url, _e)
                logo_img = None

        # Features: must be list of dicts with at least "title"
        raw_features = ad.get("features") or []
        features: List[Dict] = [
            f for f in raw_features
            if isinstance(f, dict) and (f.get("title") or f.get("icon"))
        ]

        # Apply design flags
        if not has_features_flag:
            features = []
        show_cta = has_cta_flag and bool(cta_text)

        # ── Font sizes via typography_engine (no duplication) ─────────────────
        # Detect platform from canvas dimensions for correct minimum sizes
        platform = platform_from_dimensions(target_width, target_height)
        typo_sizes = get_font_sizes(platform, W, target_height, font_style)

        sz_brand    = typo_sizes["brand"]
        sz_headline = typo_sizes["headline"]
        sz_sub      = typo_sizes["subheadline"]
        sz_body     = typo_sizes["body"]
        sz_cta      = typo_sizes["cta"]
        sz_tagline  = typo_sizes["tagline"]
        # Feature card sizes: body-proportional (not in PLATFORM_SIZES, keep local)
        sz_feat_ttl = max(22, int(W * 0.032))
        sz_feat_dsc = max(18, int(W * 0.026))
        sz_url      = max(18, int(W * 0.025))

        # Load fonts via typography_engine key (cached — no repeated disk I/O)
        fn_brand    = _font(f_headline, sz_brand)
        fn_headline = _font(f_headline, sz_headline)
        fn_sub      = _font(f_body,     sz_sub)
        fn_body     = _font(f_body,     sz_body)
        fn_feat_ttl = _font(f_body,     sz_feat_ttl)
        fn_feat_dsc = _font(f_body,     sz_feat_dsc)
        fn_cta      = _font(f_headline, sz_cta)
        fn_url      = _font(f_body,     sz_url)
        fn_tagline  = _font(f_body,     sz_tagline)

        GAP = int(W * 0.035)
        SECTION_PAD = int(W * 0.05)

        # ── Pre-measure text on temp canvas ───────────────────────────────────
        tmp = Image.new("RGBA", (1, 1))
        d = ImageDraw.Draw(tmp)

        hl_wrapped  = _wrap(d, headline,    fn_headline, inner_w) if headline else ""
        sub_wrapped = _wrap(d, subheadline, fn_sub,      inner_w) if subheadline else ""
        body_wrapped= _wrap(d, body_text,   fn_body,     inner_w) if body_text else ""

        _, hl_h   = _text_size(d, hl_wrapped,  fn_headline)
        _, sub_h  = _text_size(d, sub_wrapped, fn_sub)
        _, body_h = _text_size(d, body_wrapped,fn_body) if body_wrapped else (0, 0)

        del tmp, d  # free measurement canvas

        # ══════════════════════════════════════════════════════════════════════
        # FULL-BLEED LAYOUT — canvas = target_height, hero fills 100%, text on top
        # NO separate zones below — everything overlaid directly on hero image
        # ══════════════════════════════════════════════════════════════════════

        canvas_h = min(target_height, MAX_CANVAS_H)
        canvas = Image.new("RGBA", (W, canvas_h), (0, 0, 0, 255))
        draw = ImageDraw.Draw(canvas)

        # ── Step 1: Hero image fills entire canvas ────────────────────────────
        hero_resized = ImageOps.fit(
            hero_img, (W, canvas_h),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.40),
        )
        canvas.paste(hero_resized.convert("RGBA"), (0, 0))

        # ── Step 2: Gradient overlays ─────────────────────────────────────────
        def _grad_overlay(w: int, h: int, top_a: int, bot_a: int,
                          color: Tuple[int,int,int]) -> Image.Image:
            """Linear gradient from top_a to bot_a alpha, full width."""
            col = Image.new("RGBA", (1, h))
            for py in range(h):
                a = int(top_a + (bot_a - top_a) * py / max(h - 1, 1))
                col.putpixel((0, py), color + (a,))
            return col.resize((w, h), Image.Resampling.BILINEAR)

        # Bottom gradient — transparent at 35% → solid dark at bottom
        # Covers lower 70% of canvas for text readability
        bot_h = int(canvas_h * 0.70)
        bot_y = canvas_h - bot_h
        canvas.alpha_composite(_grad_overlay(W, bot_h, 0, 220, bg_color), (0, bot_y))

        # Top vignette — thin dark strip for brand bar
        top_h = int(canvas_h * 0.14)
        canvas.alpha_composite(_grad_overlay(W, top_h, 180, 0, (0, 0, 0)), (0, 0))

        draw = ImageDraw.Draw(canvas)
        shadow_off = max(3, sz_headline // 16)

        # ── Step 3: Brand bar (top strip) ────────────────────────────────────
        if brand_name or logo_img:
            bar_h = int(canvas_h * 0.07)
            # Accent left stripe
            draw.rectangle([0, 0, max(5, W // 90), bar_h], fill=accent + (220,))

            if logo_img:
                lh = int(bar_h * 0.62)
                lw = int(lh * logo_img.width / max(logo_img.height, 1))
                lw = min(lw, W // 4)
                logo_r = logo_img.resize((lw, lh), Image.Resampling.LANCZOS)
                canvas.paste(logo_r, (PAD, (bar_h - lh) // 2), logo_r)
                if brand_name:
                    draw.text(
                        (PAD + lw + PAD // 2, (bar_h - sz_brand) // 2),
                        brand_name, font=fn_brand, fill=(255, 255, 255, 220),
                    )
            else:
                bw, bh = _text_size(draw, brand_name, fn_brand)
                draw.text(
                    (PAD, (bar_h - bh) // 2),
                    brand_name, font=fn_brand, fill=(255, 255, 255, 220),
                )

        # ── Step 4: Main text block — positioned at 52%–78% of canvas ────────
        # Headline starts at 52%, subheadline + body below, CTA pinned at 82%
        ty = int(canvas_h * 0.52)

        if hl_wrapped:
            _draw_text_centered(
                draw, hl_wrapped, fn_headline, W, ty, txt_pri + (255,),
                shadow=True, shadow_offset=shadow_off,
                shadow_color=(0, 0, 0, 200),
            )
            ty += hl_h + GAP // 3

            # Accent underline bar
            line_h = max(4, sz_headline // 20)
            ul_w = min(inner_w, int(W * 0.55))
            draw.rectangle(
                [(W - ul_w) // 2, ty, (W + ul_w) // 2, ty + line_h],
                fill=accent + (255,),
            )
            ty += line_h + GAP // 3

        if sub_wrapped:
            _draw_text_centered(
                draw, sub_wrapped, fn_sub, W, ty, txt_sec + (240,),
                shadow=True, shadow_offset=max(2, shadow_off // 2),
                shadow_color=(0, 0, 0, 180),
            )
            ty += sub_h + GAP // 3

        if body_wrapped:
            _draw_text_centered(
                draw, body_wrapped, fn_body, W, ty, txt_sec + (200,),
                shadow=True, shadow_offset=2, shadow_color=(0, 0, 0, 150),
            )
            ty += body_h + GAP // 4

        # ── Step 5: CTA button — pinned at 82% canvas height ─────────────────
        if show_cta:
            cta_btn_h = int(sz_cta * 1.9)
            btn_w = min(int(W * 0.68), inner_w)
            cta_y = max(ty + GAP, int(canvas_h * 0.82))
            btn_x = (W - btn_w) // 2

            # Drop shadow
            shd = Image.new("RGBA", (btn_w + 16, cta_btn_h + 16), (0, 0, 0, 0))
            shd_d = ImageDraw.Draw(shd)
            shd_d.rounded_rectangle(
                [8, 8, btn_w + 8, cta_btn_h + 8],
                radius=btn_radius, fill=(0, 0, 0, 120),
            )
            shd = shd.filter(ImageFilter.GaussianBlur(8))
            canvas.alpha_composite(shd, (btn_x - 8, cta_y - 8))

            _rounded_rect(
                draw, (btn_x, cta_y, btn_x + btn_w, cta_y + cta_btn_h),
                btn_radius, accent + (255,),
            )
            cta_label = _wrap(draw, cta_text, fn_cta, btn_w - 40)
            clw, clh = _text_size(draw, cta_label, fn_cta)
            draw.text(
                (btn_x + (btn_w - clw) // 2, cta_y + (cta_btn_h - clh) // 2),
                cta_label, font=fn_cta, fill=accent_text + (255,),
            )

            if cta_url:
                url_disp = cta_url if len(cta_url) <= 40 else cta_url[:37] + "..."
                uw, uh = _text_size(draw, url_disp, fn_url)
                draw.text(
                    ((W - uw) // 2, cta_y + cta_btn_h + GAP // 3),
                    url_disp, font=fn_url, fill=(255, 255, 255, 120),
                )

        # ── Step 6: Tagline — bottom edge ────────────────────────────────────
        if tagline:
            tg_w, tg_h = _text_size(draw, tagline, fn_tagline)
            draw.text(
                ((W - tg_w) // 2, canvas_h - tg_h - int(GAP * 0.7)),
                tagline, font=fn_tagline, fill=(255, 255, 255, 130),
            )

        # ── Encode output ─────────────────────────────────────────────────────
        final = canvas.crop((0, 0, W, canvas_h))
        bg_flat = Image.new("RGB", final.size, bg_color)
        bg_flat.paste(final.convert("RGBA"), mask=final.convert("RGBA").split()[3])

        buf = io.BytesIO()
        bg_flat.save(buf, format="JPEG", quality=95, optimize=True)
        result_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        logger.info(
            "[compositor] built poster w=%d h=%d cta=%s",
            W, canvas_h, show_cta,
        )
        return result_b64


# Singleton — stateless by design
poster_compositor = PosterCompositor()

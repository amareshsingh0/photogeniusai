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

        # ── Hero height ────────────────────────────────────────────────────────
        hero_h_map = {
            "top_60":    int(target_height * 0.58),
            "top_58":    int(target_height * 0.56),   # 4:5 ratio (1080×1350)
            "top_55":    int(target_height * 0.53),
            "top_50":    int(target_height * 0.50),
            "center_50": int(target_height * 0.50),
            "full_bleed":int(target_height * 0.65),
            "top_40":    int(target_height * 0.40),
        }
        hero_h = hero_h_map.get(hero_zone, int(target_height * 0.58))

        # ── Feature grid geometry ──────────────────────────────────────────────
        feat_cols = 2
        feat_rows = math.ceil(len(features) / feat_cols) if features else 0
        feat_card_w = (inner_w - GAP) // feat_cols
        feat_card_h = int(W * 0.26) if features else 0  # approximate; see actual drawing

        # ── Section height estimates ──────────────────────────────────────────
        BRAND_BAR_H = int(W * 0.10) if (brand_name or logo_url) else 0
        sl_h = int(W * 0.026) + 4 if features else 0  # "KEY FEATURES" label

        text_section_h = (
            SECTION_PAD
            + (hl_h + GAP // 2 if hl_wrapped else 0)
            + (sub_h if sub_wrapped else 0)
            + (GAP // 2 + body_h if body_wrapped else 0)
            + SECTION_PAD
        )

        features_section_h = (
            GAP + sl_h + GAP // 2
            + (feat_card_h + GAP // 2) * feat_rows + GAP // 2
        ) if features else 0

        cta_h = int(sz_cta * 1.8)
        cta_section_h = (
            GAP + cta_h
            + (GAP // 2 + int(sz_url * 1.5) if cta_url else 0)
            + GAP
        ) if show_cta else GAP

        tagline_h = (GAP + int(sz_tagline * 1.4) + GAP // 2) if tagline else 0

        total_h = min(
            BRAND_BAR_H + hero_h + text_section_h + features_section_h + cta_section_h + tagline_h + GAP,
            MAX_CANVAS_H,
        )
        if total_h < 100:
            total_h = target_height

        # ── Create canvas (oversized by 20% to prevent crop truncation) ────────
        canvas_h = min(int(total_h * 1.2), MAX_CANVAS_H)
        canvas = Image.new("RGBA", (W, canvas_h), bg_color + (255,))
        draw = ImageDraw.Draw(canvas)
        y = 0

        # ── Zone 1: Brand bar ─────────────────────────────────────────────────
        if (brand_name or logo_img) and BRAND_BAR_H > 0:
            draw.rectangle([0, 0, W, BRAND_BAR_H], fill=accent + (255,))

            if logo_img:
                # Fit logo inside brand bar with padding, left-aligned
                logo_bar_h = int(BRAND_BAR_H * 0.65)
                logo_bar_w = int(logo_bar_h * (logo_img.width / max(logo_img.height, 1)))
                logo_bar_w = min(logo_bar_w, W // 3)  # cap at 1/3 canvas width
                logo_resized = logo_img.resize(
                    (logo_bar_w, logo_bar_h), Image.Resampling.LANCZOS
                )
                logo_x = PAD
                logo_y = (BRAND_BAR_H - logo_bar_h) // 2
                canvas.paste(logo_resized, (logo_x, logo_y), logo_resized)

                # Brand name to the right of logo (if both present)
                if brand_name:
                    text_x = logo_x + logo_bar_w + PAD // 2
                    brand_wrapped = _wrap(draw, brand_name, fn_brand, W - text_x - PAD)
                    _, bh = _text_size(draw, brand_wrapped, fn_brand)
                    draw.text(
                        (text_x, (BRAND_BAR_H - bh) // 2),
                        brand_wrapped, font=fn_brand, fill=accent_text + (255,),
                    )
            else:
                # No logo — centered brand name
                brand_wrapped = _wrap(draw, brand_name, fn_brand, inner_w)
                _, bh = _text_size(draw, brand_wrapped, fn_brand)
                _draw_text_centered(
                    draw, brand_wrapped, fn_brand, W,
                    (BRAND_BAR_H - bh) // 2, accent_text + (255,),
                )
            y = BRAND_BAR_H

        # ══════════════════════════════════════════════════════════════════════
        # FULL-BLEED LAYOUT — image fills entire canvas, text overlaid on top
        # This replaces the old "split zone" (image top 60% + dark panel below)
        # ══════════════════════════════════════════════════════════════════════

        canvas_full_h = total_h
        canvas = Image.new("RGBA", (W, min(int(canvas_full_h * 1.05), MAX_CANVAS_H)), (0, 0, 0, 255))
        canvas_h = canvas.height
        draw = ImageDraw.Draw(canvas)

        # ── Step 1: Hero image fills entire canvas ────────────────────────────
        hero_resized = ImageOps.fit(
            hero_img, (W, canvas_h),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.35),
        )
        canvas.paste(hero_resized.convert("RGBA"), (0, 0))

        # ── Step 2: Gradient overlays for text readability ────────────────────
        # Bottom gradient: transparent → dark (text zone)
        def _make_overlay(w: int, h: int, top_alpha: int, bot_alpha: int,
                          color: Tuple[int,int,int]) -> Image.Image:
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            for py in range(h):
                a = int(top_alpha + (bot_alpha - top_alpha) * py / max(h - 1, 1))
                overlay.putpixel((0, py), color + (a,))
            overlay = overlay.resize((w, h), Image.Resampling.BILINEAR)
            return overlay

        # Bottom 65% — dark gradient for text zone
        bot_zone_h = int(canvas_h * 0.72)
        bot_zone_y = canvas_h - bot_zone_h
        bot_overlay = _make_overlay(W, bot_zone_h, 0, 210, bg_color)
        canvas.alpha_composite(bot_overlay, (0, bot_zone_y))

        # Top strip — subtle dark for brand bar readability
        top_overlay = _make_overlay(W, int(canvas_h * 0.18), 160, 0, bg_color)
        canvas.alpha_composite(top_overlay, (0, 0))

        draw = ImageDraw.Draw(canvas)
        shadow_offset = max(3, sz_headline // 18)

        # ── Step 3: Brand bar (top) ───────────────────────────────────────────
        y = 0
        if brand_name or logo_img:
            bar_h = int(canvas_h * 0.075)
            # Accent left stripe
            draw.rectangle([0, 0, max(6, W // 80), bar_h], fill=accent + (230,))

            if logo_img:
                lh = int(bar_h * 0.60)
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
                    ((W - bw) // 2, (bar_h - bh) // 2),
                    brand_name, font=fn_brand, fill=(255, 255, 255, 220),
                )
            y = bar_h + GAP // 2

        # ── Step 4: Headline + subheadline (lower-center of image) ───────────
        # Position text block starting at ~52% of canvas height
        text_start_y = max(y + GAP, int(canvas_h * 0.50))
        ty = text_start_y

        if hl_wrapped:
            # Strong text shadow for contrast on any background
            _draw_text_centered(
                draw, hl_wrapped, fn_headline, W, ty, txt_pri + (255,),
                shadow=True, shadow_offset=shadow_offset,
                shadow_color=(0, 0, 0, 180),
            )
            ty += hl_h + GAP // 3

            # Accent underline
            line_h = max(4, sz_headline // 18)
            ul_w = min(inner_w, _text_width_multiline(draw, hl_wrapped, fn_headline) + PAD)
            draw.rectangle(
                [(W - ul_w) // 2, ty,
                 (W + ul_w) // 2, ty + line_h],
                fill=accent + (255,),
            )
            ty += line_h + GAP // 3

        if sub_wrapped:
            _draw_text_centered(
                draw, sub_wrapped, fn_sub, W, ty, txt_sec + (240,),
                shadow=True, shadow_offset=max(2, shadow_offset // 2),
                shadow_color=(0, 0, 0, 160),
            )
            ty += sub_h + GAP // 4

        if body_wrapped:
            _draw_text_centered(
                draw, body_wrapped, fn_body, W, ty, txt_sec + (200,),
                shadow=True, shadow_offset=2, shadow_color=(0, 0, 0, 140),
            )
            ty += body_h + GAP // 4

        ty += GAP // 2

        # ── Step 5: Feature chips (compact horizontal rows on image) ─────────
        if features:
            chip_font  = _font(f_body, max(18, int(W * 0.025)))
            chip_pad_x = int(W * 0.028)
            chip_pad_y = int(W * 0.016)
            chip_gap   = int(W * 0.018)
            chip_r     = int(W * 0.025)

            # Measure all chips first to layout 2-per-row
            chip_sizes = []
            for feat in features[:4]:
                icon_s  = str(feat.get("icon") or "•").strip()
                title_s = str(feat.get("title") or "").strip()
                label   = f"{icon_s}  {title_s}" if icon_s and title_s else title_s or icon_s
                cw, ch  = _text_size(draw, label, chip_font)
                chip_sizes.append((label, cw + chip_pad_x * 2, ch + chip_pad_y * 2))

            # Lay out 2 chips per row
            for row_i in range(0, len(chip_sizes), 2):
                row_chips = chip_sizes[row_i: row_i + 2]
                total_row_w = sum(c[1] for c in row_chips) + chip_gap * (len(row_chips) - 1)
                rx = (W - total_row_w) // 2

                max_chip_h = 0
                for label, cw, ch in row_chips:
                    _rounded_rect(
                        draw, (rx, ty, rx + cw, ty + ch),
                        chip_r, accent + (55,),
                    )
                    draw.rounded_rectangle(
                        [rx, ty, rx + cw, ty + ch],
                        radius=chip_r, outline=accent + (140,), width=1,
                    )
                    lw2, lh2 = _text_size(draw, label, chip_font)
                    draw.text(
                        (rx + (cw - lw2) // 2, ty + (ch - lh2) // 2),
                        label, font=chip_font, fill=txt_pri + (240,),
                    )
                    rx += cw + chip_gap
                    max_chip_h = max(max_chip_h, ch)

                ty += max_chip_h + chip_gap

            ty += GAP // 2

        # ── Step 6: CTA button ────────────────────────────────────────────────
        if show_cta:
            btn_h = cta_h
            btn_w = min(int(W * 0.70), inner_w)
            # Pin CTA to 87% of canvas height if there's room
            cta_y = max(ty + GAP, int(canvas_h * 0.83))
            btn_x = (W - btn_w) // 2

            # Button shadow
            shadow_img = Image.new("RGBA", (btn_w + 12, btn_h + 12), (0, 0, 0, 0))
            shadow_d = ImageDraw.Draw(shadow_img)
            shadow_d.rounded_rectangle([6, 6, btn_w + 6, btn_h + 6], radius=btn_radius, fill=(0, 0, 0, 100))
            shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(6))
            canvas.alpha_composite(shadow_img, (btn_x - 6, cta_y - 6))

            _rounded_rect(draw, (btn_x, cta_y, btn_x + btn_w, cta_y + btn_h), btn_radius, accent + (255,))
            cta_wrapped = _wrap(draw, cta_text, fn_cta, btn_w - 40)
            cw2, ch2 = _text_size(draw, cta_wrapped, fn_cta)
            draw.text(
                (btn_x + (btn_w - cw2) // 2, cta_y + (btn_h - ch2) // 2),
                cta_wrapped, font=fn_cta, fill=accent_text + (255,),
            )
            ty = cta_y + btn_h + GAP // 2

            if cta_url:
                url_display = cta_url if len(cta_url) <= 40 else cta_url[:37] + "..."
                uw, uh = _text_size(draw, url_display, fn_url)
                draw.text(
                    ((W - uw) // 2, ty),
                    url_display, font=fn_url, fill=(255, 255, 255, 130),
                )
                ty += uh + GAP // 4

        # ── Step 7: Tagline (bottom edge) ─────────────────────────────────────
        if tagline:
            tg_w, tg_h = _text_size(draw, tagline, fn_tagline)
            tg_y = canvas_h - tg_h - int(GAP * 0.8)
            draw.text(
                ((W - tg_w) // 2, tg_y),
                tagline, font=fn_tagline, fill=(255, 255, 255, 140),
            )
            y = tg_y + tg_h

        y = canvas_h  # full canvas used

        # ── Encode output ─────────────────────────────────────────────────────
        final_h = min(y + GAP, canvas_h)
        final = canvas.crop((0, 0, W, final_h))

        # Flatten RGBA → RGB against bg_color before JPEG encode
        bg_flat = Image.new("RGB", final.size, bg_color)
        bg_flat.paste(final.convert("RGBA"), mask=final.convert("RGBA").split()[3])

        buf = io.BytesIO()
        bg_flat.save(buf, format="JPEG", quality=95, optimize=True)
        result_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        logger.info(
            "[compositor] built poster w=%d h=%d features=%d cta=%s elapsed=N/A",
            W, final_h, len(features), show_cta,
        )
        return result_b64


# Singleton — stateless by design
poster_compositor = PosterCompositor()

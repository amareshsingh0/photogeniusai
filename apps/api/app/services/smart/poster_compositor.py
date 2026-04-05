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
        headline    = str(ad.get("headline")    or "").strip().upper()
        subheadline = str(ad.get("subheadline") or "").strip()
        body_text   = str(ad.get("body")        or "").strip()
        cta_text    = str(ad.get("cta")         or "GET STARTED").strip().upper()
        cta_url     = str(ad.get("cta_url")     or "").strip()
        tagline     = str(ad.get("tagline")     or "").strip()

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
        BRAND_BAR_H = int(W * 0.10) if brand_name else 0
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
        if brand_name and BRAND_BAR_H > 0:
            draw.rectangle([0, 0, W, BRAND_BAR_H], fill=accent + (255,))
            brand_wrapped = _wrap(draw, brand_name, fn_brand, inner_w)
            _, bh = _text_size(draw, brand_wrapped, fn_brand)
            _draw_text_centered(
                draw, brand_wrapped, fn_brand, W,
                (BRAND_BAR_H - bh) // 2, accent_text + (255,),
            )
            y = BRAND_BAR_H

        # ── Zone 2: Hero image (aspect-preserved cover crop) ─────────────────
        # Use ImageOps.fit for cover-crop (no distortion)
        hero_resized = ImageOps.fit(
            hero_img, (W, hero_h),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.3),  # bias slightly up (faces/subjects usually upper area)
        )

        # Vectorized gradient fade (not per-pixel loop)
        fade = _make_gradient_fade(W, hero_h, fade_start_frac=0.60, bg_color=bg_color)
        hero_comp = Image.alpha_composite(hero_resized, fade)
        canvas.paste(hero_comp, (0, y))
        y += hero_h

        # ── Zone 3: Text section ──────────────────────────────────────────────
        draw.rectangle([0, y, W, y + text_section_h + 40], fill=bg_color + (255,))
        y += SECTION_PAD

        shadow_offset = max(3, sz_headline // 20)

        if hl_wrapped:
            _draw_text_centered(
                draw, hl_wrapped, fn_headline, W, y, txt_pri + (255,),
                shadow=True, shadow_offset=shadow_offset,
            )
            y += hl_h + GAP // 2

            # Accent underline — full inner_w for consistency
            line_h = max(4, sz_headline // 20)
            draw.rectangle(
                [(W - inner_w) // 2, y - GAP // 4,
                 (W + inner_w) // 2, y - GAP // 4 + line_h],
                fill=accent + (255,),
            )

        if sub_wrapped:
            _draw_text_centered(draw, sub_wrapped, fn_sub, W, y, txt_sec + (255,))
            y += sub_h

        if body_wrapped:
            y += GAP // 2
            _draw_text_centered(draw, body_wrapped, fn_body, W, y, txt_sec + (200,))
            y += body_h

        y += SECTION_PAD

        # ── Zone 4: Feature grid ──────────────────────────────────────────────
        if features:
            y += GAP
            # "KEY FEATURES" section label
            sl_font = _font(f_body, max(18, int(W * 0.026)))
            sl_w, sl_h_actual = _text_size(draw, "KEY FEATURES", sl_font)
            draw.text(((W - sl_w) // 2, y), "KEY FEATURES", font=sl_font, fill=accent + (200,))
            y += sl_h_actual + GAP // 2

            # Fixed icon boundary for aligned grid
            icon_size  = max(28, int(W * 0.040))
            circle_r   = max(22, icon_size // 2 + 6)
            icon_font  = _font(f_body, icon_size)

            for row_i in range(feat_rows):
                row_y = y
                # Find number of cards in this row (last row may be partial)
                row_start = row_i * feat_cols
                row_end   = min(row_start + feat_cols, len(features))
                cards_in_row = row_end - row_start
                # Center partial last row
                row_total_w = cards_in_row * feat_card_w + (cards_in_row - 1) * GAP
                row_x0 = (W - row_total_w) // 2

                for col_i in range(cards_in_row):
                    fi = row_start + col_i
                    feat = features[fi]
                    fx = row_x0 + col_i * (feat_card_w + GAP)

                    card_bg = accent + (40,)
                    _rounded_rect(draw, (fx, row_y, fx + feat_card_w, row_y + feat_card_h), card_radius, card_bg)
                    draw.rounded_rectangle(
                        [fx+1, row_y+1, fx+feat_card_w-1, row_y+feat_card_h-1],
                        radius=card_radius, outline=accent + (100,), width=1,
                    )

                    cp = int(feat_card_w * 0.10)
                    icon_str  = str(feat.get("icon")  or "●").strip()
                    title_str = str(feat.get("title") or "").strip()
                    desc_str  = str(feat.get("desc")  or "").strip()

                    # Icon circle (fixed size for alignment)
                    ic_cx = fx + cp + circle_r
                    ic_cy = row_y + cp + circle_r
                    draw.ellipse(
                        [ic_cx-circle_r, ic_cy-circle_r, ic_cx+circle_r, ic_cy+circle_r],
                        fill=accent + (180,),
                    )
                    ic_w, ic_h = _text_size(draw, icon_str, icon_font)
                    draw.text(
                        (ic_cx - ic_w // 2, ic_cy - ic_h // 2),
                        icon_str, font=icon_font, fill=accent_text + (255,),
                    )

                    # Title (clamped to 2 lines)
                    title_x = fx + cp
                    title_y = row_y + cp * 2 + circle_r * 2 + 4
                    title_w_max = feat_card_w - 2 * cp
                    title_wrapped = _wrap(draw, title_str, fn_feat_ttl, title_w_max)
                    # Clamp to 2 lines
                    title_lines = title_wrapped.split("\n")[:2]
                    title_wrapped = "\n".join(title_lines)
                    draw.text((title_x, title_y), title_wrapped, font=fn_feat_ttl, fill=txt_pri + (255,))
                    _, ttl_h = _text_size(draw, title_wrapped, fn_feat_ttl)

                    # Desc (clamped to 2 lines)
                    desc_y = title_y + ttl_h + 4
                    desc_wrapped = _wrap(draw, desc_str, fn_feat_dsc, title_w_max)
                    desc_lines = desc_wrapped.split("\n")[:2]
                    desc_wrapped = "\n".join(desc_lines)
                    draw.text((fx + cp, desc_y), desc_wrapped, font=fn_feat_dsc, fill=txt_sec + (200,))

                y += feat_card_h + GAP // 2

            y += GAP // 2

        # ── Zone 5: CTA section ───────────────────────────────────────────────
        if show_cta:
            y += GAP
            btn_h = cta_h
            btn_w = min(int(W * 0.75), inner_w)
            btn_x = (W - btn_w) // 2
            _rounded_rect(draw, (btn_x, y, btn_x + btn_w, y + btn_h), btn_radius, accent + (255,))

            cta_wrapped = _wrap(draw, cta_text, fn_cta, btn_w - 40)
            cw, ch = _text_size(draw, cta_wrapped, fn_cta)
            draw.text(
                (btn_x + (btn_w - cw) // 2, y + (btn_h - ch) // 2),
                cta_wrapped, font=fn_cta, fill=accent_text + (255,),
            )
            y += btn_h

            if cta_url:
                y += GAP // 2
                # Truncate long URLs with ellipsis
                url_display = cta_url
                url_w, url_h = _text_size(draw, url_display, fn_url)
                while url_w > inner_w and len(url_display) > 10:
                    url_display = url_display[:-4] + "..."
                    url_w, url_h = _text_size(draw, url_display, fn_url)
                draw.text(((W - url_w) // 2, y), url_display, font=fn_url, fill=accent + (200,))
                y += url_h

            y += GAP

        # ── Zone 6: Tagline footer ────────────────────────────────────────────
        if tagline:
            draw.line([(PAD, y), (W - PAD, y)], fill=txt_sec + (60,), width=1)
            y += GAP // 2
            tg_w, tg_h = _text_size(draw, tagline, fn_tagline)
            draw.text(((W - tg_w) // 2, y), tagline, font=fn_tagline, fill=txt_sec + (160,))
            y += tg_h + GAP // 2

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

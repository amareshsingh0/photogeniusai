"""
PosterCompositor — PIL-based structured poster builder.

Takes a hero background image + Gemini ad_copy/poster_design JSON
and builds a FULL structured poster with:

  Zone 1 — Brand bar (top strip): logo area + brand name
  Zone 2 — Hero image: background scene (top 55-65% of canvas)
  Zone 3 — Headline + subheadline: large bold type over hero or below
  Zone 4 — Feature grid: 2-col or 3-col pill/card layout
  Zone 5 — CTA section: pill button + URL line
  Zone 6 — Footer strip: tagline / app badges / social handle

Design principles:
- Dark or colored panel below hero for text legibility (no text on noisy background)
- Consistent spacing: 5% horizontal margin, 2.5% vertical gap
- Accent color from poster_design drives buttons, icons, highlights
- Feature cards: rounded rect with semi-transparent fill + accent icon
- CTA button: full-width pill with high-contrast accent fill

Output: base64 PNG at full resolution (width × computed_height)
"""

from __future__ import annotations

import base64
import io
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# ── Font paths ─────────────────────────────────────────────────────────────────
_FONTS_DIR = Path(__file__).parent / "fonts"

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font by name, fall back gracefully."""
    candidates = {
        "bebas":       _FONTS_DIR / "BebasNeue-Regular.ttf",
        "anton":       _FONTS_DIR / "Anton-Regular.ttf",
        "montserrat_black": _FONTS_DIR / "Montserrat-Black.ttf",
        "montserrat_bold":  _FONTS_DIR / "Montserrat-Bold.ttf",
    }
    chain = [
        candidates.get(name),
        candidates["montserrat_black"],
        candidates["montserrat_bold"],
        candidates["bebas"],
    ]
    for path in chain:
        if path and path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _parse_hex(hex_str: str, fallback: Tuple[int,int,int] = (255,255,255)) -> Tuple[int,int,int]:
    """Parse #RRGGBB or #RGB hex color string."""
    s = (hex_str or "").strip().lstrip("#")
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


def _contrast_color(bg: Tuple[int,int,int]) -> Tuple[int,int,int]:
    """Return white or near-black for maximum contrast against bg."""
    return (255,255,255) if _luminance(bg) < 0.4 else (15,15,20)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    """Word-wrap text to fit max_w pixels."""
    words = text.split()
    if not words:
        return text
    lines, cur = [], words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        bbox = draw.textbbox((0,0), test, font=font)
        if (bbox[2]-bbox[0]) <= max_w:
            cur = test
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return "\n".join(lines)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int,int]:
    bbox = draw.textbbox((0,0), text, font=font)
    return bbox[2]-bbox[0], bbox[3]-bbox[1]


def _rounded_rect(draw: ImageDraw.ImageDraw,
                  xy: Tuple[int,int,int,int],
                  radius: int,
                  fill: Tuple[int,int,int,int]) -> None:
    """Draw a rounded rectangle (RGBA fill)."""
    x0,y0,x1,y1 = xy
    draw.rounded_rectangle([x0,y0,x1,y1], radius=radius, fill=fill)


# ══════════════════════════════════════════════════════════════════════════════
# Main compositor
# ══════════════════════════════════════════════════════════════════════════════

class PosterCompositor:
    """
    Build a structured multi-zone poster from a background image + Gemini brief.
    """

    def composite(
        self,
        hero_b64: str,                  # base64 of the background/hero image
        ad_copy: Dict,                  # from brief["ad_copy"]
        poster_design: Optional[Dict],  # from brief["poster_design"] (may be None)
        target_width: int = 1024,
        target_height: int = 1536,      # 2:3 poster ratio
    ) -> str:
        """
        Returns base64 PNG of the fully composited poster.
        """
        pd = poster_design or {}

        # ── Parse design tokens ──────────────────────────────────────────────
        accent     = _parse_hex(pd.get("accent_color",      "#6C63FF"), (108, 99, 255))
        bg_color   = _parse_hex(pd.get("bg_color",          "#0A0A1A"), ( 10, 10, 26))
        txt_pri    = _parse_hex(pd.get("text_color_primary", "#FFFFFF"), (255,255,255))
        txt_sec    = _parse_hex(pd.get("text_color_secondary","#CCCCDD"),(200,200,220))
        font_style = pd.get("font_style", "bold_tech")
        has_features = pd.get("has_feature_grid", True) and bool(ad_copy.get("features"))
        has_cta      = pd.get("has_cta_button", True)
        hero_zone    = pd.get("hero_occupies", "top_60")

        # Derived
        accent_text  = _contrast_color(accent)
        btn_radius   = target_width // 20       # ~51px on 1024w
        card_radius  = target_width // 30       # ~34px

        # ── Font selection by style ──────────────────────────────────────────
        if font_style in ("bold_tech", "expressive_display"):
            f_headline = "bebas"
            f_body     = "montserrat_bold"
        elif font_style == "elegant_serif":
            f_headline = "anton"
            f_body     = "montserrat_bold"
        else:  # clean_sans default
            f_headline = "montserrat_black"
            f_body     = "montserrat_bold"

        W = target_width
        PAD = int(W * 0.055)           # horizontal padding
        inner_w = W - 2 * PAD

        # ── Decode hero image ────────────────────────────────────────────────
        hero_bytes = base64.b64decode(hero_b64)
        hero_img   = Image.open(io.BytesIO(hero_bytes)).convert("RGBA")

        # Determine hero height
        if hero_zone == "top_60":
            hero_h = int(target_height * 0.58)
        elif hero_zone == "center_50":
            hero_h = int(target_height * 0.50)
        elif hero_zone == "full_bleed":
            hero_h = int(target_height * 0.65)
        else:  # left_half — use full height with different layout
            hero_h = int(target_height * 0.55)

        # ── Build layout plan to compute total canvas height ─────────────────
        # We'll compute heights section by section
        tmp = Image.new("RGBA", (1,1))
        tmp_draw = ImageDraw.Draw(tmp)

        brand_name   = (ad_copy.get("brand_name") or "").strip()
        headline     = (ad_copy.get("headline") or "").strip().upper()
        subheadline  = (ad_copy.get("subheadline") or "").strip()
        body_text    = (ad_copy.get("body") or "").strip()
        cta_text     = (ad_copy.get("cta") or "GET STARTED").strip().upper()
        cta_url      = (ad_copy.get("cta_url") or "").strip()
        tagline      = (ad_copy.get("tagline") or "").strip()
        features     = ad_copy.get("features") or []

        # Font sizes (proportional to width)
        sz_brand    = max(28, int(W * 0.042))
        sz_headline = max(64, int(W * 0.115))
        sz_sub      = max(26, int(W * 0.038))
        sz_body     = max(22, int(W * 0.030))
        sz_feat_ttl = max(22, int(W * 0.032))
        sz_feat_dsc = max(18, int(W * 0.026))
        sz_cta      = max(28, int(W * 0.042))
        sz_url      = max(20, int(W * 0.028))
        sz_tagline  = max(18, int(W * 0.026))

        fn_brand    = _font(f_headline, sz_brand)
        fn_headline = _font(f_headline, sz_headline)
        fn_sub      = _font(f_body, sz_sub)
        fn_body     = _font(f_body, sz_body)
        fn_feat_ttl = _font(f_body, sz_feat_ttl)
        fn_feat_dsc = _font(f_body, sz_feat_dsc)
        fn_cta      = _font(f_headline, sz_cta)
        fn_url      = _font(f_body, sz_url)
        fn_tagline  = _font(f_body, sz_tagline)

        GAP = int(W * 0.035)           # vertical gap unit
        SECTION_PAD = int(W * 0.05)    # padding inside colored sections

        # Pre-wrap headline and sub to measure heights
        d = tmp_draw
        hl_wrapped  = _wrap(d, headline,    fn_headline, inner_w)
        sub_wrapped = _wrap(d, subheadline, fn_sub, inner_w)
        body_wrapped= _wrap(d, body_text,   fn_body, inner_w) if body_text else ""

        _, hl_h   = _text_size(d, hl_wrapped,  fn_headline)
        _, sub_h  = _text_size(d, sub_wrapped, fn_sub)
        _, body_h = _text_size(d, body_wrapped,fn_body) if body_wrapped else (0, 0)

        # Feature grid geometry
        feat_cols = 2
        feat_per_row = math.ceil(len(features) / feat_cols) if features else 0
        feat_rows = math.ceil(len(features) / feat_cols) if features else 0
        feat_card_w = (inner_w - GAP) // feat_cols
        # Estimate card height
        feat_card_h = int(W * 0.26) if features else 0
        features_section_h = (feat_card_h + GAP//2) * feat_rows + GAP if features else 0

        # CTA button height
        cta_h = int(sz_cta * 1.8)

        # Total canvas height
        BRAND_BAR_H = int(W * 0.10) if brand_name else 0
        TEXT_SEC_PAD_TOP = SECTION_PAD
        TEXT_SEC_PAD_BOT = SECTION_PAD

        text_section_h = (
            TEXT_SEC_PAD_TOP
            + hl_h + GAP//2
            + sub_h + (GAP//2 + body_h if body_wrapped else 0)
            + TEXT_SEC_PAD_BOT
        )

        cta_section_h = (
            GAP
            + cta_h
            + (GAP//2 + int(sz_url * 1.3) if cta_url else 0)
            + GAP
        )

        tagline_h = (GAP + int(sz_tagline * 1.4) + GAP//2) if tagline else 0

        total_h = (
            BRAND_BAR_H
            + hero_h
            + text_section_h
            + (GAP + features_section_h if features else 0)
            + cta_section_h
            + tagline_h
            + GAP
        )

        # ── Create canvas ────────────────────────────────────────────────────
        canvas = Image.new("RGBA", (W, total_h), bg_color + (255,))
        draw   = ImageDraw.Draw(canvas)

        y = 0  # current draw cursor

        # ── Zone 1: Brand bar ────────────────────────────────────────────────
        if brand_name and BRAND_BAR_H > 0:
            # Solid accent strip
            draw.rectangle([0, 0, W, BRAND_BAR_H], fill=accent + (255,))
            brand_wrapped = _wrap(draw, brand_name, fn_brand, inner_w)
            bw, bh = _text_size(draw, brand_wrapped, fn_brand)
            draw.text(
                ((W - bw)//2, (BRAND_BAR_H - bh)//2),
                brand_wrapped, font=fn_brand, fill=accent_text + (255,),
            )
            y = BRAND_BAR_H

        # ── Zone 2: Hero image ───────────────────────────────────────────────
        hero_resized = hero_img.resize((W, hero_h), Image.Resampling.LANCZOS)

        # Add gradient fade at bottom of hero for seamless blend
        fade = Image.new("RGBA", (W, hero_h), (0,0,0,0))
        fade_draw = ImageDraw.Draw(fade)
        fade_start = int(hero_h * 0.65)
        for py in range(fade_start, hero_h):
            alpha = int(255 * (py - fade_start) / (hero_h - fade_start))
            fade_draw.line([(0, py), (W, py)], fill=bg_color + (alpha,))
        hero_comp = Image.alpha_composite(hero_resized, fade)
        canvas.paste(hero_comp, (0, y))
        y += hero_h

        # ── Zone 3: Text section (dark bg panel) ─────────────────────────────
        text_sec_y0 = y
        text_sec_y1 = y + text_section_h
        # Background: blend from bg_color with slight alpha for depth
        draw.rectangle([0, text_sec_y0, W, text_sec_y1], fill=bg_color + (255,))

        # Headline
        y += TEXT_SEC_PAD_TOP
        hl_x = (W - _text_size(draw, hl_wrapped, fn_headline)[0]) // 2

        # Drop shadow for headline
        shadow_offset = max(3, sz_headline//20)
        draw.text((hl_x + shadow_offset, y + shadow_offset), hl_wrapped,
                  font=fn_headline, fill=(0,0,0,160), align="center")
        draw.text((hl_x, y), hl_wrapped, font=fn_headline, fill=txt_pri + (255,), align="center")
        y += hl_h + GAP//2

        # Accent underline under headline
        line_w = min(inner_w, max(120, _text_size(draw, hl_wrapped.split("\n")[0], fn_headline)[0]))
        draw.rectangle(
            [(W - line_w)//2, y - GAP//4, (W + line_w)//2, y - GAP//4 + max(4, sz_headline//20)],
            fill=accent + (255,)
        )

        # Subheadline
        sub_x = (W - _text_size(draw, sub_wrapped, fn_sub)[0]) // 2
        draw.text((sub_x, y), sub_wrapped, font=fn_sub, fill=txt_sec + (255,), align="center")
        y += sub_h

        # Body text
        if body_wrapped:
            y += GAP//2
            body_x = (W - _text_size(draw, body_wrapped, fn_body)[0]) // 2
            draw.text((body_x, y), body_wrapped, font=fn_body, fill=txt_sec + (200,), align="center")
            y += body_h

        y += TEXT_SEC_PAD_BOT

        # ── Zone 4: Feature grid ─────────────────────────────────────────────
        if features:
            y += GAP
            section_label = "KEY FEATURES"
            sl_font = _font(f_body, max(18, int(W * 0.026)))
            sl_w, sl_h = _text_size(draw, section_label, sl_font)
            draw.text(((W - sl_w)//2, y), section_label, font=sl_font, fill=accent + (200,))
            y += sl_h + GAP//2

            for row_i in range(feat_rows):
                row_y = y
                for col_i in range(feat_cols):
                    fi = row_i * feat_cols + col_i
                    if fi >= len(features):
                        break
                    feat = features[fi]
                    fx = PAD + col_i * (feat_card_w + GAP)

                    # Card background: semi-transparent accent
                    card_bg = accent + (40,)
                    _rounded_rect(
                        draw,
                        (fx, row_y, fx + feat_card_w, row_y + feat_card_h),
                        card_radius,
                        card_bg,
                    )
                    # Accent border
                    for bw_px in range(2):
                        draw.rounded_rectangle(
                            [fx+bw_px, row_y+bw_px, fx+feat_card_w-bw_px, row_y+feat_card_h-bw_px],
                            radius=card_radius,
                            outline=accent + (100,),
                            width=1,
                        )

                    cp = int(feat_card_w * 0.10)  # inner card padding
                    icon_str = (feat.get("icon") or "●").strip()
                    title_str = (feat.get("title") or "").strip()
                    desc_str  = (feat.get("desc") or "").strip()

                    # Icon circle
                    icon_size = max(28, int(W * 0.040))
                    icon_font = _font(f_body, icon_size)
                    ic_x = fx + cp
                    ic_y = row_y + cp
                    ic_w, ic_h = _text_size(draw, icon_str, icon_font)
                    # Accent circle behind icon
                    circle_r = max(ic_w, ic_h) // 2 + 6
                    ic_cx = ic_x + circle_r
                    ic_cy = ic_y + circle_r
                    draw.ellipse(
                        [ic_cx-circle_r, ic_cy-circle_r, ic_cx+circle_r, ic_cy+circle_r],
                        fill=accent + (180,)
                    )
                    draw.text(
                        (ic_cx - ic_w//2, ic_cy - ic_h//2),
                        icon_str, font=icon_font, fill=accent_text + (255,)
                    )

                    # Title
                    title_x = fx + cp
                    title_y = row_y + cp * 2 + circle_r * 2 + 4
                    title_w_max = feat_card_w - 2 * cp
                    title_wrapped = _wrap(draw, title_str, fn_feat_ttl, title_w_max)
                    draw.text((title_x, title_y), title_wrapped, font=fn_feat_ttl, fill=txt_pri + (255,))
                    _, ttl_h = _text_size(draw, title_wrapped, fn_feat_ttl)

                    # Desc
                    desc_x = fx + cp
                    desc_y = title_y + ttl_h + 4
                    desc_wrapped = _wrap(draw, desc_str, fn_feat_dsc, title_w_max)
                    draw.text((desc_x, desc_y), desc_wrapped, font=fn_feat_dsc, fill=txt_sec + (200,))

                y += feat_card_h + GAP//2

            y += GAP//2

        # ── Zone 5: CTA section ───────────────────────────────────────────────
        y += GAP

        # CTA pill button
        btn_h = cta_h
        btn_w = min(int(W * 0.75), inner_w)
        btn_x = (W - btn_w) // 2
        _rounded_rect(draw, (btn_x, y, btn_x + btn_w, y + btn_h), btn_radius, accent + (255,))

        cta_wrapped = _wrap(draw, cta_text, fn_cta, btn_w - 40)
        cw, ch = _text_size(draw, cta_wrapped, fn_cta)
        draw.text(
            (btn_x + (btn_w - cw)//2, y + (btn_h - ch)//2),
            cta_wrapped, font=fn_cta, fill=accent_text + (255,)
        )
        y += btn_h

        # URL line
        if cta_url:
            y += GAP//2
            url_w, url_h = _text_size(draw, cta_url, fn_url)
            draw.text(((W - url_w)//2, y), cta_url, font=fn_url, fill=accent + (200,))
            y += url_h

        y += GAP

        # ── Zone 6: Tagline footer ────────────────────────────────────────────
        if tagline:
            # Separator line
            draw.line([(PAD, y), (W-PAD, y)], fill=txt_sec + (60,), width=1)
            y += GAP//2
            tg_w, tg_h = _text_size(draw, tagline, fn_tagline)
            draw.text(((W - tg_w)//2, y), tagline, font=fn_tagline, fill=txt_sec + (160,))
            y += tg_h + GAP//2

        # ── Encode output ─────────────────────────────────────────────────────
        # Trim canvas to actual used height
        final = canvas.crop((0, 0, W, min(y + GAP, total_h))).convert("RGB")
        buf = io.BytesIO()
        final.save(buf, format="JPEG", quality=95)
        return base64.b64encode(buf.getvalue()).decode("ascii")


# Singleton
poster_compositor = PosterCompositor()

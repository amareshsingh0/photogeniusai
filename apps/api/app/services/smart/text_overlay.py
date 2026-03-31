"""
Text Overlay System — detect text requests in prompts and overlay via PIL.

AI models generate garbled text. This module:
1. Detects when a user wants text in their image
2. Extracts the exact text content
3. Strips text instructions from prompt (so AI generates a clean image)
4. Augments prompt with layout modifiers (negative space for text placement)
5. Overlays pixel-perfect text using PIL with WCAG-compliant auto color

Usage:
    from app.services.smart.text_overlay import text_overlay

    info = text_overlay.detect(prompt)
    if info["has_text"]:
        # Generate with cleaned + layout-augmented prompt
        image = generate(info["cleaned_prompt"])
        # Overlay text on final image (auto color, dynamic font)
        image_b64 = text_overlay.apply(image_b64, info["texts"])
"""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import List, TypedDict

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import (
    FONTS_DIR,
    FONT_FALLBACK_CHAIN,
    HIERARCHY_RATIOS,
    STYLES,
    TYPOGRAPHY,
    VIBRANT_COLOR_STYLES,
    get_style,
    _POSTER_ROLE_COLORS,
    _CLEAN_ROLE_COLORS,
)

logger = logging.getLogger(__name__)


class TextInfo(TypedDict):
    text: str
    position: str  # "top", "center", "bottom"
    role: str      # "headline", "subtitle", "cta" (auto-detected)


class DetectionResult(TypedDict):
    has_text: bool
    texts: List[TextInfo]
    cleaned_prompt: str
    original_prompt: str


# ── Stage 1: Quoted text patterns (highest confidence — exact match) ──────────
_QUOTED_PATTERNS = [
    # "text 'hello'" / "write 'hello'" / "sign 'hello'"
    re.compile(
        r"""(?:text|write|writing|sign|banner|poster|label|caption|title|heading|saying|reads?|showing)\s+['"`]([^'"`]+)['"`]""",
        re.IGNORECASE,
    ),
    # "with text 'hello'" / "with the words 'hello'"
    re.compile(
        r"""with\s+(?:the\s+)?(?:text|words?|writing|caption|title|label)\s+['"`]([^'"`]+)['"`]""",
        re.IGNORECASE,
    ),
    # "'hello' written on" / "'hello' on a sign"
    re.compile(
        r"""['"`]([^'"`]+)['"`]\s+(?:text|written|printed|displayed|on\s+(?:a\s+)?(?:sign|banner|poster|board|screen))""",
        re.IGNORECASE,
    ),
    # "that says 'hello'" / "which reads 'hello'"
    re.compile(
        r"""(?:that|which)\s+(?:says?|reads?)\s+['"`]([^'"`]+)['"`]""",
        re.IGNORECASE,
    ),
]

# ── Stage 2: Unquoted text patterns (fallback — keyword + rest of phrase) ────
_UNQUOTED_PATTERNS = [
    # "poster saying SUMMER SALE" / "sign reading OPEN NOW"
    re.compile(
        r"""(?:sign|banner|poster|board|screen|label|card|flyer|billboard)\s+(?:saying|reading|showing|displaying|with)\s+(.+?)(?:\s+(?:on|in|at|near|for|and|with)\s|$)""",
        re.IGNORECASE,
    ),
    # "that says SUMMER SALE" / "which reads OPEN NOW"
    re.compile(
        r"""(?:that|which)\s+(?:says?|reads?)\s+(.+?)(?:\s+(?:on|in|at|near|for|and|with)\s|$)""",
        re.IGNORECASE,
    ),
    # "text SUMMER SALE on poster" / "writing HELLO WORLD on banner"
    re.compile(
        r"""(?:text|writing|caption|title|heading)\s+(.+?)\s+(?:on|in|at|over|across)\s+""",
        re.IGNORECASE,
    ),
    # "with text SUMMER SALE" / "with the words HELLO WORLD" (end of prompt)
    re.compile(
        r"""with\s+(?:the\s+)?(?:text|words?|writing|caption|title)\s+(.+?)$""",
        re.IGNORECASE,
    ),
]

# Combined: quoted first (high confidence), then unquoted (fallback)
_TEXT_PATTERNS = _QUOTED_PATTERNS + _UNQUOTED_PATTERNS

# ── Patterns to clean text instructions from the prompt ──────────────────────
_CLEAN_PATTERNS = [
    # Quoted cleaners
    re.compile(r"""(?:with\s+)?(?:the\s+)?(?:text|words?|writing|caption|title|label|heading)\s+['"`][^'"`]+['"`]""", re.IGNORECASE),
    re.compile(r"""(?:that|which)\s+(?:says?|reads?)\s+['"`][^'"`]+['"`]""", re.IGNORECASE),
    re.compile(r"""['"`][^'"`]+['"`]\s+(?:text|written|printed|displayed|on\s+(?:a\s+)?(?:sign|banner|poster|board|screen))""", re.IGNORECASE),
    re.compile(r"""(?:sign|banner|poster|label)\s+(?:saying|reading|showing)\s+['"`][^'"`]+['"`]""", re.IGNORECASE),
    # Unquoted cleaners
    re.compile(r"""(?:sign|banner|poster|board|screen|label|card|flyer|billboard)\s+(?:saying|reading|showing|displaying|with)\s+.+?(?:\s+(?:on|in|at|near|for|and|with)\s|$)""", re.IGNORECASE),
    re.compile(r"""(?:that|which)\s+(?:says?|reads?)\s+.+?(?:\s+(?:on|in|at|near|for|and|with)\s|$)""", re.IGNORECASE),
    re.compile(r"""(?:text|writing|caption|title|heading)\s+.+?\s+(?:on|in|at|over|across)\s+""", re.IGNORECASE),
    re.compile(r"""with\s+(?:the\s+)?(?:text|words?|writing|caption|title)\s+.+?$""", re.IGNORECASE),
]

# Position keywords (local context near the text match)
_POSITION_HINTS = {
    "top": ["top", "above", "header", "heading", "title"],
    "bottom": ["bottom", "below", "footer", "subtitle", "caption"],
    "center": ["center", "middle", "centered"],
}

# ── Semantic intent heuristics (PDF Table 2) ─────────────────────────────────
# When no local position hint is found, infer from overall prompt intent.
_SEMANTIC_POSITION_RULES: list[tuple[list[str], str]] = [
    # Cinematic/Theatrical → title at bottom (hero image dominates upper space)
    (["movie", "film", "cinematic", "trailer", "documentary", "thriller", "horror"], "bottom"),
    # Retail/E-Commerce → headline at top (Z-pattern: grab attention first)
    (["sale", "discount", "promo", "advertising", "offer", "deal", "shop", "buy"], "top"),
    # Event/Minimalist → text as central visual anchor
    (["minimalist", "typography-first", "brutalist", "modern art", "abstract"], "center"),
]


# ── Layout modifiers injected into cleaned prompt (negative space prompting) ──
_LAYOUT_MODIFIERS_BY_POSITION = {
    "top": "with large empty space at the top for headline, clean uncluttered upper area",
    "center": "with large empty space in the center for text, minimal central area, clean backdrop",
    "bottom": "with large empty space at the bottom for headline, clean uncluttered lower area",
}
_LAYOUT_MODIFIERS_GENERIC = (
    "poster layout, advertising style, clean gradient areas for text placement, "
    "minimal background clutter, decorative framing elements around the edges, "
    "objects arranged at borders with clean center space"
)

# ── Negative prompt additions when text overlay is active ─────────────────────
# Text artifacts + clutter suppression (PDF: protect negative space)
TEXT_NEGATIVE_PROMPT = (
    "text, typography, letters, words, watermark, signature, writing, font, caption, "
    "busy background, cluttered, distracting elements, messy, complex patterns"
)


class TextOverlay:
    """Detect text requests and overlay text on generated images."""

    def detect(self, prompt: str) -> DetectionResult:
        """Detect text requests in a prompt and extract content."""
        texts: List[TextInfo] = []
        seen: set[str] = set()

        for pattern in _TEXT_PATTERNS:
            for match in pattern.finditer(prompt):
                text = match.group(1).strip()
                # Strip any residual quotes from extraction
                text = text.strip("'\"` ")
                if not text:
                    continue
                norm = text.lower()
                # Skip if this text is a duplicate, substring, or superset of existing
                if norm in seen or any(norm in s or s in norm for s in seen):
                    continue
                seen.add(norm)
                position = self._detect_position(prompt, match.start())
                texts.append(TextInfo(text=text, position=position, role="headline"))

        if not texts:
            return DetectionResult(
                has_text=False,
                texts=[],
                cleaned_prompt=prompt,
                original_prompt=prompt,
            )

        # ── Smart hierarchy: detect which text is the MAIN OFFER ─────────
        # Real poster rule: the offer/deal word is BIGGEST, not just the first.
        # "SUMMER SALE" + "50% OFF" → "SALE" or "50% OFF" should be headline
        # Priority: % discount > price > sale/offer keyword > longest text
        self._assign_smart_roles(texts)

        # ── Multi-text position spreading ─────────────────────────────────
        # When 3+ texts, spread across top/center/bottom for real poster layout
        # Instead of all stacking at same detected position
        if len(texts) >= 3:
            texts[0]["position"] = "top"       # first text → top
            texts[-1]["position"] = "bottom"   # last text → bottom
            for t in texts[1:-1]:
                t["position"] = "center"       # middle texts → center
        elif len(texts) == 2:
            # 2 texts: headline at center (hero), subtitle at bottom
            for t in texts:
                if t["role"] == "headline":
                    t["position"] = "center"
                else:
                    t["position"] = "bottom"

        # Clean text instructions from prompt
        cleaned = prompt
        for pattern in _CLEAN_PATTERNS:
            cleaned = pattern.sub("", cleaned)
        # Collapse whitespace
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        # Remove trailing punctuation artifacts
        cleaned = cleaned.rstrip(",. ")

        if len(cleaned) < 3:
            cleaned = prompt  # safety: don't send empty prompt

        # ── Augment with layout modifiers (negative space prompting) ──────
        # Collect unique positions
        positions = {t.get("position", "bottom") for t in texts}
        layout_parts = []
        for pos in positions:
            modifier = _LAYOUT_MODIFIERS_BY_POSITION.get(pos, _LAYOUT_MODIFIERS_BY_POSITION["bottom"])
            layout_parts.append(modifier)

        cleaned = f"{cleaned}, {_LAYOUT_MODIFIERS_GENERIC}, {', '.join(layout_parts)}"

        logger.info(
            "[TEXT_OVERLAY] Detected %d text(s): %s | cleaned: %r",
            len(texts), [t["text"] for t in texts], cleaned[:120],
        )

        return DetectionResult(
            has_text=True,
            texts=texts,
            cleaned_prompt=cleaned,
            original_prompt=prompt,
        )

    def apply(
        self,
        image_b64: str,
        texts: List[TextInfo],
        font_size: int = 0,
        color: str = "",
        outline_color: str = "",
        outline_width: int = 0,
        style: str = "poster",
    ) -> str:
        """
        Overlay text on a base64 image and return new base64.

        Professional poster-grade text rendering:
        1. Force UPPERCASE for poster/marketing (real posters are ALL CAPS)
        2. 12% width headline size (not 8% — real posters are BOLD)
        3. Dramatic hierarchy: headline 100%, subtitle 60%, CTA 50%
        4. Theme-aware vibrant colors (not just black/white)
        5. Vertical stacking with proper spacing (no overlap)
        6. 3-layer rendering: shadow → glow → text+stroke
        7. Style-aware font selection (Bebas Neue, Montserrat Black, Anton)
        """
        # Decode
        img_bytes = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        orig_format = Image.open(io.BytesIO(img_bytes)).format or "PNG"

        # ── Base headline font size from config ─────────────────────────
        T = TYPOGRAPHY  # shorthand
        if font_size <= 0:
            font_size = max(T["min_font_size"], int(img.width * T["headline_size_ratio"]))

        # ── Style config from central registry ─────────────────────────
        style_cfg = get_style(style)

        max_text_width = int(img.width * T["max_width_ratio"])

        # ── Font cache: avoid re-loading same font during shrink loop ─────
        _font_cache: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

        def _cached_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
            if size not in _font_cache:
                _font_cache[size] = self._get_font(size, style)
            return _font_cache[size]

        # ── Pre-compute: measure all texts and plan vertical stacking ─────
        # Group texts by position, then stack vertically within each group
        position_groups: dict[str, list[dict]] = {}
        tmp_img = Image.new("RGBA", (1, 1))
        tmp_draw = ImageDraw.Draw(tmp_img)

        for text_info in texts:
            raw_text = text_info["text"]
            position = text_info.get("position", "bottom")
            role = text_info.get("role", "headline")

            # Force UPPERCASE for poster styles
            text = raw_text.upper() if style_cfg.get("uppercase", False) else raw_text

            # Hierarchy-based font size
            role_multiplier = HIERARCHY_RATIOS.get(role, 1.0)
            target_size = max(20, int(font_size * role_multiplier))

            # Max text height per item: proportional to role
            max_item_height = (
                int(img.height * T["max_height_headline"]) if role == "headline"
                else int(img.height * T["max_height_other"])
            )

            # Poster mode: word-per-line for headlines in poster styles
            use_poster_mode = (
                style_cfg.get("poster_mode", False)
                and role == "headline"
            )

            # Font shrink loop
            current_size = target_size
            current_font = _cached_font(current_size)
            while current_size >= T["min_font_size"] // 2:
                wrapped = self._wrap_text(
                    tmp_draw, text, current_font, max_text_width,
                    poster_mode=use_poster_mode,
                )
                bbox = tmp_draw.multiline_textbbox((0, 0), wrapped, font=current_font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                if text_h <= max_item_height and text_w <= max_text_width:
                    break
                current_size -= T["shrink_step"]
                current_font = _cached_font(current_size)
            else:
                wrapped = self._wrap_text(
                    tmp_draw, text, current_font, max_text_width,
                    poster_mode=use_poster_mode,
                )
                bbox = tmp_draw.multiline_textbbox((0, 0), wrapped, font=current_font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]

            entry = {
                "text": text, "wrapped": wrapped, "font": current_font,
                "size": current_size, "w": text_w, "h": text_h, "role": role,
            }
            position_groups.setdefault(position, []).append(entry)

        # ── Render each position group with vertical stacking ─────────────
        for position, items in position_groups.items():
            # Calculate total stack height (with spacing between items)
            spacing = max(8, font_size // T["spacing_divisor"])
            total_h = sum(it["h"] for it in items) + spacing * (len(items) - 1)

            # Stack Y start position
            if position == "top":
                stack_y = int(img.height * T["position_top_margin"])
            elif position == "center":
                stack_y = (img.height - total_h) // 2
            else:  # bottom
                stack_y = int(img.height * T["position_bottom_anchor"]) - total_h

            # Clamp to image bounds
            stack_y = max(5, min(stack_y, img.height - total_h - 5))

            current_y = stack_y
            for item in items:
                text_w = item["w"]
                text_h = item["h"]
                current_font = item["font"]
                current_size = item["size"]
                wrapped = item["wrapped"]
                role = item["role"]

                x = (img.width - text_w) // 2  # horizontally centered

                # ── Theme-aware color selection ─────────────────────────
                if not color:
                    fill, stroke = self._auto_color_vibrant(
                        img, x, current_y, text_w, text_h, role, style
                    )
                else:
                    fill = color
                    stroke = outline_color or ("black" if color == "white" else "white")

                # Outline width scales with font size
                is_poster = style_cfg.get("poster_mode", False)
                if is_poster:
                    actual_outline = max(T["stroke_min_poster"], current_size // T["stroke_divisor_poster"])
                else:
                    actual_outline = max(T["stroke_min_normal"], current_size // T["stroke_divisor_normal"])

                # ── Layer 1: Drop shadow ────────────────────────────────
                shadow_offset = max(4, current_size // T["shadow_offset_divisor"])
                shadow_blur = max(6, current_size // T["shadow_blur_divisor"])
                shadow_layer = Image.new("RGBA", img.size, 0)
                shadow_draw = ImageDraw.Draw(shadow_layer)
                shadow_draw.multiline_text(
                    (x + shadow_offset, current_y + shadow_offset), wrapped,
                    font=current_font, fill=(0, 0, 0, T["shadow_alpha"]),
                    align="center",
                )
                shadow_layer = shadow_layer.filter(
                    ImageFilter.GaussianBlur(radius=shadow_blur)
                )
                img = Image.alpha_composite(img, shadow_layer)

                # ── Layer 2: Glow halo ──────────────────────────────────
                glow_radius = max(8, current_size // T["glow_radius_divisor"])
                glow_alpha = T["glow_alpha_poster"] if is_poster else T["glow_alpha_normal"]
                glow_color = (0, 0, 0, glow_alpha) if fill == "white" else (255, 255, 255, glow_alpha)
                glow_layer = Image.new("RGBA", img.size, 0)
                glow_draw = ImageDraw.Draw(glow_layer)
                glow_draw.multiline_text(
                    (x, current_y), wrapped, font=current_font,
                    fill=glow_color,
                    stroke_width=actual_outline + T["glow_extra_stroke"],
                    stroke_fill=glow_color,
                    align="center",
                )
                glow_layer = glow_layer.filter(
                    ImageFilter.GaussianBlur(radius=glow_radius)
                )
                img = Image.alpha_composite(img, glow_layer)

                # ── Layer 3: Main text with stroke ──────────────────────
                text_layer = Image.new("RGBA", img.size, 0)
                text_draw = ImageDraw.Draw(text_layer)
                text_draw.multiline_text(
                    (x, current_y), wrapped, font=current_font, fill=fill,
                    stroke_width=actual_outline, stroke_fill=stroke,
                    align="center",
                )
                img = Image.alpha_composite(img, text_layer)

                # Advance Y for next item in stack
                current_y += text_h + spacing

        # Re-encode to same format
        buf = io.BytesIO()
        fmt = orig_format
        if fmt.upper() == "JPEG":
            img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=95)
        else:
            img.save(buf, format=fmt)

        return base64.b64encode(buf.getvalue()).decode("ascii")

    def apply_to_data_url(self, data_url: str, texts: List[TextInfo], style: str = "poster", **kwargs) -> str:
        """Apply text overlay to a data URL (data:image/...;base64,...) and return updated data URL."""
        if not data_url.startswith("data:"):
            logger.warning("[TEXT_OVERLAY] Not a data URL, skipping overlay")
            return data_url

        # Split header and base64
        header, b64_data = data_url.split(",", 1)
        new_b64 = self.apply(b64_data, texts, style=style, **kwargs)
        return f"{header},{new_b64}"

    def _auto_color_vibrant(
        self, img: Image.Image, x: int, y: int, text_w: int, text_h: int,
        role: str = "headline", style: str = "poster",
    ) -> tuple[str, str]:
        """
        Smart color selection for poster text.

        Priority:
        1. For headlines in poster/marketing → vibrant theme color
        2. For subtitles/CTAs → white or contrasting color
        3. Fallback → WCAG luminance-based black/white

        Returns (fill_color, stroke_color).
        """
        # ── Step 1: Measure background luminance ──────────────────────
        luminance = self._measure_luminance(img, x, y, text_w, text_h)
        bg_key = "light_bg" if luminance > 0.5 else "dark_bg"

        # ── Step 2: For non-poster styles, use clean WCAG colors ──────
        if style not in VIBRANT_COLOR_STYLES:
            colors = _CLEAN_ROLE_COLORS[bg_key]
            return colors[0], colors[1]

        # ── Step 3: Poster/marketing — vibrant colors by role ─────────
        role_colors = _POSTER_ROLE_COLORS.get(role, _POSTER_ROLE_COLORS["headline"])
        colors = role_colors[bg_key]
        return colors[0], colors[1]

    def _measure_luminance(
        self, img: Image.Image, x: int, y: int, w: int, h: int
    ) -> float:
        """Measure WCAG relative luminance of the image region under text."""
        pad = 10
        left = max(0, x - pad)
        top_y = max(0, y - pad)
        right = min(img.width, x + w + pad)
        bottom = min(img.height, y + h + pad)

        if right <= left or bottom <= top_y:
            return 0.0  # assume dark

        region = img.crop((left, top_y, right, bottom)).convert("RGB")
        avg = region.resize((1, 1), Image.Resampling.BILINEAR).getpixel((0, 0))

        def _srgb_to_linear(c: int) -> float:
            s = c / 255.0
            return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

        r_lin = _srgb_to_linear(avg[0])
        g_lin = _srgb_to_linear(avg[1])
        b_lin = _srgb_to_linear(avg[2])
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

    def _wrap_text(
        self, draw: ImageDraw.ImageDraw, text: str, font,
        max_width: int, poster_mode: bool = False,
    ) -> str:
        """
        Word-wrap text to fit within max_width pixels.

        poster_mode=True: Force one word per line for short texts (≤4 words).
        This is the #1 visual trick that makes posters look professional:
            "SUMMER SALE" → "SUMMER\nSALE" (each word HUGE on its own line)
        """
        words = text.split()
        if not words:
            return text

        # ── Poster mode: one word per line for punchy short texts ─────
        if poster_mode and len(words) <= 4:
            # Check if each word fits on one line
            all_fit = all(
                (draw.textbbox((0, 0), w, font=font)[2] - draw.textbbox((0, 0), w, font=font)[0]) <= max_width
                for w in words
            )
            if all_fit:
                return "\n".join(words)

        # ── Standard word-wrap ────────────────────────────────────────
        lines: list[str] = []
        current_line = words[0]

        for word in words[1:]:
            test_line = f"{current_line} {word}"
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word

        lines.append(current_line)
        return "\n".join(lines)

    def _assign_smart_roles(self, texts: List[TextInfo]) -> None:
        """
        Smart role assignment based on content analysis.

        Real poster hierarchy: the OFFER/DEAL is biggest, not the first text.
        Priority scoring:
          - % discount patterns ("50% OFF", "70% SALE") → highest (headline)
          - Price patterns ("$9.99", "₹499") → high
          - Sale/offer keywords → high
          - Shortest text (punchy) → medium
          - Everything else → subtitle

        The highest-scoring text becomes headline, lowest becomes CTA,
        rest are subtitles.
        """
        if len(texts) == 1:
            texts[0]["role"] = "headline"
            return

        # Score each text for "headline worthiness"
        _OFFER_PATTERNS = re.compile(
            r"(\d+\s*%|\boff\b|\bsale\b|\bdiscount\b|\bdeal\b|\bfree\b|\bbogo\b)",
            re.IGNORECASE,
        )
        _PRICE_PATTERNS = re.compile(r"[\$₹€£¥]\s*\d+|\d+\s*[\$₹€£¥]", re.IGNORECASE)

        scores: list[tuple[int, int]] = []  # (score, index)
        for i, t in enumerate(texts):
            txt = t["text"].lower()
            score = 0
            # % discount = strongest headline signal
            if re.search(r"\d+\s*%", txt):
                score += 10
            # Sale/offer keywords
            if _OFFER_PATTERNS.search(txt):
                score += 5
            # Price
            if _PRICE_PATTERNS.search(txt):
                score += 4
            # Shorter text = punchier = better headline
            if len(txt) <= 12:
                score += 2
            scores.append((score, i))

        # Sort by score descending
        scores.sort(key=lambda x: -x[0])

        # Highest score = headline, lowest = CTA, middle = subtitle
        headline_idx = scores[0][1]
        cta_idx = scores[-1][1] if len(scores) >= 3 else -1

        for i, t in enumerate(texts):
            if i == headline_idx:
                t["role"] = "headline"
            elif i == cta_idx and len(texts) >= 3:
                t["role"] = "cta"
            else:
                t["role"] = "subtitle"

    def _detect_position(self, prompt: str, match_start: int) -> str:
        """
        Detect text position using 2-stage logic:
        1. Local context hints (words near the text match)
        2. Semantic intent heuristics (overall prompt meaning — PDF Table 2)
        """
        # Stage 1: Check nearby words (within 50 chars before/after match)
        context = prompt[max(0, match_start - 50):match_start + 50].lower()
        for pos, keywords in _POSITION_HINTS.items():
            if any(kw in context for kw in keywords):
                return pos

        # Stage 2: Semantic intent from full prompt (PDF Table 2)
        prompt_lower = prompt.lower()
        for keywords, position in _SEMANTIC_POSITION_RULES:
            if any(kw in prompt_lower for kw in keywords):
                return position

        return "bottom"

    def _get_font(self, size: int, style: str = "poster") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Get a font appropriate for the design style (from config registry)."""
        style_cfg = get_style(style)
        candidates = list(style_cfg.get("fonts", [])) + FONT_FALLBACK_CHAIN

        seen: set[str] = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue

        logger.warning("[TEXT_OVERLAY] No TrueType font found, using default")
        return ImageFont.load_default()


# Singleton
text_overlay = TextOverlay()

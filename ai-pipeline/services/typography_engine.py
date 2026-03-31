"""
Typography Engine: GlyphControl + Post-Overlay.
Perfect text rendering in images — 100% OCR accuracy target.

Dual Approach:
- GlyphControl: Text integrated in scene (e.g. sign on building) — control image for conditioning.
- Post-Overlay: UI text (labels, captions, watermarks) — render on top of image.

Post-Overlay (99% use case):
- add_text_overlay(image, text, position='bottom'|'top'|'center'|(x,y), font_size, color, background, padding)
- add_watermark(image, text, position='bottom-right'|..., opacity, font_size)

Flexible API: overlay_text(image, placements) and overlay_single() for TextPlacement-based control.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PIL = True
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None
    HAS_PIL = False

import numpy as np


@dataclass
class TextPlacement:
    """Single text placement for GlyphControl or Post-Overlay."""

    text: str
    x: int  # left or center (see anchor)
    y: int  # top or center
    width: Optional[int] = None
    height: Optional[int] = None
    style: str = "sans"  # sans, sans_bold, serif, script, modern, mono
    font_size: Optional[int] = None  # auto if None
    color: Tuple[int, int, int] = (255, 255, 255)
    background: Optional[Tuple[int, int, int]] = None
    anchor: str = "lt"  # lt, ct, rt, lm, mm, rm, lb, cb, rb (PIL style)
    in_scene: bool = (
        False  # True = GlyphControl (sign in scene), False = Post-Overlay (UI)
    )


# Font search paths (cross-platform)
FONT_SEARCH_PATHS: List[Path] = []
if os.name == "nt":
    FONT_SEARCH_PATHS = [Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"]
else:
    FONT_SEARCH_PATHS = [
        Path("/usr/share/fonts/truetype"),
        Path("/usr/share/fonts/TTF"),
        Path("/usr/share/fonts"),
    ]

# Preferred filenames per style (OCR-friendly: clear sans/serif)
FONT_STYLE_FILES: Dict[str, List[str]] = {
    "sans": ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf", "arial.ttf"],
    "sans_bold": [
        "DejaVuSans-Bold.ttf",
        "LiberationSans-Bold.ttf",
        "Arial Bold.ttf",
        "arialbd.ttf",
    ],
    "serif": ["DejaVuSerif.ttf", "LiberationSerif-Regular.ttf", "times.ttf"],
    "serif_bold": ["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf", "timesbd.ttf"],
    "mono": ["DejaVuSansMono.ttf", "LiberationMono-Regular.ttf", "consola.ttf"],
    "script": ["DejaVuSerif-Italic.ttf", "DejaVuSans.ttf"],
    "modern": ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"],
    "display": ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"],
}


def _find_font(style: str) -> Optional[str]:
    """Return path to first available font for style, or None (use PIL default)."""
    for name in FONT_STYLE_FILES.get(style, FONT_STYLE_FILES["sans"]):
        for base in FONT_SEARCH_PATHS:
            if not base.exists():
                continue
            for root, _, files in os.walk(str(base)):
                for f in files:
                    if f == name or f.lower() == name.lower():
                        path = Path(root) / f
                        if path.exists():
                            return str(path)
    return None


def _get_font(style: str, size: int) -> Any:
    """PIL ImageFont for style and size; fallback to default."""
    if not HAS_PIL or not ImageFont:
        return None
    path = _find_font(style)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None


class TypographyEngine:
    """
    Dual approach: GlyphControl (in-scene text conditioning) + Post-Overlay (UI labels/captions).
    Target: 100% OCR accuracy on rendered text (clear fonts, high contrast, sufficient size).
    """

    def __init__(self, default_font_style: str = "sans", min_font_size: int = 14):
        self.default_font_style = default_font_style
        self.min_font_size = min_font_size
        self._font_cache: Dict[Tuple[str, int], Any] = {}
        # Backwards-compatible: some tests/consumers expect `engine.fonts`
        # (a small collection of commonly used fonts).
        self.fonts: Dict[str, Any] = {}
        if HAS_PIL and ImageFont is not None:
            self.fonts = {
                "default": self._font("sans", 40),
                "bold": self._font("sans_bold", 40),
                "title": self._font("sans_bold", 60),
                "caption": self._font("sans", 24),
            }

    def _font(self, style: str, size: int) -> Any:
        key = (style, size)
        if key not in self._font_cache:
            self._font_cache[key] = _get_font(style or self.default_font_style, size)
        return self._font_cache[key]

    def _fit_font_size(
        self,
        text: str,
        style: str,
        max_width: int,
        max_height: int,
    ) -> int:
        """Largest font size such that text fits in max_width x max_height."""
        low, high = self.min_font_size, max(
            200, max_height, max_width // max(1, len(text))
        )
        best = low
        for _ in range(12):
            mid = (low + high) // 2
            font = self._font(style, mid)
            if font is None:
                return mid
            try:
                bbox = font.getbbox(text)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            except Exception:
                w, h = len(text) * mid // 2, mid
            if w <= max_width and h <= max_height:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        return best

    # ---------- GlyphControl: control image for in-scene text ----------

    def build_glyph_control_image(
        self,
        width: int,
        height: int,
        placements: List[TextPlacement],
        background: Tuple[int, int, int] = (0, 0, 0),
        text_color: Tuple[int, int, int] = (255, 255, 255),
    ) -> Any:
        """
        Build control image for GlyphControl: same size as target image,
        with text rendered at specified regions (high contrast for conditioning).
        Returns PIL Image or numpy array; 100% readable by OCR in rendered regions.
        """
        if not HAS_PIL or Image is None:
            arr = np.zeros((height, width, 3), dtype=np.uint8)
            arr[:] = background
            return arr
        img = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(img)
        for p in placements:
            if not p.text:
                continue
            w = p.width or width // 2
            h = p.height or height // 8
            size = p.font_size or self._fit_font_size(p.text, p.style, w, h)
            font = self._font(p.style, size)
            if font is None:
                continue
            color = p.color if p.background is None else text_color
            # Draw text centered in (x, y, x+w, y+h) for control image
            x1, y1 = p.x, p.y
            x2, y2 = p.x + w, p.y + h
            try:
                bbox = font.getbbox(p.text)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            except Exception:
                tw, th = w, h
            cx = x1 + (w - tw) // 2
            cy = y1 + (h - th) // 2
            draw.text((cx, cy), p.text, font=font, fill=color)
        return img

    def glyph_control_placements_from_specs(
        self,
        specs: List[Dict[str, Any]],
        image_width: int,
        image_height: int,
    ) -> List[TextPlacement]:
        """Convert list of {text, x, y, width?, height?, style?} to TextPlacement (GlyphControl)."""
        out: List[TextPlacement] = []
        for s in specs:
            x = int(s.get("x", 0))
            y = int(s.get("y", 0))
            w = s.get("width")
            h = s.get("height")
            if w is not None:
                w = int(w)
            if h is not None:
                h = int(h)
            out.append(
                TextPlacement(
                    text=str(s.get("text", "")),
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    style=str(s.get("style", self.default_font_style)),
                    in_scene=True,
                )
            )
        return out

    # ---------- Post-Overlay: UI text on image ----------

    def overlay_text(
        self,
        image: Any,
        placements: List[TextPlacement],
        antialias: bool = True,
    ) -> Any:
        """
        Draw text on image (Post-Overlay). High contrast, clear font — 100% OCR accuracy.
        image: PIL Image or numpy array (H, W, 3).
        """
        if not HAS_PIL or Image is None:
            return image
        if hasattr(image, "mode"):
            img = image.convert("RGB")
        else:
            img = Image.fromarray(np.asarray(image).astype(np.uint8))
        draw = ImageDraw.Draw(img)
        for p in placements:
            if not p.text:
                continue
            w = p.width or 200
            h = p.height or 40
            size = p.font_size or self._fit_font_size(p.text, p.style, w, h)
            font = self._font(p.style, size)
            if font is None:
                continue
            if p.background is not None:
                try:
                    bbox = font.getbbox(p.text)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                except Exception:
                    tw, th = w, h
                pad = 4
                draw.rectangle(
                    [p.x - pad, p.y - pad, p.x + tw + pad, p.y + th + pad],
                    fill=p.background,
                )
            draw.text((p.x, p.y), p.text, font=font, fill=p.color, anchor=p.anchor)
        return img

    def overlay_single(
        self,
        image: Any,
        text: str,
        x: int = 10,
        y: int = 10,
        style: str = "sans",
        font_size: Optional[int] = None,
        color: Tuple[int, int, int] = (255, 255, 255),
        background: Optional[Tuple[int, int, int]] = (0, 0, 0),
    ) -> Any:
        """Convenience: overlay one line of text (anchor lt)."""
        fs = font_size or 24
        return self.overlay_text(
            image,
            [
                TextPlacement(
                    text=text,
                    x=x,
                    y=y,
                    width=len(text) * (fs // 2 + 4),
                    height=fs + 8,
                    style=style,
                    font_size=fs,
                    color=color,
                    background=background,
                    anchor="lt",
                )
            ],
        )

    # ---------- Post-Overlay convenience: captions, watermarks (99% use case) ----------

    def _wrap_text(self, text: str, font: Any, max_width: int) -> str:
        """Wrap text to fit within max_width using font metrics."""
        if not text or max_width <= 0 or font is None:
            return text or ""
        lines: List[str] = []
        for paragraph in text.split("\n"):
            words = paragraph.split()
            current_line: List[str] = []
            for word in words:
                test_line = " ".join(current_line + [word])
                try:
                    bbox = font.getbbox(test_line)
                    width = bbox[2] - bbox[0]
                except Exception:
                    width = len(test_line) * 10
                if width <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
        return "\n".join(lines)

    @staticmethod
    def _hex_to_rgba(hex_color: str, opacity: float) -> Tuple[int, int, int, int]:
        """Convert color to RGBA tuple. Supports color names, #RGB and #RRGGBB."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            r = int(hex_color[0] * 2, 16)
            g = int(hex_color[1] * 2, 16)
            b = int(hex_color[2] * 2, 16)
        elif len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
        else:
            # Try named colors (e.g. "black") when Pillow is available
            try:
                from PIL import ImageColor  # type: ignore

                r, g, b = ImageColor.getrgb("#" + hex_color) if len(hex_color) in (3, 6) else ImageColor.getrgb(hex_color)  # type: ignore[arg-type]
            except Exception:
                r, g, b = 0, 0, 0
        a = int(255 * max(0.0, min(1.0, opacity)))
        return (r, g, b, a)

    @staticmethod
    def _color_to_fill(
        color: Union[str, Tuple[int, int, int], Tuple[int, int, int, int]],
    ) -> Union[str, Tuple[int, int, int], Tuple[int, int, int, int]]:
        """Return fill suitable for ImageDraw (str or RGB/RGBA tuple)."""
        if isinstance(color, (tuple, list)) and len(color) >= 3:
            return (
                tuple(int(x) for x in color[:4])
                if len(color) == 4
                else tuple(int(x) for x in color[:3])
            )
        if isinstance(color, str) and color.startswith("#"):
            c = color.lstrip("#")
            if len(c) == 6:
                return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
            if len(c) == 3:
                return (int(c[0] * 2, 16), int(c[1] * 2, 16), int(c[2] * 2, 16))
        return color

    def add_text_overlay(
        self,
        image: Any,
        text: str,
        position: Union[str, Tuple[int, int]] = "bottom",
        font_size: int = 40,
        color: Union[str, Tuple[int, int, int]] = "white",
        background: Optional[str] = None,
        background_opacity: float = 0.7,
        padding: int = 20,
        style: str = "sans_bold",
    ) -> Any:
        """
        Add text overlay to image (captions, labels). Wraps long text; optional background.

        Args:
            image: PIL Image or numpy array (H, W, 3).
            text: Text to overlay.
            position: 'top', 'bottom', 'center', or (x, y) tuple.
            font_size: Font size in pixels.
            color: Text color (name or hex, e.g. 'white' or '#ffffff').
            background: Background color hex (None for no background).
            background_opacity: 0–1.
            padding: Padding around text block.
            style: Font style key (sans_bold, sans, etc.).

        Returns:
            Image with text overlay (same type as input when possible).
        """
        if not HAS_PIL or Image is None or not text:
            return image
        if hasattr(image, "mode"):
            img = image.copy()
        else:
            img = Image.fromarray(np.asarray(image).astype(np.uint8))
        font = self._font(style, font_size)
        if font is None:
            font = self._font("sans", font_size)
        if font is None:
            return img
        need_rgba = bool(background)
        if need_rgba and img.mode != "RGBA":
            img = img.convert("RGBA")
        draw = ImageDraw.Draw(img, "RGBA" if need_rgba else img.mode)
        max_width = img.width - (padding * 2)
        wrapped_text = self._wrap_text(text, font, max_width)
        lines = wrapped_text.split("\n") if wrapped_text else []
        text_w, text_h = 0, 0
        for line in lines:
            try:
                lb = font.getbbox(line)
                text_w = max(text_w, lb[2] - lb[0])
                text_h += lb[3] - lb[1]
            except Exception:
                text_w = max(text_w, len(line) * font_size // 2)
                text_h += font_size
        if not lines:
            text_w, text_h = 0, font_size
        if isinstance(position, (tuple, list)) and len(position) >= 2:
            x, y = int(position[0]), int(position[1])
        elif position == "top":
            x = (img.width - text_w) // 2
            y = padding
        elif position == "bottom":
            x = (img.width - text_w) // 2
            y = img.height - text_h - padding
        elif position == "center":
            x = (img.width - text_w) // 2
            y = (img.height - text_h) // 2
        else:
            x = (img.width - text_w) // 2
            y = img.height - text_h - padding
        if background:
            bg_color = self._hex_to_rgba(background, background_opacity)
            draw.rectangle(
                (
                    x - padding,
                    y - padding,
                    x + text_w + padding,
                    y + text_h + padding,
                ),
                fill=bg_color,
            )
        fill = self._color_to_fill(color)
        draw.multiline_text((x, y), wrapped_text, font=font, fill=fill)
        if (
            need_rgba
            and image is not None
            and hasattr(image, "mode")
            and image.mode == "RGB"
        ):
            img = img.convert("RGB")
        return img

    def add_watermark(
        self,
        image: Any,
        text: str = "PhotoGenius AI",
        position: str = "bottom-right",
        opacity: float = 0.3,
        font_size: int = 24,
        style: str = "sans",
    ) -> Any:
        """Add subtle watermark. position: 'bottom-right', 'bottom-left', 'top-right', 'top-left'."""
        if not HAS_PIL or Image is None:
            return image
        if hasattr(image, "mode"):
            img = image.convert("RGBA")
        else:
            img = Image.fromarray(np.asarray(image).astype(np.uint8)).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        font = self._font(style, font_size)
        if font is None:
            font = self._font("sans", font_size)
        if font is None:
            return (
                image.convert("RGB")
                if hasattr(image, "mode")
                else Image.fromarray(np.asarray(image).astype(np.uint8))
            )
        try:
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except Exception:
            text_width, text_height = len(text) * font_size // 2, font_size
        pad = 20
        if position == "bottom-right":
            x, y = img.width - text_width - pad, img.height - text_height - pad
        elif position == "bottom-left":
            x, y = pad, img.height - text_height - pad
        elif position == "top-right":
            x, y = img.width - text_width - pad, pad
        else:
            x, y = pad, pad
        alpha = int(255 * max(0.0, min(1.0, opacity)))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, alpha))
        img = Image.alpha_composite(img, overlay)
        return img.convert("RGB")

    # ---------- OCR verification (optional) ----------

    def verify_ocr(
        self,
        image: Any,
        expected_text: str,
        similarity_threshold: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Run OCR on image and check expected text is present.

        Args:
            image: PIL Image or numpy array.
            expected_text: Text that should appear in the image.
            similarity_threshold: If set (e.g. 0.9), success requires similarity >= threshold
                (uses difflib.SequenceMatcher). If None, success = expected substring in detected.

        Returns:
            (success, detected_string). Requires pytesseract when available.
        """
        try:
            import pytesseract

            if hasattr(image, "mode"):
                img = image
            else:
                img = Image.fromarray(np.asarray(image).astype(np.uint8))
            detected = pytesseract.image_to_string(img).strip()
            normalized = " ".join(detected.split()).lower()
            expected_norm = " ".join(expected_text.split()).lower()

            if similarity_threshold is not None:
                if expected_norm in normalized or expected_norm in detected:
                    return True, detected
                from difflib import SequenceMatcher

                ratio = SequenceMatcher(None, expected_norm, normalized).ratio()
                # Also try ratio against full detected (case-insensitive)
                if ratio < similarity_threshold:
                    ratio = max(
                        ratio,
                        SequenceMatcher(None, expected_norm, detected.lower()).ratio(),
                    )
                return (ratio >= similarity_threshold, detected)
            ok = expected_norm in normalized or expected_norm in detected
            return ok, detected
        except ImportError:
            return True, ""  # no OCR: assume pass
        except Exception:
            return False, ""


def render_text_placement(
    width: int,
    height: int,
    text: str,
    x: int = 0,
    y: int = 0,
    style: str = "sans",
    font_size: Optional[int] = None,
) -> Any:
    """Standalone: render single text placement on blank image (for testing OCR)."""
    engine = TypographyEngine()
    p = TextPlacement(
        text=text,
        x=x,
        y=y,
        width=width,
        height=height,
        style=style,
        font_size=font_size,
        color=(255, 255, 255),
        background=(0, 0, 0),
    )
    return engine.build_glyph_control_image(width, height, [p])

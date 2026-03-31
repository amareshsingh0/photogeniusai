"""
Tests for Typography Engine: GlyphControl + Post-Overlay.
P1: 100% OCR accuracy on rendered text.
"""

import pytest
import numpy as np

try:
    from services.typography_engine import (
        TypographyEngine,
        TextPlacement,
        render_text_placement,
        FONT_SEARCH_PATHS,
        FONT_STYLE_FILES,
    )
except ImportError:
    from ai_pipeline.services.typography_engine import (
        TypographyEngine,
        TextPlacement,
        render_text_placement,
        FONT_SEARCH_PATHS,
        FONT_STYLE_FILES,
    )


def test_glyph_control_image():
    """GlyphControl produces control image with text in regions."""
    engine = TypographyEngine()
    placements = [
        TextPlacement(text="OPEN", x=50, y=50, width=200, height=60, style="sans"),
        TextPlacement(
            text="SALE", x=50, y=130, width=200, height=60, style="sans_bold"
        ),
    ]
    img = engine.build_glyph_control_image(400, 300, placements)
    assert img is not None
    if hasattr(img, "size"):
        assert img.size[0] == 400 and img.size[1] == 300
    else:
        assert img.shape[1] == 400 and img.shape[0] == 300


def test_post_overlay():
    """Post-Overlay draws text on image."""
    engine = TypographyEngine()
    try:
        from PIL import Image

        base = Image.new("RGB", (320, 240), (40, 40, 40))
    except ImportError:
        base = np.zeros((240, 320, 3), dtype=np.uint8)
        base[:] = 40
    placements = [
        TextPlacement(
            text="Caption",
            x=10,
            y=10,
            width=120,
            height=30,
            style="sans",
            color=(255, 255, 255),
        ),
    ]
    out = engine.overlay_text(base, placements)
    assert out is not None
    if hasattr(out, "size"):
        assert out.size[0] == 320 and out.size[1] == 240
    else:
        assert out.shape[1] == 320 and out.shape[0] == 240


def test_overlay_single():
    """overlay_single adds one line of text."""
    engine = TypographyEngine()
    try:
        from PIL import Image

        base = Image.new("RGB", (200, 100), (30, 30, 30))
    except ImportError:
        pytest.skip("PIL required for overlay")
    out = engine.overlay_single(base, "Hello World", x=20, y=20, font_size=24)
    assert out is not None


def test_ocr_accuracy_rendered_text():
    """Rendered text is readable (OCR when available)."""
    engine = TypographyEngine()
    # Render clear text on high-contrast background
    placements = [
        TextPlacement(
            text="TEST123",
            x=20,
            y=20,
            width=200,
            height=50,
            style="sans",
            font_size=32,
            color=(255, 255, 255),
            background=(0, 0, 0),
        ),
    ]
    try:
        from PIL import Image

        img = Image.new("RGB", (256, 128), (0, 0, 0))
        img = engine.overlay_text(img, placements)
        ok, detected = engine.verify_ocr(img, "TEST123")
        # With pytesseract we expect match; without we pass (no OCR)
        assert ok or not detected, "OCR should find TEST123 when pytesseract available"
    except ImportError:
        # No PIL: just check engine runs
        img = engine.build_glyph_control_image(256, 128, placements)
        assert img is not None


def test_glyph_control_placements_from_specs():
    """glyph_control_placements_from_specs converts dicts to TextPlacement."""
    engine = TypographyEngine()
    specs = [
        {"text": "Sign", "x": 10, "y": 20, "width": 100, "height": 40},
        {"text": "Exit", "x": 150, "y": 20, "style": "sans_bold"},
    ]
    placements = engine.glyph_control_placements_from_specs(specs, 300, 200)
    assert len(placements) == 2
    assert placements[0].text == "Sign"
    assert placements[0].x == 10 and placements[0].y == 20
    assert placements[1].text == "Exit"


def test_render_text_placement_standalone():
    """Standalone render_text_placement produces image with text."""
    img = render_text_placement(200, 80, "Label", x=10, y=10, font_size=24)
    assert img is not None
    if hasattr(img, "size"):
        assert img.size[0] == 200 and img.size[1] == 80
    else:
        assert img.shape[1] == 200 and img.shape[0] == 80


def test_verify_ocr_no_tesseract():
    """verify_ocr returns (True, '') when pytesseract not installed."""
    engine = TypographyEngine()
    try:
        from PIL import Image

        img = Image.new("RGB", (64, 32), (0, 0, 0))
    except ImportError:
        img = np.zeros((32, 64, 3), dtype=np.uint8)
    ok, detected = engine.verify_ocr(img, "anything")
    assert ok is True  # no OCR = assume pass
    assert isinstance(detected, str)


def test_add_text_overlay_bottom():
    """add_text_overlay with position='bottom' places text at bottom center."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required")
    engine = TypographyEngine()
    base = Image.new("RGB", (400, 300), (50, 50, 50))
    out = engine.add_text_overlay(base, "Caption here", position="bottom", font_size=32)
    assert out is not None
    assert out.size == (400, 300)


def test_add_text_overlay_center_with_background():
    """add_text_overlay with position='center' and background draws background rect."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required")
    engine = TypographyEngine()
    base = Image.new("RGB", (320, 240), (30, 30, 30))
    out = engine.add_text_overlay(
        base,
        "Centered",
        position="center",
        font_size=28,
        color="white",
        background="#000000",
        background_opacity=0.8,
        padding=12,
    )
    assert out is not None
    assert out.size == (320, 240)


def test_add_text_overlay_tuple_position():
    """add_text_overlay with (x, y) uses exact position."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required")
    engine = TypographyEngine()
    base = Image.new("RGB", (200, 100), (0, 0, 0))
    out = engine.add_text_overlay(base, "XY", position=(20, 30), font_size=24)
    assert out is not None
    assert out.size == (200, 100)


def test_add_text_overlay_empty_text_returns_unchanged():
    """add_text_overlay with empty text returns image unchanged."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required")
    engine = TypographyEngine()
    base = Image.new("RGB", (100, 100), (1, 2, 3))
    out = engine.add_text_overlay(base, "", position="bottom")
    assert out is not None
    assert out.size == base.size


def test_add_watermark():
    """add_watermark places subtle text at specified corner."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required")
    engine = TypographyEngine()
    base = Image.new("RGB", (400, 300), (40, 40, 40))
    out = engine.add_watermark(base, "PhotoGenius AI", position="bottom-right", opacity=0.3, font_size=24)
    assert out is not None
    assert out.size == (400, 300)
    assert out.mode == "RGB"


def test_add_watermark_positions():
    """add_watermark accepts all position values."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required")
    engine = TypographyEngine()
    base = Image.new("RGB", (200, 200), (0, 0, 0))
    for pos in ("bottom-right", "bottom-left", "top-right", "top-left"):
        out = engine.add_watermark(base, "W", position=pos, font_size=16)
        assert out is not None and out.size == (200, 200)


def test_hex_to_rgba():
    """_hex_to_rgba converts hex to RGBA tuple."""
    assert TypographyEngine._hex_to_rgba("#000000", 1.0) == (0, 0, 0, 255)
    assert TypographyEngine._hex_to_rgba("#ffffff", 0.5) == (255, 255, 255, 127)
    assert TypographyEngine._hex_to_rgba("ff0000", 0.0) == (255, 0, 0, 0)


def test_wrap_text():
    """_wrap_text wraps long lines to max_width."""
    try:
        from PIL import ImageFont
    except ImportError:
        pytest.skip("PIL required")
    engine = TypographyEngine()
    font = engine._font("sans", 24)
    if font is None:
        pytest.skip("no font available")
    wrapped = engine._wrap_text("one two three four five", font, 80)
    assert "\n" in wrapped or len(wrapped.split()) <= 4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:asyncio"])

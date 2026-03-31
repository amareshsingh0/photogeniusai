import pytest
from PIL import Image

from services.typography_engine import TypographyEngine


def test_typography_engine_init():
    """Test engine initializes"""
    engine = TypographyEngine()
    assert engine.fonts is not None


def test_add_text_overlay():
    """Test adding text overlay"""
    engine = TypographyEngine()

    # Create test image
    img = Image.new("RGB", (800, 600), color="blue")

    # Add text
    result = engine.add_text_overlay(
        img,
        "Test Caption",
        position="bottom",
        color="white",
        background="black",
        background_opacity=0.7,
    )

    assert result.size == img.size
    assert result != img  # Should be modified (new image object)


def test_add_watermark():
    """Test watermark"""
    engine = TypographyEngine()

    img = Image.new("RGB", (800, 600), color="green")

    result = engine.add_watermark(
        img,
        text="PhotoGenius AI",
        position="bottom-right",
        opacity=0.3,
    )

    assert result.size == img.size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


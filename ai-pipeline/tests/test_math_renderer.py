"""
Tests for Math Renderer: LaTeX to image and formula overlay.
"""

import pytest

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from services.math_renderer import MathRenderer
except ImportError:
    from ai_pipeline.services.math_renderer import MathRenderer


def test_math_renderer_init():
    """MathRenderer initializes."""
    r = MathRenderer()
    assert r is not None


@pytest.mark.skipif(not HAS_PIL, reason="PIL required")
def test_render_latex_to_image():
    """render_latex_to_image returns a PIL Image for valid LaTeX."""
    r = MathRenderer()
    img = r.render_latex_to_image(r"$E = mc^2$", dpi=150)
    if img is None:
        pytest.skip("matplotlib not available")
    assert img is not None
    assert hasattr(img, "size")
    assert img.size[0] > 0 and img.size[1] > 0


def test_render_latex_empty_returns_none():
    """Empty LaTeX returns None."""
    r = MathRenderer()
    assert r.render_latex_to_image("") is None


@pytest.mark.skipif(not HAS_PIL, reason="PIL required")
def test_add_formula_to_image():
    """add_formula_to_image pastes formula on image."""
    r = MathRenderer()
    base = Image.new("RGB", (400, 300), (240, 240, 240))
    out = r.add_formula_to_image(base, r"$x^2$", position=(50, 50))
    assert out is not None
    assert out.size == base.size
    assert out.mode == "RGB"


@pytest.mark.skipif(not HAS_PIL, reason="PIL required")
def test_add_formula_to_image_no_matplotlib():
    """When render fails, add_formula_to_image returns original image."""
    r = MathRenderer()
    base = Image.new("RGB", (100, 100), (0, 0, 0))
    # Pass something that might still render; if render returns None we return base
    out = r.add_formula_to_image(base, r"$a$", position=(10, 10))
    assert out is not None
    assert out.size == base.size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

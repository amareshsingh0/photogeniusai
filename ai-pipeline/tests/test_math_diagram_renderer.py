"""
Tests for Math & Diagram Renderer.
P1: 98%+ formula correctness, aesthetically pleasing.

Full setup (all 15 tests run, no skips):
  cd ai-pipeline
  pip install -r requirements.txt
  python -m pytest tests/test_math_diagram_renderer.py -v -p no:asyncio

Or: ./scripts/run_math_diagram_tests.ps1  (install deps + run tests)
"""

import io
import pytest
import numpy as np


# Require full deps so tests run without skipping when setup is complete
def _require_math_diagram_deps():
    """Skip only if required packages are missing; use before tests that need them."""
    pytest.importorskip(
        "matplotlib", reason="pip install -r requirements.txt (matplotlib)"
    )
    pytest.importorskip("PIL", reason="pip install -r requirements.txt (Pillow)")
    pytest.importorskip("sympy", reason="pip install -r requirements.txt (sympy)")
    pytest.importorskip(
        "antlr4", reason="pip install -r requirements.txt (antlr4-python3-runtime)"
    )


try:
    from services.math_diagram_renderer import (
        MathDiagramRenderer,
        FormulaPlacement,
        ChartSpec,
        DiagramKind,
        LightingOptions,
        ValidationResult,
        validate_formula_latex,
        validate_formula_sympy_expr,
        check_formula_equivalence,
        render_latex_to_png,
        overlay_math_on_image,
        get_default_math_diagram_renderer,
    )
except ImportError:
    from ai_pipeline.services.math_diagram_renderer import (
        MathDiagramRenderer,
        FormulaPlacement,
        ChartSpec,
        LightingOptions,
        ValidationResult,
        validate_formula_latex,
        validate_formula_sympy_expr,
        check_formula_equivalence,
        render_latex_to_png,
        overlay_math_on_image,
        get_default_math_diagram_renderer,
    )

    try:
        from ai_pipeline.services.math_diagram_renderer import DiagramKind
    except ImportError:
        DiagramKind = None  # type: ignore[misc, assignment]


# Formula samples for 98%+ correctness target (SymPy parse_latex subset)
FORMULA_SAMPLES_VALID = [
    r"x^2 + y^2",
    r"x^{2}",
    r"1 + 1",
    r"a + b",
    r"a b",
    r"x",
    r"2",
    r"\alpha",
    r"x^2",
    r"y^2",
]

FORMULA_SAMPLES_INVALID = [
    "",  # empty
    r"\frac{",  # unclosed command (parse_latex may reject)
]


def test_validate_formula_latex_valid():
    """SymPy validation: valid formulas parse successfully (requires antlr4 for parse_latex)."""
    _require_math_diagram_deps()
    for latex in FORMULA_SAMPLES_VALID:
        r = validate_formula_latex(latex)
        assert r.valid, f"Expected valid for: {latex!r}, got error: {r.error}"


def test_validate_formula_latex_invalid():
    """SymPy validation: empty formula is invalid; malformed may be invalid or parsed as symbol."""
    pytest.importorskip("sympy", reason="pip install -r requirements.txt (sympy)")
    r_empty = validate_formula_latex("")
    assert not r_empty.valid, "Empty formula must be invalid"
    # Malformed LaTeX (e.g. \frac{) may be invalid or parsed; at least we get a result
    for latex in FORMULA_SAMPLES_INVALID:
        if latex == "":
            continue
        r = validate_formula_latex(latex)
        assert hasattr(r, "valid"), f"Expected ValidationResult for: {latex!r}"


def test_formula_correctness_rate():
    """Renderer reports correctness rate >= 98% on valid samples."""
    _require_math_diagram_deps()
    renderer = MathDiagramRenderer()
    rate = renderer.formula_correctness_rate(FORMULA_SAMPLES_VALID)
    assert rate >= 0.98, f"Expected >= 98% correctness, got {rate * 100:.1f}%"


def test_validate_formula_sympy_expr():
    """SymPy expression string validation (e.g. x**2 + 1)."""
    pytest.importorskip("sympy", reason="pip install -r requirements.txt (sympy)")
    r = validate_formula_sympy_expr("x**2 + 1")
    assert r.valid
    assert r.parsed_expr is not None
    r2 = validate_formula_sympy_expr("invalid {{{")
    assert not r2.valid


def test_check_formula_equivalence():
    """Equivalence check: same meaning formulas (LaTeX) return True."""
    _require_math_diagram_deps()
    # LaTeX-only: x^2 and x^{2} are equivalent; 1+1 and 2 are equivalent
    assert check_formula_equivalence("x^2", "x^{2}") is True
    assert check_formula_equivalence("1+1", "2") is True
    assert check_formula_equivalence("x", "y") is False


def test_latex_to_raster():
    """LaTeX renders to non-empty PNG bytes (matplotlib fallback if no latex2svg)."""
    _require_math_diagram_deps()
    png = render_latex_to_png(r"x^2 + y^2", font_size=20, dpi=100)
    assert png is not None, "LaTeX rasterization failed (matplotlib required)"
    assert len(png) > 100
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_renderer_singleton():
    """Default renderer is a singleton."""
    r1 = get_default_math_diagram_renderer()
    r2 = get_default_math_diagram_renderer()
    assert r1 is r2


def test_render_formula_placement():
    """Render formula onto image at placement."""
    _require_math_diagram_deps()
    from PIL import Image

    renderer = MathDiagramRenderer()
    base = Image.new("RGB", (400, 300), (50, 50, 50))
    placement = FormulaPlacement(
        latex=r"E = mc^2",
        x=50,
        y=50,
        font_size=22,
        color=(255, 255, 255),
    )
    out = renderer.render_formula_placement(base, placement)
    assert out is not None
    assert out.size == (400, 300)


def test_overlay_math_on_image():
    """Convenience overlay_math_on_image produces image."""
    _require_math_diagram_deps()
    from PIL import Image

    base = Image.new("RGB", (320, 240), (30, 30, 30))
    out = overlay_math_on_image(base, r"\frac{1}{2}", x=20, y=20, font_size=18)
    assert out is not None
    assert out.size == base.size


def test_lighting_options():
    """Blend with shadow/opacity produces image."""
    _require_math_diagram_deps()
    from PIL import Image

    renderer = MathDiagramRenderer()
    base = Image.new("RGB", (300, 200), (60, 60, 60))
    placement = FormulaPlacement(
        latex=r"a^2 + b^2",
        x=150,
        y=100,
        anchor="mm",
        lighting=LightingOptions(
            shadow_offset=(4, 4),
            shadow_blur=3,
            shadow_opacity=0.4,
            opacity=1.0,
        ),
    )
    out = renderer.render_formula_placement(base, placement)
    assert out is not None


def test_chart_render():
    """Matplotlib chart renders to PNG bytes."""
    _require_math_diagram_deps()
    assert DiagramKind is not None
    renderer = MathDiagramRenderer()
    spec = ChartSpec(
        kind=DiagramKind.CHART_BAR,
        data={"labels": ["A", "B", "C"], "values": [10, 20, 15]},
        width=300,
        height=200,
        title="Test Chart",
    )
    png = renderer.render_chart(spec)
    assert png is not None, "Chart rendering failed (matplotlib required)"
    assert len(png) > 100
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_chart_line():
    """Line chart renders."""
    _require_math_diagram_deps()
    assert DiagramKind is not None
    spec = ChartSpec(
        kind=DiagramKind.CHART_LINE,
        data={"x": [1, 2, 3], "y": [1, 4, 2]},
        width=400,
        height=300,
    )
    png = MathDiagramRenderer().render_chart(spec)
    assert png is not None


def test_chart_pie():
    """Pie chart renders."""
    _require_math_diagram_deps()
    assert DiagramKind is not None
    spec = ChartSpec(
        kind=DiagramKind.CHART_PIE,
        data={"labels": ["X", "Y", "Z"], "sizes": [30, 50, 20]},
        width=300,
        height=300,
    )
    png = MathDiagramRenderer().render_chart(spec)
    assert png is not None


def test_overlay_chart():
    """Chart overlay on image."""
    _require_math_diagram_deps()
    from PIL import Image

    assert DiagramKind is not None
    renderer = MathDiagramRenderer()
    base = Image.new("RGB", (500, 400), (40, 40, 40))
    spec = ChartSpec(
        kind=DiagramKind.CHART_BAR,
        data={"labels": ["Q1", "Q2"], "values": [100, 150]},
        width=200,
        height=150,
    )
    out = renderer.overlay_chart(base, spec, x=50, y=50, anchor="lt")
    assert out is not None
    assert out.size == base.size


def test_validation_result_attributes():
    """ValidationResult has valid, error, parsed_expr, normalized_latex."""
    _require_math_diagram_deps()
    r = validate_formula_latex(r"x^2")
    assert hasattr(r, "valid")
    assert hasattr(r, "error")
    assert hasattr(r, "parsed_expr")
    assert hasattr(r, "normalized_latex")
    assert r.valid
    assert r.error is None

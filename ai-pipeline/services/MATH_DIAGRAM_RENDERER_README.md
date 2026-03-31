# Math & Diagram Renderer

**Priority:** P1 | **Success metric:** 98%+ formula correctness, aesthetically pleasing.

## Goal

Render LaTeX formulas and diagrams in images:

- **LaTeX → SVG → Rasterize → Blend with lighting**
- **Matplotlib** for charts/graphs (line, bar, pie, scatter)
- **SymPy** validation for formula correctness

## File

`math_diagram_renderer.py`

## Pipeline

1. **LaTeX formula**
   - Optional: `latex2svg` (system LaTeX + dvisvgm) → SVG → `cairosvg` → PNG
   - Fallback: matplotlib mathtext → PNG (no system LaTeX)

2. **Blend with lighting**
   - Shadow (offset, blur, opacity), optional glow, tint, overall opacity
   - Alpha-composite onto base image with anchor (lt, ct, rt, lm, mm, rm, lb, cb, rb)

3. **Charts**
   - `ChartSpec(kind=CHART_LINE|CHART_BAR|CHART_PIE|CHART_SCATTER|AXES_2D, data={...})`
   - Rendered via Matplotlib → PNG → overlay on image

4. **Validation**
   - `validate_formula_latex(latex)` → SymPy `parse_latex` (requires `antlr4-python3-runtime`)
   - `validate_formula_sympy_expr(expr_str)` for plain expressions (e.g. `x**2 + 1`)
   - `check_formula_equivalence(latex1, latex2)` for semantic equality

## Dependencies

- **Required:** `sympy`, `antlr4-python3-runtime>=4.11,<4.12` (SymPy parse_latex needs 4.11.x; 4.13+ incompatible), `matplotlib`, `Pillow`
- **Optional:** `latex2svg` (LaTeX→SVG; needs system `latex` + `dvisvgm`), `cairosvg` (SVG→PNG)

## Usage

```python
from services.math_diagram_renderer import (
    MathDiagramRenderer,
    FormulaPlacement,
    ChartSpec,
    DiagramKind,
    LightingOptions,
    validate_formula_latex,
    render_latex_to_png,
    overlay_math_on_image,
    get_default_math_diagram_renderer,
)

# Validate
r = validate_formula_latex(r"x^2 + y^2")
assert r.valid

# Render formula to PNG bytes
png = render_latex_to_png(r"E = mc^2", font_size=24, dpi=150)

# Overlay formula on image
from PIL import Image
img = Image.open("base.png")
out = overlay_math_on_image(img, r"\frac{a}{b}", x=50, y=50, font_size=22)

# Multiple placements with lighting
renderer = get_default_math_diagram_renderer()
placements = [
    FormulaPlacement(latex=r"x^2", x=100, y=100, font_size=28, anchor="mm",
                     lighting=LightingOptions(shadow_offset=(4, 4), shadow_opacity=0.4)),
]
out = renderer.overlay_formulas(img, placements)

# Chart overlay
spec = ChartSpec(kind=DiagramKind.CHART_BAR, data={"labels": ["A", "B"], "values": [10, 20]}, width=300, height=200)
out = renderer.overlay_chart(img, spec, x=50, y=50, anchor="lt")
```

## Deterministic pipeline

When using `DeterministicPipeline`, set post-process to overlay formulas from the scene graph:

```python
from services.deterministic_pipeline import create_pipeline, math_diagram_post_process

pipeline = create_pipeline(use_post_process=False)
pipeline.set_post_process(math_diagram_post_process)
# scene_graph should contain "formula_placements": [{"latex": r"E=mc^2", "x": 50, "y": 50}, ...]
```

## Tests

`ai-pipeline/tests/test_math_diagram_renderer.py`

- Formula validation (valid/invalid), correctness rate (98%+ on SymPy-parseable samples)
- LaTeX→raster, overlay formula/chart, lighting options
- Chart kinds (bar, line, pie), overlay on image

Install `antlr4-python3-runtime` for full LaTeX validation; tests that depend on `parse_latex` skip when antlr4 is missing.

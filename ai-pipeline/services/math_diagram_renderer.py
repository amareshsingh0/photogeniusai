"""
Math & Diagram Renderer — LaTeX formulas and diagrams in images.

Pipeline:
  LaTeX → SVG → Rasterize → Blend with lighting
  Matplotlib for charts/graphs
  SymPy validation for formula correctness

Success metric: 98%+ formula correctness, aesthetically pleasing.
Dependencies: sympy, matplotlib; optional: latex2svg, cairosvg (for SVG path).
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Optional PIL
try:
    from PIL import Image, ImageFilter

    HAS_PIL = True
except ImportError:
    Image = None
    ImageFilter = None
    HAS_PIL = False

# Optional matplotlib (formulas + charts)
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:
    plt = None
    HAS_MATPLOTLIB = False

# SymPy for validation (and optional LaTeX export)
try:
    import sympy
    from sympy import latex as sympy_latex
    from sympy.parsing.latex import parse_latex
    from sympy import simplify, Eq

    HAS_SYMPY = True
except ImportError:
    sympy = None
    parse_latex = None
    HAS_SYMPY = False

# Optional: LaTeX → SVG (requires system latex + dvisvgm)
try:
    from latex2svg import latex2svg as _latex2svg

    HAS_LATEX2SVG = True
except ImportError:
    _latex2svg = None
    HAS_LATEX2SVG = False

# Optional: SVG → PNG rasterization
try:
    import cairosvg

    HAS_CAIROSVG = True
except ImportError:
    cairosvg = None
    HAS_CAIROSVG = False


class DiagramKind(Enum):
    """Kind of diagram or formula to render."""

    FORMULA = "formula"  # LaTeX math
    CHART_LINE = "chart_line"
    CHART_BAR = "chart_bar"
    CHART_PIE = "chart_pie"
    CHART_SCATTER = "chart_scatter"
    AXES_2D = "axes_2d"  # Generic 2D plot


@dataclass
class LightingOptions:
    """Options for blending with lighting (shadow, glow, tint)."""

    shadow_offset: Tuple[int, int] = (3, 3)
    shadow_blur: int = 4
    shadow_opacity: float = 0.35
    glow_radius: int = 0
    glow_opacity: float = 0.0
    tint_rgb: Optional[Tuple[int, int, int]] = None
    blend_mode: str = "over"  # over, soft_light, multiply
    opacity: float = 1.0


@dataclass
class FormulaPlacement:
    """Where and how to place a formula on the image."""

    latex: str
    x: int
    y: int
    width: Optional[int] = None
    height: Optional[int] = None
    font_size: int = 24
    color: Tuple[int, int, int] = (255, 255, 255)
    background: Optional[Tuple[int, int, int]] = None
    anchor: str = "lt"  # lt, ct, rt, lm, mm, rm, lb, cb, rb
    lighting: Optional[LightingOptions] = None


@dataclass
class ChartSpec:
    """Specification for a Matplotlib chart to render."""

    kind: DiagramKind
    data: Dict[str, Any]  # x, y for line/scatter; labels, sizes for pie; etc.
    width: int = 400
    height: int = 300
    title: Optional[str] = None
    style: str = "seaborn-v0_8-whitegrid"
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    color_cycle: Optional[List[str]] = None


@dataclass
class ValidationResult:
    """Result of SymPy-based formula validation."""

    valid: bool
    parsed_expr: Optional[Any] = None
    error: Optional[str] = None
    normalized_latex: Optional[str] = None
    simplified: Optional[str] = None


# ---------------------------------------------------------------------------
# SymPy validation (98%+ correctness target)
# ---------------------------------------------------------------------------


def validate_formula_latex(latex: str) -> ValidationResult:
    """
    Validate LaTeX formula for correctness using SymPy.
    Returns ValidationResult with valid=True if parseable and well-formed.
    """
    if not HAS_SYMPY:
        return ValidationResult(valid=False, error="SymPy not installed")
    latex = (latex or "").strip()
    if not latex:
        return ValidationResult(valid=False, error="Empty formula")
    # Strip display/inline wrappers for parsing
    stripped = re.sub(r"^\\\[|\]$", "", latex)
    stripped = re.sub(r"^\\\(|\\\)$", "", stripped)
    stripped = re.sub(r"^\$+|\$+$", "", stripped)
    try:
        expr = parse_latex(stripped)
        if expr is None:
            return ValidationResult(valid=False, error="Parse returned None")
        simplified = str(simplify(expr))
        try:
            norm_latex = sympy_latex(expr)
        except Exception:
            norm_latex = None
        return ValidationResult(
            valid=True,
            parsed_expr=expr,
            normalized_latex=norm_latex,
            simplified=simplified,
        )
    except Exception as e:
        return ValidationResult(valid=False, error=str(e))


def validate_formula_sympy_expr(expr_str: str) -> ValidationResult:
    """Validate a SymPy-notation expression string (e.g. 'x**2 + 1')."""
    if not HAS_SYMPY:
        return ValidationResult(valid=False, error="SymPy not installed")
    try:
        expr = sympy.sympify(expr_str)
        simplified = str(simplify(expr))
        norm_latex = sympy_latex(expr)
        return ValidationResult(
            valid=True,
            parsed_expr=expr,
            normalized_latex=norm_latex,
            simplified=simplified,
        )
    except Exception as e:
        return ValidationResult(valid=False, error=str(e))


def check_formula_equivalence(latex1: str, latex2: str) -> bool:
    """Return True if both formulas parse and simplify to the same expression."""
    r1 = validate_formula_latex(latex1)
    r2 = validate_formula_latex(latex2)
    if not r1.valid or not r2.valid:
        return False
    if r1.parsed_expr is None or r2.parsed_expr is None:
        return False
    try:
        eq = simplify(Eq(r1.parsed_expr, r2.parsed_expr))
        sympy_true = getattr(getattr(sympy, "S", None), "True", None)
        if sympy_true is not None and eq == sympy_true:
            return True
        # Fallback: difference simplifies to zero, or equals()
        diff = simplify(r1.parsed_expr - r2.parsed_expr)
        if diff == 0:
            return True
        if getattr(r1.parsed_expr, "equals", None) and r1.parsed_expr.equals(
            r2.parsed_expr
        ):
            return True
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# LaTeX → SVG (latex2svg or fallback)
# ---------------------------------------------------------------------------


def _latex_to_svg_latex2svg(latex: str) -> Optional[str]:
    """Use latex2svg if available (requires system LaTeX + dvisvgm)."""
    if not HAS_LATEX2SVG or _latex2svg is None:
        return None
    try:
        # latex2svg expects a full minimal document or inline math
        if not latex.strip().startswith("\\"):
            latex = r"\( " + latex + r" \)"
        out = _latex2svg(latex)
        if isinstance(out, dict) and "svg" in out:
            return out["svg"]
        return None
    except Exception as e:
        logger.debug("latex2svg failed: %s", e)
        return None


def _latex_to_png_matplotlib(
    latex: str, font_size: int = 24, dpi: int = 150
) -> Optional[bytes]:
    """Render LaTeX to PNG via matplotlib mathtext (no system LaTeX required)."""
    if not HAS_MATPLOTLIB or plt is None:
        return None
    latex = (latex or "").strip()
    latex = re.sub(r"^\\\[|\]$", "", latex)
    latex = re.sub(r"^\\\(|\\\)$", "", latex)
    latex = re.sub(r"^\$+|\$+$", "", latex)
    if not latex:
        return None
    try:
        fig, ax = plt.subplots(figsize=(6, 2), dpi=dpi)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.text(0.5, 0.5, f"${latex}$", fontsize=font_size, ha="center", va="center")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.05, dpi=dpi)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.debug("matplotlib formula render failed: %s", e)
        return None


def _svg_to_png_cairo(
    svg_content: Union[str, bytes], scale: float = 2.0
) -> Optional[bytes]:
    """Rasterize SVG to PNG using cairosvg."""
    if not HAS_CAIROSVG or cairosvg is None:
        return None
    try:
        if isinstance(svg_content, str):
            svg_content = svg_content.encode("utf-8")
        png_bytes = cairosvg.svg2png(bytestring=svg_content, scale=scale)
        return png_bytes
    except Exception as e:
        logger.debug("cairosvg rasterize failed: %s", e)
        return None


def _svg_to_png_pil_fallback(svg_content: Union[str, bytes]) -> Optional[bytes]:
    """Fallback: we don't have a pure-Python SVG rasterizer; return None so caller uses matplotlib PNG."""
    return None


# ---------------------------------------------------------------------------
# Blend with lighting (shadow, glow, tint)
# ---------------------------------------------------------------------------


def _blend_with_lighting(
    base: "Image.Image",
    overlay: "Image.Image",
    x: int,
    y: int,
    options: Optional[LightingOptions] = None,
    anchor: str = "lt",
) -> "Image.Image":
    """Composite overlay onto base with optional shadow, glow, and tint."""
    if not HAS_PIL or Image is None or base is None or overlay is None:
        return base
    opts = options or LightingOptions()
    ow, oh = overlay.size
    # Anchor: adjust (x,y) so overlay is positioned correctly
    if "c" in anchor or "m" in anchor:
        x = x - ow // 2
    if "r" in anchor:
        x = x - ow
    if "m" in anchor or "c" in anchor:
        y = y - oh // 2
    if "b" in anchor:
        y = y - oh
    x, y = int(x), int(y)
    overlay = overlay.convert("RGBA")
    alpha_channel = overlay.split()[-1]
    # Shadow layer (from copy so we don't mutate overlay yet)
    if (
        opts.shadow_offset != (0, 0)
        and opts.shadow_opacity > 0
        and opts.shadow_blur >= 0
    ):
        shadow = overlay.copy()
        shadow_arr = np.array(shadow)
        if shadow_arr.ndim == 3:
            shadow_arr[..., :3] = np.clip(
                shadow_arr[..., :3].astype(np.float32) * 0.2, 0, 255
            ).astype(np.uint8)
            shadow_arr[..., 3] = (
                shadow_arr[..., 3].astype(np.float32) * opts.shadow_opacity
            ).astype(np.uint8)
        shadow_pil = Image.fromarray(shadow_arr)
        if opts.shadow_blur > 0 and ImageFilter is not None:
            shadow_pil = shadow_pil.filter(
                ImageFilter.GaussianBlur(radius=opts.shadow_blur)
            )
        dx, dy = opts.shadow_offset
        base.paste(shadow_pil, (x + dx, y + dy), shadow_pil.split()[-1])
    # Glow (optional): blurred copy behind overlay
    if opts.glow_radius > 0 and opts.glow_opacity > 0 and ImageFilter is not None:
        glow = overlay.copy()
        glow = glow.filter(ImageFilter.GaussianBlur(radius=opts.glow_radius))
        glow_arr = np.array(glow)
        if glow_arr.ndim == 3 and glow_arr.shape[2] == 4:
            glow_arr[..., 3] = (
                glow_arr[..., 3].astype(np.float32) * opts.glow_opacity
            ).astype(np.uint8)
            glow = Image.fromarray(glow_arr)
        base.paste(glow, (x, y), glow.split()[-1])
    # Main overlay: opacity and optional tint
    out_overlay = overlay
    if opts.opacity < 1.0:
        a = overlay.split()[-1]
        a = a.point(lambda v: int(v * opts.opacity))
        out_overlay = overlay.copy()
        out_overlay.putalpha(a)
    if opts.tint_rgb:
        arr = np.array(out_overlay)
        if arr.ndim == 3 and arr.shape[2] >= 3:
            r, g, b = opts.tint_rgb
            arr[..., 0] = np.clip(
                arr[..., 0].astype(np.float32) * (r / 255.0), 0, 255
            ).astype(np.uint8)
            arr[..., 1] = np.clip(
                arr[..., 1].astype(np.float32) * (g / 255.0), 0, 255
            ).astype(np.uint8)
            arr[..., 2] = np.clip(
                arr[..., 2].astype(np.float32) * (b / 255.0), 0, 255
            ).astype(np.uint8)
            out_overlay = Image.fromarray(arr)
    base.paste(out_overlay, (x, y), out_overlay.split()[-1])
    return base


# ---------------------------------------------------------------------------
# Matplotlib charts
# ---------------------------------------------------------------------------


def _render_chart(spec: ChartSpec) -> Optional[bytes]:
    """Render a chart to PNG bytes using Matplotlib."""
    if not HAS_MATPLOTLIB or plt is None:
        return None
    try:
        if spec.style:
            try:
                plt.style.use(spec.style)
            except Exception:
                try:
                    plt.style.use("seaborn-v0_8-whitegrid")
                except Exception:
                    pass
        fig, ax = plt.subplots(figsize=(spec.width / 100, spec.height / 100), dpi=100)
        data = spec.data or {}
        kind = spec.kind
        if kind == DiagramKind.CHART_LINE:
            x = data.get("x", [])
            y = data.get("y", [])
            if not x:
                x = list(range(len(y)))
            ax.plot(
                x,
                y,
                marker=data.get("marker", "o"),
                markersize=data.get("markersize", 4),
            )
        elif kind == DiagramKind.CHART_BAR:
            labels = data.get("labels", [])
            values = data.get("values", [])
            colors = spec.color_cycle or ["#2ecc71", "#3498db", "#9b59b6", "#e74c3c"]
            bars = ax.bar(labels, values, color=colors[: len(values)])
            ax.tick_params(axis="x", rotation=data.get("rotation", 45))
        elif kind == DiagramKind.CHART_PIE:
            labels = data.get("labels", [])
            sizes = data.get("sizes", [])
            colors = (
                spec.color_cycle or plt.rcParams["axes.prop_cycle"].by_key()["color"]
            )
            ax.pie(
                sizes,
                labels=labels,
                autopct=data.get("autopct", "%1.1f%%"),
                colors=colors[: len(sizes)],
            )
        elif kind == DiagramKind.CHART_SCATTER:
            x = data.get("x", [])
            y = data.get("y", [])
            ax.scatter(
                x, y, s=data.get("s", 20), c=data.get("c"), alpha=data.get("alpha", 0.7)
            )
        else:
            x = data.get("x", [])
            y = data.get("y", [])
            if x or y:
                ax.plot(x or list(range(len(y))), y or [], "o-")
        if spec.title:
            ax.set_title(spec.title)
        if spec.x_label:
            ax.set_xlabel(spec.x_label)
        if spec.y_label:
            ax.set_ylabel(spec.y_label)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning("Chart render failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Main renderer class
# ---------------------------------------------------------------------------


class MathDiagramRenderer:
    """
    Render LaTeX formulas and Matplotlib diagrams; blend with lighting.
    Pipeline: LaTeX → SVG → Rasterize → Blend (or Matplotlib → PNG → Blend).
    SymPy used for formula validation (98%+ correctness target).
    """

    def __init__(
        self,
        default_font_size: int = 24,
        default_dpi: int = 150,
        prefer_latex2svg: bool = True,
    ):
        self.default_font_size = default_font_size
        self.default_dpi = default_dpi
        self.prefer_latex2svg = prefer_latex2svg and HAS_LATEX2SVG

    def validate(self, latex: str) -> ValidationResult:
        """Validate formula for correctness (SymPy)."""
        return validate_formula_latex(latex)

    def latex_to_raster(
        self,
        latex: str,
        font_size: Optional[int] = None,
        dpi: Optional[int] = None,
    ) -> Optional[bytes]:
        """
        Render LaTeX to PNG bytes.
        Tries: latex2svg → cairosvg; fallback: matplotlib mathtext → PNG.
        """
        fs = font_size or self.default_font_size
        dpi = dpi or self.default_dpi
        png_bytes: Optional[bytes] = None
        if self.prefer_latex2svg and HAS_LATEX2SVG:
            svg = _latex_to_svg_latex2svg(latex)
            if svg and HAS_CAIROSVG:
                png_bytes = _svg_to_png_cairo(svg, scale=dpi / 72.0)
            if png_bytes is None and svg:
                png_bytes = _svg_to_png_pil_fallback(svg)
        if png_bytes is None and HAS_MATPLOTLIB:
            png_bytes = _latex_to_png_matplotlib(latex, font_size=fs, dpi=dpi)
        return png_bytes

    def render_formula_placement(
        self,
        image: Any,
        placement: FormulaPlacement,
    ) -> Any:
        """
        Render one formula onto the image at (x, y) with optional lighting.
        image: PIL Image or numpy array (H, W, 3).
        """
        if not HAS_PIL or Image is None:
            return image
        if hasattr(image, "mode"):
            base = image.convert("RGB")
        else:
            base = Image.fromarray(np.asarray(image).astype(np.uint8)).convert("RGB")
        png_bytes = self.latex_to_raster(placement.latex, font_size=placement.font_size)
        if not png_bytes:
            return base
        overlay = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        if placement.background is not None:
            bg = Image.new("RGBA", overlay.size, placement.background + (255,))
            overlay = Image.alpha_composite(bg, overlay)
        w, h = overlay.size
        if placement.width is not None or placement.height is not None:
            nw = placement.width or w
            nh = placement.height or h
            overlay = overlay.resize((nw, nh), Image.Resampling.LANCZOS)
        lighting = placement.lighting or LightingOptions()
        return _blend_with_lighting(
            base,
            overlay,
            placement.x,
            placement.y,
            options=lighting,
            anchor=placement.anchor,
        )

    def overlay_formulas(
        self,
        image: Any,
        placements: List[FormulaPlacement],
    ) -> Any:
        """Render multiple formulas onto the image."""
        out = image
        for p in placements:
            out = self.render_formula_placement(out, p)
        return out

    def render_chart(
        self,
        spec: ChartSpec,
    ) -> Optional[bytes]:
        """Render a chart to PNG bytes."""
        return _render_chart(spec)

    def overlay_chart(
        self,
        image: Any,
        spec: ChartSpec,
        x: int = 0,
        y: int = 0,
        anchor: str = "lt",
        lighting: Optional[LightingOptions] = None,
    ) -> Any:
        """Render chart and composite onto image at (x, y)."""
        if not HAS_PIL or Image is None:
            return image
        png_bytes = _render_chart(spec)
        if not png_bytes:
            return image
        if hasattr(image, "mode"):
            base = image.convert("RGB")
        else:
            base = Image.fromarray(np.asarray(image).astype(np.uint8)).convert("RGB")
        overlay = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        opts = lighting or LightingOptions()
        return _blend_with_lighting(base, overlay, x, y, options=opts, anchor=anchor)

    def formula_correctness_rate(self, latex_samples: List[str]) -> float:
        """
        Compute fraction of samples that validate successfully (for 98%+ target).
        """
        if not latex_samples:
            return 1.0
        ok = sum(1 for s in latex_samples if validate_formula_latex(s).valid)
        return ok / len(latex_samples)


# Singleton and helpers
_default_renderer: Optional[MathDiagramRenderer] = None


def get_default_math_diagram_renderer() -> MathDiagramRenderer:
    global _default_renderer
    if _default_renderer is None:
        _default_renderer = MathDiagramRenderer()
    return _default_renderer


def render_latex_to_png(
    latex: str,
    font_size: int = 24,
    dpi: int = 150,
) -> Optional[bytes]:
    """Convenience: render LaTeX to PNG using default renderer."""
    return get_default_math_diagram_renderer().latex_to_raster(
        latex, font_size=font_size, dpi=dpi
    )


def overlay_math_on_image(
    image: Any,
    latex: str,
    x: int = 10,
    y: int = 10,
    font_size: int = 24,
    color: Optional[Tuple[int, int, int]] = None,
    lighting: Optional[LightingOptions] = None,
) -> Any:
    """Convenience: overlay single formula on image."""
    placement = FormulaPlacement(
        latex=latex,
        x=x,
        y=y,
        font_size=font_size,
        color=color or (255, 255, 255),
        lighting=lighting,
    )
    return get_default_math_diagram_renderer().render_formula_placement(
        image, placement
    )

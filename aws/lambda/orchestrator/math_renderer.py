"""
Math & Diagram Rendering.

Renders LaTeX formulas and charts onto images.
Lightweight alternative to math_diagram_renderer; uses matplotlib mathtext.
"""

from __future__ import annotations

import io
from typing import Any, Optional, Tuple

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    Image = None
    HAS_PIL = False

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:
    plt = None
    HAS_MATPLOTLIB = False


class MathRenderer:
    """Render mathematical formulas and charts onto images."""

    def __init__(self) -> None:
        pass

    def render_latex_to_image(
        self,
        latex: str,
        dpi: int = 300,
    ) -> Any:
        """
        Render LaTeX formula to image using matplotlib mathtext.

        Args:
            latex: LaTeX string (e.g. r"$E = mc^2$" or "$\\\\frac{1}{2}$")
            dpi: Resolution for output image.

        Returns:
            PIL Image of rendered formula (RGBA), or None if dependencies missing.
        """
        if not latex or not HAS_PIL or not HAS_MATPLOTLIB or plt is None:
            return None
        # Ensure math mode for mathtext if not already wrapped
        text = latex.strip()
        if not (text.startswith("$") and text.endswith("$")):
            text = f"${text}$"
        try:
            fig, ax = plt.subplots(figsize=(4, 2))
            ax.text(0.5, 0.5, text, size=40, ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            buf = io.BytesIO()
            plt.savefig(
                buf,
                format="png",
                dpi=dpi,
                bbox_inches="tight",
                pad_inches=0.1,
                transparent=True,
            )
            plt.close(fig)
            buf.seek(0)
            img = Image.open(buf).copy()
            return img.convert("RGBA")
        except Exception:
            plt.close("all")
            return None

    def add_formula_to_image(
        self,
        image: Any,
        latex: str,
        position: Tuple[int, int] = (50, 50),
    ) -> Any:
        """
        Add formula overlay to image.

        Args:
            image: PIL Image (RGB or RGBA).
            latex: LaTeX string to render.
            position: (x, y) top-left where formula is pasted.

        Returns:
            New image with formula pasted, or original image if render fails.
        """
        if not HAS_PIL or Image is None:
            return image
        formula_img = self.render_latex_to_image(latex)
        if formula_img is None:
            return image
        if hasattr(image, "mode"):
            img_copy = image.copy()
        else:
            import numpy as np

            img_copy = Image.fromarray(np.asarray(image).astype("uint8"))
        if img_copy.mode != "RGBA":
            img_copy = img_copy.convert("RGBA")
        x, y = int(position[0]), int(position[1])
        img_copy.paste(formula_img, (x, y), formula_img)
        return img_copy.convert("RGB")

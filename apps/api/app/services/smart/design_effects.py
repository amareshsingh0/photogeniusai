"""
Design Effects Engine — PIL-based post-processing for professional polish.

Applied AFTER generation + text overlay to add that "100% premium" feel.
These are the subtle touches that separate amateur from professional:

1. Vignette — darkened edges draw eye to center
2. Color grading — mood-appropriate tonal shift
3. Sharpening — crisp professional finish
4. Subtle grain — analog film texture (optional)

All effects run on CPU via PIL. No GPU needed.

Usage:
    from app.services.smart.design_effects import design_effects

    # Apply effects based on style
    enhanced_b64 = design_effects.apply(image_b64, style="poster")
"""

from __future__ import annotations

import base64
import io
import logging

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from .config import get_effect_preset

logger = logging.getLogger(__name__)


class DesignEffects:
    """Post-processing effects engine for professional image polish."""

    def apply(
        self,
        image_b64: str,
        style: str = "photo",
        intensity: float = 1.0,
    ) -> str:
        """
        Apply style-appropriate post-processing effects.

        Args:
            image_b64: Base64-encoded image (raw, no data: prefix)
            style: Design style from layout planner
            intensity: Effect intensity multiplier (0.0-1.0)

        Returns:
            Base64-encoded enhanced image
        """
        img_bytes = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(img_bytes))
        orig_format = img.format or "PNG"
        img = img.convert("RGB")

        # ── Style-specific effect chains (from central config) ────────────
        effects = get_effect_preset(style)

        if effects.get("color_boost"):
            img = self._color_boost(img, effects["color_boost"] * intensity)

        if effects.get("contrast"):
            img = self._contrast(img, effects["contrast"] * intensity)

        if effects.get("sharpness"):
            img = self._sharpen(img, effects["sharpness"] * intensity)

        if effects.get("vignette"):
            img = self._vignette(img, effects["vignette"] * intensity)

        if effects.get("warmth"):
            img = self._warmth(img, effects["warmth"] * intensity)

        if effects.get("grain"):
            img = self._subtle_grain(img, effects["grain"] * intensity)

        # ── Re-encode ─────────────────────────────────────────────────────
        buf = io.BytesIO()
        if orig_format.upper() == "JPEG":
            img.save(buf, format="JPEG", quality=95)
        else:
            img.save(buf, format=orig_format)

        return base64.b64encode(buf.getvalue()).decode("ascii")

    def apply_to_data_url(self, data_url: str, style: str = "photo", **kwargs) -> str:
        """Apply effects to a data URL and return updated data URL."""
        if not data_url.startswith("data:"):
            return data_url
        header, b64_data = data_url.split(",", 1)
        new_b64 = self.apply(b64_data, style=style, **kwargs)
        return f"{header},{new_b64}"

    # ── Individual effects ────────────────────────────────────────────────

    def _color_boost(self, img: Image.Image, factor: float) -> Image.Image:
        """Boost color saturation. factor: 0.0=grey, 1.0=no change, >1.0=boost."""
        enhancer = ImageEnhance.Color(img)
        return enhancer.enhance(1.0 + (factor - 1.0) * 0.5)

    def _contrast(self, img: Image.Image, factor: float) -> Image.Image:
        """Adjust contrast. factor: 1.0=no change, >1.0=more contrast."""
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)

    def _sharpen(self, img: Image.Image, factor: float) -> Image.Image:
        """Sharpen image for crisp details. factor: 1.0=normal, >1.0=sharper."""
        enhancer = ImageEnhance.Sharpness(img)
        return enhancer.enhance(factor)

    def _vignette(self, img: Image.Image, strength: float) -> Image.Image:
        """
        Add radial vignette — darkened edges drawing eye to center.

        strength: 0.0=none, 1.0=full
        """
        if strength <= 0.05:
            return img

        w, h = img.size
        # Create radial gradient mask
        vignette = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(vignette)

        # Draw concentric ellipses from edge (dark) to center (bright)
        max_dim = max(w, h)
        steps = 40
        for i in range(steps):
            # From outer (dark) to inner (bright)
            t = i / steps
            brightness = int(255 * (t**1.5))  # power curve for smooth falloff
            margin_x = int(w * (1 - t) * 0.5)
            margin_y = int(h * (1 - t) * 0.5)
            draw.ellipse(
                [margin_x, margin_y, w - margin_x, h - margin_y],
                fill=brightness,
            )

        # Blur the mask for smooth transition
        vignette = vignette.filter(ImageFilter.GaussianBlur(radius=int(max_dim // 15)))

        # Blend: darken edges by mixing with a black layer
        dark = Image.new("RGB", (w, h), 0)
        # Scale vignette alpha by strength
        vignette_scaled = vignette.point(lambda p: int(p + (255 - p) * (1 - strength)))
        img = Image.composite(img, dark, vignette_scaled)

        return img

    def _warmth(self, img: Image.Image, factor: float) -> Image.Image:
        """
        Shift color temperature.

        factor > 0 = warmer (golden tones)
        factor < 0 = cooler (blue tones)
        """
        if abs(factor) < 0.05:
            return img

        channels = img.split()
        if len(channels) < 3:
            return img
        r, g, b = channels[0], channels[1], channels[2]
        shift = int(factor * 8)  # subtle: ±8 per channel max

        r = r.point(lambda p: min(255, max(0, p + shift)))
        b = b.point(lambda p: min(255, max(0, p - shift)))

        return Image.merge("RGB", (r, g, b))

    def _subtle_grain(self, img: Image.Image, strength: float) -> Image.Image:
        """Add subtle film grain for analog texture."""
        if strength <= 0.05:
            return img

        import random

        w, h = img.size
        # Create noise layer
        grain = Image.new("L", (w, h))
        pixel_access = grain.load()
        if pixel_access is None:
            return img
        grain_amount = int(strength * 15)
        for y in range(0, h, 2):  # skip every other row for performance
            for x in range(0, w, 2):
                noise = 128 + random.randint(-grain_amount, grain_amount)
                pixel_access[x, y] = noise
                if x + 1 < w:
                    pixel_access[x + 1, y] = noise
                if y + 1 < h:
                    pixel_access[x, y + 1] = noise
                    if x + 1 < w:
                        pixel_access[x + 1, y + 1] = noise

        grain = grain.filter(ImageFilter.GaussianBlur(radius=1))
        grain_rgb = Image.merge("RGB", (grain, grain, grain))

        # Blend grain with original using low-opacity overlay
        blended = Image.blend(img, grain_rgb, alpha=min(0.08, strength * 0.08))
        return blended



# Singleton
design_effects = DesignEffects()

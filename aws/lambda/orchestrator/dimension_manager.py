"""
Dimension Manager
=================
Users can request any width × height they want.  Diffusion models are picky
about their native resolutions (e.g. 512×512, 1024×1024, 768×512, etc.).

This module:
    1. Validates incoming W×H (min / max limits, sane ratios)
    2. Maps it to the *closest* native diffusion resolution
    3. After the model generates, upscales / crops / pads back to the exact
       user-requested dimensions with high quality.

Supported aspect ratios (Stable Diffusion style — all multiples of 64):
    1:1   →  512×512,   768×768,   1024×1024
    4:3   →  768×576,   1024×768
    3:2   →  768×512,   1024×682 → rounded to 1024×704
    16:9  →  1024×576,  1280×720
    2:1   →  1024×512,  1280×640
    3:4   →  576×768,   768×1024
    2:3   →  512×768,   704×1024
    9:16  →  576×1024,  720×1280

Any ratio not exactly in the table is mapped to the closest supported one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image  # type: ignore[reportMissingImports]

    HAS_PIL = True
except ImportError:
    Image = None  # type: ignore
    HAS_PIL = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Hard limits (pixels)
MIN_DIMENSION = 64
MAX_DIMENSION = 4096
MAX_MEGAPIXELS = 12.0  # 12 MP max total

# All supported native resolutions the diffusion model can produce
NATIVE_RESOLUTIONS: List[Tuple[int, int]] = [
    # Square
    (512, 512),
    (768, 768),
    (1024, 1024),
    # Landscape
    (768, 512),
    (1024, 768),
    (768, 576),
    (1024, 682),
    (1280, 720),
    (1024, 576),
    (1280, 640),
    (1536, 1024),
    (2048, 1024),
    # Portrait (just flip landscape)
    (512, 768),
    (768, 1024),
    (576, 768),
    (682, 1024),
    (720, 1280),
    (576, 1024),
    (640, 1280),
    (1024, 1536),
    (1024, 2048),
]

# Quality presets map to native res ranges
QUALITY_NATIVE_MAP: Dict[str, Tuple[int, int]] = {
    "low": (256, 512),
    "medium": (512, 768),
    "high": (768, 1024),
    "ultra": (1024, 1536),
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DimensionSpec:
    """User-requested dimensions."""

    width: int
    height: int
    label: Optional[str] = None  # "4K", "Instagram", "story", etc.


@dataclass
class DimensionPlan:
    """
    Output of the Dimension Manager.
    Contains everything the pipeline needs to generate at the right size
    and then post-process to the exact requested size.
    """

    requested_w: int
    requested_h: int
    native_w: int  # what we actually ask the model to generate
    native_h: int
    post_process_strategy: str  # "upscale", "downscale", "crop", "pad", "exact", "none"
    aspect_ratio: str  # human-friendly e.g. "16:9"
    is_valid: bool = True
    validation_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Aspect-ratio helpers
# ---------------------------------------------------------------------------


def gcd(a: int, b: int) -> int:
    a, b = int(a), int(b)
    while b:
        a, b = b, a % b
    return max(a, 1)


def compute_aspect_ratio(w: int, h: int) -> str:
    """Return simplified aspect ratio string, e.g. '16:9'."""
    if h <= 0:
        return "1:1"
    g = gcd(w, h)
    return f"{w // g}:{h // g}"


def aspect_ratio_float(w: int, h: int) -> float:
    if h <= 0:
        return 1.0
    return w / h


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


class DimensionManager:
    """
    Validates, maps, and post-processes dimensions.

    Typical usage:
        dm = DimensionManager()

        # 1. User says "1920x1080"
        plan = dm.plan_dimensions(1920, 1080)

        # 2. Pipeline generates at (plan.native_w, plan.native_h)
        generated_image = pipeline.generate(width=plan.native_w, height=plan.native_h, ...)

        # 3. Post-process to exact user size
        final_image = dm.post_process(generated_image, plan)
    """

    def __init__(self) -> None:
        self._native = NATIVE_RESOLUTIONS

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, width: int, height: int) -> Optional[str]:
        """Returns None if valid, or an error string."""
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            return "Width and height must be numbers."
        width, height = int(width), int(height)
        if width < MIN_DIMENSION or width > MAX_DIMENSION:
            return f"Width must be between {MIN_DIMENSION} and {MAX_DIMENSION}. Got {width}."
        if height < MIN_DIMENSION or height > MAX_DIMENSION:
            return f"Height must be between {MIN_DIMENSION} and {MAX_DIMENSION}. Got {height}."
        megapixels = (width * height) / 1_000_000
        if megapixels > MAX_MEGAPIXELS:
            return (
                f"Total resolution {width}×{height} = {megapixels:.1f} MP exceeds "
                f"the {MAX_MEGAPIXELS} MP limit. Try reducing one dimension."
            )
        return None  # valid

    # ------------------------------------------------------------------
    # Native resolution mapping
    # ------------------------------------------------------------------

    def _find_closest_native(self, target_w: int, target_h: int) -> Tuple[int, int]:
        """
        Find the native resolution that:
            a) has the most similar aspect ratio to the target, AND
            b) among equal-ratio candidates, is closest in total pixel count.
        """
        target_ratio = aspect_ratio_float(target_w, target_h)
        target_pixels = target_w * target_h

        best: Optional[Tuple[int, int]] = None
        best_ratio_diff: float = float("inf")
        best_pixel_diff: float = float("inf")

        for nw, nh in self._native:
            r_diff = abs(aspect_ratio_float(nw, nh) - target_ratio)
            p_diff = abs((nw * nh) - target_pixels)
            if (r_diff < best_ratio_diff) or (
                r_diff == best_ratio_diff and p_diff < best_pixel_diff
            ):
                best = (nw, nh)
                best_ratio_diff = r_diff
                best_pixel_diff = p_diff

        return best or (1024, 1024)  # fallback

    # ------------------------------------------------------------------
    # Plan
    # ------------------------------------------------------------------

    def plan_dimensions(self, width: int, height: int) -> DimensionPlan:
        """Main entry point. Returns a complete DimensionPlan."""
        try:
            w, h = int(width), int(height)
        except (TypeError, ValueError):
            return DimensionPlan(
                requested_w=0,
                requested_h=0,
                native_w=0,
                native_h=0,
                post_process_strategy="none",
                aspect_ratio="",
                is_valid=False,
                validation_error="Width and height must be integers.",
            )
        error = self.validate(w, h)
        if error:
            return DimensionPlan(
                requested_w=w,
                requested_h=h,
                native_w=0,
                native_h=0,
                post_process_strategy="none",
                aspect_ratio="",
                is_valid=False,
                validation_error=error,
            )

        native_w, native_h = self._find_closest_native(w, h)

        if native_w == w and native_h == h:
            strategy = "exact"
        elif w * h > native_w * native_h:
            strategy = "upscale"
        else:
            strategy = "downscale"

        return DimensionPlan(
            requested_w=w,
            requested_h=h,
            native_w=native_w,
            native_h=native_h,
            post_process_strategy=strategy,
            aspect_ratio=compute_aspect_ratio(w, h),
            is_valid=True,
        )

    # ------------------------------------------------------------------
    # Post-processing  (PIL-based)
    # ------------------------------------------------------------------

    def post_process(self, image: Any, plan: DimensionPlan) -> Any:
        """
        Takes the model-generated image at native resolution and produces
        an image at exactly (plan.requested_w × plan.requested_h).

        Strategy:
            exact      → return as-is
            upscale    → high-quality LANCZOS resize (preserving aspect ratio)
                         then center-crop to exact dimensions
            downscale  → LANCZOS resize (preserving ratio) + center-crop
        """
        if not plan.is_valid or plan.post_process_strategy in ("none", "exact"):
            return image
        if not HAS_PIL or Image is None:
            return image
        if not hasattr(image, "resize") or not hasattr(image, "crop"):
            return image

        target_w = plan.requested_w
        target_h = plan.requested_h
        cur_w, cur_h = image.size
        scale_w = target_w / max(1, cur_w)
        scale_h = target_h / max(1, cur_h)
        scale = max(scale_w, scale_h)
        new_w = int(round(cur_w * scale))
        new_h = int(round(cur_h * scale))
        resized = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        right = left + target_w
        bottom = top + target_h
        cropped = resized.crop((left, top, right, bottom))
        return cropped

    # ------------------------------------------------------------------
    # Convenience: parse user input strings
    # ------------------------------------------------------------------

    @staticmethod
    def parse_dimension_string(dim_str: str) -> Optional[Tuple[int, int]]:
        """
        Parse strings like "1920x1080", "1920 x 1080", "1920×1080", "1920, 1080".
        Returns (width, height) or None if unparseable.
        """
        if not dim_str or not isinstance(dim_str, str):
            return None
        m = re.match(r"^\s*(\d+)\s*[x×,\s]\s*(\d+)\s*$", dim_str.strip())
        if m:
            return int(m.group(1)), int(m.group(2))
        return None

    @staticmethod
    def preset_dimensions(label: str) -> Optional[Tuple[int, int]]:
        """Common named presets."""
        presets: Dict[str, Tuple[int, int]] = {
            "instagram_square": (1080, 1080),
            "instagram_story": (1080, 1920),
            "instagram_portrait": (1080, 1350),
            "instagram_landscape": (1200, 1000),
            "twitter_header": (1500, 500),
            "twitter_post": (1200, 675),
            "facebook_cover": (820, 312),
            "facebook_post": (1200, 630),
            "linkedin_cover": (1584, 396),
            "youtube_thumbnail": (1280, 720),
            "hd": (1280, 720),
            "fullhd": (1920, 1080),
            "1440p": (2560, 1440),
            "4k": (3840, 2160),
            "mac_retina": (2560, 1600),
            "a4_portrait_300dpi": (2480, 3508),
            "a4_landscape_300dpi": (3508, 2480),
            "letter_portrait": (2550, 3300),
            "letter_landscape": (3300, 2550),
            "thumbnail_small": (256, 256),
            "thumbnail_medium": (512, 512),
            "icon_app": (1024, 1024),
            "favicon": (64, 64),
            "phone_wallpaper": (1080, 1920),
            "desktop_wallpaper": (1920, 1080),
            "ipad_wallpaper": (2048, 2732),
        }
        key = (label or "").lower().replace(" ", "_").replace("-", "_")
        return presets.get(key)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def resolve_dimensions(
    width: Optional[int] = None,
    height: Optional[int] = None,
    preset: Optional[str] = None,
) -> DimensionPlan:
    """
    Resolve dimensions from either explicit W×H or a preset name.
    Returns a ready-to-use DimensionPlan.
    """
    dm = DimensionManager()
    if preset:
        resolved = DimensionManager.preset_dimensions(preset)
        if resolved:
            width, height = resolved
    if width is None or height is None:
        width = width or 1024
        height = height or 1024
    return dm.plan_dimensions(width, height)


__all__ = [
    "MIN_DIMENSION",
    "MAX_DIMENSION",
    "MAX_MEGAPIXELS",
    "NATIVE_RESOLUTIONS",
    "QUALITY_NATIVE_MAP",
    "DimensionSpec",
    "DimensionPlan",
    "gcd",
    "compute_aspect_ratio",
    "aspect_ratio_float",
    "DimensionManager",
    "resolve_dimensions",
]

"""
Brand Checker — Validate image/design against brand guidelines.

Checks:
    1. Color palette compliance — dominant colors match brand palette
    2. Tone consistency — creative tone matches brand tone
    3. Forbidden colors — no brand-restricted colors present
    4. Contrast compliance — meets brand's min contrast ratio (WCAG)
    5. Restriction compliance — free-text rule checks

All checks are PIL/numpy-based (CPU-only). No external APIs.

Feature Flag:
    USE_BRAND_CHECKER = True  — Enable brand compliance checking
"""

from __future__ import annotations

import logging
import math
import base64
import io
from typing import Dict, List, Optional, TypedDict, Tuple

from .config import BrandGuidelines, get_brand, DEFAULT_BRAND

logger = logging.getLogger(__name__)

USE_BRAND_CHECKER = True


class BrandVerdict(TypedDict):
    compliant: bool                  # Overall pass/fail
    score: float                     # 0.0-1.0 compliance score
    color_match: float               # 0.0-1.0 palette match
    tone_match: float                # 0.0-1.0 tone consistency
    forbidden_violation: bool        # True if forbidden colors detected
    contrast_ok: bool                # Meets min contrast ratio
    issues: List[str]                # Detected issues


# Tone keywords for matching creative tone → brand tone
_TONE_KEYWORDS: Dict[str, List[str]] = {
    "professional": ["business", "corporate", "office", "meeting", "professional", "clean", "minimal"],
    "playful": ["fun", "party", "colorful", "bright", "happy", "cute", "cartoon", "game"],
    "luxury": ["luxury", "premium", "elegant", "gold", "diamond", "exclusive", "vip", "high-end"],
    "casual": ["casual", "everyday", "simple", "chill", "relaxed", "friendly", "easy"],
    "bold": ["bold", "strong", "power", "intense", "extreme", "mega", "ultimate", "fire"],
}


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return (
        int(hex_color[0:2], 16),
        int(hex_color[1:4][:2], 16) if len(hex_color) >= 4 else 0,
        int(hex_color[4:6], 16) if len(hex_color) >= 6 else 0,
    )


def _hex_to_rgb_safe(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex to RGB, handling edge cases."""
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    if len(hex_color) < 6:
        hex_color = hex_color.ljust(6, "0")
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (128, 128, 128)


def _color_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    """Euclidean distance in RGB space (0-441.67)."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def _relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG relative luminance from sRGB."""
    def linearize(v: int) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _wcag_contrast_ratio(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    """WCAG 2.1 contrast ratio between two colors."""
    l1 = _relative_luminance(*c1)
    l2 = _relative_luminance(*c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class BrandChecker:
    """Validate designs against brand guidelines."""

    def check(
        self,
        image_b64: Optional[str] = None,
        prompt: str = "",
        brand_name: str = "default",
        has_text: bool = False,
        creative_tone: str = "",
    ) -> BrandVerdict:
        if not USE_BRAND_CHECKER:
            return BrandVerdict(
                compliant=True, score=1.0, color_match=1.0,
                tone_match=1.0, forbidden_violation=False,
                contrast_ok=True, issues=[],
            )

        brand = get_brand(brand_name)
        issues: List[str] = []

        # 1. Color palette match
        color_match = self._check_color_palette(image_b64, brand)
        if color_match < 0.4:
            issues.append("Image colors diverge significantly from brand palette")

        # 2. Tone consistency
        tone_match = self._check_tone(prompt, creative_tone, brand)
        if tone_match < 0.3:
            issues.append(f"Creative tone doesn't match brand tone '{brand.get('tone', 'professional')}'")

        # 3. Forbidden colors
        forbidden_violation = self._check_forbidden_colors(image_b64, brand)
        if forbidden_violation:
            issues.append("Forbidden brand colors detected in image")

        # 4. Contrast compliance
        contrast_ok = True
        if has_text and image_b64:
            contrast_ok = self._check_contrast(image_b64, brand)
            if not contrast_ok:
                min_ratio = brand.get("min_contrast_ratio", 4.5)
                issues.append(f"Text contrast below brand minimum ({min_ratio}:1 WCAG)")

        # Composite score
        weights = {"color": 0.35, "tone": 0.25, "forbidden": 0.20, "contrast": 0.20}
        score = (
            color_match * weights["color"]
            + tone_match * weights["tone"]
            + (0.0 if forbidden_violation else 1.0) * weights["forbidden"]
            + (1.0 if contrast_ok else 0.3) * weights["contrast"]
        )
        score = round(score, 3)
        compliant = score >= 0.50 and not forbidden_violation

        logger.info(
            "[BRAND] score=%.3f color=%.2f tone=%.2f forbidden=%s contrast=%s compliant=%s",
            score, color_match, tone_match, forbidden_violation, contrast_ok, compliant,
        )

        return BrandVerdict(
            compliant=compliant,
            score=score,
            color_match=round(color_match, 3),
            tone_match=round(tone_match, 3),
            forbidden_violation=forbidden_violation,
            contrast_ok=contrast_ok,
            issues=issues,
        )

    def _check_color_palette(self, image_b64: Optional[str], brand: BrandGuidelines) -> float:
        """Check if dominant image colors match brand palette."""
        brand_colors = brand.get("primary_colors", []) + brand.get("secondary_colors", [])
        if not brand_colors or not image_b64:
            return 0.7  # no brand colors defined = assume OK

        try:
            from PIL import Image
            import numpy as np

            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
            img = img.resize((32, 32))
            pixels = np.array(img).reshape(-1, 3)

            # Get top 5 dominant colors via simple binning
            # Quantize to 8 levels per channel
            quantized = (pixels // 32) * 32 + 16
            unique, counts = np.unique(quantized, axis=0, return_counts=True)
            top_idx = np.argsort(-counts)[:5]
            dominant = [tuple(unique[i]) for i in top_idx]

            # Check how many dominant colors are close to brand colors
            brand_rgbs = [_hex_to_rgb_safe(c) for c in brand_colors]
            match_threshold = 100  # RGB distance

            matches = 0
            for dom in dominant:
                for br in brand_rgbs:
                    if _color_distance(dom, br) < match_threshold:
                        matches += 1
                        break

            return min(matches / max(len(dominant), 1) * 1.5, 1.0)

        except Exception as e:
            logger.debug("Color palette check failed: %s", e)
            return 0.6

    def _check_tone(self, prompt: str, creative_tone: str, brand: BrandGuidelines) -> float:
        """Check if creative tone matches brand tone."""
        brand_tone = brand.get("tone", "professional")
        if not brand_tone:
            return 0.8

        # Direct match
        if creative_tone.lower() == brand_tone.lower():
            return 1.0

        # Keyword match from prompt
        prompt_lower = prompt.lower()
        brand_keywords = _TONE_KEYWORDS.get(brand_tone.lower(), [])
        if not brand_keywords:
            return 0.7

        hits = sum(1 for kw in brand_keywords if kw in prompt_lower)
        return min(hits / 3, 1.0) if hits > 0 else 0.4

    def _check_forbidden_colors(self, image_b64: Optional[str], brand: BrandGuidelines) -> bool:
        """Check if any forbidden colors appear prominently in the image."""
        forbidden = brand.get("forbidden_colors", [])
        if not forbidden or not image_b64:
            return False

        try:
            from PIL import Image
            import numpy as np

            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
            img = img.resize((32, 32))
            pixels = np.array(img).reshape(-1, 3)

            forbidden_rgbs = [_hex_to_rgb_safe(c) for c in forbidden]
            threshold = 60  # tighter threshold for forbidden

            for frgb in forbidden_rgbs:
                distances = np.sqrt(np.sum((pixels.astype(float) - np.array(frgb, dtype=float)) ** 2, axis=1))
                # If >5% of pixels match forbidden color, flag it
                if (distances < threshold).sum() > len(pixels) * 0.05:
                    return True

            return False

        except Exception as e:
            logger.debug("Forbidden color check failed: %s", e)
            return False

    def _check_contrast(self, image_b64: str, brand: BrandGuidelines) -> bool:
        """Check if text zones meet WCAG contrast requirements."""
        min_ratio = brand.get("min_contrast_ratio", 4.5)

        try:
            from PIL import Image
            import numpy as np

            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
            w, h = img.size
            arr = np.array(img)

            # Sample text zones (top 15%, bottom 15%)
            for zone_slice in [arr[:int(h * 0.15), :], arr[int(h * 0.85):, :]]:
                if zone_slice.size == 0:
                    continue
                pixels = zone_slice.reshape(-1, 3)

                # Find darkest and lightest in zone
                lums = np.array([_relative_luminance(int(p[0]), int(p[1]), int(p[2])) for p in pixels[:100]])
                if len(lums) < 2:
                    continue

                darkest_lum = float(np.percentile(lums, 5))
                lightest_lum = float(np.percentile(lums, 95))

                ratio = (lightest_lum + 0.05) / (darkest_lum + 0.05)
                if ratio < min_ratio:
                    return False

            return True

        except Exception as e:
            logger.debug("Contrast check failed: %s", e)
            return True  # assume OK if check fails


# Singleton
brand_checker = BrandChecker()

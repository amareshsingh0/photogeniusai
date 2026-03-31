"""
Poster / Ad Jury v2 — Advanced quality signals for advertising content.

Extends the existing jury with poster-specific quality checks that run
on the FINAL image (after text overlay + effects).

Signals:
    1. Text readability   — contrast ratio between text and background
    2. Layout balance     — visual weight distribution (from creative graph)
    3. Negative space     — ratio of "breathing room" in composition
    4. Color harmony      — palette coherence score
    5. OCR validation     — PIL-based text rendering quality check (NEW v2)
    6. Composition score  — Rule-of-thirds adherence (NEW v2)
    7. WCAG contrast      — Accessibility-grade contrast ratio (NEW v2)
    8. Brand compliance   — Score from BrandChecker (NEW v2)

All checks are PIL-based (CPU-only). No external models needed.

Feature Flags:
    USE_OCR_ALIGNMENT = True    — PIL-based text zone quality validation
    USE_BRAND_CHECKER = True    — Brand guideline compliance via BrandChecker
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, TypedDict, Tuple
import base64
import io

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Feature Flags
# ══════════════════════════════════════════════════════════════════════════════
USE_OCR_ALIGNMENT = True        # PIL-based text rendering quality check
USE_BRAND_CHECKER = True        # Brand guideline compliance


# ══════════════════════════════════════════════════════════════════════════════
# Types
# ══════════════════════════════════════════════════════════════════════════════

class JuryVerdict(TypedDict):
    overall_score: float         # 0.0-1.0 composite quality score
    readability: float           # 0.0-1.0 text contrast/readability
    balance: float               # 0.0-1.0 visual balance
    negative_space: float        # 0.0-1.0 breathing room quality
    color_harmony: float         # 0.0-1.0 palette coherence
    ocr_quality: float           # 0.0-1.0 text rendering quality (NEW)
    composition: float           # 0.0-1.0 rule-of-thirds adherence (NEW)
    wcag_contrast: float         # 0.0-1.0 WCAG contrast compliance (NEW)
    brand_score: float           # 0.0-1.0 brand compliance (NEW)
    passed: bool                 # meets minimum quality threshold
    issues: List[str]            # list of detected issues
    grade: str                   # A/B/C/D/F letter grade (NEW)


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

# WCAG AA minimum contrast ratio for large text
MIN_CONTRAST_RATIO_AA = 3.0
# WCAG AA for normal text
MIN_CONTRAST_RATIO_NORMAL = 4.5
# Our target for great readability
TARGET_CONTRAST_RATIO = 7.0

# Minimum overall score to pass
MIN_PASS_SCORE = 0.40

# Weights for composite score (v2 — 8 signals)
_WEIGHTS = {
    "readability": 0.20,
    "balance": 0.15,
    "negative_space": 0.10,
    "color_harmony": 0.10,
    "ocr_quality": 0.15,
    "composition": 0.10,
    "wcag_contrast": 0.10,
    "brand_score": 0.10,
}

# Grade thresholds
_GRADES = [
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.40, "D"),
    (0.00, "F"),
]


def _relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG 2.1 relative luminance."""
    def linearize(v: int) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


# ══════════════════════════════════════════════════════════════════════════════
# Jury Class
# ══════════════════════════════════════════════════════════════════════════════

class PosterJury:
    """
    Evaluates final ad/poster image quality using design heuristics.

    Runs after text overlay and design effects have been applied.
    Returns actionable quality signals that can feed back into the pipeline.
    """

    def evaluate(
        self,
        image_b64: Optional[str] = None,
        visual_balance: float = 0.5,
        total_text_area: float = 0.0,
        has_text: bool = False,
        is_ad: bool = False,
        subject_x: float = 0.5,
        subject_y: float = 0.5,
        brand_verdict: Optional[Dict] = None,
    ) -> JuryVerdict:
        """
        Evaluate a poster/ad image with 8 quality signals.

        Args:
            image_b64: Base64-encoded image (for readability + color checks)
            visual_balance: From creative graph (0.0-1.0)
            total_text_area: Fraction of image with text
            has_text: Whether text overlay was applied
            is_ad: Whether this is advertising content
            subject_x: Subject horizontal position (0-1, from layout planner)
            subject_y: Subject vertical position (0-1, from layout planner)
            brand_verdict: Pre-computed BrandVerdict dict (optional)

        Returns:
            JuryVerdict with scores, issues, and letter grade
        """
        issues: List[str] = []

        # ── 1. Text readability ─────────────────────────────────────────
        if image_b64 and has_text:
            readability = self._check_readability(image_b64)
        else:
            readability = 0.7 if not has_text else 0.5

        if readability < 0.4:
            issues.append("Low text readability — consider higher contrast colors")

        # ── 2. Visual balance ───────────────────────────────────────────
        balance = visual_balance
        if balance < 0.3:
            issues.append("Poor visual balance — elements feel lopsided")

        # ── 3. Negative space ───────────────────────────────────────────
        negative_space = self._score_negative_space(total_text_area, is_ad)
        if negative_space < 0.3:
            issues.append("Insufficient breathing room — composition feels cramped")

        # ── 4. Color harmony ────────────────────────────────────────────
        if image_b64:
            color_harmony = self._check_color_harmony(image_b64)
        else:
            color_harmony = 0.6

        if color_harmony < 0.3:
            issues.append("Color palette feels disjointed — consider more cohesive colors")

        # ── 5. OCR validation (text rendering quality) ──────────────────
        if USE_OCR_ALIGNMENT and image_b64 and has_text:
            ocr_quality = self._check_text_rendering(image_b64)
        else:
            ocr_quality = 0.7 if not has_text else 0.5

        if ocr_quality < 0.4 and has_text:
            issues.append("Text rendering quality is low — text may be hard to read")

        # ── 6. Composition score (rule-of-thirds) ───────────────────────
        composition = self._score_composition(subject_x, subject_y, is_ad)
        if composition < 0.4:
            issues.append("Subject placement misses power points — consider rule-of-thirds")

        # ── 7. WCAG contrast ratio ─────────────────────────────────────
        if image_b64 and has_text:
            wcag_contrast = self._check_wcag_contrast(image_b64)
        else:
            wcag_contrast = 0.8 if not has_text else 0.5

        if wcag_contrast < 0.4 and has_text:
            issues.append("Text fails WCAG AA contrast — accessibility issue")

        # ── 8. Brand compliance ─────────────────────────────────────────
        if USE_BRAND_CHECKER and brand_verdict:
            brand_score = brand_verdict.get("score", 0.7)
            if not brand_verdict.get("compliant", True):
                issues.extend(brand_verdict.get("issues", []))
        else:
            brand_score = 0.7  # neutral default

        # ── Composite score ─────────────────────────────────────────────
        overall = (
            readability * _WEIGHTS["readability"]
            + balance * _WEIGHTS["balance"]
            + negative_space * _WEIGHTS["negative_space"]
            + color_harmony * _WEIGHTS["color_harmony"]
            + ocr_quality * _WEIGHTS["ocr_quality"]
            + composition * _WEIGHTS["composition"]
            + wcag_contrast * _WEIGHTS["wcag_contrast"]
            + brand_score * _WEIGHTS["brand_score"]
        )
        overall = round(overall, 3)
        passed = overall >= MIN_PASS_SCORE

        # Letter grade
        grade = "F"
        for threshold, letter in _GRADES:
            if overall >= threshold:
                grade = letter
                break

        verdict = JuryVerdict(
            overall_score=overall,
            readability=round(readability, 3),
            balance=round(balance, 3),
            negative_space=round(negative_space, 3),
            color_harmony=round(color_harmony, 3),
            ocr_quality=round(ocr_quality, 3),
            composition=round(composition, 3),
            wcag_contrast=round(wcag_contrast, 3),
            brand_score=round(brand_score, 3),
            passed=passed,
            issues=issues,
            grade=grade,
        )

        logger.info(
            "[JURY] grade=%s overall=%.3f read=%.2f bal=%.2f space=%.2f "
            "color=%.2f ocr=%.2f comp=%.2f wcag=%.2f brand=%.2f pass=%s issues=%d",
            grade, overall, readability, balance, negative_space,
            color_harmony, ocr_quality, composition, wcag_contrast, brand_score,
            passed, len(issues),
        )

        return verdict

    # ── Readability check ──────────────────────────────────────────────────

    def _check_readability(self, image_b64: str) -> float:
        """
        Check text readability by sampling luminance in text regions.

        Strategy: sample top 15% and bottom 15% of image (where text
        typically appears) and measure luminance variance. High variance
        in text zones = good contrast = readable text.
        """
        try:
            from PIL import Image
            import numpy as np

            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            w, h = img.size
            arr = np.array(img, dtype=np.float32)

            # Compute luminance (ITU-R BT.709)
            lum = 0.2126 * arr[:,:,0] + 0.7152 * arr[:,:,1] + 0.0722 * arr[:,:,2]
            lum /= 255.0

            # Sample text zones (top 15% and bottom 15%)
            top_zone = lum[:int(h * 0.15), :]
            bottom_zone = lum[int(h * 0.85):, :]

            scores = []
            for zone in [top_zone, bottom_zone]:
                if zone.size == 0:
                    continue
                std = float(np.std(zone))
                score = min(std / 0.3, 1.0)
                scores.append(score)

            return sum(scores) / len(scores) if scores else 0.5

        except Exception as e:
            logger.debug("Readability check failed: %s", e)
            return 0.5

    # ── Negative space scoring ─────────────────────────────────────────────

    def _score_negative_space(self, text_area: float, is_ad: bool) -> float:
        """Score negative space quality."""
        if not is_ad:
            return max(0.3, 1.0 - text_area * 3)

        if 0.15 <= text_area <= 0.30:
            return 0.9
        elif 0.10 <= text_area <= 0.35:
            return 0.7
        elif text_area < 0.05:
            return 0.4
        elif text_area > 0.50:
            return 0.2
        else:
            return 0.5

    # ── Color harmony check ────────────────────────────────────────────────

    def _check_color_harmony(self, image_b64: str) -> float:
        """Check color palette coherence by analyzing hue distribution."""
        try:
            from PIL import Image
            import numpy as np

            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(img_bytes)).convert("HSV")
            img = img.resize((64, 64))
            arr = np.array(img)

            hue = arr[:, :, 0].flatten()
            sat = arr[:, :, 1].flatten()

            mask = sat > 50
            if mask.sum() < 10:
                return 0.8

            hue_saturated = hue[mask]
            hist, _ = np.histogram(hue_saturated, bins=12, range=(0, 256))
            hist = hist / hist.sum()

            significant = (hist > 0.10).sum()

            if significant <= 2:
                return 0.9
            elif significant == 3:
                return 0.75
            elif significant == 4:
                return 0.5
            else:
                return 0.3

        except Exception as e:
            logger.debug("Color harmony check failed: %s", e)
            return 0.6

    # ── OCR validation (text rendering quality) ────────────────────────────

    def _check_text_rendering(self, image_b64: str) -> float:
        """
        PIL-based text rendering quality check (no external OCR).

        Strategy:
        - Sample text zones (top/bottom 15%)
        - Check for high-frequency edges (sharp text = more edges)
        - Measure local contrast variance (crisp text = high local contrast)
        - Check for text-on-busy-background overlap
        """
        try:
            from PIL import Image, ImageFilter
            import numpy as np

            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("L")
            w, h = img.size

            scores = []
            for zone_box in [(0, 0, w, int(h * 0.18)), (0, int(h * 0.82), w, h)]:
                zone = img.crop(zone_box)
                if zone.size[0] < 10 or zone.size[1] < 10:
                    continue

                # Edge detection — sharp text has strong edges
                edges = zone.filter(ImageFilter.FIND_EDGES)
                edge_arr = np.array(edges, dtype=np.float32)
                edge_density = float(np.mean(edge_arr > 30))

                # Local contrast — text creates strong local contrast
                arr = np.array(zone, dtype=np.float32)
                # Block-level variance (4x4 blocks)
                bh, bw = max(arr.shape[0] // 4, 1), max(arr.shape[1] // 4, 1)
                block_vars = []
                for by in range(0, arr.shape[0] - bh + 1, bh):
                    for bx in range(0, arr.shape[1] - bw + 1, bw):
                        block = arr[by:by+bh, bx:bx+bw]
                        block_vars.append(float(np.var(block)))
                avg_var = sum(block_vars) / max(len(block_vars), 1)

                # High edge density + high local variance = good text rendering
                # edge_density: 0.05→good text, 0.15+→great text
                edge_score = min(edge_density / 0.12, 1.0)
                # avg_var: 200→decent, 800+→great contrast
                var_score = min(avg_var / 600.0, 1.0)

                zone_score = 0.6 * edge_score + 0.4 * var_score
                scores.append(zone_score)

            return sum(scores) / max(len(scores), 1) if scores else 0.5

        except Exception as e:
            logger.debug("Text rendering check failed: %s", e)
            return 0.5

    # ── Composition score (rule-of-thirds) ─────────────────────────────────

    def _score_composition(self, subject_x: float, subject_y: float, is_ad: bool) -> float:
        """
        Score how well the subject aligns with rule-of-thirds power points.

        Power points: (1/3, 1/3), (2/3, 1/3), (1/3, 2/3), (2/3, 2/3)
        Also golden ratio points: (0.382, 0.382), (0.618, 0.382), etc.
        """
        # Rule-of-thirds power points
        rot_points = [
            (1/3, 1/3), (2/3, 1/3),
            (1/3, 2/3), (2/3, 2/3),
        ]
        # Golden ratio points
        golden_points = [
            (0.382, 0.382), (0.618, 0.382),
            (0.382, 0.618), (0.618, 0.618),
        ]
        # Center (acceptable for ads/products)
        center = (0.5, 0.5)

        all_points = rot_points + golden_points

        # Find minimum distance to any power point
        min_dist = float("inf")
        for px, py in all_points:
            dist = math.sqrt((subject_x - px) ** 2 + (subject_y - py) ** 2)
            min_dist = min(min_dist, dist)

        # Center bonus for ads (products often centered)
        center_dist = math.sqrt((subject_x - 0.5) ** 2 + (subject_y - 0.5) ** 2)
        if is_ad and center_dist < 0.1:
            return 0.85  # centered is fine for ads

        # Map distance to score: 0.0→1.0, 0.15→0.7, 0.3→0.3
        if min_dist < 0.08:
            return 0.95  # right on a power point
        elif min_dist < 0.15:
            return 0.80
        elif min_dist < 0.25:
            return 0.60
        else:
            return max(0.2, 1.0 - min_dist * 2)

    # ── WCAG contrast ratio ────────────────────────────────────────────────

    def _check_wcag_contrast(self, image_b64: str) -> float:
        """
        Check WCAG 2.1 contrast ratio in text zones.

        Measures actual contrast ratio between foreground/background
        in text regions and scores against WCAG AA/AAA thresholds.
        """
        try:
            from PIL import Image
            import numpy as np

            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
            w, h = img.size
            arr = np.array(img)

            scores = []
            for zone_slice in [arr[:int(h * 0.15), :], arr[int(h * 0.85):, :]]:
                if zone_slice.size == 0:
                    continue
                pixels = zone_slice.reshape(-1, 3)

                # Sample up to 200 pixels for speed
                step = max(1, len(pixels) // 200)
                sampled = pixels[::step]

                # Compute luminance for sampled pixels
                lums = []
                for p in sampled:
                    lums.append(_relative_luminance(int(p[0]), int(p[1]), int(p[2])))
                lums = sorted(lums)

                if len(lums) < 2:
                    continue

                # Contrast = ratio between 10th and 90th percentile luminance
                dark = lums[max(0, int(len(lums) * 0.10))]
                light = lums[min(len(lums) - 1, int(len(lums) * 0.90))]

                ratio = (light + 0.05) / (dark + 0.05)

                # Score: 7:1 → 1.0 (AAA), 4.5:1 → 0.75 (AA), 3:1 → 0.5 (AA large), <3 → poor
                if ratio >= TARGET_CONTRAST_RATIO:
                    scores.append(1.0)
                elif ratio >= MIN_CONTRAST_RATIO_NORMAL:
                    scores.append(0.75)
                elif ratio >= MIN_CONTRAST_RATIO_AA:
                    scores.append(0.50)
                else:
                    scores.append(max(0.1, ratio / MIN_CONTRAST_RATIO_AA * 0.5))

            return sum(scores) / max(len(scores), 1) if scores else 0.5

        except Exception as e:
            logger.debug("WCAG contrast check failed: %s", e)
            return 0.5


# Singleton
poster_jury = PosterJury()

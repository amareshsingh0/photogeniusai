"""
CTR Predictor — STAGE 10 of the Creative OS pipeline.

Predicts the click-through-rate potential of a generated ad/poster
based on heuristic design rules (future: trained model on CTR data).

Current implementation: rule-based scoring using proven design principles.
Returns a 0.0-1.0 "engagement potential" score.

Feature Flags:
    USE_CTR_MODEL = False      — Future: trained ML model on CTR data
    USE_AB_VARIANT = False     — Future: generate A/B test variants

This is a STUB that uses heuristic scoring NOW and will be upgraded
to a real model when training data is available.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Feature Flags — flip when models/data are ready
# ══════════════════════════════════════════════════════════════════════════════
USE_CTR_MODEL = False           # Future: trained CTR prediction model
USE_AB_VARIANT = False          # Future: auto-generate A/B variants
USE_HEATMAP_PREDICTOR = False   # Future: predict attention heatmap


# ══════════════════════════════════════════════════════════════════════════════
# Types
# ══════════════════════════════════════════════════════════════════════════════

class CTRPrediction(TypedDict):
    engagement_score: float      # 0.0-1.0 predicted engagement potential
    confidence: float            # how confident we are (low for heuristic)
    factors: Dict[str, float]    # breakdown of contributing factors
    suggestions: List[str]       # improvement suggestions
    method: str                  # "heuristic" | "model" (for transparency)


# ══════════════════════════════════════════════════════════════════════════════
# Heuristic Scoring Rules (based on ad design research)
# ══════════════════════════════════════════════════════════════════════════════

# Design principles that correlate with higher CTR (from advertising research):
# 1. High contrast text = +readability = +engagement
# 2. Clear CTA = +clicks
# 3. Faces in images = +attention (innate human response)
# 4. Color vibrancy = +attention (within limits)
# 5. Visual balance = +trust = +engagement
# 6. Negative space = +readability = +engagement
# 7. Rule of thirds = +aesthetic appeal


class CTRPredictor:
    """
    Predicts engagement potential of a creative composition.

    Current: heuristic scoring based on design research.
    Future (USE_CTR_MODEL=True): trained model on actual CTR data.
    """

    def predict(
        self,
        creative_type: str = "photo",
        is_ad: bool = False,
        visual_balance: float = 0.5,
        total_text_area: float = 0.0,
        cta_strength: float = 0.0,
        has_text: bool = False,
        quality_score: Optional[float] = None,
        goal: str = "aesthetic",
    ) -> CTRPrediction:
        """
        Predict engagement potential.

        Args:
            creative_type: "poster" | "ad" | "photo" | etc.
            is_ad: whether this is advertising content
            visual_balance: from creative graph (0.0-1.0)
            total_text_area: fraction of image covered by text
            cta_strength: how strong the CTA is (0.0-1.0)
            has_text: whether text overlay is present
            quality_score: CLIP quality score if available
            goal: "conversion" | "awareness" | "engagement" | "aesthetic"

        Returns:
            CTRPrediction with score, factors, and suggestions
        """
        if USE_CTR_MODEL:
            # Future: call trained model
            return self._predict_with_model()

        return self._predict_heuristic(
            creative_type, is_ad, visual_balance, total_text_area,
            cta_strength, has_text, quality_score, goal
        )

    def _predict_heuristic(
        self,
        creative_type: str,
        is_ad: bool,
        visual_balance: float,
        total_text_area: float,
        cta_strength: float,
        has_text: bool,
        quality_score: Optional[float],
        goal: str,
    ) -> CTRPrediction:
        factors: Dict[str, float] = {}
        suggestions: List[str] = []

        # Factor 1: Visual balance (well-balanced = trustworthy)
        factors["balance"] = visual_balance * 0.15
        if visual_balance < 0.4:
            suggestions.append("Improve visual balance — redistribute elements more evenly")

        # Factor 2: Text-to-image ratio (20-30% text is optimal for ads)
        if is_ad:
            if 0.15 <= total_text_area <= 0.35:
                factors["text_ratio"] = 0.15  # optimal range
            elif total_text_area < 0.10:
                factors["text_ratio"] = 0.05
                suggestions.append("Add more text content — ads need clear messaging")
            elif total_text_area > 0.40:
                factors["text_ratio"] = 0.05
                suggestions.append("Reduce text — too much text overwhelms the visual")
            else:
                factors["text_ratio"] = 0.10
        else:
            factors["text_ratio"] = 0.10  # non-ads: text ratio less important

        # Factor 3: CTA presence and strength
        if is_ad:
            factors["cta"] = cta_strength * 0.20
            if cta_strength < 0.3 and goal == "conversion":
                suggestions.append("Add a stronger call-to-action for conversion goals")
        else:
            factors["cta"] = 0.10

        # Factor 4: Quality score (from CLIP/aesthetic model)
        if quality_score is not None:
            factors["quality"] = min(quality_score, 1.0) * 0.20
        else:
            factors["quality"] = 0.10  # assume average

        # Factor 5: Has clear text hierarchy
        if has_text:
            factors["text_clarity"] = 0.12  # base for having text
        else:
            factors["text_clarity"] = 0.05 if not is_ad else 0.02

        # Factor 6: Creative type bonus
        type_bonus = {
            "poster": 0.10, "ad": 0.12, "banner": 0.10,
            "social": 0.08, "product_shot": 0.08,
        }
        factors["type_fit"] = type_bonus.get(creative_type, 0.05)

        # Sum factors
        engagement_score = min(sum(factors.values()), 1.0)

        # Generate additional suggestions based on goal
        if goal == "engagement" and not has_text:
            suggestions.append("Add engaging text or question to boost interaction")
        if goal == "awareness" and creative_type == "photo":
            suggestions.append("Consider poster/banner format for better brand awareness")

        prediction = CTRPrediction(
            engagement_score=round(engagement_score, 3),
            confidence=0.35,  # heuristic = low confidence
            factors={k: round(v, 3) for k, v in factors.items()},
            suggestions=suggestions,
            method="heuristic",
        )

        logger.info(
            "[CTR] score=%.3f confidence=%.2f method=%s factors=%s",
            prediction["engagement_score"], prediction["confidence"],
            prediction["method"], list(prediction["factors"].keys()),
        )

        return prediction

    def _predict_with_model(self) -> CTRPrediction:
        """Future: trained CTR model prediction."""
        raise NotImplementedError("CTR model not yet available. Set USE_CTR_MODEL=False")


# Singleton
ctr_predictor = CTRPredictor()

"""
Unified Scoring System – canonical schema, normalization, explainability.

All engines (Identity V2, Creative, Quality Scorer) emit scores in different
formats (0–1 vs 0–100). This service normalizes to 0–100, applies configurable
weights, produces human-readable explanations, and supports adaptive weighting
by prompt type (portrait / creative / product / default).

Audit: breakdown, confidence, selection_reason, comparison_notes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)


class ScoreComponent(str, Enum):
    """Standardized score components."""
    FACE_MATCH = "face_match"
    AESTHETIC = "aesthetic"
    TECHNICAL = "technical"
    PROMPT_ADHERENCE = "prompt_adherence"
    COMPOSITION = "composition"
    STYLE_CONSISTENCY = "style_consistency"


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown with explanations."""
    component: ScoreComponent
    raw_score: float
    normalized_score: float
    weight: float
    weighted_score: float
    confidence: float
    explanation: str
    source: str


@dataclass
class FinalScore:
    """Complete scoring result."""
    total: float
    breakdown: List[ScoreBreakdown]
    confidence: float
    selection_reason: str
    comparison_notes: Optional[str] = None


class ScoringService:
    """Centralized scoring with normalization and explainability."""

    DEFAULT_WEIGHTS: Dict[ScoreComponent, float] = {
        ScoreComponent.FACE_MATCH: 0.35,
        ScoreComponent.AESTHETIC: 0.30,
        ScoreComponent.TECHNICAL: 0.15,
        ScoreComponent.PROMPT_ADHERENCE: 0.15,
        ScoreComponent.COMPOSITION: 0.05,
    }

    WEIGHT_PROFILES: Dict[str, Dict[ScoreComponent, float]] = {
        "portrait": {
            ScoreComponent.FACE_MATCH: 0.50,
            ScoreComponent.AESTHETIC: 0.25,
            ScoreComponent.TECHNICAL: 0.15,
            ScoreComponent.PROMPT_ADHERENCE: 0.10,
        },
        "creative": {
            ScoreComponent.FACE_MATCH: 0.20,
            ScoreComponent.AESTHETIC: 0.40,
            ScoreComponent.COMPOSITION: 0.20,
            ScoreComponent.STYLE_CONSISTENCY: 0.20,
        },
        "product": {
            ScoreComponent.TECHNICAL: 0.40,
            ScoreComponent.AESTHETIC: 0.30,
            ScoreComponent.PROMPT_ADHERENCE: 0.30,
        },
    }

    def __init__(self, weight_profile: str = "default") -> None:
        if weight_profile == "default":
            self._weights = dict(self.DEFAULT_WEIGHTS)
        else:
            self._weights = dict(
                self.WEIGHT_PROFILES.get(
                    weight_profile,
                    self.DEFAULT_WEIGHTS,
                )
            )
        logger.info("ScoringService initialized with profile=%s", weight_profile)

    @property
    def weights(self) -> Dict[ScoreComponent, float]:
        """Weight set for current profile (same as DEFAULT_WEIGHTS / WEIGHT_PROFILES)."""
        return self._weights

    def normalize_score(
        self,
        raw_score: float,
        score_range: Tuple[float, float] = (0.0, 1.0),
    ) -> float:
        """Normalize any score to 0–100."""
        if raw_score is None:
            return 0.0
        min_val, max_val = score_range
        if max_val > 10:
            return float(np.clip(raw_score, 0, 100))
        normalized = ((raw_score - min_val) / (max_val - min_val + 1e-12)) * 100
        return float(np.clip(normalized, 0, 100))

    def compute_component_score(
        self,
        component: ScoreComponent,
        raw_score: float,
        confidence: float = 1.0,
        source: str = "unknown",
        score_range: Tuple[float, float] = (0.0, 1.0),
        weight: Optional[float] = None,
    ) -> ScoreBreakdown:
        """Compute a single score component with full breakdown."""
        normalized = self.normalize_score(raw_score, score_range)
        w = weight if weight is not None else self._weights.get(component, 0.0)
        weighted = normalized * w
        explanation = self._generate_explanation(component, normalized, confidence, source)
        return ScoreBreakdown(
            component=component,
            raw_score=raw_score,
            normalized_score=normalized,
            weight=w,
            weighted_score=weighted,
            confidence=confidence,
            explanation=explanation,
            source=source,
        )

    def _generate_explanation(
        self,
        component: ScoreComponent,
        normalized_score: float,
        confidence: float,
        source: str,
    ) -> str:
        if normalized_score >= 90:
            quality = "excellent"
        elif normalized_score >= 75:
            quality = "good"
        elif normalized_score >= 60:
            quality = "acceptable"
        else:
            quality = "needs improvement"
        if confidence < 0.7:
            conf_text = " (low confidence)"
        elif confidence < 0.9:
            conf_text = " (medium confidence)"
        else:
            conf_text = ""
        explanations = {
            ScoreComponent.FACE_MATCH: f"{quality} facial similarity{conf_text} - {source}",
            ScoreComponent.AESTHETIC: f"{quality} aesthetic quality{conf_text} - {source}",
            ScoreComponent.TECHNICAL: f"{quality} technical quality (sharpness, exposure, noise){conf_text}",
            ScoreComponent.PROMPT_ADHERENCE: f"{quality} alignment with prompt{conf_text}",
            ScoreComponent.COMPOSITION: f"{quality} composition and framing{conf_text}",
            ScoreComponent.STYLE_CONSISTENCY: f"{quality} style consistency{conf_text}",
        }
        return explanations.get(component, f"{quality} score")

    def _renormalize_weights(self, components: List[ScoreBreakdown]) -> List[ScoreBreakdown]:
        """Renormalize weights over available components so they sum to 1."""
        total_w = sum(c.weight for c in components)
        if total_w <= 0:
            return components
        out = []
        for c in components:
            w_new = c.weight / total_w
            out.append(
                ScoreBreakdown(
                    component=c.component,
                    raw_score=c.raw_score,
                    normalized_score=c.normalized_score,
                    weight=w_new,
                    weighted_score=c.normalized_score * w_new,
                    confidence=c.confidence,
                    explanation=c.explanation,
                    source=c.source,
                )
            )
        return out

    def compute_final_score(self, components: List[ScoreBreakdown]) -> FinalScore:
        """Compute final weighted score with full breakdown."""
        if not components:
            return FinalScore(
                total=0.0,
                breakdown=[],
                confidence=0.0,
                selection_reason="No score components available.",
            )
        normalized_components = self._renormalize_weights(components)
        total = sum(c.weighted_score for c in normalized_components)
        avg_confidence = float(np.mean([c.confidence for c in normalized_components]))
        selection_reason = self._generate_selection_reason(normalized_components, total)
        return FinalScore(
            total=round(total, 2),
            breakdown=normalized_components,
            confidence=round(avg_confidence, 3),
            selection_reason=selection_reason,
        )

    def _generate_selection_reason(
        self,
        components: List[ScoreBreakdown],
        total: float,
    ) -> str:
        sorted_comps = sorted(components, key=lambda c: c.weighted_score, reverse=True)
        strongest = sorted_comps[0]
        weakest = sorted_comps[-1]
        if total >= 85:
            return f"Excellent overall quality. Particularly strong {strongest.component.value} ({strongest.normalized_score:.1f}/100)."
        if total >= 70:
            return f"Good quality. Strong {strongest.component.value} ({strongest.normalized_score:.1f}/100), could improve {weakest.component.value}."
        if total >= 60:
            return f"Acceptable quality. Best aspect: {strongest.component.value}. Consider regenerating for better {weakest.component.value}."
        return f"Below quality threshold. Main issue: {weakest.component.value} ({weakest.normalized_score:.1f}/100). Recommend regeneration."

    def score_image(
        self,
        image_path: str,
        raw_scores: Dict[str, float],
        confidences: Dict[str, float],
        sources: Dict[str, str],
        score_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> FinalScore:
        """Score an image with full breakdown. image_path used as identifier for audit."""
        components: List[ScoreBreakdown] = []
        score_ranges = score_ranges or {}
        for component_name, raw_score in raw_scores.items():
            try:
                component = ScoreComponent(component_name)
            except ValueError:
                logger.warning("Unknown score component: %s", component_name)
                continue
            breakdown = self.compute_component_score(
                component=component,
                raw_score=raw_score,
                confidence=confidences.get(component_name, 1.0),
                source=sources.get(component_name, "unknown"),
                score_range=score_ranges.get(component_name, (0.0, 1.0)),
            )
            components.append(breakdown)
        return self.compute_final_score(components)

    def compare_images(
        self,
        image_scores: List[FinalScore],
        use_llm_tiebreak: bool = True,
        llm_threshold: float = 5.0,
    ) -> Tuple[int, str]:
        """Compare multiple image scores and select best. Returns (best_index, comparison_notes)."""
        if not image_scores:
            return 0, "No images to compare."
        sorted_indices = sorted(
            range(len(image_scores)),
            key=lambda i: image_scores[i].total,
            reverse=True,
        )
        best_idx = sorted_indices[0]
        best_score = image_scores[best_idx].total
        close = [
            i for i in sorted_indices
            if abs(image_scores[i].total - best_score) <= llm_threshold
        ]
        if len(close) > 1 and use_llm_tiebreak:
            return best_idx, (
                f"Top {len(close)} images within {llm_threshold} points. LLM tiebreak recommended."
            )
        if len(image_scores) > 1:
            second = image_scores[sorted_indices[1]].total
            gap = best_score - second
            comparison_notes = f"Clear winner by {gap:.1f} points."
        else:
            comparison_notes = "Single image scored."
        return best_idx, comparison_notes

    def get_audit_trail(self, fs: FinalScore) -> List[Dict[str, Any]]:
        """Audit trail of score calculation steps (normalize -> weight -> contribution)."""
        steps: List[Dict[str, Any]] = []
        for b in fs.breakdown:
            steps.append({
                "step": "normalize",
                "component": b.component.value,
                "raw_score": b.raw_score,
                "output": b.normalized_score,
                "explanation": f"Normalized to 0-100",
            })
            steps.append({
                "step": "weight",
                "component": b.component.value,
                "weight": b.weight,
                "weighted_contribution": b.weighted_score,
                "explanation": f"weight {b.weight:.2f} * {b.normalized_score:.1f} = {b.weighted_score:.2f}",
            })
        steps.append({
            "step": "total",
            "total": fs.total,
            "confidence": fs.confidence,
            "explanation": fs.selection_reason,
        })
        return steps

    def final_score_to_dict(self, fs: FinalScore) -> Dict[str, Any]:
        """Serialize FinalScore for API/storage."""
        return {
            "total": fs.total,
            "confidence": fs.confidence,
            "selection_reason": fs.selection_reason,
            "comparison_notes": fs.comparison_notes,
            "breakdown": [
                {
                    "component": b.component.value,
                    "raw_score": b.raw_score,
                    "normalized_score": b.normalized_score,
                    "weight": b.weight,
                    "weighted_score": b.weighted_score,
                    "confidence": b.confidence,
                    "explanation": b.explanation,
                    "source": b.source,
                }
                for b in fs.breakdown
            ],
            "audit_trail": self.get_audit_trail(fs),
        }


if __name__ == "__main__":
    # Validation: normalize, weight profiles, compare_images, audit trail
    s = ScoringService("portrait")
    assert abs(s.normalize_score(0.95, (0.0, 1.0)) - 95.0) < 1e-6
    assert abs(s.normalize_score(85, (0.0, 100.0)) - 85.0) < 1e-6
    assert s.weights.get(ScoreComponent.FACE_MATCH) == 0.50
    b = s.compute_component_score(
        ScoreComponent.FACE_MATCH, 0.98, 0.95, "ensemble", (0.0, 1.0)
    )
    assert abs(b.normalized_score - 98.0) < 1e-6
    fs = s.compute_final_score([b])
    assert fs.total > 0
    trail = s.get_audit_trail(fs)
    assert any(st["step"] == "normalize" for st in trail)
    assert any(st["step"] == "total" for st in trail)
    d = s.final_score_to_dict(fs)
    assert "audit_trail" in d and "breakdown" in d
    idx, notes = s.compare_images([fs, fs])
    assert idx in (0, 1)
    print("scoring_service validation OK")

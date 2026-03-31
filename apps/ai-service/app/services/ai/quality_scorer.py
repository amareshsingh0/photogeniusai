"""
Quality scoring for Best-of-N selection.

Scores:
- Face match % (if identity provided)
- Aesthetic score (LAION aesthetic predictor)
- Technical quality (blur, noise, exposure)
- Prompt adherence (CLIP similarity)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class QualityReport:
    """Quality report card for a generated image."""
    overall_score: float           # 0-100
    face_match_percent: Optional[float]  # 0-100, None if no identity
    aesthetic_score: float         # 0-10 (LAION scale)
    technical_quality: float       # 0-100
    prompt_adherence: float        # 0-100 (CLIP similarity)
    
    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "face_match_percent": self.face_match_percent,
            "aesthetic_score": self.aesthetic_score,
            "technical_quality": self.technical_quality,
            "prompt_adherence": self.prompt_adherence,
        }


def score(image_url: str, prompt: str, identity_embedding: Optional[bytes] = None) -> QualityReport:
    """
    Score a generated image for quality.
    
    Args:
        image_url: URL to the generated image
        prompt: Original prompt for CLIP similarity
        identity_embedding: Optional face embedding for match scoring
    
    Returns:
        QualityReport with all scores
    
    TODO: Integrate actual models
    - LAION aesthetic predictor
    - CLIP for prompt adherence
    - Face recognition for identity match
    - Technical quality (blur detection, etc.)
    """
    # Placeholder scores
    return QualityReport(
        overall_score=85.0,
        face_match_percent=92.0 if identity_embedding else None,
        aesthetic_score=7.5,
        technical_quality=88.0,
        prompt_adherence=90.0,
    )


def select_best(candidates: list[tuple[str, QualityReport]]) -> tuple[str, QualityReport]:
    """
    Select the best image from N candidates.
    
    Args:
        candidates: List of (image_url, QualityReport) tuples
    
    Returns:
        Best (image_url, QualityReport) based on overall_score
    """
    return max(candidates, key=lambda x: x[1].overall_score)

"""
Age estimation for Layer 2 safety.

Uses face detection + age estimation to block:
- Generated images depicting minors
- Any content where estimated age < 18
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgeResult:
    """Result of age estimation."""
    is_adult: bool
    estimated_age: Optional[float]  # None if no face detected
    confidence: float               # 0-1
    face_detected: bool
    
    def to_dict(self) -> dict:
        return {
            "is_adult": self.is_adult,
            "estimated_age": self.estimated_age,
            "confidence": self.confidence,
            "face_detected": self.face_detected,
        }


# Age threshold
MIN_ADULT_AGE = 18


def estimate(image_url: str) -> AgeResult:
    """
    Estimate age of person in image.
    
    Args:
        image_url: URL to the image
    
    Returns:
        AgeResult with age estimation
    
    TODO: Integrate actual estimator
    - Use face detection (e.g., MTCNN, RetinaFace)
    - Use age estimation model (e.g., DEX, AgeNet)
    - Handle multiple faces (block if any < 18)
    """
    # Placeholder: assume adult
    return AgeResult(
        is_adult=True,
        estimated_age=25.0,
        confidence=0.85,
        face_detected=True,
    )

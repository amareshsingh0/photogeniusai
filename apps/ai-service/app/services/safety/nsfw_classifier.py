"""
NSFW classification for Layer 2 safety.

Uses image classification to detect:
- Explicit sexual content
- Suggestive content
- Violence/gore
"""

from dataclasses import dataclass


@dataclass
class NSFWResult:
    """Result of NSFW classification."""
    is_safe: bool
    nsfw_score: float      # 0-1, higher = more NSFW
    category: str          # "safe", "suggestive", "explicit", "violence"
    confidence: float      # 0-1
    
    def to_dict(self) -> dict:
        return {
            "is_safe": self.is_safe,
            "nsfw_score": self.nsfw_score,
            "category": self.category,
            "confidence": self.confidence,
        }


# Thresholds
EXPLICIT_THRESHOLD = 0.7
SUGGESTIVE_THRESHOLD = 0.5


def classify(image_url: str) -> NSFWResult:
    """
    Classify an image for NSFW content.
    
    Args:
        image_url: URL to the image
    
    Returns:
        NSFWResult with classification
    
    TODO: Integrate actual classifier
    - Use NSFW detection model (e.g., nsfw_model, NudeNet)
    - Download image, run inference
    """
    # Placeholder: assume safe
    return NSFWResult(
        is_safe=True,
        nsfw_score=0.05,
        category="safe",
        confidence=0.95,
    )

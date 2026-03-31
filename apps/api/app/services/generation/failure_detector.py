"""
Failure Detector - Detects bad generation results and triggers auto-retry.

The secret weapon: Users NEVER see bad outputs.

Checks:
- Overall score below threshold
- Face score too low (portrait mode)
- Aesthetic score too low
- Technical issues (blur, noise, artifacts)

Used by ai_orchestrator to silently regenerate when results are bad.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# ─── Quality Thresholds ──────────────────────────────────────────────────────

# Default thresholds (score 0-100 scale)
DEFAULT_THRESHOLDS = {
    'overall': 55.0,
    'aesthetic': 45.0,
    'technical': 40.0,
    'composition': 35.0,
}

# Mode-specific thresholds (stricter for photographic modes)
MODE_THRESHOLDS = {
    'REALISM': {
        'overall': 60.0,
        'aesthetic': 50.0,
        'technical': 50.0,
        'face': 40.0,
    },
    'REALISM_portrait': {
        'overall': 60.0,
        'aesthetic': 50.0,
        'technical': 50.0,
        'face': 45.0,  # Stricter face threshold for portraits
    },
    'CINEMATIC': {
        'overall': 55.0,
        'aesthetic': 50.0,
        'technical': 45.0,
    },
    'PRODUCT': {
        'overall': 60.0,
        'aesthetic': 50.0,
        'technical': 55.0,  # Products need sharp detail
    },
    'FOOD': {
        'overall': 55.0,
        'aesthetic': 50.0,
        'technical': 45.0,
    },
    'DESIGN': {
        'overall': 50.0,
        'aesthetic': 45.0,
        'technical': 40.0,
    },
    'ANIME': {
        'overall': 50.0,
        'aesthetic': 45.0,
        'technical': 35.0,  # Anime is more forgiving technically
    },
    'ART': {
        'overall': 45.0,
        'aesthetic': 40.0,
        'technical': 30.0,  # Art is very forgiving technically
    },
}


class FailureDetector:
    """Detects generation failures based on quality scores.

    Returns True if the result should be retried.
    """

    def is_failure(
        self,
        scores: Dict[str, float],
        mode: str = 'REALISM',
        sub_mode: Optional[str] = None,
    ) -> bool:
        """Check if generation result is a failure that needs retry.

        Args:
            scores: Quality scores dict from quality_scorer
            mode: Master mode
            sub_mode: Sub-mode

        Returns:
            True if result is bad and should be retried
        """
        mode_key = f"{mode}_{sub_mode}" if sub_mode else mode
        thresholds = MODE_THRESHOLDS.get(mode_key,
                     MODE_THRESHOLDS.get(mode, DEFAULT_THRESHOLDS))

        overall = scores.get('overall_score', 0)
        aesthetic = scores.get('aesthetic_score', 0)
        technical = scores.get('technical_score', 0)
        face = scores.get('face_match', scores.get('face_score'))

        # Check overall score
        if overall < thresholds.get('overall', DEFAULT_THRESHOLDS['overall']):
            logger.info(f"Failure: overall={overall:.1f} < {thresholds.get('overall')}")
            return True

        # Check aesthetic score
        if aesthetic < thresholds.get('aesthetic', DEFAULT_THRESHOLDS['aesthetic']):
            logger.info(f"Failure: aesthetic={aesthetic:.1f} < {thresholds.get('aesthetic')}")
            return True

        # Check technical score
        if technical < thresholds.get('technical', DEFAULT_THRESHOLDS['technical']):
            logger.info(f"Failure: technical={technical:.1f} < {thresholds.get('technical')}")
            return True

        # Check face score (only for modes with face threshold)
        if face is not None and 'face' in thresholds:
            if face < thresholds['face']:
                logger.info(f"Failure: face={face:.1f} < {thresholds['face']}")
                return True

        return False

    def get_retry_hint(self, scores: Dict[str, float], mode: str) -> str:
        """Get hint about what to improve on retry."""
        overall = scores.get('overall_score', 0)
        aesthetic = scores.get('aesthetic_score', 0)
        technical = scores.get('technical_score', 0)

        if technical < 40:
            return 'increase_steps'  # More steps = better detail
        if aesthetic < 40:
            return 'change_guidance'  # Different guidance = different look
        if overall < 50:
            return 'full_retry'  # Complete re-generation
        return 'new_seed'  # Just try different seed


# Singleton instance
failure_detector = FailureDetector()

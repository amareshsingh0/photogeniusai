"""
Bridge to ai-pipeline adversarial defense for API pre-queue validation.

Runs multi-layer defense (homoglyphs, leetspeak, jailbreaks, injection, rate)
before dual_pipeline. Uses ai-pipeline/services/adversarial_defense when
ai-pipeline is on PYTHONPATH; otherwise skips (dual_pipeline still runs).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_defense = None
_defense_tried_failed = False


def _ensure_defense() -> bool:
    global _defense, _defense_tried_failed
    if _defense is not None:
        return True
    if _defense_tried_failed:
        return False
    try:
        cur = Path(__file__).resolve().parent
        ai_pipeline = None
        for _ in range(8):
            cur = cur.parent
            ap = cur / "ai-pipeline"
            if ap.is_dir():
                ai_pipeline = ap
                break
        if not ai_pipeline or not ai_pipeline.is_dir():
            _defense_tried_failed = True
            return False
        if str(ai_pipeline) not in sys.path:
            sys.path.insert(0, str(ai_pipeline))
        from services.adversarial_defense import AdversarialDefenseSystem

        _defense = AdversarialDefenseSystem(use_semantic=False)
        logger.info("Adversarial defense bridge: ai-pipeline defense loaded")
        return True
    except Exception as e:
        logger.debug("Adversarial defense bridge unavailable: %s", e)
        _defense_tried_failed = True
        return False


def analyze_prompt_for_api(
    prompt: str,
    user_id: Optional[str] = None,
) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Run adversarial defense on prompt before queuing.

    Returns:
        (is_safe, threats_or_none, sanitized_prompt_or_none)
        If defense unavailable, returns (True, None, None).
    """
    if not _ensure_defense() or _defense is None:
        return True, None, None
    try:
        r = _defense.analyze(prompt=prompt, user_id=user_id, strict_mode=True)
        if r.is_safe:
            threats = None
            sanitized = r.sanitized_prompt
        else:
            threats = [
                {"type": t.threat_type, "severity": t.severity, "explanation": t.explanation}
                for t in r.threats_detected
            ]
            sanitized = None
        return r.is_safe, threats, sanitized
    except Exception as e:
        logger.warning("Adversarial defense analyze failed: %s", e)
        return True, None, None

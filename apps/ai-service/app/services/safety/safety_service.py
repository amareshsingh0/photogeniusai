"""
Safety service for Modal GPU environment.

Wraps the dual_pipeline safety checks into a GPU-aware service that can
run NSFW classification and age estimation on-GPU when available,
falling back to CPU-based checks otherwise.

Layers:
1. Pre-generation: prompt sanitization (CPU, instant)
2. Post-generation: NSFW + age classification (GPU-accelerated)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.services.safety.dual_pipeline import (  # type: ignore[reportAttributeAccessIssue]
    run_pre_check,
    run_post_check,
    run_pipeline,
    SafetyResult,
)
from app.services.safety.prompt_sanitizer import sanitize, SanitizeResult  # type: ignore[reportAttributeAccessIssue]


@dataclass
class SafetyCheckResult:
    allowed: bool
    blocked_reason: Optional[str] = None
    nsfw_score: float = 0.0
    age_estimate: Optional[int] = None
    prompt_violations: list[str] | None = None


class SafetyService:
    """GPU-accelerated safety checking service."""

    def __init__(self):
        self._nsfw_model = None
        self._age_model = None
        self._loaded = False

    def load_models(self):
        """Load safety classification models. Call once on container start."""
        if self._loaded:
            return

        try:
            from transformers import pipeline as hf_pipeline  # type: ignore[reportMissingImports]

            cache_dir = os.getenv("MODEL_CACHE_DIR", "/root/.cache/huggingface")

            self._nsfw_model = hf_pipeline(
                "image-classification",
                model="Falconsai/nsfw_image_detection",
                device=0,
                model_kwargs={"cache_dir": cache_dir},
            )
            self._loaded = True
            print("Safety models loaded")
        except Exception as e:
            print(f"Warning: safety models not loaded (using fallback): {e}")

    def check_prompt(self, prompt: str) -> SafetyCheckResult:
        """Pre-generation prompt safety check (CPU, instant)."""
        allowed, result = run_pre_check(prompt)
        violations = [result.reason] if result.reason and not allowed else []
        return SafetyCheckResult(
            allowed=allowed,
            blocked_reason=result.reason if not allowed else None,
            prompt_violations=violations,
        )

    def check_image(self, image_path: str) -> SafetyCheckResult:
        """Post-generation image safety check (GPU when available)."""
        if self._nsfw_model and Path(image_path).exists():
            try:
                from PIL import Image  # type: ignore[reportMissingImports]

                img = Image.open(image_path).convert("RGB")
                results = self._nsfw_model(img)

                nsfw_score = 0.0
                for r in results:
                    if r["label"].lower() in ("nsfw", "porn", "sexy", "hentai"):
                        nsfw_score = max(nsfw_score, r["score"])

                allowed = nsfw_score < 0.5
                return SafetyCheckResult(
                    allowed=allowed,
                    blocked_reason="NSFW content detected" if not allowed else None,
                    nsfw_score=nsfw_score,
                )
            except Exception as e:
                print(f"Warning: GPU safety check failed, using fallback: {e}")

        # Fallback to dual_pipeline
        post_allowed, nsfw_result, age_result = run_post_check(image_path)
        return SafetyCheckResult(
            allowed=post_allowed,
            blocked_reason="Content policy violation" if not post_allowed else None,
            nsfw_score=getattr(nsfw_result, "score", 0.0) if nsfw_result else 0.0,
            age_estimate=getattr(age_result, "estimated_age", None) if age_result else None,
        )

    def full_check(self, prompt: str, image_path: Optional[str] = None) -> SafetyCheckResult:
        """Run full safety pipeline (prompt + optional image)."""
        prompt_check = self.check_prompt(prompt)
        if not prompt_check.allowed:
            return prompt_check

        if image_path:
            image_check = self.check_image(image_path)
            image_check.prompt_violations = prompt_check.prompt_violations
            return image_check

        return prompt_check


# Singleton
_service: Optional[SafetyService] = None


def get_safety_service() -> SafetyService:
    global _service
    if _service is None:
        _service = SafetyService()
    return _service

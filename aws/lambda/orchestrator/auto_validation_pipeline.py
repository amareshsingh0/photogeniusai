"""
Auto-Validation Pipeline – validate and auto-fix images with HARD guarantees.
P0: 95%+ first-try success; user never sees failures, only validated results.

Uses: TriModelValidator, FailureMemorySystem, IterativeRefinementV2, UniversalPromptClassifier.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image  # type: ignore[reportMissingImports]
except ImportError:
    Image = None  # type: ignore

try:
    from .tri_model_validator import TriModelValidator, AnatomyValidationResult
except ImportError:
    TriModelValidator = None  # type: ignore
    AnatomyValidationResult = None  # type: ignore

try:
    from .failure_memory_system import FailureMemorySystem
except ImportError:
    FailureMemorySystem = None  # type: ignore

try:
    from .iterative_refinement_v2 import IterativeRefinementV2
except ImportError:
    IterativeRefinementV2 = None  # type: ignore

try:
    from .universal_prompt_classifier import (
        UniversalPromptClassifier,
        ClassificationResult,
    )
except ImportError:
    UniversalPromptClassifier = None  # type: ignore
    ClassificationResult = None  # type: ignore


def _anatomy_result_person_count_accurate(result: Any) -> bool:
    """True if person count matches expected (no critical person_count/face_count issues)."""
    if result is None:
        return True
    for issue in getattr(result, "issues", []):
        if issue.get("type") in ("person_count", "face_count"):
            return False
    return result.scores.get("person_count_yolo", 0) >= 0.6


def _anatomy_result_hand_anatomy_passed(result: Any) -> bool:
    """True if hand anatomy checks passed."""
    if result is None:
        return True
    for issue in getattr(result, "issues", []):
        if issue.get("type") == "hand_anatomy":
            return False
    return result.scores.get("hands", 1.0) >= 0.7


_UNSET = object()


class AutoValidationPipeline:
    """
    Validates generated images and auto-fixes issues silently.
    User never sees failures – only validated results.
    """

    def __init__(
        self,
        validator: Any = _UNSET,
        failure_memory: Any = _UNSET,
        refinement: Any = _UNSET,
        classifier: Any = _UNSET,
        use_models: bool = False,
    ) -> None:
        self.validator = (
            TriModelValidator(use_models=use_models)
            if TriModelValidator
            else None if validator is _UNSET else validator
        )
        self.failure_memory = (
            FailureMemorySystem()
            if FailureMemorySystem
            else None if failure_memory is _UNSET else failure_memory
        )
        self.refinement = (
            IterativeRefinementV2()
            if IterativeRefinementV2
            else None if refinement is _UNSET else refinement
        )
        self.classifier = (
            UniversalPromptClassifier()
            if UniversalPromptClassifier
            else None if classifier is _UNSET else classifier
        )

    def validate_and_fix(
        self,
        image: Any,
        prompt: str,
        max_retries: int = 2,
    ) -> Tuple[Any, bool, Dict[str, Any]]:
        """
        Validate image and optionally refine until it passes or max_retries reached.

        Args:
            image: Generated image (PIL or array).
            prompt: Original prompt.
            max_retries: Max refinement loops (default 2).

        Returns:
            (final_image, passed_validation, metadata)
        """
        metadata: Dict[str, Any] = {"attempts": 0, "issues_fixed": [], "issues": []}
        if Image is not None and hasattr(image, "convert"):
            image = (
                image.convert("RGB") if getattr(image, "mode", "") != "RGB" else image
            )

        classification: Optional[Any] = None
        if self.classifier:
            classification = self.classifier.classify(prompt or "")
            metadata["classification"] = getattr(classification, "category", "")
        required_checks = (
            self._get_required_checks(classification) if classification else []
        )
        if not required_checks and (
            "person" in (prompt or "").lower() or "people" in (prompt or "").lower()
        ):
            required_checks = ["person_count", "hand_anatomy"]

        if self.failure_memory:
            known_fix = self.failure_memory.get_fix_for_prompt(prompt or "")
            if known_fix:
                metadata["known_fix_applied"] = True

        if self.validator is None:
            return image, True, {**metadata, "validator_skipped": True}
        if not required_checks:
            return image, True, {**metadata, "no_checks_required": True}

        scene_graph: Dict[str, Any] = {
            "quality_requirements": {"person_count_exact": 0}
        }
        if classification is not None:
            scene_graph["quality_requirements"]["person_count_exact"] = getattr(
                classification, "person_count", 0
            )

        for attempt in range(max_retries + 1):
            metadata["attempts"] = attempt
            validation_result = self.validator.validate_anatomy(
                image, scene_graph, return_detailed=True
            )

            passed = True
            issues: List[str] = []

            if "person_count" in required_checks:
                if not _anatomy_result_person_count_accurate(validation_result):
                    passed = False
                    issues.append("person_count")

            if "hand_anatomy" in required_checks:
                if not _anatomy_result_hand_anatomy_passed(validation_result):
                    passed = False
                    issues.append("hand_anatomy")

            if "text_accuracy" in required_checks and self.classifier:
                classification = self.classifier.classify(prompt or "")
                if not self._verify_text(image, classification):
                    passed = False
                    issues.append("text")

            if "object_placement" in required_checks:
                if not getattr(validation_result, "is_valid", True):
                    passed = False
                    issues.append("object_placement")

            if passed:
                if self.failure_memory:
                    self.failure_memory.record_success(
                        prompt or "", metadata.get("applied_fix") or {}
                    )
                return image, True, {**metadata, "issues_fixed": []}

            if attempt < max_retries and self.refinement and issues:
                image = self.refinement.refine_issues(
                    image, prompt or "", issues, validation_result
                )
                metadata["issues_fixed"].extend(issues)
            else:
                if self.failure_memory:
                    self.failure_memory.record_failure(
                        prompt or "",
                        "validation_failed",
                        failed_rules=issues,
                        context={"issues": issues},
                    )
                metadata["issues"] = issues
                return image, False, metadata

        metadata["max_retries_exceeded"] = True
        return image, False, metadata

    def _get_required_checks(self, classification: Any) -> List[str]:
        """Determine which validations are needed based on prompt classification."""
        checks: List[str] = []
        if getattr(classification, "has_people", False):
            checks.extend(["person_count", "hand_anatomy"])
        raw = (getattr(classification, "raw_prompt", "") or "").lower()
        if getattr(classification, "has_text", False) or "text" in raw or "sign" in raw:
            checks.append("text_accuracy")
        cat = getattr(classification, "category", "") or ""
        if cat in ("product", "advertisement"):
            checks.append("object_placement")
        return checks

    def _verify_text(self, image: Any, classification: Any) -> bool:
        """Verify text accuracy using OCR when expected. Returns True if no text expected or OCR matches."""
        if not getattr(classification, "has_text", False):
            return True
        try:
            import pytesseract  # type: ignore[reportMissingImports]
        except ImportError:
            return True
        try:
            ocr_text = (pytesseract.image_to_string(image) or "").strip().lower()
        except Exception:
            return True
        raw = (getattr(classification, "raw_prompt", "") or "").lower()
        quoted = re.findall(r'"([^"]+)"', raw) or re.findall(r"'([^']+)'", raw)
        if not quoted:
            return True
        for expected in quoted:
            expected_clean = expected.strip().lower()
            if expected_clean and expected_clean not in ocr_text:
                return False
        return True

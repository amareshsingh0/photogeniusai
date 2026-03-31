"""
Tests for Auto-Validation Pipeline: person count, hand anatomy, text accuracy,
max retries, failure memory integration.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from services.auto_validation_pipeline import (
        AutoValidationPipeline,
        _anatomy_result_person_count_accurate,
        _anatomy_result_hand_anatomy_passed,
    )
    from services.universal_prompt_classifier import ClassificationResult
    from services.tri_model_validator import AnatomyValidationResult
except ImportError:
    from ai_pipeline.services.auto_validation_pipeline import (
        AutoValidationPipeline,
        _anatomy_result_person_count_accurate,
        _anatomy_result_hand_anatomy_passed,
    )
    from ai_pipeline.services.universal_prompt_classifier import ClassificationResult
    from ai_pipeline.services.tri_model_validator import AnatomyValidationResult


def _gray_image(width: int = 256, height: int = 256):
    if Image is None:
        pytest.skip("PIL required")
    return Image.new("RGB", (width, height), color=(128, 128, 128))


# ---------------------------------------------------------------------------
# Person count validation
# ---------------------------------------------------------------------------


def test_person_count_accurate_when_no_issues():
    """person_count_accurate is True when result has no person_count/face_count issues."""
    result = MagicMock()
    result.issues = []
    result.scores = {"person_count_yolo": 0.9}
    assert _anatomy_result_person_count_accurate(result) is True


def test_person_count_inaccurate_when_issue_present():
    """person_count_accurate is False when result has person_count issue."""
    result = MagicMock()
    result.issues = [{"type": "person_count", "expected": 2, "detected_yolo": 1}]
    result.scores = {"person_count_yolo": 0.5}
    assert _anatomy_result_person_count_accurate(result) is False


def test_hand_anatomy_passed_when_no_hand_issue():
    """hand_anatomy_passed is True when no hand_anatomy issue."""
    result = MagicMock()
    result.issues = []
    result.scores = {"hands": 0.9}
    assert _anatomy_result_hand_anatomy_passed(result) is True


def test_hand_anatomy_failed_when_issue_present():
    """hand_anatomy_passed is False when hand_anatomy issue present."""
    result = MagicMock()
    result.issues = [{"type": "hand_anatomy", "invalid_hands": 1}]
    result.scores = {"hands": 0.4}
    assert _anatomy_result_hand_anatomy_passed(result) is False


# ---------------------------------------------------------------------------
# validate_and_fix: person count and hand anatomy
# ---------------------------------------------------------------------------


def test_validate_and_fix_no_validator_returns_passed():
    """When validator is explicitly None, validate_and_fix returns (image, True, metadata)."""
    pipeline = AutoValidationPipeline(
        validator=None,
        failure_memory=None,
        refinement=None,
        classifier=None,
    )
    img = _gray_image()
    final, passed, meta = pipeline.validate_and_fix(img, "a cat", max_retries=0)
    assert passed is True
    assert meta.get("validator_skipped") is True or meta.get("no_checks_required") is True
    assert final is img


def test_validate_and_fix_no_required_checks_returns_passed():
    """When classifier says no people, required_checks empty, returns passed."""
    classifier = MagicMock()
    classifier.classify.return_value = ClassificationResult(
        raw_prompt="sunset",
        style="photorealistic",
        medium="photograph",
        category="landscape",
        lighting="natural",
        color_palette="warm",
        has_people=False,
        person_count=0,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    validator = MagicMock()
    pipeline = AutoValidationPipeline(validator=validator, classifier=classifier)
    img = _gray_image()
    final, passed, meta = pipeline.validate_and_fix(img, "sunset over mountains", max_retries=0)
    assert passed is True
    assert meta.get("no_checks_required") is True
    validator.validate_anatomy.assert_not_called()


def test_validate_and_fix_person_count_validation_integration():
    """When validator returns valid anatomy (no issues), validate_and_fix returns passed."""
    validator = MagicMock()
    anatomy_result = AnatomyValidationResult()
    anatomy_result.issues = []
    anatomy_result.scores = {"person_count_yolo": 0.9, "hands": 0.9}
    anatomy_result.is_valid = True
    validator.validate_anatomy.return_value = anatomy_result

    classifier = MagicMock()
    classifier.classify.return_value = ClassificationResult(
        raw_prompt="two people",
        style="photorealistic",
        medium="photograph",
        category="portrait",
        lighting="natural",
        color_palette="natural",
        has_people=True,
        person_count=2,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    pipeline = AutoValidationPipeline(
        validator=validator,
        classifier=classifier,
        failure_memory=None,
        refinement=None,
    )
    # Force mocks in case default init is used (e.g. different import path)
    pipeline.validator = validator
    pipeline.classifier = classifier
    pipeline._get_required_checks = lambda classification: ["person_count", "hand_anatomy"]
    img = _gray_image()
    final, passed, meta = pipeline.validate_and_fix(img, "two people in a park", max_retries=0)
    assert passed is True, f"expected passed=True, meta={meta}"
    assert meta.get("attempts", 0) == 0
    validator.validate_anatomy.assert_called_once()


def test_validate_and_fix_hand_anatomy_fail_then_refinement():
    """When hand_anatomy fails, refinement is called; after retries, issues include hand_anatomy."""
    validator = MagicMock()
    anatomy_result = AnatomyValidationResult()
    anatomy_result.issues = [{"type": "hand_anatomy"}]
    anatomy_result.scores = {"person_count_yolo": 0.9, "hands": 0.3}
    validator.validate_anatomy.return_value = anatomy_result

    classifier = MagicMock()
    classifier.classify.return_value = ClassificationResult(
        raw_prompt="person",
        style="photorealistic",
        medium="photograph",
        category="portrait",
        lighting="natural",
        color_palette="natural",
        has_people=True,
        person_count=1,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    refinement = MagicMock()
    refinement.refine_issues.return_value = _gray_image()

    pipeline = AutoValidationPipeline(
        validator=validator,
        classifier=classifier,
        refinement=refinement,
        failure_memory=None,
    )
    pipeline.validator = validator
    pipeline.classifier = classifier
    pipeline.refinement = refinement
    pipeline._get_required_checks = lambda classification: ["person_count", "hand_anatomy"]
    img = _gray_image()
    final, passed, meta = pipeline.validate_and_fix(img, "portrait of a woman", max_retries=1)
    assert validator.validate_anatomy.call_count >= 2
    assert refinement.refine_issues.called
    assert "hand_anatomy" in meta.get("issues", []) or "hand_anatomy" in meta.get("issues_fixed", [])


# ---------------------------------------------------------------------------
# Text accuracy
# ---------------------------------------------------------------------------


def test_get_required_checks_includes_text_accuracy_when_has_text():
    """_get_required_checks includes text_accuracy when classification.has_text."""
    pipeline = AutoValidationPipeline(validator=None, classifier=MagicMock())
    classification = ClassificationResult(
        raw_prompt='Sign saying "Hello"',
        style="photorealistic",
        medium="photograph",
        category="specialty",
        lighting="natural",
        color_palette="natural",
        has_people=False,
        person_count=0,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=True,
        has_architecture=False,
    )
    checks = pipeline._get_required_checks(classification)
    assert "text_accuracy" in checks


def test_verify_text_returns_true_when_no_text_expected():
    """_verify_text returns True when classification.has_text is False."""
    pipeline = AutoValidationPipeline()
    classification = ClassificationResult(
        raw_prompt="landscape",
        style="photorealistic",
        medium="photograph",
        category="landscape",
        lighting="natural",
        color_palette="natural",
        has_people=False,
        person_count=0,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    img = _gray_image()
    assert pipeline._verify_text(img, classification) is True


# ---------------------------------------------------------------------------
# Max retries
# ---------------------------------------------------------------------------


def test_max_retries_behavior():
    """After max_retries refinements, returns (image, False, metadata) with issues."""
    validator = MagicMock()
    anatomy_result = AnatomyValidationResult()
    anatomy_result.issues = [{"type": "person_count"}, {"type": "hand_anatomy"}]
    anatomy_result.scores = {"person_count_yolo": 0.3, "hands": 0.3}
    validator.validate_anatomy.return_value = anatomy_result

    refinement = MagicMock()
    refinement.refine_issues.return_value = _gray_image()

    classifier = MagicMock()
    classifier.classify.return_value = ClassificationResult(
        raw_prompt="two people",
        style="photorealistic",
        medium="photograph",
        category="portrait",
        lighting="natural",
        color_palette="natural",
        has_people=True,
        person_count=2,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    pipeline = AutoValidationPipeline(
        validator=validator,
        classifier=classifier,
        refinement=refinement,
        failure_memory=None,
    )
    pipeline.validator = validator
    pipeline.classifier = classifier
    pipeline._get_required_checks = lambda classification: ["person_count", "hand_anatomy"]
    img = _gray_image()
    final, passed, meta = pipeline.validate_and_fix(img, "two people", max_retries=2)
    assert passed is False
    assert meta["attempts"] == 2
    assert len(meta.get("issues", [])) > 0
    assert validator.validate_anatomy.call_count == 3


# ---------------------------------------------------------------------------
# Failure memory integration
# ---------------------------------------------------------------------------


def test_failure_memory_record_failure_called_on_validation_fail():
    """When validation fails after all retries (no refinement), record_failure is called."""
    validator = MagicMock()
    anatomy_result = AnatomyValidationResult()
    anatomy_result.issues = [{"type": "person_count"}]
    anatomy_result.scores = {"person_count_yolo": 0.2, "hands": 0.9}
    validator.validate_anatomy.return_value = anatomy_result

    failure_memory = MagicMock()
    refinement = None  # no refinement so we fail immediately after first attempt

    classifier = MagicMock()
    classifier.classify.return_value = ClassificationResult(
        raw_prompt="three people",
        style="photorealistic",
        medium="photograph",
        category="portrait",
        lighting="natural",
        color_palette="natural",
        has_people=True,
        person_count=3,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    pipeline = AutoValidationPipeline(
        validator=validator,
        classifier=classifier,
        refinement=refinement,
        failure_memory=failure_memory,
    )
    pipeline.validator = validator
    pipeline.classifier = classifier
    pipeline.failure_memory = failure_memory
    pipeline._get_required_checks = lambda classification: ["person_count", "hand_anatomy"]
    img = _gray_image()
    final, passed, meta = pipeline.validate_and_fix(img, "three people", max_retries=0)
    assert passed is False
    failure_memory.record_failure.assert_called_once()
    call_args = failure_memory.record_failure.call_args
    assert call_args[0][1] == "validation_failed"
    assert "person_count" in (call_args[1].get("context") or {}).get("issues", [])


def test_failure_memory_record_success_called_when_passed():
    """When validation passes (no issues), record_success is called."""
    validator = MagicMock()
    anatomy_result = AnatomyValidationResult()
    anatomy_result.issues = []
    anatomy_result.scores = {"person_count_yolo": 0.95, "hands": 0.9}
    anatomy_result.is_valid = True
    validator.validate_anatomy.return_value = anatomy_result

    failure_memory = MagicMock()
    classifier = MagicMock()
    classifier.classify.return_value = ClassificationResult(
        raw_prompt="one person",
        style="photorealistic",
        medium="photograph",
        category="portrait",
        lighting="natural",
        color_palette="natural",
        has_people=True,
        person_count=1,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    pipeline = AutoValidationPipeline(
        validator=validator,
        classifier=classifier,
        failure_memory=failure_memory,
        refinement=None,
    )
    pipeline.validator = validator
    pipeline.classifier = classifier
    pipeline.failure_memory = failure_memory
    pipeline._get_required_checks = lambda classification: ["person_count", "hand_anatomy"]
    img = _gray_image()
    final, passed, meta = pipeline.validate_and_fix(img, "portrait", max_retries=0)
    assert passed is True
    failure_memory.record_success.assert_called_once()
    args = failure_memory.record_success.call_args[0]
    assert args[0] == "portrait"
    assert isinstance(args[1], dict)


def test_get_required_checks_product_category_adds_object_placement():
    """_get_required_checks includes object_placement for product category."""
    pipeline = AutoValidationPipeline(validator=None, classifier=MagicMock())
    classification = ClassificationResult(
        raw_prompt="product shot",
        style="photorealistic",
        medium="photograph",
        category="product",
        lighting="studio",
        color_palette="natural",
        has_people=False,
        person_count=0,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    checks = pipeline._get_required_checks(classification)
    assert "object_placement" in checks


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:asyncio"])

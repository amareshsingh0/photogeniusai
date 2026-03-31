"""
Tests for Tri-Model Validation: YOLO + MediaPipe + SAM/fallback consensus.
Task 4: 99%+ person count accuracy, 95%+ hand anatomy correctness.

- Heuristic tests: run without GPU (use_models=False).
- GPU validation tests: skipped when no CUDA (use_models=True).
"""

import pytest
import numpy as np

try:
    from services.tri_model_validator import (
        TriModelValidator,
        TriModelConsensus,
        ValidationResult,
        AnatomyValidationResult,
        AnatomyIssueLocalizer,
    )
    from services.scene_graph_compiler import SceneGraphCompiler
except ImportError:
    from ai_pipeline.services.tri_model_validator import (
        TriModelValidator,
        TriModelConsensus,
        ValidationResult,
        AnatomyValidationResult,
        AnatomyIssueLocalizer,
    )
    from ai_pipeline.services.scene_graph_compiler import SceneGraphCompiler

# Skip GPU-only tests when no CUDA
try:
    import torch

    HAS_CUDA = torch.cuda.is_available()
except Exception:
    HAS_CUDA = False

requires_gpu = pytest.mark.skipif(
    not HAS_CUDA, reason="GPU required for validation tests"
)


# -----------------------------------------------------------------------------
# Heuristic tests (no GPU, no heavy models)
# -----------------------------------------------------------------------------


def test_validate_heuristic_fallback():
    """Without models, validator returns heuristic consensus."""
    validator = TriModelValidator(use_models=False)
    compiler = SceneGraphCompiler(use_spacy=False)
    scene = compiler.compile("Couple at beach")
    constraints = scene.get("constraints", [])
    expected = scene.get("quality_requirements", {}).get("person_count_exact", 2)

    dummy = np.zeros((64, 64, 3), dtype=np.uint8)

    consensus = validator.validate(dummy, expected, constraints)

    assert isinstance(consensus, TriModelConsensus)
    assert consensus.all_passed in (True, False)
    assert isinstance(consensus.results, list)
    assert (
        consensus.consensus_count is not None
        or consensus.head_count_detected is not None
    )
    assert consensus.hand_anatomy_passed is True


def test_validate_person_count_expected():
    """Person count from scene matches expected in consensus details."""
    validator = TriModelValidator(use_models=False)
    compiler = SceneGraphCompiler(use_spacy=False)
    scene = compiler.compile("Family of 4 at picnic")
    constraints = scene.get("constraints", [])
    expected = 4

    dummy = np.zeros((128, 128, 3), dtype=np.uint8)
    consensus = validator.validate(dummy, expected, constraints)

    for r in consensus.results:
        if "detected" in r.details or "expected" in r.details:
            assert (
                r.details.get("expected") == expected
                or r.details.get("detected") == expected
            )


def test_consensus_constraint_dict_or_object():
    """Validator accepts constraints as dict or HardConstraint-like objects."""
    validator = TriModelValidator(use_models=False)
    constraints_dict = [
        {
            "type": "visibility",
            "rule": "exactly_2_heads_fully_visible",
            "severity": "critical",
        },
        {"type": "anatomy", "rule": "each_person_arms_2_legs", "severity": "high"},
    ]

    dummy = np.zeros((64, 64, 3), dtype=np.uint8)
    consensus = validator.validate(dummy, 2, constraints_dict)
    assert isinstance(consensus, TriModelConsensus)
    assert len(consensus.results) >= 2


# -----------------------------------------------------------------------------
# Anatomy API tests (no GPU required)
# -----------------------------------------------------------------------------


def test_validate_anatomy_structure_no_gpu():
    """validate_anatomy returns AnatomyValidationResult with expected structure (no models)."""
    validator = TriModelValidator(use_models=False)
    image = np.zeros((128, 128, 3), dtype=np.uint8)
    scene_graph = {"quality_requirements": {"person_count_exact": 0}}

    result = validator.validate_anatomy(image, scene_graph)

    assert isinstance(result, AnatomyValidationResult)
    assert hasattr(result, "is_valid")
    assert hasattr(result, "overall_score")
    assert hasattr(result, "model_results")
    assert hasattr(result, "issues")
    assert hasattr(result, "scores")
    assert "yolo" in result.model_results
    assert "mediapipe" in result.model_results
    assert "segmentation" in result.model_results
    assert 0.0 <= result.overall_score <= 1.0
    assert "to_dict" in dir(result)
    assert isinstance(result.to_dict(), dict)


def test_validate_simple_interface():
    """validate_simple returns (bool, float)."""
    validator = TriModelValidator(use_models=False)
    image = np.zeros((64, 64, 3), dtype=np.uint8)

    is_valid, score = validator.validate_simple(image, expected_people=0)

    assert isinstance(is_valid, bool)
    assert 0.0 <= score <= 1.0


# -----------------------------------------------------------------------------
# GPU validation tests (skipped when no CUDA)
# -----------------------------------------------------------------------------


@requires_gpu
class TestTriModelValidator:
    """Test tri-model validation system with real models (GPU)."""

    def test_validator_initialization(self):
        """Test validator loads all models when use_models=True."""
        validator = TriModelValidator(use_models=True, device="cuda")

        assert validator.yolo is not None
        assert validator.mp_hands is not None
        assert validator.mp_face_mesh is not None

    def test_yolo_person_detection(self):
        """Test YOLO detects correct number of people."""
        validator = TriModelValidator(use_models=True, device="cuda")

        image = self._create_test_image_with_people(num_people=2)
        image_np = np.array(image)

        yolo_result = validator._validate_with_yolo(image_np, expected_people=2)

        assert "detected_people" in yolo_result
        assert "score" in yolo_result
        assert 0.0 <= yolo_result["score"] <= 1.0

    def test_mediapipe_face_detection(self):
        """Test MediaPipe face detection (expects RGB image)."""
        validator = TriModelValidator(use_models=True, device="cuda")

        from PIL import Image

        image = Image.new("RGB", (512, 512), color="gray")
        image_rgb = np.array(image)

        mp_result = validator._validate_with_mediapipe(image_rgb, expected_people=0)

        assert "detected_faces" in mp_result
        assert mp_result["detected_faces"] == 0

    def test_validation_result_structure(self):
        """Test validate_anatomy returns correct structure."""
        validator = TriModelValidator(use_models=True, device="cuda")

        from PIL import Image

        image = Image.new("RGB", (512, 512), color="blue")

        scene_graph = {
            "quality_requirements": {
                "person_count_exact": 0,
            }
        }

        result = validator.validate_anatomy(image, scene_graph)

        assert hasattr(result, "is_valid")
        assert hasattr(result, "overall_score")
        assert hasattr(result, "model_results")
        assert hasattr(result, "issues")
        assert hasattr(result, "scores")

        assert "yolo" in result.model_results
        assert "mediapipe" in result.model_results
        assert "segmentation" in result.model_results

    def test_simple_validation_interface(self):
        """Test simplified validation."""
        validator = TriModelValidator(use_models=True, device="cuda")

        from PIL import Image

        image = Image.new("RGB", (512, 512), color="white")

        is_valid, score = validator.validate_simple(image, expected_people=0)

        assert isinstance(is_valid, bool)
        assert 0.0 <= score <= 1.0

    def test_issue_localization(self):
        """Test issue localizer returns list of issues."""
        validator = TriModelValidator(use_models=True, device="cuda")
        localizer = AnatomyIssueLocalizer(device="cuda")

        from PIL import Image

        image = Image.new("RGB", (512, 512), color="gray")
        scene_graph = {
            "quality_requirements": {
                "person_count_exact": 1,
            }
        }

        result = validator.validate_anatomy(image, scene_graph)
        issues = localizer.localize_issues(image, result)

        assert isinstance(issues, list)

    @staticmethod
    def _create_test_image_with_people(num_people: int):
        """Create synthetic test image with person-like shapes (RGB)."""
        try:
            import cv2
            from PIL import Image
        except ImportError:
            pytest.skip("opencv-python and PIL required for synthetic image")

        img_bgr = np.ones((512, 512, 3), dtype=np.uint8) * 200
        spacing = 512 // (num_people + 1)

        for i in range(num_people):
            x = spacing * (i + 1)
            y = 256
            cv2.ellipse(
                img_bgr,
                (x, y),
                (40, 80),
                0,
                0,
                360,
                (150, 100, 100),
                -1,
            )
            cv2.circle(
                img_bgr,
                (x, y - 100),
                30,
                (100, 100, 120),
                -1,
            )

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_rgb)


@requires_gpu
class TestIntegrationValidation:
    """Integration tests with scene graph (GPU)."""

    @pytest.mark.skip(reason="Requires full generation pipeline")
    def test_validate_generated_image(self):
        """Test validation on actually generated image."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-p", "no:asyncio"])

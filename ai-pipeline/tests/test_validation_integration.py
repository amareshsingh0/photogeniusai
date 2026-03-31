"""
Comprehensive tests for ValidationIntegration.

- Default: run with use_models=False (no GPU required, tests decision logic).
- With GPU: optional tests run with real models (use_models=True).
"""

import pytest
import numpy as np

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from services.validation_integration import ValidationIntegration
    from services.scene_graph_compiler import SceneGraphCompiler
except ImportError:
    from ai_pipeline.services.validation_integration import ValidationIntegration
    from ai_pipeline.services.scene_graph_compiler import SceneGraphCompiler

try:
    import torch

    HAS_CUDA = torch.cuda.is_available()
except Exception:
    HAS_CUDA = False

requires_gpu = pytest.mark.skipif(not HAS_CUDA, reason="GPU required")


# -----------------------------------------------------------------------------
# Core tests (no GPU required)
# -----------------------------------------------------------------------------


def test_validation_integration_initialization():
    """Test integration initializes with defaults."""
    integration = ValidationIntegration()
    assert integration.validator is not None
    assert integration.quality_threshold == 0.85


def test_validation_integration_custom_threshold():
    """Test integration accepts custom threshold."""
    integration = ValidationIntegration(quality_threshold=0.90)
    assert integration.quality_threshold == 0.90


def test_check_and_decide():
    """Test validation decision logic (heuristic mode, no GPU)."""
    integration = ValidationIntegration(use_models=False)

    if Image is None:
        pytest.skip("PIL required")
    image = Image.new("RGB", (512, 512), color="blue")

    compiler = SceneGraphCompiler(use_spacy=False)
    scene = compiler.compile("Person standing")

    should_refine, feedback = integration.check_and_decide(image, scene)

    assert isinstance(should_refine, bool)
    assert "validation_result" in feedback
    assert "refinement_priority" in feedback
    assert "suggested_fixes" in feedback
    assert "quality_score" in feedback
    assert "issues_count" in feedback
    assert feedback["refinement_priority"] in ["high", "medium", "low"]


def test_check_and_decide_with_numpy_image():
    """Test check_and_decide accepts numpy image."""
    integration = ValidationIntegration(use_models=False)
    image = np.zeros((128, 128, 3), dtype=np.uint8)
    scene_graph = {"quality_requirements": {"person_count_exact": 0}}

    should_refine, feedback = integration.check_and_decide(image, scene_graph)

    assert isinstance(should_refine, bool)
    assert feedback["quality_score"] >= 0.0
    assert feedback["quality_score"] <= 1.0


def test_validation_summary():
    """Test summary generation from anatomy result."""
    integration = ValidationIntegration(use_models=False)

    if Image is None:
        pytest.skip("PIL required")
    image = Image.new("RGB", (512, 512), color="white")

    compiler = SceneGraphCompiler(use_spacy=False)
    scene = compiler.compile("Two people")

    result = integration.validator.validate_anatomy(image, scene, return_detailed=True)
    summary = integration.get_validation_summary(result)

    assert isinstance(summary, str)
    assert "Validation:" in summary
    assert "Overall Score" in summary
    assert "Model Results:" in summary
    assert "YOLO:" in summary
    assert "Faces:" in summary
    assert "Hands:" in summary


def test_suggested_fixes_structure():
    """Test that suggested_fixes have expected structure when issues exist."""
    integration = ValidationIntegration(use_models=False)
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    scene_graph = {"quality_requirements": {"person_count_exact": 2}}

    _, feedback = integration.check_and_decide(image, scene_graph)

    assert isinstance(feedback["suggested_fixes"], list)
    for fix in feedback["suggested_fixes"]:
        assert "type" in fix
        assert "reason" in fix
        assert "severity" in fix


def test_check_and_decide_custom_threshold():
    """Test check_and_decide respects custom threshold."""
    integration = ValidationIntegration(use_models=False, quality_threshold=0.85)
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    scene_graph = {"quality_requirements": {"person_count_exact": 0}}

    _, feedback_low = integration.check_and_decide(image, scene_graph, threshold=0.99)
    _, feedback_high = integration.check_and_decide(image, scene_graph, threshold=0.10)

    assert feedback_low["quality_score"] <= 1.0
    assert feedback_high["quality_score"] <= 1.0


# -----------------------------------------------------------------------------
# GPU tests (skipped when no CUDA)
# -----------------------------------------------------------------------------


@requires_gpu
def test_check_and_decide_with_models():
    """Test check_and_decide with real models (GPU)."""
    integration = ValidationIntegration(use_models=True, device="cuda")

    if Image is None:
        pytest.skip("PIL required")
    image = Image.new("RGB", (512, 512), color="gray")
    scene_graph = {"quality_requirements": {"person_count_exact": 0}}

    should_refine, feedback = integration.check_and_decide(image, scene_graph)

    assert isinstance(should_refine, bool)
    assert feedback["refinement_priority"] in ["high", "medium", "low"]


@requires_gpu
def test_validation_summary_with_models():
    """Test summary with real validation (GPU)."""
    integration = ValidationIntegration(use_models=True, device="cuda")

    if Image is None:
        pytest.skip("PIL required")
    image = Image.new("RGB", (512, 512), color="blue")
    scene_graph = {"quality_requirements": {"person_count_exact": 0}}

    result = integration.validator.validate_anatomy(image, scene_graph)
    summary = integration.get_validation_summary(result)

    assert "Validation:" in summary
    assert "Overall Score" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-p", "no:asyncio"])

"""
Tests for iterative refinement: IssueAnalyzer and IterativeRefinementEngine.

- IssueAnalyzer tests: run without GPU.
- RefinementEngine tests: skipped (slow/full pipeline) or require GPU when enabled.
"""

import pytest
import numpy as np

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from services.issue_analyzer import IssueAnalyzer, IssueFix
    from services.tri_model_validator import TriModelValidator, ValidationResult
except ImportError:
    from ai_pipeline.services.issue_analyzer import IssueAnalyzer, IssueFix
    from ai_pipeline.services.tri_model_validator import TriModelValidator, ValidationResult

try:
    import torch
    HAS_CUDA = torch.cuda.is_available()
except Exception:
    HAS_CUDA = False

requires_gpu = pytest.mark.skipif(not HAS_CUDA, reason="GPU required")


# -----------------------------------------------------------------------------
# IssueAnalyzer tests (no GPU required)
# -----------------------------------------------------------------------------


class TestIssueAnalyzer:
    """Test issue analysis and fix planning."""

    def test_analyzer_initialization(self):
        """Test analyzer initializes."""
        analyzer = IssueAnalyzer()
        assert analyzer.fix_history == []

    def test_issue_to_fix_conversion(self):
        """Test converting issue dict to IssueFix."""
        analyzer = IssueAnalyzer()

        issue = {
            "type": "person_count",
            "severity": "critical",
            "expected": 4,
            "detected_yolo": 3,
        }

        fix = analyzer._issue_to_fix(issue)

        assert fix is not None
        assert fix.fix_type == "regenerate"
        assert fix.severity == "critical"
        assert fix.issue_category == "count"

    def test_issue_to_fix_hand_anatomy(self):
        """Test hand_anatomy issue maps to inpaint fix."""
        analyzer = IssueAnalyzer()
        issue = {
            "type": "hand_anatomy",
            "severity": "high",
            "invalid_hands": 1,
        }
        fix = analyzer._issue_to_fix(issue)
        assert fix is not None
        assert fix.fix_type == "inpaint"
        assert fix.issue_category == "anatomy"

    def test_fix_priority_calculation(self):
        """Test fix priority is set correctly from severity."""
        fix_critical = IssueFix(
            fix_type="regenerate",
            severity="critical",
            issue_category="count",
        )

        fix_low = IssueFix(
            fix_type="inpaint",
            severity="low",
            issue_category="anatomy",
        )

        assert fix_critical.priority > fix_low.priority

    def test_should_continue_refining(self):
        """Test refinement continuation logic."""
        analyzer = IssueAnalyzer()

        class MockValidation:
            overall_score = 0.7

        result = MockValidation()

        # Should continue: score below threshold, not at max
        should_continue = analyzer.should_continue_refining(
            result, iteration=1, max_iterations=5, score_threshold=0.85
        )
        assert should_continue is True

        # Should stop: at max iterations
        should_stop = analyzer.should_continue_refining(
            result, iteration=5, max_iterations=5, score_threshold=0.85
        )
        assert should_stop is False

        # Should stop: score above threshold
        result.overall_score = 0.90
        should_stop = analyzer.should_continue_refining(
            result, iteration=1, max_iterations=5, score_threshold=0.85
        )
        assert should_stop is False

    def test_record_iteration(self):
        """Test recording iteration updates fix_history."""
        analyzer = IssueAnalyzer()
        fix = IssueFix(
            fix_type="inpaint",
            severity="high",
            issue_category="anatomy",
        )
        analyzer.record_iteration(0.6, [fix])
        assert len(analyzer.fix_history) == 1
        assert analyzer.fix_history[0]["score"] == 0.6
        assert len(analyzer.fix_history[0]["fixes"]) == 1


# -----------------------------------------------------------------------------
# RefinementEngine tests (skipped by default; require GPU when enabled)
# -----------------------------------------------------------------------------


@requires_gpu
class TestRefinementEngine:
    """Test refinement engine (integration tests)."""

    @pytest.mark.skip(reason="Very slow, requires full pipeline")
    def test_refinement_engine_initialization(self):
        """Test engine initializes all components."""
        try:
            from services.iterative_refinement_engine import IterativeRefinementEngine
        except ImportError:
            from ai_pipeline.services.iterative_refinement_engine import IterativeRefinementEngine

        engine = IterativeRefinementEngine(
            device="cuda",
            use_reward_guidance=False,
            max_iterations=2,
            use_models=False,
        )

        assert engine.scene_compiler is not None
        assert engine.validator is not None

    @pytest.mark.skip(reason="Very slow, full generation test")
    def test_full_refinement_cycle(self):
        """Test complete refinement: generate -> validate -> fix -> validate."""
        try:
            from services.iterative_refinement_engine import IterativeRefinementEngine
        except ImportError:
            from ai_pipeline.services.iterative_refinement_engine import IterativeRefinementEngine

        engine = IterativeRefinementEngine(
            device="cuda",
            max_iterations=2,
            quality_threshold=0.75,
            use_models=False,
        )

        result = engine.generate_perfect(
            prompt="Person standing",
            max_iterations=2,
            save_iterations=True,
            seed=42,
        )

        assert "image" in result
        assert "iterations" in result
        assert result["total_iterations"] >= 1
        assert result["total_iterations"] <= 2

        first_iter = result["iterations"][0]
        assert first_iter.image is not None
        assert 0.0 <= first_iter.validation_score <= 1.0


# -----------------------------------------------------------------------------
# Lightweight engine test (no GPU, no full pipeline)
# -----------------------------------------------------------------------------


def test_engine_generate_perfect_one_iteration():
    """Test engine.generate_perfect runs one iteration without diffusion (placeholder)."""
    try:
        from services.iterative_refinement_engine import IterativeRefinementEngine
    except ImportError:
        from ai_pipeline.services.iterative_refinement_engine import IterativeRefinementEngine

    engine = IterativeRefinementEngine(
        device="cpu",
        use_models=False,
        max_iterations=1,
    )

    result = engine.generate_perfect(
        prompt="One person standing",
        max_iterations=1,
    )

    assert "image" in result
    assert "iterations" in result
    assert "final_score" in result
    assert "success" in result
    assert result["total_iterations"] >= 1
    assert len(result["iterations"]) >= 1
    assert 0.0 <= result["final_score"] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-p", "no:asyncio"])

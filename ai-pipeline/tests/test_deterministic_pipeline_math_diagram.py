"""
Tests for Math/Diagram integration in Deterministic Pipeline.
Formula overlay with SymPy validation; chart overlay with ChartSpec.
"""

import pytest

try:
    from services.deterministic_pipeline import (
        DeterministicPipeline,
        _extract_chart_data_from_prompt,
        _diagram_type_to_kind,
    )
except ImportError:
    from ai_pipeline.services.deterministic_pipeline import (
        DeterministicPipeline,
        _extract_chart_data_from_prompt,
        _diagram_type_to_kind,
    )


def test_extract_chart_data_percentages():
    """_extract_chart_data_from_prompt parses 30%, 50%, 20%."""
    data = _extract_chart_data_from_prompt("bar chart showing 30%, 50%, 20%", "bar")
    assert "sizes" in data or "values" in data
    assert len(data.get("sizes", data.get("values", []))) == 3


def test_extract_chart_data_default():
    """_extract_chart_data_from_prompt returns default labels/values when no numbers."""
    data = _extract_chart_data_from_prompt("bar chart comparing sales data", "bar")
    assert "labels" in data
    assert "values" in data
    assert len(data["labels"]) >= 2


def test_diagram_type_to_kind():
    """_diagram_type_to_kind maps string to DiagramKind."""
    kind = _diagram_type_to_kind("bar")
    assert kind is not None
    assert str(kind).endswith("CHART_BAR")
    assert _diagram_type_to_kind("pie") is not None
    assert _diagram_type_to_kind("line") is not None
    assert _diagram_type_to_kind("scatter") is not None


def test_run_with_requires_math_sets_formula_valid():
    """When requires_math and expected_formula, pipeline runs math overlay when validation passes."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required")
    # Mock validate_formula_latex so overlay runs (SymPy/antlr4 may be missing in env)
    try:
        from services.math_diagram_renderer import ValidationResult
    except ImportError:
        from ai_pipeline.services.math_diagram_renderer import ValidationResult
    pipeline = DeterministicPipeline(max_refinement_iterations=1)
    class MockCompiler:
        def compile(self, prompt: str):
            return {
                "layout": {"entities": []},
                "camera": {},
                "constraints": [],
                "entities": [],
                "quality_requirements": {},
                "hard_constraints": [],
            }
    pipeline.compiler = MockCompiler()
    pipeline.constraint_solver = None
    pipeline.occlusion_solver = None
    pipeline.physics_sim = None
    pipeline.validator = None
    pipeline.failure_memory_system = None
    pipeline._typography_engine = None
    class MockClassification:
        requires_text = False
        expected_text = None
        requires_math = True
        expected_formula = "E=mc^2"
        requires_diagram = False
        diagram_type = None
    pipeline._classifier = type("C", (), {"classify": lambda self, p: MockClassification()})()
    class MockMathRenderer:
        def render_formula_placement(self, image, placement):
            return image
    pipeline._math_diagram_renderer = MockMathRenderer()
    def fake_generator(prompt, negative, **kwargs):
        return Image.new("RGB", (128, 128), color=(200, 200, 200))
    pipeline.set_generator(fake_generator)
    from unittest.mock import patch
    # Patch so formula validates and overlay runs
    with patch("services.deterministic_pipeline.validate_formula_latex", return_value=ValidationResult(valid=True)):
        result = pipeline.run("poster with equation E=mc²")
    assert result.image is not None
    assert result.quality_metrics.get("formula_valid") is True


def test_run_with_requires_diagram_sets_diagram_applied():
    """When requires_diagram, pipeline runs chart overlay and sets diagram_applied."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required")
    pipeline = DeterministicPipeline(max_refinement_iterations=1)
    class MockCompiler:
        def compile(self, prompt: str):
            return {
                "layout": {"entities": []},
                "camera": {},
                "constraints": [],
                "entities": [],
                "quality_requirements": {},
                "hard_constraints": [],
            }
    pipeline.compiler = MockCompiler()
    pipeline.constraint_solver = None
    pipeline.occlusion_solver = None
    pipeline.physics_sim = None
    pipeline.validator = None
    pipeline.failure_memory_system = None
    pipeline._typography_engine = None
    class MockClassification:
        requires_text = False
        expected_text = None
        requires_math = False
        expected_formula = None
        requires_diagram = True
        diagram_type = "bar"
    pipeline._classifier = type("C", (), {"classify": lambda self, p: MockClassification()})()
    class MockMathRenderer:
        def overlay_chart(self, image, spec, x=0, y=0, anchor="lt", lighting=None):
            return image
    pipeline._math_diagram_renderer = MockMathRenderer()
    def fake_generator(prompt, negative, **kwargs):
        return Image.new("RGB", (128, 128), color=(200, 200, 200))
    pipeline.set_generator(fake_generator)
    result = pipeline.run("bar chart comparing sales data")
    assert result.quality_metrics.get("diagram_applied") is True

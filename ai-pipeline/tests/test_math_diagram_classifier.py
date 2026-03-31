"""
Tests for Math/Diagram detection in Universal Prompt Classifier (Integrate Math Diagram Renderer).
requires_math, expected_formula, requires_diagram, diagram_type.
"""

import pytest

try:
    from services.universal_prompt_classifier import (
        UniversalPromptClassifier,
        _extract_latex_from_prompt,
        _detect_math_requirements,
        _detect_diagram_requirements,
    )
except ImportError:
    from ai_pipeline.services.universal_prompt_classifier import (
        UniversalPromptClassifier,
        _extract_latex_from_prompt,
        _detect_math_requirements,
        _detect_diagram_requirements,
    )


def test_poster_with_equation_emc2():
    """Poster with equation E=mc² -> requires_math, expected_formula extracted."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("poster with equation E=mc²")
    assert result.requires_math is True
    assert result.expected_formula is not None
    assert "mc" in (result.expected_formula or "").lower() or "E" in (result.expected_formula or "")


def test_educational_diagram_photosynthesis():
    """Educational diagram showing photosynthesis -> requires_diagram, diagram_type."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("educational diagram showing photosynthesis process")
    assert result.requires_diagram is True
    assert result.diagram_type is not None
    assert result.diagram_type in ("bar", "line", "pie", "scatter")


def test_bar_chart_comparing_sales():
    """Bar chart comparing sales data -> requires_diagram, diagram_type bar."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("bar chart comparing sales data")
    assert result.requires_diagram is True
    assert result.diagram_type == "bar"


def test_extract_latex_emc2():
    """_extract_latex_from_prompt extracts E=mc² style."""
    assert _extract_latex_from_prompt("equation E=mc²") == "E=mc^2"
    assert _extract_latex_from_prompt("formula e=mc^2") == "E=mc^2"


def test_extract_latex_dollar():
    """_extract_latex_from_prompt extracts $...$ and \\( \\) ."""
    assert _extract_latex_from_prompt("show $a^2 + b^2 = c^2$") == "a^2 + b^2 = c^2"
    assert _extract_latex_from_prompt(r"inline \( x^2 \)") == "x^2"


def test_detect_math_requirements():
    """_detect_math_requirements returns (requires_math, expected_formula)."""
    req, formula = _detect_math_requirements("poster with equation E=mc²")
    assert req is True
    assert formula is not None
    req2, formula2 = _detect_math_requirements("a cat on a sofa")
    assert req2 is False
    assert formula2 is None


def test_detect_diagram_requirements():
    """_detect_diagram_requirements returns (requires_diagram, diagram_type)."""
    req, dtype = _detect_diagram_requirements("bar chart showing 30%, 50%, 20%")
    assert req is True
    assert dtype == "bar"
    req2, dtype2 = _detect_diagram_requirements("pie chart of market share")
    assert req2 is True
    assert dtype2 == "pie"
    req3, dtype3 = _detect_diagram_requirements("sunset over mountains")
    assert req3 is False
    assert dtype3 is None


def test_to_dict_includes_math_diagram():
    """ClassificationResult.to_dict includes requires_math, expected_formula, requires_diagram, diagram_type."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("bar chart comparing sales data")
    d = result.to_dict()
    assert "requires_math" in d
    assert "expected_formula" in d
    assert "requires_diagram" in d
    assert "diagram_type" in d
    assert d["requires_diagram"] is True
    assert d["diagram_type"] == "bar"

"""
Tests for Task 4.1: Auto-Trigger Text Rendering in Universal Prompt Classifier.
Text/Math/Diagram guarantee: requires_text, text_type, expected_text, text_placement, confidence.
"""

import pytest

try:
    from services.universal_prompt_classifier import (
        UniversalPromptClassifier,
        _extract_quoted_text,
        _detect_text_requirements,
    )
except ImportError:
    from ai_pipeline.services.universal_prompt_classifier import (
        UniversalPromptClassifier,
        _extract_quoted_text,
        _detect_text_requirements,
    )


def test_coffee_shop_sign_example():
    """Example from task: coffee shop with sign saying 'Fresh Brew'."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("coffee shop with sign saying 'Fresh Brew'")
    assert result.requires_text is True
    assert result.text_type == "sign"
    assert result.expected_text == "Fresh Brew"
    assert result.text_placement == "on_object"
    assert result.text_confidence >= 0.5


def test_sign_with_double_quotes():
    """Sign that says \"Hello World\" -> expected_text = Hello World."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify('street with sign that says "Hello World"')
    assert result.requires_text is True
    assert result.text_type == "sign"
    assert result.expected_text == "Hello World"
    assert result.text_placement == "on_object"


def test_extract_quoted_single():
    """_extract_quoted_text returns content inside single quotes."""
    assert _extract_quoted_text("sign saying 'Fresh Brew'") == "Fresh Brew"
    assert _extract_quoted_text("hello 'world'") == "world"


def test_extract_quoted_double():
    """_extract_quoted_text returns content inside double quotes."""
    assert _extract_quoted_text('label "Hello World"') == "Hello World"


def test_extract_quoted_none():
    """_extract_quoted_text returns None when no quotes."""
    assert _extract_quoted_text("no quotes here") is None


def test_detect_text_requirements_sign():
    """_detect_text_requirements detects sign and extracts text."""
    req, ttype, expected, place, conf = _detect_text_requirements("sign that says 'Open'")
    assert req is True
    assert ttype == "sign"
    assert expected == "Open"
    assert place == "on_object"
    assert conf >= 0.5


def test_detect_caption_bottom():
    """Caption implies bottom placement."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("photo with caption that says 'Sunset at sea'")
    assert result.requires_text is True
    assert result.text_type == "caption"
    assert result.expected_text == "Sunset at sea"
    assert result.text_placement == "bottom"


def test_detect_label():
    """Label detection and on_object placement."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("product with label reading 'Organic'")
    assert result.requires_text is True
    assert result.text_type == "label"
    assert result.expected_text == "Organic"


def test_detect_poster_centered():
    """Poster often centered."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("movie poster that says 'Coming Soon'")
    assert result.requires_text is True
    assert result.text_type == "poster"
    assert result.text_placement in ("centered", "on_object")


def test_no_text_requirement():
    """Prompt without text has requires_text False."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("a cat on a sofa")
    assert result.requires_text is False
    assert result.text_type is None
    assert result.expected_text is None
    assert result.text_confidence == 0.0


def test_confidence_scores():
    """Text detection returns confidence in [0, 1]."""
    classifier = UniversalPromptClassifier()
    r1 = classifier.classify("sign that says 'Hi'")
    r2 = classifier.classify("something with text")
    assert 0 <= r1.text_confidence <= 1.0
    assert 0 <= r2.text_confidence <= 1.0
    # Quoted text typically gives higher confidence
    assert r1.text_confidence >= 0.5


def test_to_dict_includes_text_fields():
    """ClassificationResult.to_dict includes new text fields."""
    classifier = UniversalPromptClassifier()
    result = classifier.classify("sign saying 'Test'")
    d = result.to_dict()
    assert "requires_text" in d
    assert "text_type" in d
    assert "expected_text" in d
    assert "text_placement" in d
    assert "text_confidence" in d
    assert d["requires_text"] is True
    assert d["expected_text"] == "Test"


def test_placement_inferred_from_context():
    """Placement inferred from 'at the top' / 'at the bottom'."""
    classifier = UniversalPromptClassifier()
    r_top = classifier.classify("header that says 'Welcome' at the top")
    r_bottom = classifier.classify("caption at the bottom that says 'Credits'")
    assert r_top.requires_text is True
    assert r_top.text_placement == "top"
    assert r_bottom.requires_text is True
    assert r_bottom.text_placement == "bottom"

"""
Tests for Typography Engine integration in Deterministic Pipeline (Task 4.2).
Auto-apply typography when requires_text, OCR verification, retries, text_not_guaranteed.
"""

import pytest

try:
    from services.deterministic_pipeline import (
        DeterministicPipeline,
        _strip_text_intent_for_generation,
        _placement_to_position,
        _typography_style_from_category,
        TYPOGRAPHY_RETRY_ATTEMPTS,
        TYPOGRAPHY_OCR_THRESHOLD,
    )
except ImportError:
    from ai_pipeline.services.deterministic_pipeline import (
        DeterministicPipeline,
        _strip_text_intent_for_generation,
        _placement_to_position,
        _typography_style_from_category,
        TYPOGRAPHY_RETRY_ATTEMPTS,
        TYPOGRAPHY_OCR_THRESHOLD,
    )


def test_strip_text_intent_removes_quoted():
    """_strip_text_intent_for_generation removes quoted expected text."""
    out = _strip_text_intent_for_generation(
        "coffee shop with sign saying 'Fresh Brew'", "Fresh Brew"
    )
    assert "Fresh Brew" not in out
    assert "coffee" in out or "sign" in out


def test_strip_text_intent_removes_that_says():
    """Strip ' that says \"...\"' style phrases."""
    out = _strip_text_intent_for_generation(
        'street with sign that says "Hello World"', "Hello World"
    )
    assert "Hello World" not in out


def test_strip_text_intent_no_expected_returns_unchanged():
    """When expected_text is None, prompt is unchanged."""
    p = "a cat on a sofa"
    assert _strip_text_intent_for_generation(p, None) == p


def test_placement_to_position():
    """_placement_to_position maps placement to position string."""
    assert _placement_to_position("top") == "top"
    assert _placement_to_position("bottom") == "bottom"
    assert _placement_to_position("centered") == "center"
    assert _placement_to_position("center") == "center"
    assert _placement_to_position("on_object") == "center"
    assert _placement_to_position(None) == "center"


def test_typography_style_from_category():
    """Style: bold for signs, serif for posters."""
    assert _typography_style_from_category("", "sign") == "sans_bold"
    assert _typography_style_from_category("", "poster") == "serif"
    assert _typography_style_from_category("", "caption") == "sans"
    assert _typography_style_from_category("", "label") == "sans"


def test_config_defaults():
    """TYPOGRAPHY_RETRY_ATTEMPTS and TYPOGRAPHY_OCR_THRESHOLD have defaults."""
    assert TYPOGRAPHY_RETRY_ATTEMPTS >= 0
    assert 0 <= TYPOGRAPHY_OCR_THRESHOLD <= 1.0


def test_run_with_requires_text_uses_stripped_prompt():
    """When classification has requires_text and expected_text, generator receives stripped prompt."""
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

    # Classifier that says prompt requires text "Fresh Brew"
    class MockClassification:
        requires_text = True
        expected_text = "Fresh Brew"
        text_placement = "on_object"
        text_type = "sign"
        category = "specialty"

    pipeline._classifier = type(
        "C", (), {"classify": lambda self, p: MockClassification()}
    )()
    pipeline._typography_engine = None  # no typography so we don't need PIL
    received_prompts = []

    def fake_generator(prompt: str, negative: str, **kwargs):
        received_prompts.append(prompt)
        return b"fake_image"

    pipeline.set_generator(fake_generator)
    pipeline.run("coffee shop with sign saying 'Fresh Brew'")
    assert len(received_prompts) == 1
    # Generator should get prompt without the quoted text
    assert "Fresh Brew" not in received_prompts[0]


def test_run_with_typography_sets_metadata_when_ocr_fails():
    """When typography runs and OCR fails after retries, quality_metrics has text_not_guaranteed."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required for typography test")
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

    class MockClassification:
        requires_text = True
        expected_text = "X"
        text_placement = "center"
        text_type = "sign"
        category = "specialty"

    pipeline._classifier = type(
        "C", (), {"classify": lambda self, p: MockClassification()}
    )()

    # Typography engine that always fails OCR (e.g. no pytesseract or mock)
    class MockTypography:
        def add_text_overlay(
            self,
            image,
            text,
            position="bottom",
            font_size=40,
            style="sans_bold",
            **kwargs
        ):
            return image

        def verify_ocr(self, image, expected_text, similarity_threshold=None):
            return False, ""

    pipeline._typography_engine = MockTypography()

    def fake_generator(prompt, negative, **kwargs):
        return Image.new("RGB", (64, 64), color=(128, 128, 128))

    pipeline.set_generator(fake_generator)
    result = pipeline.run("sign that says 'X'")
    assert result.quality_metrics.get("text_not_guaranteed") is True
    assert result.quality_metrics.get("text_ocr_passed") is False


def test_run_with_typography_sets_ocr_passed_when_ok():
    """When typography runs and OCR passes, quality_metrics has text_ocr_passed True."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL required for typography test")
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

    class MockClassification:
        requires_text = True
        expected_text = "OK"
        text_placement = "bottom"
        text_type = "caption"
        category = "specialty"

    pipeline._classifier = type(
        "C", (), {"classify": lambda self, p: MockClassification()}
    )()

    class MockTypography:
        def add_text_overlay(
            self,
            image,
            text,
            position="bottom",
            font_size=40,
            style="sans_bold",
            **kwargs
        ):
            return image

        def verify_ocr(self, image, expected_text, similarity_threshold=None):
            return True, expected_text

    pipeline._typography_engine = MockTypography()

    def fake_generator(prompt, negative, **kwargs):
        return Image.new("RGB", (64, 64), color=(128, 128, 128))

    pipeline.set_generator(fake_generator)
    result = pipeline.run("caption that says 'OK'")
    assert result.quality_metrics.get("text_ocr_passed") is True
    assert result.quality_metrics.get("text_not_guaranteed") is not True

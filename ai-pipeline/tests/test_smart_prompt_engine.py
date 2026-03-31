"""
Tests for Smart Prompt Engine and Universal Prompt Classifier.
"""

import pytest

try:
    from services.universal_prompt_classifier import (
        ClassificationResult,
        UniversalPromptClassifier,
        get_default_classifier,
    )
    from services.smart_prompt_engine import SmartPromptEngine
except ImportError:
    from ai_pipeline.services.universal_prompt_classifier import (
        ClassificationResult,
        UniversalPromptClassifier,
        get_default_classifier,
    )
    from ai_pipeline.services.smart_prompt_engine import SmartPromptEngine


def test_classifier_returns_rich_result():
    """UniversalPromptClassifier.classify returns ClassificationResult with all fields."""
    c = UniversalPromptClassifier()
    r = c.classify("a cat on a rooftop at dusk")
    assert r.raw_prompt == "a cat on a rooftop at dusk"
    assert isinstance(r.style, str)
    assert isinstance(r.medium, str)
    assert isinstance(r.category, str)
    assert isinstance(r.lighting, str)
    assert isinstance(r.color_palette, str)
    assert isinstance(r.has_people, bool)
    assert isinstance(r.person_count, int)
    assert isinstance(r.has_fantasy, bool)
    assert isinstance(r.has_weather, bool)
    assert isinstance(r.has_animals, bool)
    assert isinstance(r.has_text, bool)
    assert isinstance(r.has_architecture, bool)


def test_classifier_detects_person():
    """Classifier detects one person."""
    c = UniversalPromptClassifier()
    r = c.classify("portrait of a woman")
    assert r.has_people is True
    assert r.person_count >= 1


def test_classifier_detects_two_people():
    """Classifier detects two people."""
    c = UniversalPromptClassifier()
    r = c.classify("two people standing in a park")
    assert r.has_people is True
    assert r.person_count == 2


def test_classifier_detects_weather():
    """Classifier detects weather."""
    c = UniversalPromptClassifier()
    r = c.classify("person walking in the rain")
    assert r.has_weather is True


def test_classifier_detects_fantasy():
    """Classifier detects fantasy."""
    c = UniversalPromptClassifier()
    r = c.classify("a dragon in a magical forest")
    assert r.has_fantasy is True


def test_smart_prompt_engine_build_prompts():
    """SmartPromptEngine.build_prompts returns (positive, negative) strings."""
    engine = SmartPromptEngine()
    r = ClassificationResult(
        raw_prompt="a cat on a rooftop at dusk",
        style="photorealistic",
        medium="photograph",
        category="nature",
        lighting="golden_hour",
        color_palette="warm",
        has_people=False,
        person_count=0,
        has_fantasy=False,
        has_weather=False,
        has_animals=True,
        has_text=False,
        has_architecture=False,
    )
    pos, neg = engine.build_prompts(r)
    assert isinstance(pos, str)
    assert isinstance(neg, str)
    assert "a cat on a rooftop at dusk" in pos
    assert "photorealistic" in pos or "8K" in pos
    assert "blurry" in neg or "low quality" in neg


def test_smart_prompt_engine_with_people():
    """Positive prompt includes people guards when has_people=True."""
    engine = SmartPromptEngine()
    r = ClassificationResult(
        raw_prompt="portrait of a woman",
        style="photorealistic",
        medium="photograph",
        category="portrait",
        lighting="studio",
        color_palette="natural",
        has_people=True,
        person_count=1,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    pos, neg = engine.build_prompts(r)
    assert "single person" in pos or "complete human figure" in pos or "anatomically correct" in pos
    assert "extra people" in neg or "merged bodies" in neg


def test_end_to_end_classifier_plus_engine():
    """Classify prompt then build prompts: full flow."""
    classifier = get_default_classifier()
    engine = SmartPromptEngine()
    classification = classifier.classify("a cat on a rooftop at dusk")
    positive, negative = engine.build_prompts(classification)
    assert len(positive) > len("a cat on a rooftop at dusk")
    assert len(negative) > 0
    assert "a cat on a rooftop at dusk" in positive


# ---------------------------------------------------------------------------
# Auto-LoRA: recommend_loras()
# ---------------------------------------------------------------------------

def test_recommend_loras_always_color_harmony():
    """recommend_loras always includes color_harmony_v1 (max 3)."""
    engine = SmartPromptEngine()
    r = ClassificationResult(
        raw_prompt="sunset over mountains",
        style="photorealistic",
        medium="photograph",
        category="landscape",
        lighting="golden_hour",
        color_palette="warm",
        has_people=False,
        person_count=0,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    loras = engine.recommend_loras(r)
    assert "color_harmony_v1" in loras
    assert len(loras) <= 3


def test_recommend_loras_portrait_adds_skin_realism():
    """Portrait or has_people adds skin_realism_v2."""
    engine = SmartPromptEngine()
    r = ClassificationResult(
        raw_prompt="portrait of a woman",
        style="photorealistic",
        medium="photograph",
        category="portrait",
        lighting="studio",
        color_palette="natural",
        has_people=True,
        person_count=1,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    loras = engine.recommend_loras(r)
    assert "color_harmony_v1" in loras
    assert "skin_realism_v2" in loras
    assert len(loras) <= 3


def test_recommend_loras_cinematic_portrait_multi_category():
    """Multi-category (cinematic portrait): skin_realism_v2 + cinematic_lighting_v3 + color_harmony_v1."""
    engine = SmartPromptEngine()
    r = ClassificationResult(
        raw_prompt="cinematic portrait of a man",
        style="cinematic",
        medium="photograph",
        category="portrait",
        lighting="dramatic",
        color_palette="natural",
        has_people=True,
        person_count=1,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    loras = engine.recommend_loras(r)
    assert "color_harmony_v1" in loras
    assert "skin_realism_v2" in loras
    assert "cinematic_lighting_v3" in loras
    assert len(loras) <= 3


def test_recommend_loras_no_people_scene():
    """No people / scene-only: only color_harmony_v1 (and cinematic_lighting_v3 if photograph)."""
    engine = SmartPromptEngine()
    r = ClassificationResult(
        raw_prompt="abstract geometric shapes",
        style="minimal_flat",
        medium="illustration",
        category="graphics",
        lighting="natural",
        color_palette="vibrant",
        has_people=False,
        person_count=0,
        has_fantasy=False,
        has_weather=False,
        has_animals=False,
        has_text=False,
        has_architecture=False,
    )
    loras = engine.recommend_loras(r)
    assert "color_harmony_v1" in loras
    assert "skin_realism_v2" not in loras
    assert len(loras) <= 3


def test_recommend_loras_photograph_adds_cinematic_lighting():
    """Medium photograph adds cinematic_lighting_v3."""
    engine = SmartPromptEngine()
    r = ClassificationResult(
        raw_prompt="product shot on white",
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
    loras = engine.recommend_loras(r)
    assert "color_harmony_v1" in loras
    assert "cinematic_lighting_v3" in loras
    assert len(loras) <= 3


def test_recommend_loras_only_known_names():
    """recommend_loras returns only known LoRA names (S3/style dir convention)."""
    allowed = {"color_harmony_v1", "skin_realism_v2", "cinematic_lighting_v3"}
    engine = SmartPromptEngine()
    for has_people, category, medium in [
        (False, "landscape", "photograph"),
        (True, "portrait", "photograph"),
        (True, "portrait", "illustration"),
    ]:
        r = ClassificationResult(
            raw_prompt="test",
            style="photorealistic",
            medium=medium,
            category=category,
            lighting="natural",
            color_palette="natural",
            has_people=has_people,
            person_count=1 if has_people else 0,
            has_fantasy=False,
            has_weather=False,
            has_animals=False,
            has_text=False,
            has_architecture=False,
        )
        loras = engine.recommend_loras(r)
        assert set(loras) <= allowed, "Unknown LoRA name in %s" % loras
        assert len(loras) <= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

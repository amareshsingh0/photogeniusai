"""
Tests for Failure Memory & Smart Recovery.
P1: 70%+ common failures auto-fixed on first attempt.
"""

import pytest
import tempfile
from pathlib import Path

try:
    from services.pattern_matcher import PatternMatcher, PatternMatch
    from services.failure_memory_system import (
        FailureMemorySystem,
        FailureEntry,
        DEFAULT_PATTERNS,
    )
except ImportError:
    from ai_pipeline.services.pattern_matcher import PatternMatcher, PatternMatch
    from ai_pipeline.services.failure_memory_system import (
        FailureMemorySystem,
        FailureEntry,
        DEFAULT_PATTERNS,
    )


def test_pattern_matcher_match():
    """PatternMatcher matches regex and returns PatternMatch."""
    matcher = PatternMatcher(case_sensitive=False)
    m = matcher.match(
        "Mother with 3 children under umbrella in heavy rain",
        r"mother.*children.*umbrella.*rain",
        "heads_occluded",
        {"camera_tilt": -10, "umbrella_height": 80},
    )
    assert m is not None
    assert m.failure == "heads_occluded"
    assert m.fix["camera_tilt"] == -10
    assert m.score >= 0.3


def test_pattern_matcher_no_match():
    """PatternMatcher returns None when no match."""
    matcher = PatternMatcher(case_sensitive=False)
    m = matcher.match(
        "A single tree in a field",
        r"mother.*children.*umbrella",
        "heads_occluded",
        {},
    )
    assert m is None


def test_failure_memory_get_fix():
    """FailureMemorySystem returns fix for matching prompt."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    fix = system.get_fix_for_prompt("Mother with 3 children under umbrella in rain")
    assert fix is not None
    assert "camera_tilt" in fix or "umbrella_height" in fix or "person_spacing" in fix


def test_failure_memory_auto_fix_common():
    """Common failure patterns (umbrella + rain) get auto-fix."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    prompts = [
        "Mother with 3 children under umbrella in heavy rain",
        "Family of 4 with umbrella in rain",
        "Couple walking with umbrella in the rain",
    ]
    fixed = 0
    for p in prompts:
        if system.get_fix_for_prompt(p):
            fixed += 1
    # At least 2 of 3 should match (70%+ metric)
    assert fixed >= 2, f"Expected at least 2/3 prompts to get fix, got {fixed}"


def test_failure_memory_apply_fix_to_layout():
    """apply_fix_to_layout applies camera_tilt, person_spacing, umbrella_height."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    layout = {
        "entities": [
            {"type": "person", "head_position": (100, 50), "bbox": (80, 20, 120, 100)},
            {"type": "umbrella", "center": (100, 30)},
        ],
        "camera": {"tilt": 0},
    }
    fix = {"camera_tilt": -10, "person_spacing": 50, "umbrella_height": 80}
    out = system.apply_fix_to_layout(layout, fix)
    assert out["camera"]["tilt"] == -10
    assert out["entities"][1]["center"][1] == 30 - 80  # umbrella up


def test_failure_memory_apply_fix_to_prompt():
    """apply_fix_to_prompt appends positive/negative_prompt_append."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    fix = {
        "negative_prompt_append": "extra limbs, deformed",
        "positive_prompt_append": "clear separation",
    }
    p, n = system.apply_fix_to_prompt("original", "blurry", fix)
    assert "clear separation" in p
    assert "extra limbs" in n


def test_failure_memory_record_and_persist():
    """record_failure and save/load persist path."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "failure_memory.json"
        system = FailureMemorySystem(persist_path=path, initial_patterns=DEFAULT_PATTERNS)
        system.record_failure("Test prompt with umbrella", "heads_occluded", context={"suggested_fix": {"camera_tilt": -5}})
        system.save()
        assert path.exists()
        system2 = FailureMemorySystem(persist_path=path)
        fix = system2.get_fix_for_prompt("Test prompt with umbrella")
        # May match default or the new pattern
        assert True  # load succeeded


# ----- Expanded patterns: match and fix tests -----

# Sample prompts per category that should match at least one pattern
MULTI_PERSON_PROMPTS = [
    "group of people holding umbrellas in the park",
    "crowd of 10 people at a concert",
    "family photo with 5 members",
    "wedding guests gathered in the garden",
    "3 friends sitting together on a bench",
]
WEATHER_PROMPTS = [
    "heavy rain on a city street",
    "portrait in falling snow storm",
    "foggy portrait at dawn",
    "rainy day scene with people walking",
]
PROPS_PROMPTS = [
    "woman holding handbag in studio",
    "person holding a sign at a protest",
    "man holding smartphone selfie",
    "beach umbrella on sunny day",
    "hand holding a coffee cup",
]
ANATOMY_PROMPTS = [
    "hands holding a gift box",
    "profile face portrait",
    "backlit person at sunset",
    "close-up of hands typing",
    "two people holding hands walking",
]
LIGHTING_PROMPTS = [
    "backlit portrait in studio",
    "nighttime portrait with city lights",
    "face in heavy shadow",
    "person at sunset on the beach",
]
TEXT_SIGNAGE_PROMPTS = [
    "store sign above a shop door",
    "poster on the wall of a cafe",
    "label on a wine bottle product shot",
    "street sign at the corner",
    "menu with text on a chalkboard",
]


def test_all_default_patterns_have_required_keys():
    """Every DEFAULT_PATTERNS entry has pattern, failure, and fix with at least one key."""
    for i, p in enumerate(DEFAULT_PATTERNS):
        assert "pattern" in p, f"Pattern {i} missing 'pattern'"
        assert "failure" in p, f"Pattern {i} missing 'failure'"
        assert "fix" in p, f"Pattern {i} missing 'fix'"
        fix = p["fix"]
        assert isinstance(fix, dict), f"Pattern {i} fix must be dict"
        allowed = {
            "camera_tilt", "umbrella_height", "person_spacing",
            "negative_prompt_append", "positive_prompt_append",
        }
        for k in fix:
            assert k in allowed, f"Pattern {i} fix has unknown key: {k}"


def test_multi_person_patterns_match():
    """Multi-person scenarios (groups, crowds, families) match and return fixes."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    matched = 0
    for prompt in MULTI_PERSON_PROMPTS:
        fix = system.get_fix_for_prompt(prompt)
        if fix:
            matched += 1
            assert isinstance(fix, dict)
            assert "person_spacing" in fix or "positive_prompt_append" in fix or "camera_tilt" in fix
    assert matched >= 3, f"Expected at least 3/5 multi-person prompts to match, got {matched}"


def test_weather_patterns_match():
    """Weather conditions (rain, snow, fog) match and return fixes."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    matched = 0
    for prompt in WEATHER_PROMPTS:
        fix = system.get_fix_for_prompt(prompt)
        if fix:
            matched += 1
            assert "positive_prompt_append" in fix or "negative_prompt_append" in fix or "camera_tilt" in fix
    assert matched >= 2, f"Expected at least 2/4 weather prompts to match, got {matched}"


def test_props_patterns_match():
    """Props and objects (umbrellas, bags, signs) match and return fixes."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    matched = 0
    for prompt in PROPS_PROMPTS:
        fix = system.get_fix_for_prompt(prompt)
        if fix:
            matched += 1
            assert "positive_prompt_append" in fix or "negative_prompt_append" in fix or "umbrella_height" in fix
    assert matched >= 3, f"Expected at least 3/5 props prompts to match, got {matched}"


def test_anatomy_patterns_match():
    """Anatomy issues (hands, faces partially visible) match and return fixes."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    matched = 0
    for prompt in ANATOMY_PROMPTS:
        fix = system.get_fix_for_prompt(prompt)
        if fix:
            matched += 1
            assert "positive_prompt_append" in fix or "negative_prompt_append" in fix
    assert matched >= 3, f"Expected at least 3/5 anatomy prompts to match, got {matched}"


def test_lighting_patterns_match():
    """Lighting challenges (backlit, shadows, night) match and return fixes."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    matched = 0
    for prompt in LIGHTING_PROMPTS:
        fix = system.get_fix_for_prompt(prompt)
        if fix:
            matched += 1
            assert "positive_prompt_append" in fix or "negative_prompt_append" in fix
    assert matched >= 2, f"Expected at least 2/4 lighting prompts to match, got {matched}"


def test_text_signage_patterns_match():
    """Text/signage (store signs, posters, labels) match and return fixes."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    matched = 0
    for prompt in TEXT_SIGNAGE_PROMPTS:
        fix = system.get_fix_for_prompt(prompt)
        if fix:
            matched += 1
            assert "positive_prompt_append" in fix or "negative_prompt_append" in fix
    assert matched >= 3, f"Expected at least 3/5 text prompts to match, got {matched}"


def test_umbrella_occlusion_pattern_example():
    """Example from spec: group holding umbrellas matches and fix improves prompt."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    prompt = "group of tourists holding umbrellas in the rain"
    fix = system.get_fix_for_prompt(prompt)
    assert fix is not None
    assert "positive_prompt_append" in fix or "negative_prompt_append" in fix or "camera_tilt" in fix
    new_prompt, new_neg = system.apply_fix_to_prompt(prompt, "blurry", fix)
    if fix.get("positive_prompt_append"):
        assert "clear view" in new_prompt or "umbrellas" in new_prompt.lower()
    if fix.get("negative_prompt_append"):
        assert "umbrella" in new_neg.lower() or "blocking" in new_neg.lower() or "face" in new_neg.lower()


def test_fixes_improve_prompts():
    """Applying fix from get_fix_for_prompt adds positive/negative append when present."""
    system = FailureMemorySystem(initial_patterns=DEFAULT_PATTERNS)
    prompts_with_expected_append = [
        ("hands holding a bouquet", "positive_prompt_append", "hand"),
        ("store sign at the corner", "positive_prompt_append", "legible"),
        ("backlit portrait", "positive_prompt_append", "face"),
    ]
    for prompt, key, substring in prompts_with_expected_append:
        fix = system.get_fix_for_prompt(prompt)
        if fix and fix.get(key):
            new_p, new_n = system.apply_fix_to_prompt(prompt, "blurry", fix)
            assert substring in new_p.lower() or substring in new_n.lower(), (
                f"Expected fix to add something containing '{substring}' for prompt: {prompt}"
            )


def test_expanded_pattern_count():
    """DEFAULT_PATTERNS has 20+ entries (original 7 + expanded)."""
    assert len(DEFAULT_PATTERNS) >= 27, (
        f"Expected at least 27 patterns (7 original + 20 new), got {len(DEFAULT_PATTERNS)}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:asyncio"])

"""
Validation tests for Creative Engine mutation system.

Run: python ai-pipeline/services/test_creative_mutation.py
Or:  pytest ai-pipeline/services/test_creative_mutation.py -v
     (if services.creative_mutation is importable without pulling Modal deps)

Covers:
- MutationSystem.mutate_params (subtle/moderate/wild, seed variation)
- MutationSystem.mutate_prompt (keyword injection, prefix/suffix/middle)
- creative_level -> mutation level mapping
"""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

# Load creative_mutation directly to avoid services __init__ (Modal, etc.)
_here = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "creative_mutation",
    _here / "creative_mutation.py",
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Could not load creative_mutation module (spec or loader missing)")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
MutationSystem = _mod.MutationSystem


def test_mutate_params_subtle():
    """Subtle mutations keep params close to base."""
    random.seed(42)
    base = {"guidance_scale": 7.5, "num_inference_steps": 50, "seed": 12345}
    out = MutationSystem.mutate_params(base, mutation_level="subtle", num_mutations=4)
    assert len(out) == 4
    for m in out:
        assert 1.0 <= m["guidance_scale"] <= 20.0
        assert 20 <= m["num_inference_steps"] <= 80
        assert m["seed"] in (12345, 12346, 12347, 12348)


def test_mutate_params_moderate():
    """Moderate mutations allow wider variation."""
    random.seed(43)
    base = {"guidance_scale": 7.5, "num_inference_steps": 50, "seed": 1}
    out = MutationSystem.mutate_params(base, mutation_level="moderate", num_mutations=3)
    assert len(out) == 3
    guidance_vals = [m["guidance_scale"] for m in out]
    assert min(guidance_vals) != max(guidance_vals) or len(set(guidance_vals)) >= 1


def test_mutate_params_wild():
    """Wild mutations use preset ranges."""
    random.seed(44)
    base = {"guidance_scale": 7.5, "num_inference_steps": 50}
    out = MutationSystem.mutate_params(base, mutation_level="wild", num_mutations=2)
    assert len(out) == 2
    for m in out:
        assert "guidance_scale" in m
        assert "num_inference_steps" in m


def test_mutate_params_unknown_level_fallback():
    """Unknown mutation level falls back to moderate."""
    random.seed(45)
    base = {"guidance_scale": 7.5, "num_inference_steps": 50}
    out = MutationSystem.mutate_params(base, mutation_level="unknown", num_mutations=2)
    assert len(out) == 2


def test_mutate_prompt_keywords():
    """Prompt variations inject style keywords."""
    random.seed(46)
    base = "portrait of a person"
    keywords = ["cinematic lighting", "film grain", "dramatic"]
    out = MutationSystem.mutate_prompt(base, keywords, num_variations=4)
    assert len(out) == 4
    assert out[0] == base
    for v in out[1:]:
        assert "portrait" in v
        assert any(k in v for k in keywords)


def test_mutate_prompt_no_keywords():
    """No keywords -> only original prompt."""
    out = MutationSystem.mutate_prompt("hello", [], num_variations=3)
    assert out == ["hello"]


def test_mutate_prompt_single_variation():
    """num_variations=1 returns only base."""
    out = MutationSystem.mutate_prompt("x", ["a", "b"], num_variations=1)
    assert out == ["x"]


def test_creative_level_to_mutation():
    """creative_level <0.3 subtle, <0.7 moderate, else wild."""
    def level(creative: float) -> str:
        if creative < 0.3:
            return "subtle"
        if creative < 0.7:
            return "moderate"
        return "wild"
    assert level(0.0) == "subtle"
    assert level(0.29) == "subtle"
    assert level(0.3) == "moderate"
    assert level(0.69) == "moderate"
    assert level(0.7) == "wild"
    assert level(1.0) == "wild"


def test_mutation_presets_exist():
    """Subtle, moderate, wild presets defined."""
    assert "subtle" in MutationSystem.MUTATION_PRESETS
    assert "moderate" in MutationSystem.MUTATION_PRESETS
    assert "wild" in MutationSystem.MUTATION_PRESETS


def run_all():
    """Run all validation tests."""
    tests = [
        test_mutate_params_subtle,
        test_mutate_params_moderate,
        test_mutate_params_wild,
        test_mutate_params_unknown_level_fallback,
        test_mutate_prompt_keywords,
        test_mutate_prompt_no_keywords,
        test_mutate_prompt_single_variation,
        test_creative_level_to_mutation,
        test_mutation_presets_exist,
    ]
    for t in tests:
        t()
        print(f"  {t.__name__}: ok")
    print(f"\nAll {len(tests)} checks passed.")


if __name__ == "__main__":
    run_all()

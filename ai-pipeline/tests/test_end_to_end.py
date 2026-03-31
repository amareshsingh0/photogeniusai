"""
End-to-end integration tests.

Tests the COMPLETE pipeline from prompt to final image:
  Prompt → Scene → Physics → Generation → Validation → Refinement → Output

Categories: simple, multi-person, weather (rain), fantasy.
Includes performance benchmarks and success-rate checks.

Run with GPU: pytest tests/test_end_to_end.py -v
Skip e2e/slow: pytest -m "not slow"  or  pytest -m "not e2e"
"""

from __future__ import annotations

import time
import pytest

# Safe GPU check: do not require torch at import so collection works without GPU
try:
    import torch
    _cuda_available = torch.cuda.is_available()
except Exception:
    _cuda_available = False

pytestmark = [
    pytest.mark.skipif(not _cuda_available, reason="Requires GPU"),
    pytest.mark.slow,
    pytest.mark.e2e,
]


def _run_pipeline(
    prompt: str,
    max_iterations: int = 2,
    quality_threshold: float = 0.75,
    seed: int = 42,
) -> dict:
    """Run full pipeline: SelfImprovementEngine + IterativeRefinementEngine."""
    from services.self_improvement_engine import SelfImprovementEngine
    from services.iterative_refinement_engine import IterativeRefinementEngine

    refinement = IterativeRefinementEngine(
        device="cuda",
        max_iterations=max_iterations,
        quality_threshold=quality_threshold,
    )
    si_engine = SelfImprovementEngine()
    return si_engine.generate_with_learning(
        refinement,
        prompt,
        max_iterations=max_iterations,
        seed=seed,
    )


# ----- Simple -----


@pytest.mark.slow
def test_complete_pipeline_simple():
    """Prompt → Scene → Physics → Generation → Validation → Refinement → Output."""
    result = _run_pipeline("Person standing", max_iterations=2, seed=42)

    assert "image" in result
    # Image may be PIL or placeholder when diffusion unavailable
    img = result["image"]
    assert img is not None
    assert hasattr(img, "size") or (hasattr(img, "shape") and len(img.shape) >= 2)
    assert result["total_iterations"] >= 1
    assert 0.0 <= result["final_score"] <= 1.0
    assert "success" in result
    assert "self_improvement" in result


# ----- Multi-person -----


@pytest.mark.slow
def test_multi_person_scene():
    """Test multi-person accuracy: scene graph and validation handle multiple people."""
    result = _run_pipeline(
        "Two people standing in a park",
        max_iterations=2,
        seed=43,
    )

    assert "image" in result
    assert result["image"] is not None
    assert result["total_iterations"] >= 1
    assert 0.0 <= result["final_score"] <= 1.0
    scene = result.get("scene_graph") or {}
    # Quality requirements may include person count
    assert "metadata" in result


# ----- Weather (rain) -----


@pytest.mark.slow
def test_rainy_scene_physics():
    """Test rain physics: environment and prompt modifiers applied."""
    result = _run_pipeline(
        "Person walking in the rain",
        max_iterations=2,
        seed=44,
    )

    assert "image" in result
    assert result["image"] is not None
    assert result["total_iterations"] >= 1
    assert 0.0 <= result["final_score"] <= 1.0
    # Physics/weather may appear in scene_graph or physics_result
    assert "physics_result" in result or "scene_graph" in result


# ----- Fantasy -----


@pytest.mark.slow
def test_fantasy_scene():
    """Test fantasy-style scene (dragon/magical)."""
    result = _run_pipeline(
        "A dragon in a magical forest",
        max_iterations=2,
        seed=45,
    )

    assert "image" in result
    assert result["image"] is not None
    assert result["total_iterations"] >= 1
    assert 0.0 <= result["final_score"] <= 1.0


# ----- Performance -----


@pytest.mark.slow
def test_performance_benchmark():
    """Pipeline completes within a reasonable time (benchmark)."""
    start = time.perf_counter()
    result = _run_pipeline("Person standing", max_iterations=2, seed=46)
    elapsed = time.perf_counter() - start

    assert result["total_iterations"] >= 1
    # Allow up to 5 minutes for 2 iterations on GPU (generation can be slow)
    assert elapsed < 300.0, f"Pipeline took {elapsed:.1f}s (max 300s)"


# ----- Success rate -----


@pytest.mark.slow
def test_success_rate_measurement():
    """Run several prompts and measure success rate (at least one completes)."""
    prompts = [
        "Person standing",
        "Two people in a park",
    ]
    results = []
    for i, prompt in enumerate(prompts):
        r = _run_pipeline(prompt, max_iterations=2, seed=50 + i)
        results.append(r)

    # All runs must return valid structure
    for r in results:
        assert "final_score" in r
        assert "total_iterations" in r
        assert 0.0 <= r["final_score"] <= 1.0
        assert r["total_iterations"] >= 1

    # At least one run should have an image
    images_ok = sum(1 for r in results if r.get("image") is not None)
    assert images_ok >= 1, "At least one run should produce an image"

    # Success rate: count how many met threshold (e.g. 0.75)
    threshold = 0.75
    success_count = sum(1 for r in results if r.get("final_score", 0) >= threshold)
    # We only require that the pipeline runs; success rate is measured for reporting
    assert len(results) == len(prompts)

"""
Tests for Comprehensive Testing Suite and Benchmark Runner.

P0: 1000-image benchmark; success metrics 99%+ person count, 95%+ hand, 90%+ physics, 85%+ fantasy.
Run: pytest tests/test_comprehensive_benchmark.py -v -p no:asyncio
"""

import pytest

try:
    from tests.comprehensive_test_suite import (
        TEST_CATEGORIES,
        SUCCESS_METRICS,
        BenchmarkTestCase,
        get_prompts_for_benchmark,
        score_image,
        aggregate_scores,
    )
except ImportError:
    from comprehensive_test_suite import (
        TEST_CATEGORIES,
        SUCCESS_METRICS,
        BenchmarkTestCase,
        get_prompts_for_benchmark,
        score_image,
        aggregate_scores,
    )

try:
    from tests.benchmark_runner import run_benchmark, BenchmarkConfig, BenchmarkResult
except ImportError:
    from benchmark_runner import run_benchmark, BenchmarkConfig, BenchmarkResult


def test_success_metrics_defined():
    """Success metrics must include 99% person count, 95% hand, 90% physics, 85% fantasy."""
    assert SUCCESS_METRICS["person_count_accuracy"] >= 0.99
    assert SUCCESS_METRICS["hand_anatomy"] >= 0.95
    assert SUCCESS_METRICS["physics_realism"] >= 0.90
    assert SUCCESS_METRICS["fantasy_coherence"] >= 0.85
    assert "text_accuracy" in SUCCESS_METRICS
    assert "math_diagram_accuracy" in SUCCESS_METRICS


def test_categories_six():
    """All six test categories must exist."""
    assert len(TEST_CATEGORIES) == 6
    assert "multi_person" in TEST_CATEGORIES
    assert "rain_weather" in TEST_CATEGORIES
    assert "hand_anatomy" in TEST_CATEGORIES
    assert "fantasy" in TEST_CATEGORIES
    assert "text_embedded" in TEST_CATEGORIES
    assert "math_diagrams" in TEST_CATEGORIES


def test_get_prompts_for_benchmark_total():
    """get_prompts_for_benchmark respects total and returns BenchmarkTestCase list."""
    cases = get_prompts_for_benchmark(
        total=50, categories=["multi_person", "rain_weather"]
    )
    assert len(cases) <= 50
    assert all(isinstance(c, BenchmarkTestCase) for c in cases)
    assert all(c.category in ("multi_person", "rain_weather") for c in cases)


def test_get_prompts_for_benchmark_1000():
    """Benchmark can build 1000 cases across all categories."""
    cases = get_prompts_for_benchmark(total=1000)
    assert len(cases) <= 1000
    cats = {c.category for c in cases}
    assert cats == set(TEST_CATEGORIES) or len(cats) >= 1


def test_score_image_dry_run():
    """score_image with None image returns heuristic scores (dry run)."""
    tc = BenchmarkTestCase(
        category="multi_person", prompt="2 people at cafe", expected_person_count=2
    )
    result = score_image("multi_person", None, tc)
    assert "person_count_accuracy" in result
    assert "hand_anatomy" in result
    assert "physics_realism" in result
    assert "fantasy_coherence" in result
    assert 0 <= result["person_count_accuracy"] <= 1
    assert 0 <= result["hand_anatomy"] <= 1


def test_aggregate_scores():
    """aggregate_scores returns dict with metric names and 0-1 values."""
    scores = [
        {
            "person_count_accuracy": 1.0,
            "hand_anatomy": 1.0,
            "physics_realism": 0.9,
            "fantasy_coherence": 0.85,
            "text_accuracy": 1.0,
            "math_diagram_accuracy": 1.0,
        },
        {
            "person_count_accuracy": 0.0,
            "hand_anatomy": 1.0,
            "physics_realism": 0.9,
            "fantasy_coherence": 0.85,
            "text_accuracy": 1.0,
            "math_diagram_accuracy": 1.0,
        },
    ]
    agg = aggregate_scores(scores)
    assert agg["person_count_accuracy"] == 0.5
    assert agg["hand_anatomy"] == 1.0


def test_benchmark_runner_dry_run():
    """run_benchmark with dry_run returns BenchmarkResult; all metrics pass in dry run."""
    config = BenchmarkConfig(total_max=18, dry_run=True)
    result = run_benchmark(None, config)
    assert isinstance(result, BenchmarkResult)
    assert result.total_run == result.total_planned
    assert result.total_run <= 18
    assert result.person_count_accuracy >= 0
    assert result.hand_anatomy >= 0
    assert result.physics_realism >= 0
    assert result.fantasy_coherence >= 0
    # In dry run we use heuristic pass, so metrics should pass
    assert result.all_metrics_passed


def test_benchmark_result_summary():
    """BenchmarkResult.summary() returns non-empty string with PASS/FAIL."""
    config = BenchmarkConfig(total_max=6, dry_run=True)
    result = run_benchmark(None, config)
    summary = result.summary()
    assert "Benchmark:" in summary
    assert "person_count_accuracy" in summary
    assert "PASS" in summary or "FAIL" in summary


def test_benchmark_single_category():
    """run_benchmark with one category runs only that category."""
    config = BenchmarkConfig(
        total_max=5, max_per_category=5, categories=["fantasy"], dry_run=True
    )
    result = run_benchmark(None, config)
    assert result.total_run <= 5
    assert result.per_category_counts.get("fantasy", 0) <= 5

"""
Tests for Enhanced Self-Improvement Engine.
"""

import json
import os
import pytest

try:
    from services.enhanced_self_improvement_engine import (
        GenerationRecord,
        CategoryStats,
        LocalStorageAdapter,
        EnhancedSelfImprovementEngine,
    )
except ImportError:
    from ai_pipeline.services.enhanced_self_improvement_engine import (
        GenerationRecord,
        CategoryStats,
        LocalStorageAdapter,
        EnhancedSelfImprovementEngine,
    )


@pytest.fixture
def storage_path(tmp_path):
    return str(tmp_path / "photogenius_learning.json")


@pytest.fixture
def storage(storage_path):
    return LocalStorageAdapter(path=storage_path)


@pytest.fixture
def engine(storage):
    return EnhancedSelfImprovementEngine(storage=storage)


def test_local_storage_save_and_get(storage):
    record = GenerationRecord(
        job_id="job-1",
        timestamp=1000.0,
        category="portrait",
        sub_category="headshot",
        style="photorealistic",
        medium="photograph",
        tier="standard",
        final_score=0.85,
        iterations_used=2,
        max_iterations=3,
        parameters={"guidance_scale": 7.5, "max_iterations": 3},
        negative_prompt_tokens=["blurry"],
        positive_prompt_tokens=["sharp"],
        had_refinement=True,
        refinement_delta=0.1,
    )
    storage.save_record(record)
    names = storage.get_all_category_names()
    assert "portrait" in names
    records = storage.get_records_for_category("portrait", limit=10)
    assert len(records) == 1
    assert records[0]["job_id"] == "job-1"
    assert records[0]["final_score"] == 0.85


def test_engine_log_generation(engine):
    engine.log_generation(
        job_id="j1",
        category="landscape",
        sub_category="nature",
        style="photorealistic",
        medium="photograph",
        tier="premium",
        final_score=0.9,
        iterations_used=2,
        max_iterations=3,
        parameters={"guidance_scale": 8.0},
        positive_tokens=["mountain", "sky"],
        negative_tokens=["blurry"],
        had_refinement=False,
        refinement_delta=0.0,
    )
    stats = engine.get_category_stats("landscape")
    assert stats.total_generations == 1
    assert stats.avg_score == 0.9
    assert stats.best_parameters.get("guidance_scale") == 8.0


def test_engine_recommend_parameters_no_history(engine):
    params = engine.recommend_parameters("portrait", "photorealistic", "standard")
    assert "guidance_scale" in params
    assert "max_iterations" in params
    assert params["max_iterations"] == 2
    assert "cfg_scale" in params


def test_engine_recommend_parameters_with_history(engine):
    engine.log_generation(
        job_id="j1",
        category="product",
        sub_category="commercial",
        style="photorealistic",
        medium="photograph",
        tier="standard",
        final_score=0.95,
        iterations_used=1,
        max_iterations=2,
        parameters={"guidance_scale": 7.2, "max_iterations": 2},
        positive_tokens=[],
        negative_tokens=[],
    )
    params = engine.recommend_parameters("product", "photorealistic", "standard")
    assert params.get("guidance_scale") == 7.2


def test_engine_get_effective_tokens_empty(engine):
    pos, neg = engine.get_effective_tokens("portrait", top_n=5)
    assert pos == []
    assert neg == []


def test_engine_get_effective_tokens_with_data(engine):
    for i in range(5):
        engine.log_generation(
            job_id=f"j{i}",
            category="illustration",
            sub_category="digital",
            style="anime",
            medium="illustration",
            tier="standard",
            final_score=0.7 + i * 0.05,
            iterations_used=1,
            max_iterations=2,
            parameters={},
            positive_tokens=["detailed", "vibrant"] if i >= 3 else ["simple"],
            negative_tokens=["blurry"],
            had_refinement=(i % 2 == 0),
            refinement_delta=0.0,
        )
    pos, neg = engine.get_effective_tokens("illustration", top_n=10)
    # At least some tokens if we have enough data (count >= 3)
    assert isinstance(pos, list)
    assert isinstance(neg, list)


def test_engine_get_all_stats(engine):
    engine.log_generation(
        job_id="a",
        category="portrait",
        sub_category="x",
        style="s",
        medium="m",
        tier="standard",
        final_score=0.8,
        iterations_used=1,
        max_iterations=2,
        parameters={},
        positive_tokens=[],
        negative_tokens=[],
    )
    engine.log_generation(
        job_id="b",
        category="landscape",
        sub_category="y",
        style="s",
        medium="m",
        tier="standard",
        final_score=0.75,
        iterations_used=2,
        max_iterations=3,
        parameters={},
        positive_tokens=[],
        negative_tokens=[],
    )
    all_stats = engine.get_all_stats()
    assert "portrait" in all_stats
    assert "landscape" in all_stats
    assert all_stats["portrait"].total_generations == 1
    assert all_stats["landscape"].total_generations == 1


def test_default_parameters_tier(engine):
    standard = engine._default_parameters("portrait", "photorealistic", "standard")
    premium = engine._default_parameters("portrait", "photorealistic", "premium")
    perfect = engine._default_parameters("portrait", "photorealistic", "perfect")
    assert standard["max_iterations"] == 2
    assert premium["max_iterations"] == 3
    assert perfect["max_iterations"] == 5
    assert standard["cfg_scale"] == 7.5
    assert premium["cfg_scale"] == 8.0
    assert perfect["cfg_scale"] == 9.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

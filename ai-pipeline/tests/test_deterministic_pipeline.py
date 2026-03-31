"""
Tests for deterministic pipeline seed handling and repeatability.
Same prompt + constraints + loras => same seed => identical result.
"""

import pytest

try:
    from services.deterministic_pipeline import (
        DeterministicPipeline,
        DeterministicPipelineResult,
        _derive_seed,
    )
except ImportError:
    from ai_pipeline.services.deterministic_pipeline import (
        DeterministicPipeline,
        DeterministicPipelineResult,
        _derive_seed,
    )


def test_derive_seed_same_inputs_same_seed():
    """Same prompt + negative + constraints + loras => same seed."""
    a = _derive_seed("a red car", "", [{"rule": "x"}], [])
    b = _derive_seed("a red car", "", [{"rule": "x"}], [])
    assert a == b


def test_derive_seed_different_prompt_different_seed():
    """Different prompt => different seed."""
    s1 = _derive_seed("a red car", "", [], [])
    s2 = _derive_seed("a blue car", "", [], [])
    assert s1 != s2


def test_derive_seed_different_constraints_different_seed():
    """Different constraints => different seed."""
    s1 = _derive_seed("a red car", "", [{"rule": "a"}], [])
    s2 = _derive_seed("a red car", "", [{"rule": "b"}], [])
    assert s1 != s2


def test_derive_seed_different_loras_different_seed():
    """Different lora_names => different seed."""
    s1 = _derive_seed("portrait", "", [], ["lora1"])
    s2 = _derive_seed("portrait", "", [], ["lora2"])
    assert s1 != s2


def test_derive_seed_in_valid_range():
    """Derived seed is 32-bit unsigned."""
    s = _derive_seed("anything", "neg", [], ["a", "b"])
    assert isinstance(s, int)
    assert 0 <= s < 2**32


def test_run_uses_provided_seed():
    """When seed is provided, result.seed and generator receive that seed."""
    pipeline = DeterministicPipeline(max_refinement_iterations=1)
    # Mock compiler to avoid heavy deps and return minimal graph
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
    received = {}

    def fake_generator(prompt: str, negative: str, **kwargs):
        received["prompt"] = prompt
        received["negative"] = negative
        received["kwargs"] = dict(kwargs)
        return b"fake_image_bytes"

    pipeline.set_generator(fake_generator)
    result = pipeline.run(
        "a woman sitting on a chair",
        negative_prompt="blurry",
        seed=12345,
    )
    assert result.seed == 12345
    assert result.quality_metrics.get("seed") == 12345
    assert received["kwargs"].get("seed") == 12345


def test_run_deterministic_derives_seed():
    """When enable_deterministic=True and no seed, seed is derived and stored."""
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
    pipeline = DeterministicPipeline(max_refinement_iterations=1)
    pipeline.compiler = MockCompiler()
    pipeline.constraint_solver = None
    pipeline.occlusion_solver = None
    pipeline.physics_sim = None
    pipeline.validator = None
    pipeline.failure_memory_system = None
    received = []

    def fake_generator(prompt: str, negative: str, **kwargs):
        received.append(kwargs.get("seed"))
        return b"fake_image_bytes"

    pipeline.set_generator(fake_generator)
    result = pipeline.run(
        "a man with umbrella in rain",
        negative_prompt="",
        enable_deterministic=True,
    )
    assert result.seed is not None
    assert 0 <= result.seed < 2**32
    assert result.quality_metrics.get("seed") == result.seed
    assert len(received) == 1 and received[0] == result.seed


def test_run_same_prompt_same_seed_when_deterministic():
    """Two runs with same prompt and enable_deterministic=True yield same seed."""
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
    pipeline = DeterministicPipeline(max_refinement_iterations=1)
    pipeline.compiler = MockCompiler()
    pipeline.constraint_solver = None
    pipeline.occlusion_solver = None
    pipeline.physics_sim = None
    pipeline.validator = None
    pipeline.failure_memory_system = None
    pipeline.set_generator(lambda p, n, **kw: b"img")
    result1 = pipeline.run("two people at the beach", enable_deterministic=True)
    result2 = pipeline.run("two people at the beach", enable_deterministic=True)
    assert result1.seed == result2.seed


def test_run_random_seed_when_not_deterministic():
    """When enable_deterministic=False, seed is random (can differ between runs)."""
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
    pipeline = DeterministicPipeline(max_refinement_iterations=1)
    pipeline.compiler = MockCompiler()
    pipeline.constraint_solver = None
    pipeline.occlusion_solver = None
    pipeline.physics_sim = None
    pipeline.validator = None
    pipeline.failure_memory_system = None
    pipeline.set_generator(lambda p, n, **kw: b"img")
    result = pipeline.run("a cat on a sofa", enable_deterministic=False)
    assert result.seed is not None
    assert 0 <= result.seed < 2**32


def test_result_has_seed_field():
    """DeterministicPipelineResult has seed field for user access."""
    r = DeterministicPipelineResult(
        image=None,
        scene_graph={},
        layout={},
        camera={},
        seed=99999,
    )
    assert r.seed == 99999

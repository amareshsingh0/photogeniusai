"""
Tests for Prompt Enhancement v3 (Multi-Modal).
P1: Scene graph + physics + validation failures → enhanced prompt + negative.
Success metric: 90%+ first-try success when using v3 prompts.

Run from ai-pipeline root:
  python -m pytest tests/test_prompt_enhancement_v3.py -v -p no:asyncio
"""

import pytest

try:
    from services.prompt_enhancement_v3 import (
        scene_graph_to_positive,
        physics_to_material_descriptors,
        validation_failures_to_negative,
        build_negative_prompt_base,
        enhance_v3,
        enhance_v3_from_compiled,
        PromptEnhancementV3Result,
        BASE_NEGATIVE,
    )
except ImportError:
    from ai_pipeline.services.prompt_enhancement_v3 import (
        scene_graph_to_positive,
        physics_to_material_descriptors,
        validation_failures_to_negative,
        build_negative_prompt_base,
        enhance_v3,
        enhance_v3_from_compiled,
        PromptEnhancementV3Result,
        BASE_NEGATIVE,
    )

try:
    from services.scene_graph_compiler import SceneGraphCompiler
except ImportError:
    SceneGraphCompiler = None

try:
    from services.physics_micro_sim import PhysicsMicroSim, PhysicsSimResult
except ImportError:
    PhysicsMicroSim = None
    PhysicsSimResult = None

try:
    from services.tri_model_validator import TriModelConsensus, ValidationResult
except ImportError:
    TriModelConsensus = None
    ValidationResult = None


def test_scene_graph_to_positive_empty():
    """Empty scene graph returns minimal positive."""
    out = scene_graph_to_positive({})
    assert isinstance(out, str)
    assert "high quality" in out.lower() or out == ""


def test_scene_graph_to_positive_with_prompt_and_entities():
    """Scene graph with prompt and entities yields combined positive."""
    scene = {
        "prompt": "Family at beach",
        "entities": [
            {"id": "p1", "type": "person", "properties": {"role": "adult", "age": "adult"}},
            {"id": "p2", "type": "person", "properties": {"role": "child", "age": "child"}},
            {"id": "o1", "type": "object", "properties": {"name": "umbrella"}},
        ],
        "relations": [],
        "constraints": [],
    }
    out = scene_graph_to_positive(scene)
    assert "Family at beach" in out
    assert "adult" in out or "person" in out
    assert "umbrella" in out


def test_scene_graph_to_positive_with_relations_and_constraints():
    """Relations and constraints appear in positive prompt."""
    scene = {
        "prompt": "Under umbrella in rain",
        "entities": [
            {"id": "p1", "type": "person", "properties": {"age": "adult"}},
            {"id": "o1", "type": "object", "properties": {"name": "umbrella"}},
        ],
        "relations": [
            {"source": "p1", "target": "o1", "relation": "under", "constraints": ["umbrella_above_head"]},
            {"source": "p1", "target": "o1", "relation": "holding", "constraints": []},
        ],
        "constraints": [
            {"type": "visibility", "rule": "exactly_1_heads_fully_visible", "severity": "critical"},
            {"type": "visibility", "rule": "no_heads_occluded_by_objects", "severity": "critical"},
        ],
    }
    out = scene_graph_to_positive(scene)
    assert "Under umbrella in rain" in out
    assert "under" in out.lower() or "holding" in out.lower()
    assert "visible" in out.lower() or "heads" in out.lower()


def test_physics_to_material_descriptors_none():
    """None physics returns empty string."""
    out = physics_to_material_descriptors(None)
    assert out == ""


def test_physics_to_material_descriptors_with_wetness():
    """Physics result with wetness yields material descriptors."""
    if PhysicsSimResult is None:
        pytest.skip("PhysicsSimResult not available")
    # Build minimal PhysicsSimResult-like (duck-typed)
    class LightingState:
        def __init__(self, direction=(0, 0, 0), intensity=0.0, color_temp=0.0, softness=0.0, ambient=0.0):
            self.direction = direction
            self.intensity = intensity
            self.color_temp = color_temp
            self.softness = softness
            self.ambient = ambient

    class FakePhysicsResult:
        def __init__(self):
            self.materials = {}
            self.lighting = LightingState(softness=0.8)
            self.wetness_map_hint = {"global": 0.7, "ground": 0.9}
            self.gravity_hints = ["cloth_drapes_down", "hair_falls_naturally"]

    fake = FakePhysicsResult()
    out = physics_to_material_descriptors(fake)
    assert "wet" in out.lower() or "gravity" in out.lower() or "cloth" in out.lower() or "hair" in out.lower()


def test_validation_failures_to_negative_none():
    """None validation failures returns base negatives only."""
    out = validation_failures_to_negative(None)
    assert "blurry" in out or "bad anatomy" in out
    assert isinstance(out, str)


def test_validation_failures_to_negative_with_consensus():
    """TriModelConsensus with failed rules adds rule-specific negatives."""
    if TriModelConsensus is None or ValidationResult is None:
        pytest.skip("TriModelConsensus not available")
    consensus = TriModelConsensus(
        all_passed=False,
        results=[
            ValidationResult("visibility", "exactly_2_heads_fully_visible", False, 0.5, {}),
            ValidationResult("anatomy", "each_person_has_2_arms_2_legs", False, 0.4, {}),
        ],
        limb_violations=["extra arm detected"],
        occlusion_detected=["head_count: expected 2, got 1"],
    )
    out = validation_failures_to_negative(consensus)
    assert "head" in out.lower() or "arm" in out.lower() or "blurry" in out.lower()


def test_build_negative_prompt_base():
    """Base negative includes anatomy and quality terms."""
    out = build_negative_prompt_base(has_people=True, multi_person=False)
    assert "blurry" in out or "bad anatomy" in out
    out_multi = build_negative_prompt_base(has_people=True, multi_person=True)
    assert "merged" in out_multi.lower() or "body" in out_multi.lower()


def test_enhance_v3_no_scene_graph():
    """enhance_v3 with only user_prompt returns prompt + base negative."""
    r = enhance_v3("A cat on a sofa", scene_graph=None, physics_result=None, validation_failures=None)
    assert isinstance(r, PromptEnhancementV3Result)
    assert r.enhanced_prompt == "A cat on a sofa"
    assert r.first_try_ready is True
    assert "blurry" in r.negative_prompt or "low quality" in r.negative_prompt


def test_enhance_v3_with_scene_graph():
    """enhance_v3 with scene_graph enriches positive from entities/relations/constraints."""
    scene = {
        "prompt": "Mother with 2 children under umbrella",
        "entities": [
            {"id": "p1", "type": "person", "properties": {"role": "mother", "age": "adult"}},
            {"id": "p2", "type": "person", "properties": {"role": "child", "age": "child"}},
            {"id": "p3", "type": "person", "properties": {"role": "child", "age": "child"}},
            {"id": "o1", "type": "object", "properties": {"name": "umbrella"}},
        ],
        "relations": [{"source": "p1", "target": "o1", "relation": "under", "constraints": ["umbrella_above_head"]}],
        "constraints": [{"type": "visibility", "rule": "no_heads_occluded_by_objects", "severity": "critical"}],
    }
    r = enhance_v3("Mother with 2 children under umbrella", scene_graph=scene)
    assert "Mother with 2 children under umbrella" in r.enhanced_prompt
    assert ("2" in r.enhanced_prompt and "child" in r.enhanced_prompt) or "umbrella" in r.enhanced_prompt
    assert r.first_try_ready is True


def test_enhance_v3_with_validation_failures():
    """When validation_failures is provided, first_try_ready is False and negative includes failure terms."""
    if TriModelConsensus is None or ValidationResult is None:
        pytest.skip("TriModelConsensus not available")
    consensus = TriModelConsensus(
        all_passed=False,
        results=[ValidationResult("visibility", "exactly_1_heads_fully_visible", False, 0.5, {})],
    )
    r = enhance_v3("One person", scene_graph=None, validation_failures=consensus)
    assert r.first_try_ready is False
    assert len(r.negative_prompt) >= len(build_negative_prompt_base())


def test_enhance_v3_from_compiled_integration():
    """enhance_v3_from_compiled with compiler output yields rich positive and base negative."""
    if SceneGraphCompiler is None:
        pytest.skip("SceneGraphCompiler not available")
    compiler = SceneGraphCompiler(use_spacy=False)
    compiled = compiler.compile("Mother with 2 children under umbrella in rain")
    r = enhance_v3_from_compiled(compiled, physics_result=None, validation_failures=None)
    assert "Mother with 2 children under umbrella in rain" in r.enhanced_prompt
    assert "umbrella" in r.enhanced_prompt
    assert r.first_try_ready is True
    assert r.sources.get("scene_graph") is True


def test_enhance_v3_from_compiled_with_physics():
    """enhance_v3_from_compiled with physics_result appends material descriptors."""
    if SceneGraphCompiler is None:
        pytest.skip("SceneGraphCompiler not available")
    if PhysicsMicroSim is None:
        pytest.skip("PhysicsMicroSim not available")
    compiler = SceneGraphCompiler(use_spacy=False)
    compiled = compiler.compile("Family under umbrella in rain")
    physics = PhysicsMicroSim()
    layout_entities = compiled.get("layout", {}).get("entities", [])
    weather_ent = next((e for e in compiled.get("entities", []) if getattr(e, "type", None) == "weather"), None)
    weather = getattr(weather_ent, "properties", None) if weather_ent else None
    physics_result = physics.run(layout_entities, weather=weather)
    r = enhance_v3_from_compiled(compiled, physics_result=physics_result, validation_failures=None)
    assert r.sources.get("physics") is True
    assert "wet" in r.enhanced_prompt.lower() or "rain" in r.enhanced_prompt.lower() or "cloth" in r.enhanced_prompt.lower() or "lighting" in r.enhanced_prompt.lower()


def test_first_try_ready_metric():
    """first_try_ready True when no validation failures; aim for 90%+ first-try success with v3."""
    r1 = enhance_v3("Couple at beach", scene_graph=None, validation_failures=None)
    assert r1.first_try_ready is True
    if TriModelConsensus is not None and ValidationResult is not None:
        consensus = TriModelConsensus(all_passed=False, results=[ValidationResult("anatomy", "arms_2_legs", False, 0.5, {})])
        r2 = enhance_v3("Two people", validation_failures=consensus)
        assert r2.first_try_ready is False

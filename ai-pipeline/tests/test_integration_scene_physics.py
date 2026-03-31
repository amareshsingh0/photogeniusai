"""
Integration tests: Scene Graph Compiler → Physics Simulation
Full pipeline: prompt → scene graph → physics → output.
"""

import pytest

try:
    from services.scene_graph_compiler import SceneGraphCompiler
    from services.physics_micro_simulation import (
        PhysicsMicroSimulation,
        create_rainy_environment,
        create_fantasy_environment,
    )
except ImportError:
    from ai_pipeline.services.scene_graph_compiler import SceneGraphCompiler
    from ai_pipeline.services.physics_micro_simulation import (
        PhysicsMicroSimulation,
        create_rainy_environment,
        create_fantasy_environment,
    )


def _get_compiler():
    """Scene graph compiler; disable spacy if not installed."""
    try:
        return SceneGraphCompiler(use_spacy=True)
    except Exception:
        return SceneGraphCompiler(use_spacy=False)


def test_full_pipeline_rainy_scene():
    """Test complete pipeline: prompt → scene graph → physics → output."""

    prompt = (
        "Mother with 3 children walking under orange umbrella in heavy rain at night"
    )

    compiler = _get_compiler()
    scene = compiler.compile(prompt)

    # Verify scene graph
    quality = scene.get("quality_requirements") or {}
    person_count = quality.get("person_count_exact", 0)
    assert (
        person_count == 4
    ), f"Expected 4 people (1 mother + 3 children), got {person_count}"

    layout_entities = scene.get("layout", {}).get("entities", [])
    assert (
        len(layout_entities) >= 4
    ), f"Layout should have at least 4 entities (people), got {len(layout_entities)}"

    env = create_rainy_environment(intensity=0.9)
    env.lighting = "night"

    engine = PhysicsMicroSimulation()
    result = engine.simulate(scene, env)

    # Verify outputs
    states = result.get("material_states") or {}
    assert (
        len(states) >= 12
    ), f"Expected at least 12 material states (4 people × 3+ each), got {len(states)}"

    protection_zones = result.get("protection_zones") or []
    assert (
        len(protection_zones) >= 1
    ), f"Expected at least 1 protection zone (umbrella), got {len(protection_zones)}"

    visual_effects = result.get("visual_effects") or []
    assert (
        len(visual_effects) >= 3
    ), f"Expected multiple visual effects, got {len(visual_effects)}"

    prompt_mods = result.get("prompt_modifiers") or ""
    assert "rain" in prompt_mods.lower(), "Prompt modifiers should mention rain"
    assert "wet" in prompt_mods.lower(), "Prompt modifiers should mention wetness"
    assert "umbrella" in prompt_mods.lower(), "Prompt modifiers should mention umbrella"
    assert (
        "night" in prompt_mods.lower()
        or "dark" in prompt_mods.lower()
        or "artificial" in prompt_mods.lower()
    ), "Prompt modifiers should mention night/dark"


def test_full_pipeline_fantasy_scene():
    """Test pipeline with fantasy elements."""

    prompt = (
        "Dragon with iridescent scales flying over a glowing crystal city at twilight"
    )

    compiler = _get_compiler()
    scene = compiler.compile(prompt)

    env = create_fantasy_environment()

    engine = PhysicsMicroSimulation()
    result = engine.simulate(scene, env)

    states = result.get("material_states") or {}
    magical_materials = [k for k, v in states.items() if v.material_type == "magical"]

    assert len(magical_materials) > 0, "Should have magical materials"

    prompt_mods = result.get("prompt_modifiers") or ""
    assert (
        "glow" in prompt_mods.lower()
        or "ethereal" in prompt_mods.lower()
        or "magical" in prompt_mods.lower()
    ), "Prompt modifiers should mention glow/ethereal/magical"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

"""
Tests for Physics Micro-Simulation Engine.
State-based material simulation: rain/snow, lighting, prompt modifiers.
"""

import pytest

try:
    from services.physics_micro_simulation import (
        MaterialState,
        EnvironmentalCondition,
        PhysicsMicroSimulation,
    )
except ImportError:
    from ai_pipeline.services.physics_micro_simulation import (
        MaterialState,
        EnvironmentalCondition,
        PhysicsMicroSimulation,
    )


def test_material_state_copy():
    """MaterialState.copy() returns a deep copy that can be mutated."""
    sim = PhysicsMicroSimulation()
    cotton = sim.MATERIAL_DB["cotton"].copy()
    assert cotton.material_type == "fabric"
    assert cotton.wetness_level == 0.0
    cotton.wetness_level = 0.5
    assert sim.MATERIAL_DB["cotton"].wetness_level == 0.0


def test_simulate_rain_prompt_modifiers():
    """Rain simulation produces prompt modifiers and visual effects."""
    sim = PhysicsMicroSimulation()
    scene_graph = {
        "entities": [
            {"id": "person_0", "type": "person", "properties": {}},
            {"id": "umbrella_1", "type": "object", "properties": {"name": "umbrella"}},
        ],
        "layout": {"entities": []},
    }
    env = EnvironmentalCondition(
        weather="rain",
        intensity=0.8,
        temperature=18.0,
        wind_speed=2.0,
        lighting="overcast",
    )
    out = sim.simulate(scene_graph, env)
    assert "prompt_modifiers" in out
    assert "rain" in out["prompt_modifiers"].lower()
    assert "visual_effects" in out
    assert "material_states" in out
    assert "ground" in out["material_states"]
    assert out["material_states"]["ground"].wetness_level > 0.5


def test_simulate_snow():
    """Snow simulation applies different effects than rain."""
    sim = PhysicsMicroSimulation()
    scene_graph = {
        "entities": [{"id": "person_0", "type": "person", "properties": {}}],
        "layout": {"entities": []},
    }
    env = EnvironmentalCondition(
        weather="snow", intensity=0.7, temperature=-2.0, wind_speed=1.0, lighting="day"
    )
    out = sim.simulate(scene_graph, env)
    assert (
        "snow" in out["prompt_modifiers"].lower()
        or "reflectivity" in str(out["lighting_effects"]).lower()
    )
    assert "material_states" in out


def test_run_pipeline_compatible():
    """run(entities, weather) and to_prompt_suffix(result) match pipeline API."""
    sim = PhysicsMicroSimulation()
    entities = [
        {"id": "p1", "type": "person"},
        {"id": "umbrella_1", "type": "object", "properties": {"name": "umbrella"}},
    ]
    result = sim.run(entities, weather={"condition": "rain", "intensity": 0.7})
    assert "prompt_modifiers" in result
    assert "gravity_hints" in result
    suffix = sim.to_prompt_suffix(result)
    assert isinstance(suffix, str)
    assert len(suffix) > 0


def test_lighting_effects():
    """Lighting effects vary by time of day and weather."""
    sim = PhysicsMicroSimulation()
    scene_graph = {"entities": [], "layout": {"entities": []}}
    env_night = EnvironmentalCondition(
        weather="sunny",
        intensity=0.0,
        temperature=20.0,
        wind_speed=0.0,
        lighting="night",
    )
    out_night = sim.simulate(scene_graph, env_night)
    env_golden = EnvironmentalCondition(
        weather="sunny",
        intensity=0.0,
        temperature=20.0,
        wind_speed=0.0,
        lighting="golden_hour",
    )
    out_golden = sim.simulate(scene_graph, env_golden)
    assert (
        out_night["lighting_effects"]["ambient_intensity"]
        < out_golden["lighting_effects"]["ambient_intensity"]
    )
    assert (
        out_night["lighting_effects"]["color_temperature"]
        != out_golden["lighting_effects"]["color_temperature"]
    )


def test_control_signals_structure():
    """Control signals contain wetness_map for ControlNet integration."""
    sim = PhysicsMicroSimulation()
    scene_graph = {
        "entities": [{"id": "person_0", "type": "person", "properties": {}}],
        "layout": {"entities": []},
    }
    env = EnvironmentalCondition(
        weather="rain", intensity=0.6, temperature=20.0, wind_speed=0.0, lighting="day"
    )
    out = sim.simulate(scene_graph, env)
    cs = out["control_signals"]
    assert "wetness_map" in cs
    assert "specular_map" in cs
    assert "shadow_map" in cs

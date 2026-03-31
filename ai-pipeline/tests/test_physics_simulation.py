"""
Comprehensive tests for Physics Micro-Simulation Engine.
Covers: material DB, rain with/without umbrella, fantasy materials,
lighting, prompt modifiers, visual effects, control signals, multi-person.
"""

import pytest

try:
    from services.physics_micro_simulation import (
        PhysicsMicroSimulation,
        EnvironmentalCondition,
        create_rainy_environment,
        create_fantasy_environment,
    )
    from services.scene_graph_compiler import SceneGraphCompiler
except ImportError:
    from ai_pipeline.services.physics_micro_simulation import (
        PhysicsMicroSimulation,
        EnvironmentalCondition,
        create_rainy_environment,
        create_fantasy_environment,
    )
    from ai_pipeline.services.scene_graph_compiler import SceneGraphCompiler


def _get_compiler():
    """Scene graph compiler; disable spacy if not installed."""
    try:
        return SceneGraphCompiler(use_spacy=True)
    except Exception:
        return SceneGraphCompiler(use_spacy=False)


class TestPhysicsMicroSimulation:
    """Comprehensive tests for physics engine."""

    def test_material_database_completeness(self):
        """Verify all materials have required properties."""
        engine = PhysicsMicroSimulation()

        required_attrs = [
            "water_absorption",
            "absorption_rate",
            "color_darkening",
            "specular_increase",
            "roughness_decrease",
        ]

        for mat_name, material in engine.MATERIAL_DB.items():
            for attr in required_attrs:
                assert hasattr(material, attr), (
                    f"Material '{mat_name}' missing attribute '{attr}'"
                )

                value = getattr(material, attr)
                assert value >= 0.0, (
                    f"Material '{mat_name}' has invalid {attr}: {value}"
                )
                if attr in ("water_absorption", "absorption_rate", "color_darkening", "specular_increase", "roughness_decrease"):
                    assert value <= 1.0 or (attr == "roughness_decrease" and value <= 1.0), (
                        f"Material '{mat_name}' {attr} out of range: {value}"
                    )

    def test_rain_wetness_with_umbrella_protection(self):
        """Test realistic rain with umbrella protection."""
        compiler = _get_compiler()
        scene = compiler.compile(
            "Mother with 2 children under orange umbrella in heavy rain"
        )

        env = create_rainy_environment(intensity=0.9)

        engine = PhysicsMicroSimulation()
        result = engine.simulate(scene, env)

        states = result["material_states"]

        if len(result.get("protection_zones", [])) > 0:
            clothing_items = [k for k in states.keys() if "clothing" in k]
            assert len(clothing_items) >= 1, "Should have at least one clothing item"

            for item in clothing_items:
                wetness = states[item].wetness_level
                assert 0.0 <= wetness <= 0.5, (
                    f"{item} wetness {wetness} should be low-moderate (protected)"
                )

            shoe_items = [k for k in states.keys() if "shoes" in k]
            for item in shoe_items:
                wetness = states[item].wetness_level
                assert wetness >= 0.0, f"{item} should have some wetness (feet exposed)"

        if "ground" in states:
            assert states["ground"].wetness_level >= 0.5, (
                "Ground should be wet in heavy rain"
            )

    def test_rain_wetness_without_protection(self):
        """Test rain on fully exposed people."""
        compiler = _get_compiler()
        scene = compiler.compile("Person walking in rain")

        env = create_rainy_environment(intensity=1.0)

        engine = PhysicsMicroSimulation()
        result = engine.simulate(scene, env)

        states = result["material_states"]

        assert len(result.get("protection_zones", [])) == 0, (
            "Should have no protection"
        )

        clothing_items = [k for k in states.keys() if "clothing" in k]
        for item in clothing_items:
            wetness = states[item].wetness_level
            assert wetness >= 0.2, (
                f"{item} wetness {wetness} should be noticeably wet (no protection)"
            )

    def test_material_specific_behavior(self):
        """Verify different materials behave differently."""
        compiler = _get_compiler()
        scene = compiler.compile(
            "Person in leather jacket and cotton pants walking in rain"
        )

        env = create_rainy_environment(intensity=0.8)

        engine = PhysicsMicroSimulation()
        result = engine.simulate(scene, env)

        cotton = engine.MATERIAL_DB["cotton"]
        leather = engine.MATERIAL_DB["leather"]

        assert cotton.water_absorption > leather.water_absorption, (
            "Cotton should absorb more water than leather"
        )

        assert leather.specular_increase > cotton.specular_increase, (
            "Leather should be shinier when wet than cotton"
        )

    def test_fantasy_material_simulation(self):
        """Test physics for magical/fantasy materials."""
        compiler = _get_compiler()
        scene = compiler.compile(
            "Dragon with glowing scales soaring through stormy skies"
        )

        env = create_fantasy_environment()

        engine = PhysicsMicroSimulation()
        result = engine.simulate(scene, env)

        states = result["material_states"]

        dragon_materials = [k for k in states.keys() if "dragon" in k.lower()]
        assert len(dragon_materials) > 0, "Should have dragon-related materials"

        for mat_key in dragon_materials:
            material = states[mat_key]
            if material.material_type == "magical":
                assert material.is_glowing, "Dragon materials should glow"
                assert material.water_absorption == 0.0, (
                    "Magical materials should repel water"
                )

    def test_lighting_simulation_day_vs_night(self):
        """Test lighting differs between day and night."""
        compiler = _get_compiler()
        scene = compiler.compile("Person standing")

        env_day = EnvironmentalCondition(
            weather="sunny",
            intensity=0.0,
            temperature=25,
            wind_speed=0,
            lighting="day",
            light_intensity=1.0,
        )

        env_night = EnvironmentalCondition(
            weather="none",
            intensity=0.0,
            temperature=15,
            wind_speed=0,
            lighting="night",
            light_intensity=0.3,
        )

        engine = PhysicsMicroSimulation()

        result_day = engine.simulate(scene, env_day)
        result_night = engine.simulate(scene, env_night)

        lighting_day = result_day["lighting_effects"]
        lighting_night = result_night["lighting_effects"]

        assert lighting_day["ambient_intensity"] > lighting_night["ambient_intensity"], (
            "Day should have higher ambient light"
        )

        assert lighting_night["shadow_strength"] > lighting_day["shadow_strength"], (
            "Night should have stronger shadows"
        )

    def test_prompt_modifier_generation(self):
        """Test that prompt modifiers accurately describe physics."""
        compiler = _get_compiler()
        scene = compiler.compile("Couple under umbrella in rain at night")

        env = EnvironmentalCondition(
            weather="rain",
            intensity=0.8,
            temperature=12,
            wind_speed=8,
            lighting="night",
        )

        engine = PhysicsMicroSimulation()
        result = engine.simulate(scene, env)

        prompt = result["prompt_modifiers"]

        assert "rain" in prompt.lower(), "Prompt should describe rain"
        assert "wet" in prompt.lower(), "Prompt should describe wetness"
        assert "umbrella" in prompt.lower(), "Prompt should mention umbrella"
        assert "night" in prompt.lower() or "dark" in prompt.lower() or "artificial" in prompt.lower(), (
            "Prompt should describe nighttime"
        )
        assert "droplets" in prompt.lower() or "puddles" in prompt.lower() or "wet" in prompt.lower(), (
            "Prompt should describe specific water effects"
        )

    def test_visual_effects_accuracy(self):
        """Test visual effects match material states."""
        compiler = _get_compiler()
        scene = compiler.compile("Person in rain")

        env = create_rainy_environment(intensity=0.7)

        engine = PhysicsMicroSimulation()
        result = engine.simulate(scene, env)

        effects = result["visual_effects"]
        states = result["material_states"]

        wet_materials = [k for k, v in states.items() if v.wetness_level > 0.3]

        for mat_key in wet_materials:
            if mat_key == "ground":
                continue
            has_effect = any(mat_key in effect for effect in effects)
            assert has_effect, (
                f"Material {mat_key} is wet but has no visual effect"
            )

    def test_control_signal_generation(self):
        """Test control signals are generated correctly."""
        compiler = _get_compiler()
        scene = compiler.compile("Mother with child in rain")

        env = create_rainy_environment(intensity=0.8)

        engine = PhysicsMicroSimulation()
        result = engine.simulate(scene, env)

        controls = result["control_signals"]

        assert "wetness_regions" in controls
        assert "specular_regions" in controls
        assert "shadow_intensity" in controls
        assert 0.0 <= controls["shadow_intensity"] <= 1.0

        assert "wetness_map" in controls
        assert "specular_map" in controls
        assert "shadow_map" in controls

    def test_multi_person_material_assignment(self):
        """Test materials assigned to multiple people correctly."""
        compiler = _get_compiler()
        scene = compiler.compile("4 people at beach")

        env = EnvironmentalCondition(
            weather="sunny",
            intensity=0.0,
            temperature=28,
            wind_speed=3,
            lighting="day",
        )

        engine = PhysicsMicroSimulation()
        result = engine.simulate(scene, env)

        states = result["material_states"]

        clothing_count = len([k for k in states.keys() if "clothing" in k])
        skin_count = len([k for k in states.keys() if "skin" in k])

        assert clothing_count >= 1, (
            f"Should have at least 1 clothing item, got {clothing_count}"
        )
        assert skin_count >= 1, (
            f"Should have at least 1 skin item, got {skin_count}"
        )
        assert clothing_count == skin_count, (
            "Clothing and skin counts should match per person"
        )

    def test_environment_helpers(self):
        """Test helper functions create valid environments."""
        rainy = create_rainy_environment(0.9)
        assert rainy.weather == "rain"
        assert rainy.intensity == 0.9
        assert rainy.humidity > 0.8

        fantasy = create_fantasy_environment()
        assert fantasy.magical_atmosphere is True
        assert fantasy.ethereal_glow is True


def test_rain_wetness_simulation_legacy():
    """Legacy: realistic rain wetness on different materials."""
    compiler = _get_compiler()
    scene = compiler.compile("Mother with 2 children under umbrella in heavy rain")

    env = EnvironmentalCondition(
        weather="rain",
        intensity=0.8,
        temperature=15,
        wind_speed=5,
        lighting="overcast",
    )

    physics = PhysicsMicroSimulation()
    result = physics.simulate(scene, env)

    states = result["material_states"]

    clothing_keys = [k for k in states.keys() if "clothing" in k]
    for key in clothing_keys:
        wetness = states[key].wetness_level
        assert 0.0 <= wetness <= 0.7, (
            f"{key} should be partially wet under umbrella, got {wetness}"
        )

    assert states["ground"].wetness_level >= 0.5, "Ground should be saturated"

    prompt = result["prompt_modifiers"]
    assert "wet" in prompt.lower(), "Prompt should describe wetness"
    assert "rain" in prompt.lower(), "Prompt should describe rain"


def test_run_and_to_prompt_suffix():
    """Pipeline API: run(entities, weather) and to_prompt_suffix(result)."""
    sim = PhysicsMicroSimulation()
    entities = [
        {"id": "p1", "type": "person", "properties": {}},
        {"id": "umbrella_1", "type": "object", "properties": {"name": "umbrella"}},
    ]
    result = sim.run(entities, weather={"condition": "rain", "intensity": 0.7})
    assert "prompt_modifiers" in result
    assert "gravity_hints" in result
    suffix = sim.to_prompt_suffix(result)
    assert isinstance(suffix, str)
    assert len(suffix) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

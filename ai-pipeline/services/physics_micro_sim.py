"""
Physics Micro-Simulation for PhotoGenius AI.
Material-aware wetness, lighting, gravity for physics-perfect images.
P0: Deterministic image generation — Task 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class MaterialState:
    """Material state for one entity or region."""

    wetness: float  # 0–1
    reflectivity: float
    roughness: float
    subsurface: float  # for skin/fabric


@dataclass
class LightingState:
    """Global or local lighting."""

    direction: tuple  # (x, y, z) or azimuth, elevation
    intensity: float
    color_temp: float  # Kelvin
    softness: float  # 0 sharp – 1 soft
    ambient: float


@dataclass
class PhysicsSimResult:
    """Result of micro-sim: parameters for diffusion/ControlNet."""

    materials: Dict[str, MaterialState]  # entity_id or "global" -> state
    lighting: LightingState
    wetness_map_hint: Optional[Dict[str, float]]  # region -> wetness
    gravity_hints: List[str]  # e.g. ["cloth_drapes_down", "hair_falls"]


class PhysicsMicroSim:
    """
    Lightweight physics micro-sim for image generation:
    - Rain → wetness on skin, fabric, pavement; reflections.
    - Gravity → cloth drape, hair fall.
    - Lighting → direction, softness, color from weather/time.
    """

    def __init__(self):
        self.weather_materials = {
            "rain": {
                "skin_wetness": 0.6,
                "fabric_wetness": 0.7,
                "ground_wetness": 0.9,
                "reflectivity_ground": 0.4,
            },
            "snow": {
                "skin_wetness": 0.0,
                "fabric_wetness": 0.2,
                "ground_wetness": 0.0,
                "reflectivity_ground": 0.8,
            },
            "sunny": {
                "skin_wetness": 0.0,
                "fabric_wetness": 0.0,
                "ground_wetness": 0.0,
                "reflectivity_ground": 0.1,
            },
            "night": {
                "skin_wetness": 0.0,
                "fabric_wetness": 0.0,
                "ground_wetness": 0.0,
                "reflectivity_ground": 0.05,
            },
        }

    def run(
        self,
        entities: List[Dict[str, Any]],
        weather: Optional[Dict[str, Any]] = None,
        time_of_day: str = "day",
    ) -> PhysicsSimResult:
        """
        Run micro-sim: compute material states and lighting from scene.

        entities: from Scene Graph (layout.entities or compiler entities).
        weather: e.g. {"condition": "rain", "wetness": True}.
        time_of_day: "day" | "night" | "golden_hour" | "overcast".
        """
        condition = "sunny"
        if weather:
            condition = weather.get("condition", "sunny")
        mat_params = self.weather_materials.get(
            condition, self.weather_materials["sunny"]
        )

        materials: Dict[str, MaterialState] = {}
        wetness_hint: Dict[str, float] = {}

        for ent in entities:
            eid = ent.get("id", "global")
            etype = ent.get("type", "person")
            if etype == "person":
                materials[eid] = MaterialState(
                    wetness=mat_params["skin_wetness"],
                    reflectivity=0.3 + 0.2 * mat_params["skin_wetness"],
                    roughness=0.4,
                    subsurface=0.5,
                )
                wetness_hint[eid] = mat_params["skin_wetness"]
            elif etype == "umbrella":
                materials[eid] = MaterialState(
                    wetness=mat_params["fabric_wetness"],
                    reflectivity=0.2,
                    roughness=0.6,
                    subsurface=0.1,
                )

        materials["ground"] = MaterialState(
            wetness=mat_params["ground_wetness"],
            reflectivity=mat_params["reflectivity_ground"],
            roughness=0.8,
            subsurface=0.0,
        )
        wetness_hint["ground"] = mat_params["ground_wetness"]

        # Lighting from weather + time
        if condition == "rain" or condition == "overcast":
            lighting = LightingState(
                direction=(0.2, -0.5, 0.8),
                intensity=0.6,
                color_temp=6500.0,
                softness=0.8,
                ambient=0.5,
            )
        elif time_of_day == "night":
            lighting = LightingState(
                direction=(-0.3, -0.2, 0.9),
                intensity=0.3,
                color_temp=4000.0,
                softness=0.6,
                ambient=0.3,
            )
        elif time_of_day == "golden_hour":
            lighting = LightingState(
                direction=(0.6, -0.4, 0.7),
                intensity=0.9,
                color_temp=3500.0,
                softness=0.7,
                ambient=0.4,
            )
        else:
            lighting = LightingState(
                direction=(0.3, -0.6, 0.7),
                intensity=0.85,
                color_temp=5500.0,
                softness=0.5,
                ambient=0.45,
            )

        gravity_hints: List[str] = []
        if condition == "rain":
            gravity_hints.extend(
                [
                    "cloth_drapes_down",
                    "hair_falls_naturally",
                    "wet_fabric_clings",
                    "water_droplets_fall",
                ]
            )
        gravity_hints.append("realistic_gravity")

        return PhysicsSimResult(
            materials=materials,
            lighting=lighting,
            wetness_map_hint=wetness_hint,
            gravity_hints=gravity_hints,
        )

    def to_prompt_suffix(self, result: PhysicsSimResult) -> str:
        """Convert sim result to prompt suffix for diffusion."""
        parts = []
        if result.wetness_map_hint:
            avg_wet = sum(result.wetness_map_hint.values()) / len(
                result.wetness_map_hint
            )
            if avg_wet > 0.3:
                parts.append("realistic wetness")
                parts.append("water reflections")
                parts.append("wet skin and fabric")
        parts.extend(result.gravity_hints)
        if result.lighting.softness > 0.6:
            parts.append("soft diffused lighting")
        return ", ".join(parts) if parts else "physically accurate materials"

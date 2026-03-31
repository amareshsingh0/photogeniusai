"""
Physics Micro-Simulation Engine for PhotoGenius AI.

Simulates material properties under environmental conditions with state-based precision.
Supports all image categories: realistic, fantasy, imaginative, living, non-living.

Architecture:
1. Material Database: Physical properties of materials
2. Environmental Simulator: Weather/lighting effects
3. State Computer: Calculate material states under conditions
4. Output Generator: Convert states to prompts/controls
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class MaterialState:
    """
    Physical state of a material.

    Attributes describe how material responds to environmental conditions.
    """

    material_type: str  # 'fabric', 'skin', 'metal', 'glass', 'stone', 'organic', 'magical'

    # Absorption properties (for liquids like rain)
    water_absorption: float  # 0.0 = waterproof, 1.0 = fully absorbent (sponge-like)
    absorption_rate: float  # Speed of absorption (0.0 = instant repel, 1.0 = instant soak)

    # Visual changes when wet
    color_darkening: float  # 0.0-1.0 (how much darker when saturated)
    specular_increase: float  # Shininess/gloss increase (0.0 = matte, 1.0 = mirror)
    roughness_decrease: float  # Surface smoothness increase

    # Physical behavior changes
    weight_multiplier: float  # Weight increase when saturated (1.0 = no change, 2.0 = doubles)
    stiffness_change: float  # -1.0 (much softer) to +1.0 (much stiffer)
    transparency_change: float  # For fabrics (0.0 = opaque, 1.0 = see-through when wet)

    # Thermal properties
    thermal_conductivity: float = 0.5  # Heat transfer (0.0 = insulator, 1.0 = conductor)
    reflectivity: float = 0.1  # Light reflection (0.0 = absorbs all, 1.0 = mirror)

    # Current dynamic state
    wetness_level: float = 0.0  # Current saturation (0.0 = dry, 1.0 = dripping wet)
    temperature: float = 20.0  # Celsius
    is_glowing: bool = False  # For magical materials
    glow_intensity: float = 0.0  # 0.0-1.0

    def __post_init__(self) -> None:
        """Validate ranges."""
        assert 0.0 <= self.water_absorption <= 1.0
        assert 0.0 <= self.absorption_rate <= 1.0
        assert 0.0 <= self.wetness_level <= 1.0

    def copy(self) -> "MaterialState":
        """Return a deep copy (safe to mutate). Pipeline and tests use this."""
        return copy.deepcopy(self)


@dataclass
class EnvironmentalCondition:
    """Environmental effects acting on the scene."""

    weather: str  # 'rain', 'snow', 'sunny', 'fog', 'storm', 'none'
    intensity: float  # 0.0-1.0 (light drizzle vs torrential rain)
    temperature: float  # Celsius
    wind_speed: float  # m/s
    humidity: float = 0.5  # 0.0-1.0

    # Lighting
    lighting: str = "day"  # 'day', 'night', 'golden_hour', 'overcast', 'twilight'
    light_intensity: float = 1.0  # 0.0 (pitch black) to 1.0 (bright sunlight)
    light_temperature: int = 5500  # Kelvin (warm to cool)

    # Special effects (for imaginative/fantasy)
    magical_atmosphere: bool = False
    ethereal_glow: bool = False


@dataclass
class ProtectionZone:
    """Area protected from environmental effects (e.g., under umbrella)."""

    zone_type: str  # 'umbrella', 'roof', 'tree_canopy'
    center: Tuple[int, int]  # (x, y) pixel coordinates
    radius: float  # Pixels
    protection_factor: float  # 0.0 (no protection) to 1.0 (full protection)
    covered_entities: List[str] = field(default_factory=list)


class PhysicsMicroSimulation:
    """
    Simulate physical material behavior under environmental conditions.

    Process:
    1. Load material database
    2. Assign materials to scene entities
    3. Simulate environmental effects (rain, lighting, etc.)
    4. Compute material state changes
    5. Generate outputs (prompts, control signals)
    """

    # ========== MATERIAL DATABASE ==========
    MATERIAL_DB: Dict[str, MaterialState] = {}

    def __init__(self) -> None:
        self.scene_graph: Optional[Dict[str, Any]] = None
        self.environment: Optional[EnvironmentalCondition] = None
        self.material_states: Dict[str, MaterialState] = {}
        self.protection_zones: List[ProtectionZone] = []
        if not PhysicsMicroSimulation.MATERIAL_DB:
            PhysicsMicroSimulation._init_material_db()

    @classmethod
    def _init_material_db(cls) -> None:
        """Initialize MATERIAL_DB once (avoids dataclass default mutable)."""
        cls.MATERIAL_DB = {
            "cotton": MaterialState(
                material_type="fabric",
                water_absorption=0.85,
                absorption_rate=0.7,
                color_darkening=0.35,
                specular_increase=0.2,
                roughness_decrease=0.15,
                weight_multiplier=1.8,
                stiffness_change=-0.4,
                transparency_change=0.1,
                thermal_conductivity=0.3,
                reflectivity=0.05,
            ),
            "denim": MaterialState(
                material_type="fabric",
                water_absorption=0.75,
                absorption_rate=0.5,
                color_darkening=0.40,
                specular_increase=0.15,
                roughness_decrease=0.10,
                weight_multiplier=1.6,
                stiffness_change=-0.3,
                transparency_change=0.0,
                thermal_conductivity=0.4,
                reflectivity=0.03,
            ),
            "leather": MaterialState(
                material_type="fabric",
                water_absorption=0.30,
                absorption_rate=0.3,
                color_darkening=0.25,
                specular_increase=0.5,
                roughness_decrease=0.3,
                weight_multiplier=1.2,
                stiffness_change=-0.1,
                transparency_change=0.0,
                thermal_conductivity=0.2,
                reflectivity=0.4,
            ),
            "silk": MaterialState(
                material_type="fabric",
                water_absorption=0.65,
                absorption_rate=0.6,
                color_darkening=0.45,
                specular_increase=0.6,
                roughness_decrease=0.5,
                weight_multiplier=1.5,
                stiffness_change=-0.5,
                transparency_change=0.3,
                thermal_conductivity=0.25,
                reflectivity=0.7,
            ),
            "skin": MaterialState(
                material_type="skin",
                water_absorption=0.05,
                absorption_rate=0.1,
                color_darkening=0.05,
                specular_increase=0.7,
                roughness_decrease=0.4,
                weight_multiplier=1.0,
                stiffness_change=0.0,
                transparency_change=0.0,
                thermal_conductivity=0.6,
                reflectivity=0.3,
            ),
            "hair": MaterialState(
                material_type="organic",
                water_absorption=0.40,
                absorption_rate=0.5,
                color_darkening=0.30,
                specular_increase=0.5,
                roughness_decrease=0.3,
                weight_multiplier=1.4,
                stiffness_change=-0.6,
                transparency_change=0.0,
                thermal_conductivity=0.3,
                reflectivity=0.4,
            ),
            "metal": MaterialState(
                material_type="metal",
                water_absorption=0.0,
                absorption_rate=0.0,
                color_darkening=0.0,
                specular_increase=0.9,
                roughness_decrease=0.8,
                weight_multiplier=1.0,
                stiffness_change=0.0,
                transparency_change=0.0,
                thermal_conductivity=0.9,
                reflectivity=0.95,
            ),
            "glass": MaterialState(
                material_type="glass",
                water_absorption=0.0,
                absorption_rate=0.0,
                color_darkening=0.0,
                specular_increase=0.95,
                roughness_decrease=0.95,
                weight_multiplier=1.0,
                stiffness_change=0.0,
                transparency_change=0.0,
                thermal_conductivity=0.1,
                reflectivity=0.92,
            ),
            "plastic": MaterialState(
                material_type="synthetic",
                water_absorption=0.0,
                absorption_rate=0.0,
                color_darkening=0.0,
                specular_increase=0.7,
                roughness_decrease=0.7,
                weight_multiplier=1.0,
                stiffness_change=0.0,
                transparency_change=0.0,
                thermal_conductivity=0.2,
                reflectivity=0.6,
            ),
            "asphalt": MaterialState(
                material_type="stone",
                water_absorption=0.20,
                absorption_rate=0.4,
                color_darkening=0.50,
                specular_increase=0.8,
                roughness_decrease=0.6,
                weight_multiplier=1.0,
                stiffness_change=0.0,
                transparency_change=0.0,
                thermal_conductivity=0.7,
                reflectivity=0.15,
            ),
            "concrete": MaterialState(
                material_type="stone",
                water_absorption=0.35,
                absorption_rate=0.5,
                color_darkening=0.40,
                specular_increase=0.3,
                roughness_decrease=0.2,
                weight_multiplier=1.0,
                stiffness_change=0.0,
                transparency_change=0.0,
                thermal_conductivity=0.8,
                reflectivity=0.1,
            ),
            "wood": MaterialState(
                material_type="organic",
                water_absorption=0.60,
                absorption_rate=0.4,
                color_darkening=0.35,
                specular_increase=0.4,
                roughness_decrease=0.3,
                weight_multiplier=1.3,
                stiffness_change=-0.2,
                transparency_change=0.0,
                thermal_conductivity=0.15,
                reflectivity=0.2,
            ),
            "ethereal_fabric": MaterialState(
                material_type="magical",
                water_absorption=0.0,
                absorption_rate=0.0,
                color_darkening=0.0,
                specular_increase=1.0,
                roughness_decrease=1.0,
                weight_multiplier=0.5,
                stiffness_change=0.5,
                transparency_change=0.6,
                thermal_conductivity=0.0,
                reflectivity=0.98,
                is_glowing=True,
                glow_intensity=0.7,
            ),
            "dragon_scales": MaterialState(
                material_type="magical",
                water_absorption=0.0,
                absorption_rate=0.0,
                color_darkening=0.0,
                specular_increase=0.95,
                roughness_decrease=0.9,
                weight_multiplier=1.0,
                stiffness_change=0.8,
                transparency_change=0.0,
                thermal_conductivity=0.5,
                reflectivity=0.9,
                is_glowing=True,
                glow_intensity=0.5,
            ),
            "crystal": MaterialState(
                material_type="magical",
                water_absorption=0.0,
                absorption_rate=0.0,
                color_darkening=0.0,
                specular_increase=1.0,
                roughness_decrease=1.0,
                weight_multiplier=1.0,
                stiffness_change=1.0,
                transparency_change=0.0,
                thermal_conductivity=0.1,
                reflectivity=0.99,
                is_glowing=True,
                glow_intensity=0.8,
            ),
        }

    @staticmethod
    def _entity_id(entity: Any) -> str:
        if isinstance(entity, dict):
            return entity.get("id", "unknown")
        return getattr(entity, "id", "unknown")

    @staticmethod
    def _entity_type(entity: Any) -> str:
        if isinstance(entity, dict):
            return entity.get("type", "object")
        return getattr(entity, "type", "object")

    @staticmethod
    def _entity_properties(entity: Any) -> Dict[str, Any]:
        if isinstance(entity, dict):
            return entity.get("properties", {}) or {}
        return getattr(entity, "properties", {}) or {}

    def _deep_copy_material(self, material_name: str) -> MaterialState:
        """Deep copy material from database."""
        original = self.MATERIAL_DB[material_name]
        return MaterialState(
            material_type=original.material_type,
            water_absorption=original.water_absorption,
            absorption_rate=original.absorption_rate,
            color_darkening=original.color_darkening,
            specular_increase=original.specular_increase,
            roughness_decrease=original.roughness_decrease,
            weight_multiplier=original.weight_multiplier,
            stiffness_change=original.stiffness_change,
            transparency_change=original.transparency_change,
            thermal_conductivity=original.thermal_conductivity,
            reflectivity=original.reflectivity,
            is_glowing=original.is_glowing,
            glow_intensity=original.glow_intensity,
        )

    def simulate(
        self,
        scene_graph: Dict[str, Any],
        environment: EnvironmentalCondition,
    ) -> Dict[str, Any]:
        """
        Run complete physics simulation on scene.

        Args:
            scene_graph: From SceneGraphCompiler
            environment: Environmental conditions

        Returns:
            material_states, protection_zones, visual_effects, prompt_modifiers,
            control_signals, lighting_effects, simulation_metadata
        """
        self.scene_graph = scene_graph
        self.environment = environment
        self.material_states = {}
        self.protection_zones = []

        entities = scene_graph.get("entities", [])

        self._assign_materials(entities)
        self._compute_protection_zones(scene_graph)

        if environment.weather in ["rain", "storm"]:
            self._simulate_rain()
        elif environment.weather == "snow":
            self._simulate_snow()

        lighting_effects = self._simulate_lighting()

        if environment.magical_atmosphere or environment.ethereal_glow:
            self._simulate_magical_effects()

        visual_effects = self._compute_visual_effects()
        prompt_modifiers = self._generate_prompt_modifiers()
        control_signals = self._generate_control_signals()

        return {
            "material_states": dict(self.material_states),
            "protection_zones": list(self.protection_zones),
            "visual_effects": visual_effects,
            "prompt_modifiers": prompt_modifiers,
            "control_signals": control_signals,
            "lighting_effects": lighting_effects,
            "simulation_metadata": {
                "entity_count": len(self.material_states),
                "weather": environment.weather,
                "lighting": environment.lighting,
                "has_protection": len(self.protection_zones) > 0,
            },
        }

    def _assign_materials(self, entities: List[Any]) -> None:
        """
        Assign appropriate materials to all scene entities.
        Supports EntityNode (scene graph) and dict (layout/pipeline).
        """
        for entity in entities:
            entity_id = self._entity_id(entity)
            entity_type = self._entity_type(entity)
            props = self._entity_properties(entity)

            if entity_type == "person":
                age = props.get("age", "adult")
                role = props.get("role", "")

                if age == "child" or "kid" in str(role).lower() or "baby" in str(role).lower():
                    clothing_material = self._deep_copy_material("cotton")
                else:
                    clothing_material = self._deep_copy_material("denim")

                self.material_states[f"{entity_id}_clothing"] = clothing_material
                self.material_states[f"{entity_id}_skin"] = self._deep_copy_material("skin")
                self.material_states[f"{entity_id}_hair"] = self._deep_copy_material("hair")
                self.material_states[f"{entity_id}_shoes"] = self._deep_copy_material("leather")

            elif entity_type == "object":
                obj_name = props.get("name", "") or ""

                if obj_name == "umbrella" or "umbrella" in str(entity_id).lower():
                    self.material_states[entity_id] = self._deep_copy_material("plastic")
                elif "car" in obj_name.lower():
                    self.material_states[f"{entity_id}_body"] = self._deep_copy_material("metal")
                    self.material_states[f"{entity_id}_windows"] = self._deep_copy_material("glass")
                elif obj_name == "building":
                    self.material_states[f"{entity_id}_walls"] = self._deep_copy_material("concrete")
                    self.material_states[f"{entity_id}_windows"] = self._deep_copy_material("glass")
                else:
                    self.material_states[entity_id] = self._deep_copy_material("plastic")

            elif entity_type in ("mythical_creature", "creature"):
                name_lower = (entity_id + " " + str(props.get("name", ""))).lower()
                if "dragon" in name_lower:
                    self.material_states[f"{entity_id}_scales"] = self._deep_copy_material("dragon_scales")
                    self.material_states[f"{entity_id}_wings"] = self._deep_copy_material("ethereal_fabric")
                else:
                    self.material_states[f"{entity_id}_body"] = self._deep_copy_material("ethereal_fabric")

            elif entity_type == "magical_object":
                self.material_states[entity_id] = self._deep_copy_material("crystal")

        self.material_states["ground"] = self._deep_copy_material("asphalt")

    def _compute_protection_zones(self, scene_graph: Dict[str, Any]) -> None:
        """Identify areas protected from weather (umbrella, roof, etc.)."""
        layout = scene_graph.get("layout", {})
        entities_layout = layout.get("entities", [])

        for entity_layout in entities_layout:
            if isinstance(entity_layout, dict) and entity_layout.get("type") == "umbrella":
                center = entity_layout.get("center", (0, 0))
                radius = float(entity_layout.get("radius", 150))

                covered: List[str] = []
                for person_layout in entities_layout:
                    if not isinstance(person_layout, dict) or person_layout.get("type") != "person":
                        continue
                    bbox = person_layout.get("bbox")
                    if not bbox or len(bbox) < 4:
                        continue
                    person_center = (
                        (bbox[0] + bbox[2]) // 2,
                        (bbox[1] + bbox[3]) // 2,
                    )
                    dist = np.sqrt(
                        (person_center[0] - center[0]) ** 2 + (person_center[1] - center[1]) ** 2
                    )
                    if dist < radius:
                        covered.append(person_layout.get("id", ""))

                self.protection_zones.append(
                    ProtectionZone(
                        zone_type="umbrella",
                        center=tuple(center),
                        radius=radius,
                        protection_factor=0.85,
                        covered_entities=covered,
                    )
                )

    def _base_entity_id(self, material_entity_id: str) -> str:
        """Get base entity id from material key (e.g. person_1_clothing -> person_1)."""
        if material_entity_id == "ground":
            return "ground"
        parts = material_entity_id.split("_")
        if len(parts) >= 2 and parts[-1] in ("clothing", "skin", "hair", "shoes", "body", "scales", "wings", "walls", "windows"):
            return "_".join(parts[:-1])
        return material_entity_id

    def _simulate_rain(self) -> None:
        """Simulate rain effects on all materials; respect protection zones."""
        if not self.environment:
            return
        intensity = self.environment.intensity

        for entity_id, material in list(self.material_states.items()):
            if material.water_absorption < 0.01:
                continue

            exposure = 1.0
            base_id = self._base_entity_id(entity_id)
            is_protected = any(
                base_id in zone.covered_entities for zone in self.protection_zones
            )

            if is_protected:
                if "_clothing" in entity_id:
                    exposure = 0.15 * intensity
                elif "_shoes" in entity_id or entity_id == "ground":
                    exposure = 1.0 * intensity
                elif "_skin" in entity_id:
                    exposure = 0.25 * intensity
                elif "_hair" in entity_id:
                    exposure = 0.10 * intensity
                else:
                    exposure = 0.30 * intensity
            else:
                exposure = 1.0 * intensity

            wetness_gain = (
                exposure * material.absorption_rate * material.water_absorption * 0.7
            )
            material.wetness_level = min(1.0, material.wetness_level + wetness_gain)

        if "ground" in self.material_states:
            self.material_states["ground"].wetness_level = min(
                1.0, 0.5 + intensity * 0.5
            )

    def _simulate_snow(self) -> None:
        """Simulate snow accumulation (light wetness from melting)."""
        if not self.environment:
            return
        intensity = self.environment.intensity
        for entity_id, material in self.material_states.items():
            if material.material_type in ["fabric", "organic"]:
                material.wetness_level = min(0.3, intensity * 0.3)

    def _simulate_lighting(self) -> Dict[str, Any]:
        """Simulate lighting effects from time of day and weather."""
        if not self.environment:
            return {
                "ambient_intensity": 1.0,
                "shadow_strength": 0.5,
                "highlight_strength": 0.3,
                "color_temperature": 5500,
                "fog_density": 0.0,
                "atmospheric_scattering": 0.1,
            }
        lighting = self.environment.lighting
        weather = self.environment.weather

        effects: Dict[str, Any] = {
            "ambient_intensity": 1.0,
            "shadow_strength": 0.5,
            "highlight_strength": 0.3,
            "color_temperature": 5500,
            "fog_density": 0.0,
            "atmospheric_scattering": 0.1,
        }

        if lighting == "night":
            effects["ambient_intensity"] = 0.25
            effects["shadow_strength"] = 0.9
            effects["highlight_strength"] = 0.6
            effects["color_temperature"] = 3500
        elif lighting == "golden_hour":
            effects["ambient_intensity"] = 0.75
            effects["shadow_strength"] = 0.3
            effects["highlight_strength"] = 0.8
            effects["color_temperature"] = 2800
        elif lighting == "twilight":
            effects["ambient_intensity"] = 0.4
            effects["shadow_strength"] = 0.6
            effects["color_temperature"] = 4500
        elif lighting == "overcast":
            effects["ambient_intensity"] = 0.6
            effects["shadow_strength"] = 0.2
            effects["color_temperature"] = 6500

        if weather in ["rain", "storm"]:
            effects["shadow_strength"] *= 0.5
            effects["ambient_intensity"] *= 0.7
            effects["atmospheric_scattering"] = 0.3
        elif weather == "fog":
            effects["fog_density"] = 0.6
            effects["shadow_strength"] *= 0.3
            effects["ambient_intensity"] *= 0.5

        return effects

    def _simulate_magical_effects(self) -> None:
        """Apply magical/fantasy atmospheric effects."""
        if not self.environment:
            return
        for material in self.material_states.values():
            if material.is_glowing and self.environment.ethereal_glow:
                material.glow_intensity = min(1.0, material.glow_intensity * 1.3)

    def _compute_visual_effects(self) -> List[str]:
        """Convert material states into human-readable visual descriptions."""
        effects: List[str] = []
        for entity_id, material in self.material_states.items():
            if material.wetness_level > 0.1:
                wetness_pct = int(material.wetness_level * 100)
                if material.material_type == "fabric":
                    darkening = material.color_darkening * material.wetness_level
                    effects.append(
                        f"{entity_id}: fabric {int(darkening*100)}% darker from water absorption"
                    )
                    if material.wetness_level > 0.6:
                        effects.append(f"{entity_id}: fabric clinging to body from saturation")
                    if material.specular_increase > 0.15:
                        shine = material.specular_increase * material.wetness_level
                        effects.append(f"{entity_id}: wet sheen visible, {int(shine*100)}% specular")
                elif material.material_type == "skin":
                    effects.append(f"{entity_id}: water droplets visible on surface")
                    effects.append(f"{entity_id}: wet glossy sheen, {wetness_pct}% coverage")
                elif material.material_type == "organic" and "hair" in entity_id:
                    if material.wetness_level > 0.5:
                        effects.append(f"{entity_id}: hair wet and dripping, strands darkened")
                    else:
                        effects.append(f"{entity_id}: hair damp with slight shine")
                elif material.material_type == "stone":
                    effects.append(f"{entity_id}: dark wet surface, {wetness_pct}% saturated")
                    if material.wetness_level > 0.7:
                        effects.append(f"{entity_id}: mirror-like reflections in water puddles")
            if material.is_glowing and material.glow_intensity > 0.3:
                glow_pct = int(material.glow_intensity * 100)
                effects.append(f"{entity_id}: ethereal glow at {glow_pct}% intensity")
        return effects

    def _generate_prompt_modifiers(self) -> str:
        """Convert physical simulation into prompt text modifiers."""
        modifiers: List[str] = []
        if not self.environment:
            return ", ".join(modifiers)

        if self.environment.weather == "rain":
            modifiers.append("realistic rain falling with accurate physics and gravity")
            modifiers.append("rain streaks visible in air, individual droplets catching ambient light")
            modifiers.append("atmospheric mist rising from rain hitting warm surfaces")
            if self.environment.intensity > 0.7:
                modifiers.append("heavy torrential rain, reduced visibility")
            elif self.environment.intensity < 0.3:
                modifiers.append("light drizzle, gentle rain")
        elif self.environment.weather == "snow":
            modifiers.append("snowflakes falling gently, each flake visible and unique")
            if self.environment.intensity > 0.6:
                modifiers.append("heavy snowfall, accumulation visible on surfaces")

        wet_fabrics = [
            k for k, v in self.material_states.items()
            if "clothing" in k and v.wetness_level > 0.4
        ]
        if wet_fabrics:
            avg_wetness = float(np.mean([self.material_states[k].wetness_level for k in wet_fabrics]))
            darkening = float(np.mean([
                self.material_states[k].color_darkening * self.material_states[k].wetness_level
                for k in wet_fabrics
            ]))
            modifiers.append(
                f"clothing fabric visibly wet, {int(darkening*100)}% darker from water absorption"
            )
            if avg_wetness > 0.6:
                modifiers.append("wet fabric clinging to body contours, heavy with moisture")

        wet_skin = [k for k, v in self.material_states.items() if "skin" in k and v.wetness_level > 0.2]
        if wet_skin:
            modifiers.append("visible water droplets on exposed skin surfaces")
            modifiers.append("wet glossy sheen on face, hands, and arms")

        wet_hair = [k for k, v in self.material_states.items() if "hair" in k and v.wetness_level > 0.4]
        if wet_hair:
            avg_hair = float(np.mean([self.material_states[k].wetness_level for k in wet_hair]))
            if avg_hair > 0.7:
                modifiers.append("hair completely soaked, dripping water, strands plastered to head")
            else:
                modifiers.append("hair damp and darkened from moisture")

        if "ground" in self.material_states and self.material_states["ground"].wetness_level > 0.5:
            modifiers.append("wet pavement reflecting street lights and neon signs")
            modifiers.append("puddles on ground with concentric ripples from falling raindrops")
            modifiers.append("water splashing slightly around footsteps")
            if self.environment.lighting == "night":
                modifiers.append("wet asphalt creating mirror-like reflections of city lights")

        if self.protection_zones:
            for zone in self.protection_zones:
                if zone.zone_type == "umbrella":
                    modifiers.append("rain droplets bouncing off umbrella canopy surface")
                    modifiers.append("water streaming down umbrella edges in clear rivulets")
                    modifiers.append("upper body dry and protected under umbrella")
                    modifiers.append("lower legs and feet wet from rain exposure below umbrella")

        lighting = self._simulate_lighting()
        if lighting.get("ambient_intensity", 1.0) < 0.4:
            modifiers.append("low ambient lighting creating dramatic atmosphere")
        if self.environment.lighting == "golden_hour":
            modifiers.append("warm golden hour lighting, long soft shadows stretching across scene")
            modifiers.append("sunlight at low angle creating rim lighting on figures")
        elif self.environment.lighting == "night":
            modifiers.append("nighttime scene with artificial street lighting")
            modifiers.append("strong contrast between lit and shadow areas")

        glowing = [k for k, v in self.material_states.items() if v.is_glowing and v.glow_intensity > 0.3]
        if glowing:
            modifiers.append("ethereal magical glow emanating from mystical elements")
            if any("dragon" in k for k in glowing):
                modifiers.append("iridescent dragon scales reflecting light with supernatural shimmer")
            if any("crystal" in k for k in glowing):
                modifiers.append("crystalline surfaces emitting soft magical luminescence")
        if getattr(self.environment, "ethereal_glow", False):
            modifiers.append("atmospheric ethereal glow suffusing the entire scene")

        modifiers.append("physically accurate material properties and light interaction")
        modifiers.append("photorealistic rendering with proper depth of field")
        return ", ".join(modifiers)

    def _generate_control_signals(self) -> Dict[str, Any]:
        """Generate control signals for ControlNet (wetness/specular/glow regions)."""
        lighting = self._simulate_lighting()
        signals: Dict[str, Any] = {
            "wetness_regions": [],
            "specular_regions": [],
            "glow_regions": [],
            "shadow_intensity": lighting.get("shadow_strength", 0.5),
        }
        for entity_id, material in self.material_states.items():
            if material.wetness_level > 0.3:
                signals["wetness_regions"].append({
                    "entity": entity_id,
                    "intensity": material.wetness_level,
                    "darkening": material.color_darkening * material.wetness_level,
                })
        for entity_id, material in self.material_states.items():
            if material.specular_increase * material.wetness_level > 0.3:
                signals["specular_regions"].append({
                    "entity": entity_id,
                    "intensity": material.specular_increase * material.wetness_level,
                })
        for entity_id, material in self.material_states.items():
            if material.is_glowing and material.glow_intensity > 0.3:
                signals["glow_regions"].append({
                    "entity": entity_id,
                    "intensity": material.glow_intensity,
                    "color": "ethereal_blue",
                })

        # Backward compatibility for tests and pipeline (wetness_map, specular_map, shadow_map)
        signals["wetness_map"] = {r["entity"]: r["intensity"] for r in signals["wetness_regions"]}
        signals["specular_map"] = {r["entity"]: r["intensity"] for r in signals["specular_regions"]}
        signals["shadow_map"] = {"shadow_intensity": signals["shadow_intensity"]}
        return signals

    # ========== Pipeline-compatible API ==========

    def run(
        self,
        entities: List[Any],
        weather: Optional[Dict[str, Any]] = None,
        time_of_day: str = "day",
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run simulation from pipeline: layout entities + weather.
        Returns dict with prompt_modifiers, visual_effects, gravity_hints, etc.
        seed: optional; ignored (simulation is deterministic); reserved for future RNG.
        """
        condition = "sunny"
        intensity = 1.0
        if weather:
            condition = str(weather.get("condition", weather.get("weather", "sunny")))
            intensity = float(weather.get("intensity", 1.0))

        env = EnvironmentalCondition(
            weather=condition,
            intensity=intensity,
            temperature=20.0,
            wind_speed=0.0,
            lighting=time_of_day if time_of_day in ("day", "night", "golden_hour", "overcast", "twilight") else "day",
        )
        scene_graph = {"entities": entities, "layout": {"entities": entities}}
        out = self.simulate(scene_graph, env)
        out["gravity_hints"] = []
        if condition == "rain":
            out["gravity_hints"] = [
                "cloth_drapes_down",
                "hair_falls_naturally",
                "wet_fabric_clings",
                "water_droplets_fall",
                "realistic_gravity",
            ]
        elif condition == "snow":
            out["gravity_hints"] = [
                "snow_accumulation_on_surfaces",
                "realistic_gravity",
            ]
        else:
            out["gravity_hints"] = ["realistic_gravity"]
        return out

    def to_prompt_suffix(self, result: Dict[str, Any]) -> str:
        """Convert simulation result to prompt suffix (pipeline compatibility)."""
        modifiers = result.get("prompt_modifiers", "")
        hints = result.get("gravity_hints", [])
        if hints:
            modifiers = f"{modifiers}, {', '.join(hints)}" if modifiers else ", ".join(hints)
        return modifiers or "physically accurate materials"


# ========== Helper functions ==========

def create_rainy_environment(intensity: float = 0.8) -> EnvironmentalCondition:
    """Quick helper to create rainy conditions."""
    return EnvironmentalCondition(
        weather="rain",
        intensity=intensity,
        temperature=15,
        wind_speed=5,
        humidity=0.95,
        lighting="overcast",
        light_intensity=0.6,
        light_temperature=6500,
    )


def create_fantasy_environment() -> EnvironmentalCondition:
    """Quick helper for magical/fantasy scenes."""
    return EnvironmentalCondition(
        weather="none",
        intensity=0.0,
        temperature=20,
        wind_speed=0,
        humidity=0.5,
        lighting="twilight",
        light_intensity=0.7,
        light_temperature=4000,
        magical_atmosphere=True,
        ethereal_glow=True,
    )

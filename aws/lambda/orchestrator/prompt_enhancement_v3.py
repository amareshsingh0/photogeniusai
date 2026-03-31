"""
Prompt Enhancement v3 (Multi-Modal) for PhotoGenius AI.

Builds ultimate prompts from scene graph + physics + validation failures.
P1: 90%+ first-try success.

Combines:
- Scene graph constraints → positive prompt (entities, relations, hard constraints)
- Physics effects → material descriptors (wetness, reflectivity, lighting, gravity)
- Negative prompts from validation failures (anatomy, occlusion, merged bodies)

Files: prompt_enhancement_v3.py
Success Metric: Enhanced prompts yield 90%+ first-try success.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Optional imports for physics and validation
try:
    from .physics_micro_sim import PhysicsSimResult, MaterialState
except ImportError:
    PhysicsSimResult = None  # type: ignore
    MaterialState = None  # type: ignore

try:
    from .tri_model_validator import TriModelConsensus, ValidationResult
except ImportError:
    TriModelConsensus = None  # type: ignore
    ValidationResult = None  # type: ignore


# ---------------------------------------------------------------------------
# Base negatives (anatomy, quality, coherence) — always included when people
# ---------------------------------------------------------------------------
BASE_NEGATIVE: List[str] = [
    "blurry",
    "low quality",
    "distorted",
    "deformed",
    "bad anatomy",
    "disfigured",
    "poorly drawn",
    "extra limbs",
    "missing limbs",
    "merged bodies",
    "mutated hands",
    "mutated feet",
    "six fingers",
    "too many fingers",
    "wrong hand count",
    "headless",
    "head cut off",
    "face cut off",
    "umbrella covering face",
    "head obscured",
    "body merging",
    "jumbled figures",
    "wrong depth order",
]

# Rule → (negative_phrases, positive_phrases) for validation failures
RULE_TO_NEGATIVE_POSITIVE: Dict[str, Tuple[List[str], List[str]]] = {
    "heads_fully_visible": (
        ["headless", "head cut off", "missing head", "head absorbed", "face cut off"],
        ["every figure has visible head", "one head per person", "head visible"],
    ),
    "heads_visible": (
        ["headless", "head cut off", "missing head", "face cut off"],
        ["all heads visible", "head visible"],
    ),
    "no_heads_occluded": (
        ["head obscured", "face cut off by object", "umbrella covering face"],
        ["umbrella above head not covering face", "head visible under umbrella"],
    ),
    "occluded_by_objects": (
        ["head obscured", "object covering face", "umbrella covering face"],
        ["head visible", "clear face"],
    ),
    "2_arms_2_legs": (
        [
            "extra arm",
            "third arm",
            "arm from back",
            "extra limbs",
            "merged limbs",
            "missing arm",
            "missing leg",
        ],
        [
            "two arms per person",
            "exactly two arms",
            "natural limbs",
            "correct limb count",
        ],
    ),
    "arms_2_legs": (
        ["extra limbs", "merged limbs", "missing limbs"],
        ["two arms two legs", "natural limbs"],
    ),
    "hands_have_5_fingers": (
        [
            "six fingers",
            "seven fingers",
            "claw hands",
            "fused fingers",
            "extra fingers",
        ],
        ["five fingers each hand", "correct hand anatomy"],
    ),
    "5_fingers": (
        ["six fingers", "extra fingers", "fused fingers"],
        ["five fingers", "correct hand anatomy"],
    ),
    "no_merged_bodies": (
        [
            "merged bodies",
            "merged figures",
            "body merging",
            "jumbled figures",
            "figures overlapping",
        ],
        ["clear separation between figures", "distinct persons", "no merged bodies"],
    ),
    "realistic_wetness": (
        ["dry in rain", "unrealistic wetness", "no wetness"],
        ["realistic wetness", "water droplets", "wet fabric", "wet skin"],
    ),
}


def _entity_to_summary(entities: List[Any]) -> str:
    """Convert scene graph entities to short positive prompt summary (counts, types)."""
    if not entities:
        return ""
    # Support both EntityNode (dataclass) and dict
    people = []
    objects: Dict[str, int] = {}
    weather = []
    for e in entities:
        if isinstance(e, dict):
            t = e.get("type", "object")
            props = e.get("properties", {})
            name = props.get("name") or props.get("role") or t
        else:
            t = getattr(e, "type", "object")
            props = getattr(e, "properties", {}) or {}
            name = props.get("name") or props.get("role") or t
        if t == "person":
            age = props.get("age", "adult")
            if age == "child":
                people.append("child")
            else:
                people.append("adult")
        elif t == "weather":
            weather.append(name if isinstance(name, str) else "weather")
        else:
            key = name if isinstance(name, str) else t
            objects[key] = objects.get(key, 0) + 1
    parts = []
    if people:
        adults = sum(1 for p in people if p == "adult")
        children = sum(1 for p in people if p == "child")
        if adults and children:
            parts.append(f"{adults} adult(s) and {children} child(ren)")
        elif adults:
            parts.append(f"{adults} adult(s)")
        elif children:
            parts.append(f"{children} child(ren)")
        else:
            parts.append(f"{len(people)} person(s)")
    for obj_name, count in sorted(objects.items()):
        parts.append(f"{count} {obj_name}(s)" if count != 1 else f"1 {obj_name}")
    for w in weather[:1]:
        parts.append(w)
    return ", ".join(parts) if parts else ""


def _relations_to_summary(relations: List[Any]) -> str:
    """Convert relations to short positive phrases (under umbrella, holding, etc.)."""
    if not relations:
        return ""
    phrases = []
    for r in relations:
        if isinstance(r, dict):
            rel = r.get("relation", "")
            constraints = r.get("constraints", [])
        else:
            rel = getattr(r, "relation", "")
            constraints = getattr(r, "constraints", []) or []
        if rel == "under":
            phrases.append(
                "under umbrella"
                if "umbrella" in str(constraints).lower()
                else "under shelter"
            )
        elif rel == "holding":
            phrases.append("holding umbrella")
        elif rel == "beside":
            phrases.append("standing beside each other")
        elif rel:
            phrases.append(rel.replace("_", " "))
    # Dedupe
    seen = set()
    out = []
    for p in phrases:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return ", ".join(out) if out else ""


def _constraints_to_positive(constraints: List[Any]) -> str:
    """Map hard constraints to short positive prompt phrases (what we want)."""
    if not constraints:
        return ""
    rule_to_positive = {
        "heads_fully_visible": "all heads fully visible",
        "heads_visible": "all heads visible",
        "no_heads_occluded": "no heads occluded by objects",
        "occluded_by_objects": "heads not covered by objects",
        "2_arms_2_legs": "each person with two arms and two legs",
        "arms_2_legs": "correct limb count",
        "hands_have_5_fingers": "five fingers per hand",
        "5_fingers": "correct hand anatomy",
        "no_merged_bodies": "clear separation between figures, no merged bodies",
        "realistic_wetness": "realistic wetness effects",
    }
    phrases = []
    for c in constraints:
        rule = ""
        if isinstance(c, dict):
            rule = c.get("rule", "")
        else:
            rule = getattr(c, "rule", "")
        rule_lower = rule.lower().replace(" ", "_").replace("-", "_")
        for key, pos in rule_to_positive.items():
            if key in rule_lower or key.replace("_", " ") in rule_lower:
                phrases.append(pos)
                break
    seen = set()
    out = []
    for p in phrases:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return ", ".join(out) if out else ""


def scene_graph_to_positive(scene_graph: Dict[str, Any]) -> str:
    """
    Build positive prompt from scene graph (entities, relations, constraints).
    Uses: entities, relations, constraints, layout (optional), prompt (original).
    """
    user_prompt = (scene_graph.get("prompt") or "").strip()
    entities_raw = scene_graph.get("entities", [])
    relations_raw = scene_graph.get("relations", [])
    constraints_raw = scene_graph.get("constraints", [])

    entity_summary = _entity_to_summary(entities_raw)
    relation_summary = _relations_to_summary(relations_raw)
    constraint_summary = _constraints_to_positive(constraints_raw)

    parts = [user_prompt] if user_prompt else []
    if entity_summary:
        parts.append(entity_summary)
    if relation_summary:
        parts.append(relation_summary)
    if constraint_summary:
        parts.append(constraint_summary)

    return ", ".join(parts).strip() or "high quality scene"


def physics_to_material_descriptors(physics_result: Any) -> str:
    """
    Convert physics sim result to material/effect descriptors for positive prompt.
    Supports: PhysicsSimResult (physics_micro_sim) or dict from PhysicsMicroSimulation.run().
    Duck-typed: wetness_map_hint / control_signals.wetness_map, materials / material_states,
    gravity_hints, lighting / lighting_effects.
    """
    if physics_result is None:
        return ""
    parts = []

    # Normalize dict from PhysicsMicroSimulation.run()
    wetness_map = None
    materials_dict = None
    gravity_hints_list = None
    lighting_obj = None
    if isinstance(physics_result, dict):
        cs = physics_result.get("control_signals") or {}
        wetness_map = cs.get("wetness_map") or physics_result.get("wetness_map_hint")
        materials_dict = physics_result.get("material_states") or physics_result.get("materials")
        gravity_hints_list = physics_result.get("gravity_hints")
        le = physics_result.get("lighting_effects") or {}
        if le:
            shadow = le.get("shadow_strength")
            shadow = shadow if shadow is not None else 0.5
            lighting_obj = type("Lighting", (), {"softness": 1.0 - min(1.0, shadow), "intensity": le.get("ambient_intensity", 1.0)})
    else:
        wetness_map = getattr(physics_result, "wetness_map_hint", None)
        materials_dict = getattr(physics_result, "materials", None)
        gravity_hints_list = getattr(physics_result, "gravity_hints", None)
        lighting_obj = getattr(physics_result, "lighting", None)

    # Wetness / materials
    if wetness_map:
        avg_wet = sum(wetness_map.values()) / max(len(wetness_map), 1)
        if avg_wet > 0.3:
            parts.append("realistic wetness")
            parts.append("water reflections")
            parts.append("wet skin and fabric")
        if avg_wet > 0.5:
            parts.append("wet reflective ground")
    # Materials per type (material_states use wetness_level; PhysicsSimResult uses wetness)
    if materials_dict:
        for eid, mat in materials_dict.items():
            w = getattr(mat, "wetness_level", None) or getattr(mat, "wetness", 0)
            if w and w > 0.4:
                if "skin" in str(eid).lower() or eid == "global":
                    parts.append("wet skin")
                if "fabric" in str(eid).lower() or "clothing" in str(eid).lower() or "umbrella" in str(eid).lower():
                    parts.append("wet fabric")
                break
    # Gravity
    if gravity_hints_list:
        for h in gravity_hints_list:
            if h and h != "realistic_gravity":
                parts.append(h.replace("_", " "))
        parts.append("realistic gravity")
    # Lighting
    if lighting_obj:
        softness = getattr(lighting_obj, "softness", 0)
        intensity = getattr(lighting_obj, "intensity", 0)
        if softness > 0.6:
            parts.append("soft diffused lighting")
        if intensity > 0.7:
            parts.append("natural lighting")
    if not parts:
        return "physically accurate materials"
    seen = set()
    out = []
    for p in parts:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return ", ".join(out)


def validation_failures_to_negative(validation_failures: Any) -> str:
    """
    Build negative prompt from validation failures (TriModelConsensus).
    Uses: results (passed=False), limb_violations, occlusion_detected.
    """
    extra_negatives: List[str] = []
    if validation_failures is None:
        pass
    elif TriModelConsensus is not None and isinstance(
        validation_failures, TriModelConsensus
    ):
        # Failed rules → lookup RULE_TO_NEGATIVE_POSITIVE
        if hasattr(validation_failures, "results"):
            for r in validation_failures.results:
                if not getattr(r, "passed", True):
                    rule = getattr(r, "rule", "")
                    rule_lower = rule.lower().replace(" ", "_").replace("-", "_")
                    for key, (neg_list, _) in RULE_TO_NEGATIVE_POSITIVE.items():
                        if key in rule_lower or key.replace("_", " ") in rule_lower:
                            extra_negatives.extend(neg_list)
                            break
        if (
            hasattr(validation_failures, "limb_violations")
            and validation_failures.limb_violations
        ):
            extra_negatives.extend(validation_failures.limb_violations)
        if (
            hasattr(validation_failures, "occlusion_detected")
            and validation_failures.occlusion_detected
        ):
            extra_negatives.extend(["head obscured", "missing head", "face cut off"])
    # Build from BASE_NEGATIVE + extra (do not mutate BASE_NEGATIVE)
    all_neg = list(BASE_NEGATIVE)
    seen = {x.lower() for x in all_neg}
    for n in extra_negatives:
        if n and n.lower() not in seen:
            seen.add(n.lower())
            all_neg.append(n)
    return ", ".join(all_neg[:80])  # cap length


def build_negative_prompt_base(
    has_people: bool = True, multi_person: bool = False
) -> str:
    """Base negative prompt (no validation failures)."""
    parts = list(BASE_NEGATIVE)
    if multi_person:
        parts.extend(
            [
                "wrong depth order",
                "body merging",
                "jumbled figures",
                "head absorbed by umbrella",
                "face cut off by object",
            ]
        )
    seen = set()
    out = []
    for p in parts:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return ", ".join(out[:80])


@dataclass
class PromptEnhancementV3Result:
    """Result of v3 enhancement."""

    enhanced_prompt: str
    negative_prompt: str
    first_try_ready: bool  # True if no validation failures were incorporated (aim for 90%+ first-try)
    sources: Dict[str, Any] = field(default_factory=dict)


def enhance_v3(
    user_prompt: str,
    scene_graph: Optional[Dict[str, Any]] = None,
    physics_result: Optional[Any] = None,
    validation_failures: Optional[Any] = None,
    *,
    include_base_negative: bool = True,
    has_people: bool = True,
    multi_person: bool = False,
) -> PromptEnhancementV3Result:
    """
    Build ultimate prompts from scene graph + physics + validation failures.

    - Scene graph constraints → positive prompt (entities, relations, hard constraints).
    - Physics effects → material descriptors (wetness, reflectivity, lighting, gravity).
    - Negative prompt: base anatomy/quality + negatives from validation failures.

    Returns:
        PromptEnhancementV3Result(enhanced_prompt, negative_prompt, first_try_ready, sources).
    """
    sources: Dict[str, Any] = {}

    # 1) Positive prompt from scene graph
    if scene_graph:
        positive = scene_graph_to_positive(scene_graph)
        sources["scene_graph"] = True
    else:
        positive = (user_prompt or "").strip() or "high quality scene"

    # 2) Append physics material descriptors
    material_desc = physics_to_material_descriptors(physics_result)
    if material_desc:
        positive = f"{positive}, {material_desc}".strip()
        sources["physics"] = True

    # 3) Negative prompt: base + validation failures
    if validation_failures is not None and validation_failures is not False:
        negative = validation_failures_to_negative(validation_failures)
        first_try_ready = False  # we used failure feedback
        sources["validation_failures"] = True
    else:
        negative = (
            build_negative_prompt_base(has_people=has_people, multi_person=multi_person)
            if include_base_negative
            else ""
        )
        first_try_ready = True

    return PromptEnhancementV3Result(
        enhanced_prompt=positive,
        negative_prompt=negative,
        first_try_ready=first_try_ready,
        sources=sources,
    )


def enhance_v3_from_compiled(
    compiled: Dict[str, Any],
    physics_result: Optional[Any] = None,
    validation_failures: Optional[Any] = None,
) -> PromptEnhancementV3Result:
    """
    Convenience: enhance from compiler output (compile() dict) + optional physics and validation.
    In pipeline: compiled = compiler.compile(prompt); then physics run; then optionally validation.
    """
    user_prompt = (compiled.get("prompt") or "").strip()
    entities = compiled.get("entities", [])
    person_count = 0
    for e in entities:
        t = (
            e.get("type", getattr(e, "type", ""))
            if isinstance(e, dict)
            else getattr(e, "type", "")
        )
        if t == "person":
            person_count += 1
    return enhance_v3(
        user_prompt,
        scene_graph=compiled,
        physics_result=physics_result,
        validation_failures=validation_failures,
        has_people=person_count > 0,
        multi_person=person_count > 1,
    )

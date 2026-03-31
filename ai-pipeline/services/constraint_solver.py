"""
Constraint Solver for PhotoGenius AI.
Converts scene graph hard constraints into concrete generation parameters:
positive/negative prompt additions, composition rules, and validation rules.
P0: Deterministic pipeline — bridge between SceneGraphCompiler and generation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class SolverResult:
    """Result of constraint solving: prompt additions, composition, validation rules."""

    positive_additions: List[str] = field(default_factory=list)
    negative_additions: List[str] = field(default_factory=list)
    composition_rules: Dict[str, Any] = field(default_factory=dict)
    validation_rules: Dict[str, Any] = field(default_factory=dict)

    def merge_into_prompt(self, prompt: str, sep: str = ", ") -> str:
        """Append positive_additions to prompt."""
        if not self.positive_additions:
            return prompt
        suffix = sep.join(self.positive_additions)
        return f"{prompt.rstrip()}{sep}{suffix}" if prompt.strip() else suffix

    def merge_into_negative(self, negative: str, sep: str = ", ") -> str:
        """Append negative_additions to negative prompt."""
        if not self.negative_additions:
            return negative
        suffix = sep.join(self.negative_additions)
        return f"{negative.rstrip()}{sep}{suffix}" if negative.strip() else suffix


def _get_constraint_list(scene_graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return list of constraint dicts with 'type' and 'rule' (and optionally 'severity')."""
    hard = scene_graph.get("hard_constraints")
    if hard and isinstance(hard, list):
        return [
            {"type": c.get("type"), "rule": c.get("rule"), "severity": c.get("severity")}
            for c in hard
            if isinstance(c, dict) and c.get("rule")
        ]
    constraints = scene_graph.get("constraints")
    if constraints and isinstance(constraints, list):
        out = []
        for c in constraints:
            if hasattr(c, "type") and hasattr(c, "rule"):
                out.append({"type": c.type, "rule": c.rule, "severity": getattr(c, "severity", "high")})
            elif isinstance(c, dict):
                out.append({"type": c.get("type"), "rule": c.get("rule"), "severity": c.get("severity")})
        return out
    return []


class ConstraintSolver:
    """
    Converts high-level scene graph constraints into concrete generation parameters.
    Example: "exactly_4_people" → composition rules, negative prompts, validation_rules.
    """

    def solve(self, scene_graph: Dict[str, Any]) -> SolverResult:
        """
        Args:
            scene_graph: Output from SceneGraphCompiler (compile(prompt)).

        Returns:
            SolverResult with:
            - positive_additions: List[str] (add to prompt)
            - negative_additions: List[str] (add to negative)
            - composition_rules: dict (layout constraints for generator)
            - validation_rules: dict (post-gen checks: person_count, hands_holding, etc.)
        """
        result = SolverResult()
        constraint_list = _get_constraint_list(scene_graph)
        seen_rules: set = set()

        for c in constraint_list:
            rule = (c.get("rule") or "").strip()
            ctype = (c.get("type") or "").strip()
            if not rule or rule in seen_rules:
                continue
            seen_rules.add(rule)

            # exactly_N_people (from count type or rule pattern)
            exactly_match = re.match(r"exactly_(\d+)_people", rule)
            if exactly_match:
                n = int(exactly_match.group(1))
                result.positive_additions.append(
                    f"exactly {n} people, {n} visible faces, all heads visible"
                )
                result.negative_additions.extend([
                    f"more than {n} people",
                    f"less than {n} people",
                    "extra person in background",
                    "partial person",
                    "person cut off",
                ])
                result.validation_rules["person_count"] = n
                continue

            # exactly_N_heads_fully_visible (visibility)
            heads_match = re.match(r"exactly_(\d+)_heads_fully_visible", rule)
            if heads_match:
                n = int(heads_match.group(1))
                if "person_count" not in result.validation_rules:
                    result.validation_rules["person_count"] = n
                result.positive_additions.append(
                    f"all {n} heads fully visible, no head occlusion"
                )
                result.negative_additions.append("head cut off, occluded face, hidden head")
                continue

            # no_heads_occluded_by_objects
            if rule == "no_heads_occluded_by_objects":
                result.positive_additions.append("clear view of all faces, no objects blocking faces")
                result.negative_additions.append("object covering face, hat over eyes, occlusion")
                continue

            # hands_holding_book_correctly / hands_holding_*_correctly
            holding_match = re.match(r"hands_holding_(\w+)_correctly", rule)
            if holding_match:
                obj = holding_match.group(1).replace("_", " ")
                result.positive_additions.append(
                    f"hands properly holding {obj}, correct grip, all fingers visible"
                )
                result.negative_additions.extend([
                    "malformed hands", "extra fingers", "missing fingers",
                    f"{obj} floating", f"{obj} not being held",
                ])
                result.validation_rules["hands_holding"] = obj
                continue

            # hands_have_5_fingers_each
            if rule == "hands_have_5_fingers_each":
                result.positive_additions.append("anatomically correct hands, five fingers each")
                result.negative_additions.extend([
                    "six fingers", "four fingers", "deformed hands", "mutated hands",
                ])
                continue

            # each_person_has_2_arms_2_legs
            if rule == "each_person_has_2_arms_2_legs":
                result.negative_additions.append("extra arms, extra legs, missing limbs")
                continue

            # no_merged_bodies
            if rule == "no_merged_bodies":
                result.positive_additions.append("clear separation between figures, distinct people")
                result.negative_additions.extend([
                    "merged bodies", "conjoined", "overlapping figures",
                ])
                result.validation_rules["no_merged_bodies"] = True
                continue

            # centered_subject (spatial)
            if rule == "centered_subject":
                result.composition_rules["center_subject"] = True
                result.positive_additions.append("centered composition, subject in frame center")
                result.negative_additions.append("off-center subject, poorly framed")
                continue

            # clean_background (visibility)
            if rule == "clean_background":
                result.positive_additions.append(
                    "clean background, studio lighting, professional product photo"
                )
                result.negative_additions.extend([
                    "cluttered background", "distracting elements", "harsh shadows",
                ])
                result.composition_rules["center_subject"] = result.composition_rules.get("center_subject", True)
                result.composition_rules["background_blur"] = 0.8
                result.validation_rules["clean_product_background"] = True
                continue

            # realistic_wetness_effects (physics)
            if rule == "realistic_wetness_effects":
                result.positive_additions.append("realistic rain, wet surfaces, natural wetness")
                result.negative_additions.append("dry in rain, unrealistic weather")
                continue

        # Deduplicate additions (keep order)
        def _dedup_list(lst: List[str]) -> List[str]:
            seen = set()
            out = []
            for x in lst:
                x_lower = x.lower()
                if x_lower not in seen:
                    seen.add(x_lower)
                    out.append(x)
            return out

        result.positive_additions = _dedup_list(result.positive_additions)
        result.negative_additions = _dedup_list(result.negative_additions)
        return result

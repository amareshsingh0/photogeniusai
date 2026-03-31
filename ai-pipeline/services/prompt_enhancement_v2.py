"""
Prompt Enhancement V2 - Uses Scene Graph for Ultimate Prompts.

Builds ultimate positive and negative prompts from scene graph analysis.
Task 3: Prompt enhancer for multi-person, anatomy, and constraint-aware generation.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

try:
    from .scene_graph_compiler import SceneGraphCompiler
except ImportError:
    SceneGraphCompiler = None  # type: ignore[misc, assignment]


class PromptEnhancementV2:
    """Build ultimate prompts from scene graph analysis."""

    def __init__(self, use_spacy: bool = False) -> None:
        if SceneGraphCompiler is None:
            raise RuntimeError("SceneGraphCompiler not available")
        self.scene_parser = SceneGraphCompiler(use_spacy=use_spacy)

    def enhance_prompt(self, user_prompt: str) -> Tuple[str, str]:
        """
        Convert user prompt to enhanced positive + negative prompts.

        Returns:
            (positive_prompt, negative_prompt)
        """
        scene = self.scene_parser.compile(user_prompt)
        positive = self._build_positive(user_prompt, scene)
        negative = self._build_negative(scene)
        return positive, negative

    def _build_positive(self, original: str, scene: Dict[str, Any]) -> str:
        """Build enhanced positive prompt."""
        parts = [original.strip() or "high quality scene"]

        parts.append(
            "highly detailed, photorealistic, 8k uhd, professional photography"
        )
        parts.append("sharp focus, perfect composition, masterpiece quality")

        reqs = scene.get("quality_requirements") or {}
        person_count = reqs.get("person_count_exact", 0)

        if person_count > 0:
            parts.append(f"exactly {person_count} people clearly visible")
            parts.append("every person has complete visible head and face")
            parts.append("all heads fully visible and unobscured")
            parts.append("perfect human anatomy, correct proportions")
            parts.append("anatomically correct hands with five fingers each")

            if person_count > 1:
                parts.append(f"{person_count} distinct separate individuals")
                parts.append("proper spacing between people, no merged bodies")
                parts.append("each person complete and independent")

        for constraint in scene.get("constraints", []):
            severity = getattr(constraint, "severity", None) or (
                constraint.get("severity", "medium")
                if isinstance(constraint, dict)
                else "medium"
            )
            if severity == "critical":
                rule = getattr(constraint, "rule", None) or (
                    constraint.get("rule", "") if isinstance(constraint, dict) else ""
                )
                if rule:
                    rule_desc = rule.replace("_", " ")
                    parts.append(rule_desc)

        return ", ".join(parts)

    def _build_negative(self, scene: Dict[str, Any]) -> str:
        """Build comprehensive negative prompt."""
        negatives = [
            "blurry",
            "low quality",
            "deformed",
            "disfigured",
            "ugly",
            "bad anatomy",
            "bad proportions",
            "gross proportions",
            "extra limbs",
            "missing limbs",
            "extra arms",
            "extra legs",
            "fused limbs",
            "merged bodies",
            "conjoined figures",
            "extra fingers",
            "missing fingers",
            "malformed hands",
            "fewer than 5 fingers",
            "more than 5 fingers",
            "deformed hands",
            "poorly drawn hands",
            "missing head",
            "extra heads",
            "head cut off",
            "head obscured",
            "head absorbed",
            "face cut off",
            "incomplete head",
            "head hidden",
            "no head visible",
            "headless",
        ]

        reqs = scene.get("quality_requirements") or {}
        person_count = reqs.get("person_count_exact", 0)
        if person_count > 1:
            negatives.extend(
                [
                    f"not exactly {person_count} people",
                    "people merging together",
                    "shared limbs",
                    "bodies fused",
                    "fewer people than expected",
                    "more people than expected",
                ]
            )

        return ", ".join(negatives)

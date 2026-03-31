"""
Iterative Refinement for PhotoGenius AI.
Max 5 iterations with learned fixes from Tri-Model Validation failures.
P0: Deterministic image generation — Task 5/6 bridge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Tri-Model validator result drives refinement
try:
    from .tri_model_validator import TriModelConsensus, TriModelValidator
except ImportError:
    TriModelConsensus = None  # type: ignore
    TriModelValidator = None  # type: ignore


@dataclass
class RefinementStep:
    """Single refinement step: prompt/params delta from failure analysis."""

    iteration: int
    failure_rules: List[str]
    prompt_delta: str  # extra negative/positive to add
    param_hints: Dict[str, Any]  # e.g. guidance_scale bump


@dataclass
class RefinementResult:
    """Result after up to max_iterations."""

    final_image: Any  # best image (PIL or base64)
    iterations_used: int
    steps: List[RefinementStep]
    validation_passed: bool
    best_consensus: Optional[Any] = None


# Learned fixes: rule -> (negative_add, positive_add)
LEARNED_FIXES: Dict[str, tuple] = {
    "exactly_N_heads_fully_visible": (
        "headless, head cut off, missing head, head absorbed",
        "every figure has visible head, one head per person, head visible",
    ),
    "no_heads_occluded_by_objects": (
        "head obscured, face cut off by object, umbrella covering face",
        "umbrella above head not covering face, head visible under umbrella",
    ),
    "each_person_has_2_arms_2_legs": (
        "extra arm, third arm, arm from back, extra limbs, merged limbs",
        "two arms per person, exactly two arms, natural limbs",
    ),
    "hands_have_5_fingers_each": (
        "six fingers, seven fingers, claw hands, fused fingers",
        "five fingers each hand, correct hand anatomy",
    ),
    "no_merged_bodies": (
        "merged bodies, merged figures, body merging, jumbled figures",
        "clear separation between figures, distinct persons, no merged bodies",
    ),
    "realistic_wetness_effects": (
        "dry in rain, unrealistic wetness",
        "realistic wetness, water droplets, wet fabric, wet skin",
    ),
}


def build_refinement_deltas(consensus: Any) -> RefinementStep:
    """Build prompt/param deltas from failed rules (learned fixes)."""
    if TriModelConsensus is None or not hasattr(consensus, "results"):
        return RefinementStep(
            iteration=0,
            failure_rules=[],
            prompt_delta="",
            param_hints={},
        )
    failed_rules = [r.rule for r in consensus.results if not r.passed]
    neg_parts = []
    pos_parts = []
    for rule in failed_rules:
        for key, (neg, pos) in LEARNED_FIXES.items():
            if key in rule:
                neg_parts.append(neg)
                pos_parts.append(pos)
                break
    prompt_delta = ""
    if neg_parts:
        prompt_delta += " [NEG: " + ", ".join(neg_parts[:3]) + "]"
    if pos_parts:
        prompt_delta += " [POS: " + ", ".join(pos_parts[:3]) + "]"
    param_hints: Dict[str, Any] = {}
    if failed_rules:
        param_hints["guidance_scale_bump"] = 0.5
    return RefinementStep(
        iteration=0,
        failure_rules=failed_rules,
        prompt_delta=prompt_delta.strip(),
        param_hints=param_hints,
    )


def apply_refinement_to_prompt(
    base_prompt: str,
    base_negative: str,
    step: RefinementStep,
) -> tuple:
    """Apply refinement step to prompt and negative."""
    if not step.prompt_delta:
        return base_prompt, base_negative
    neg_add = []
    pos_add = []
    for rule in step.failure_rules:
        for key, (neg, pos) in LEARNED_FIXES.items():
            if key in rule:
                neg_add.append(neg)
                pos_add.append(pos)
                break
    new_negative = base_negative
    if neg_add:
        new_negative = base_negative + ", " + ", ".join(neg_add[:2])
    new_prompt = base_prompt
    if pos_add:
        new_prompt = base_prompt + ", " + ", ".join(pos_add[:2])
    return new_prompt, new_negative

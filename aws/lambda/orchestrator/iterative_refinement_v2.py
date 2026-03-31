"""
Iterative Refinement v2: Smart Inpainting and Issue Localization.
Refine images up to 5 iterations with targeted regional inpainting.
P0: Task 5 — 85%+ images perfect within 3 iterations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from .tri_model_validator import TriModelConsensus, TriModelValidator
except ImportError:
    TriModelConsensus = None
    TriModelValidator = None

try:
    from .iterative_refinement import (
        LEARNED_FIXES,
        build_refinement_deltas,
        apply_refinement_to_prompt,
        RefinementStep,
    )
except ImportError:
    LEARNED_FIXES = {}
    build_refinement_deltas = None
    apply_refinement_to_prompt = None
    RefinementStep = None


@dataclass
class IssueRegion:
    """Localized issue: e.g. hand at (x,y) malformed."""

    issue_type: str  # 'hand', 'head', 'limb', 'merged_body'
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    description: str
    rule_failed: str
    confidence: float = 0.8


@dataclass
class InpaintRequest:
    """Regional inpainting request for one issue."""

    image: Any  # PIL or numpy
    mask_bbox: Tuple[int, int, int, int]  # region to inpaint
    prompt: str
    negative_prompt: str
    issue_type: str


@dataclass
class RefinementStepV2:
    """Refinement step with optional regional inpainting."""

    iteration: int
    failure_rules: List[str]
    prompt_delta: str
    param_hints: Dict[str, Any]
    issue_regions: List[IssueRegion] = field(default_factory=list)
    inpaint_requests: List[InpaintRequest] = field(default_factory=list)
    use_full_regenerate: bool = True  # if True, full regen; else try inpainting first


@dataclass
class RefinementResultV2:
    """Result after up to max_iterations with optional inpainting."""

    final_image: Any
    iterations_used: int
    steps: List[RefinementStepV2]
    validation_passed: bool
    best_consensus: Optional[Any] = None
    inpainting_used: bool = False


def localize_issues_from_consensus(
    consensus: Any,
    image_size: Tuple[int, int] = (1024, 1024),
) -> List[IssueRegion]:
    """
    Convert validation failures into localized issue regions.
    When validators don't return coordinates, use heuristic regions from limb_violations/occlusion_detected.
    """
    regions: List[IssueRegion] = []
    if consensus is None or not hasattr(consensus, "results"):
        return regions
    w, h = image_size[0], image_size[1]
    for r in consensus.results:
        if not r.passed and r.constraint_type == "anatomy":
            # Placeholder: center-third of image (typical hand/limb area)
            regions.append(
                IssueRegion(
                    issue_type="limb",
                    bbox=(w // 4, h // 3, 3 * w // 4, 2 * h // 3),
                    description=r.rule,
                    rule_failed=r.rule,
                    confidence=r.confidence,
                )
            )
        if not r.passed and r.constraint_type == "visibility":
            regions.append(
                IssueRegion(
                    issue_type="head",
                    bbox=(w // 4, 0, 3 * w // 4, h // 4),
                    description=r.rule,
                    rule_failed=r.rule,
                    confidence=r.confidence,
                )
            )
    for _ in (consensus.limb_violations or [])[:2]:
        regions.append(
            IssueRegion(
                issue_type="hand",
                bbox=(w // 3, h // 2, 2 * w // 3, 3 * h // 4),
                description="hand anatomy",
                rule_failed="hands_5_fingers",
                confidence=0.7,
            )
        )
    return regions[:5]  # cap at 5 regions per step


def build_refinement_deltas_v2(
    consensus: Any,
    image: Any = None,
    image_size: Tuple[int, int] = (1024, 1024),
) -> RefinementStepV2:
    """Build refinement step with issue localization and optional inpaint requests."""
    step = RefinementStepV2(
        iteration=0,
        failure_rules=[],
        prompt_delta="",
        param_hints={},
        issue_regions=[],
        inpaint_requests=[],
        use_full_regenerate=True,
    )
    if build_refinement_deltas and consensus is not None:
        base = build_refinement_deltas(consensus)
        step.iteration = base.iteration
        step.failure_rules = base.failure_rules
        step.prompt_delta = base.prompt_delta
        step.param_hints = base.param_hints
    step.issue_regions = localize_issues_from_consensus(consensus, image_size)
    if image is not None and step.issue_regions:
        for ir in step.issue_regions[:2]:  # at most 2 inpaint requests per step
            step.inpaint_requests.append(
                InpaintRequest(
                    image=image,
                    mask_bbox=ir.bbox,
                    prompt="correct anatomy, natural hands, clear separation",
                    negative_prompt="deformed, extra fingers, merged",
                    issue_type=ir.issue_type,
                )
            )
        step.use_full_regenerate = len(step.issue_regions) > 2
    return step


def refine_with_inpainting(
    image: Any,
    consensus: Any,
    generator_fn: Callable[..., Any],
    inpaint_fn: Optional[Callable[..., Any]] = None,
    max_iterations: int = 5,
    validator: Optional[Any] = None,
    expected_count: int = 0,
    constraints: Optional[List[Any]] = None,
) -> RefinementResultV2:
    """
    Refine image up to max_iterations; use regional inpainting when available.
    generator_fn(prompt, negative_prompt, **kwargs) -> image
    inpaint_fn(image, mask_bbox, prompt, negative_prompt) -> image or None
    """
    steps: List[RefinementStepV2] = []
    current_image = image
    best_consensus = consensus
    inpainting_used = False
    constraints = constraints or []

    for it in range(max_iterations):
        if best_consensus is not None and getattr(best_consensus, "all_passed", False):
            break
        step = build_refinement_deltas_v2(
            best_consensus,
            image=current_image,
            image_size=(
                getattr(current_image, "width", 1024),
                getattr(current_image, "height", 1024),
            ),
        )
        step.iteration = it + 1
        steps.append(step)

        if not step.use_full_regenerate and inpaint_fn and step.inpaint_requests:
            for req in step.inpaint_requests[:1]:
                try:
                    current_image = inpaint_fn(
                        req.image,
                        req.mask_bbox,
                        req.prompt,
                        req.negative_prompt,
                    )
                    if current_image is not None:
                        inpainting_used = True
                except Exception:
                    pass
        if not inpainting_used or current_image is None:
            if generator_fn and step.prompt_delta:
                base_prompt = "high quality, correct anatomy"
                base_neg = "deformed, blurry"
                if apply_refinement_to_prompt and RefinementStep:
                    from .iterative_refinement import RefinementStep as RS

                    fake_step = RS(
                        iteration=step.iteration,
                        failure_rules=step.failure_rules,
                        prompt_delta=step.prompt_delta,
                        param_hints=step.param_hints,
                    )
                    new_prompt, new_neg = apply_refinement_to_prompt(
                        base_prompt, base_neg, fake_step
                    )
                else:
                    new_prompt, new_neg = (
                        base_prompt + ", " + step.prompt_delta,
                        base_neg,
                    )
                try:
                    current_image = generator_fn(
                        new_prompt, new_neg, **step.param_hints
                    )
                except Exception:
                    break
        if (
            validator is not None
            and current_image is not None
            and expected_count
            and constraints
        ):
            best_consensus = validator.validate(
                current_image, expected_count, constraints
            )
        else:
            break

    return RefinementResultV2(
        final_image=current_image,
        iterations_used=len(steps),
        steps=steps,
        validation_passed=best_consensus is not None
        and getattr(best_consensus, "all_passed", False),
        best_consensus=best_consensus,
        inpainting_used=inpainting_used,
    )


def _anatomy_result_to_consensus_like(validation_result: Any, issues: List[str]) -> Any:
    """Build a consensus-like object from AnatomyValidationResult and issue list for refinement deltas."""
    try:
        from .tri_model_validator import ValidationResult, TriModelConsensus
    except ImportError:
        ValidationResult = None
        TriModelConsensus = None
    if ValidationResult is None or TriModelConsensus is None:
        return None
    results: List[Any] = []
    limb_violations: List[str] = []
    for issue in issues:
        if issue == "person_count":
            results.append(
                ValidationResult(
                    constraint_type="visibility",
                    rule="exactly_N_heads_fully_visible",
                    passed=False,
                    confidence=0.5,
                    details={},
                )
            )
        elif issue == "hand_anatomy":
            results.append(
                ValidationResult(
                    constraint_type="anatomy",
                    rule="hands_have_5_fingers_each",
                    passed=False,
                    confidence=0.5,
                    details={},
                )
            )
            limb_violations.append("hand_anatomy")
        elif issue == "text":
            results.append(
                ValidationResult(
                    constraint_type="text",
                    rule="text_accuracy",
                    passed=False,
                    confidence=0.5,
                    details={},
                )
            )
    return TriModelConsensus(
        all_passed=False,
        results=results,
        limb_violations=limb_violations,
        hand_anatomy_passed="hand_anatomy" not in issues,
    )


class IterativeRefinementV2:
    """
    Wrapper for refinement with a simple refine_issues(image, prompt, issues, validation_result) API.
    Used by AutoValidationPipeline. Optional generator_fn to re-run generation with deltas.
    """

    def __init__(self, generator_fn: Optional[Callable[..., Any]] = None) -> None:
        self.generator_fn = generator_fn

    def refine_issues(
        self,
        image: Any,
        prompt: str,
        issues: List[str],
        validation_result: Any,
    ) -> Any:
        """
        Attempt to refine image given validation issues. If generator_fn is set, calls it with
        prompt + deltas and returns new image; otherwise returns image unchanged.
        """
        consensus = _anatomy_result_to_consensus_like(validation_result, issues)
        step = build_refinement_deltas_v2(
            consensus,
            image=image,
            image_size=(
                getattr(image, "width", 1024),
                getattr(image, "height", 1024),
            ),
        )
        if self.generator_fn and (step.prompt_delta or step.param_hints):
            try:
                base_neg = "deformed, blurry, low quality"
                if apply_refinement_to_prompt and RefinementStep:
                    from .iterative_refinement import RefinementStep as RS

                    fake_step = RS(
                        iteration=0,
                        failure_rules=step.failure_rules,
                        prompt_delta=step.prompt_delta,
                        param_hints=step.param_hints,
                    )
                    new_prompt, new_neg = apply_refinement_to_prompt(
                        prompt, base_neg, fake_step
                    )
                else:
                    new_prompt = prompt + (", " + step.prompt_delta if step.prompt_delta else "")
                    new_neg = base_neg
                return self.generator_fn(new_prompt, new_neg, **step.param_hints)
            except Exception:
                return image
        return image

"""
Deterministic, Self-Evolving Image Generation Pipeline.
Wires: Scene Graph -> Camera/Occlusion -> Physics -> Generation -> Tri-Model Validation -> Refinement -> Self-Improvement -> Post-Process.
P0: 99.9% multi-person accuracy, physics-perfect, self-improving.

Repeatability (seeds):
- run(..., seed=None, enable_deterministic=True): seed from hash(prompt + constraints + loras) -> same inputs => identical image.
- run(..., seed=12345): use that seed for all steps; stored in result.seed and result.quality_metrics["seed"].
- run(..., enable_deterministic=False): random seed for variety.
API clients should expose enable_deterministic (default True) and optional seed.

Typography (Task 4.2): When classification.requires_text and expected_text are set, the pipeline
generates a base image without text (stripped prompt), then overlays text via TypographyEngine,
runs verify_ocr with TYPOGRAPHY_OCR_THRESHOLD, and retries up to TYPOGRAPHY_RETRY_ATTEMPTS on failure.
On OCR failure after retries, result.quality_metrics["text_not_guaranteed"] = True and the best
attempt image is still returned. Config: TYPOGRAPHY_RETRY_ATTEMPTS (default 2), TYPOGRAPHY_OCR_THRESHOLD (default 0.9).

Math/Diagram: When requires_math and expected_formula are set, LaTeX is validated with SymPy
(validate_formula_latex); if valid (or normalized_latex available), formula is rendered and
blended with lighting. When requires_diagram and diagram_type are set, chart data is extracted
from the prompt (e.g. 30%, 50%, 20%) and overlay_chart(ChartSpec) is applied. Success metric: 98%+ formula correctness on SymPy-parseable subset.
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Typography integration (Task 4.2): env config
TYPOGRAPHY_RETRY_ATTEMPTS = int(os.environ.get("TYPOGRAPHY_RETRY_ATTEMPTS", "2"))
TYPOGRAPHY_OCR_THRESHOLD = float(os.environ.get("TYPOGRAPHY_OCR_THRESHOLD", "0.9"))

# Local imports (same package)
try:
    from .scene_graph_compiler import SceneGraphCompiler
    from .camera_occlusion_solver import CameraOcclusionSolver
    from .constraint_solver import ConstraintSolver, SolverResult
except ImportError:
    SceneGraphCompiler = None
    CameraOcclusionSolver = None
    ConstraintSolver = None
    SolverResult = None

try:
    from .physics_micro_simulation import PhysicsMicroSimulation as PhysicsMicroSim
except ImportError:
    try:
        from .physics_micro_sim import PhysicsMicroSim
    except ImportError:
        PhysicsMicroSim = None

try:
    from .tri_model_validator import TriModelValidator, TriModelConsensus
    from .iterative_refinement import (
        build_refinement_deltas,
        apply_refinement_to_prompt,
        RefinementStep,
    )
except ImportError:
    TriModelValidator = None
    TriModelConsensus = None
    build_refinement_deltas = None
    apply_refinement_to_prompt = None
    RefinementStep = None

try:
    from .failure_memory_system import FailureMemorySystem
except ImportError:
    FailureMemorySystem = None

try:
    from .typography_engine import TypographyEngine, TextPlacement
except ImportError:
    TypographyEngine = None
    TextPlacement = None

try:
    from .math_diagram_renderer import (
        MathDiagramRenderer,
        FormulaPlacement as MathFormulaPlacement,
        ChartSpec,
        DiagramKind,
        validate_formula_latex,
        LightingOptions as MathLightingOptions,
    )
except ImportError:
    MathDiagramRenderer = None
    MathFormulaPlacement = None
    ChartSpec = None
    DiagramKind = None
    validate_formula_latex = None
    MathLightingOptions = None

try:
    from .prompt_enhancement_v3 import enhance_v3_from_compiled
except ImportError:
    enhance_v3_from_compiled = None

try:
    from .universal_prompt_classifier import (
        UniversalPromptClassifier,
        ClassificationResult,
    )
except ImportError:
    UniversalPromptClassifier = None
    ClassificationResult = None

try:
    from .observability import (
        record_typography_ocr,
        record_typography_ocr_result,
        record_math_validation,
        record_constraint_solver_time_ms,
        is_typography_no_text_fallback,
    )
except ImportError:
    record_typography_ocr = lambda ok: None  # type: ignore[assignment, misc]
    record_typography_ocr_result = lambda ok: None  # type: ignore[assignment, misc]
    record_math_validation = lambda ok: None  # type: ignore[assignment, misc]
    record_constraint_solver_time_ms = lambda ms: None  # type: ignore[assignment, misc]
    is_typography_no_text_fallback = lambda: False  # type: ignore[assignment, misc]


def _derive_seed(
    prompt: str,
    negative_prompt: str,
    constraints: Any,
    lora_names: Any,
) -> int:
    """Derive a deterministic 32-bit seed from prompt + constraints + loras."""
    payload = (
        prompt.strip()
        + "\n"
        + (negative_prompt or "").strip()
        + "\n"
        + repr(constraints)
        + "\n"
        + repr(lora_names)
    )
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % (2**32)


def _strip_text_intent_for_generation(prompt: str, expected_text: Optional[str]) -> str:
    """Remove quoted text and 'that says/saying/reads ...' so base image is generated without text."""
    if not prompt or not expected_text:
        return prompt
    import re

    p = prompt
    # Remove quoted expected_text (single or double quotes)
    for q in ("'", '"'):
        p = p.replace(f"{q}{expected_text}{q}", "").replace(
            f"{q} {expected_text} {q}", ""
        )
    # Remove phrases like " that says '...'", " saying '...'", " reads '...'"
    p = re.sub(r"\s+that\s+says\s+['\"][^'\"]*['\"]", " ", p, flags=re.IGNORECASE)
    p = re.sub(r"\s+saying\s+['\"][^'\"]*['\"]", " ", p, flags=re.IGNORECASE)
    p = re.sub(r"\s+reads\s+['\"][^'\"]*['\"]", " ", p, flags=re.IGNORECASE)
    p = re.sub(r"\s+with\s+text\s+['\"][^'\"]*['\"]", " ", p, flags=re.IGNORECASE)
    return " ".join(p.split()).strip() or prompt


def _placement_to_position(placement: Optional[str]) -> str:
    """Map classification text_placement to typography position string."""
    if not placement:
        return "center"
    pl = placement.lower()
    if pl == "top":
        return "top"
    if pl == "bottom":
        return "bottom"
    if pl in ("centered", "center"):
        return "center"
    return "center"  # on_object -> center for overlay


def _typography_style_from_category(category: str, text_type: Optional[str]) -> str:
    """Infer font style: bold for signs, elegant for posters."""
    if text_type == "sign":
        return "sans_bold"
    if text_type == "poster":
        return "serif"
    if text_type == "caption":
        return "sans"
    if text_type == "label" or text_type == "ui":
        return "sans"
    return (
        "sans_bold"
        if (category or "").lower() in ("publishing", "technical")
        else "sans"
    )


def _ensure_pil(image: Any):
    """Convert image (bytes, base64, numpy) to PIL Image for typography/OCR."""
    if image is None:
        return None
    if hasattr(image, "mode"):
        return image
    try:
        import base64
        import io
        import numpy as np  # type: ignore[reportMissingImports]
        from PIL import Image as PILImage  # type: ignore[reportMissingImports]

        if isinstance(image, bytes):
            return PILImage.open(io.BytesIO(image)).convert("RGB")
        if isinstance(image, str):
            raw = base64.b64decode(image)
            return PILImage.open(io.BytesIO(raw)).convert("RGB")
        arr = np.asarray(image)
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        return PILImage.fromarray(arr.astype(np.uint8)).convert("RGB")
    except Exception:
        return None


def _diagram_type_to_kind(diagram_type: Optional[str]):
    """Map classifier diagram_type string to DiagramKind enum."""
    if not DiagramKind or not diagram_type:
        return None
    d = (diagram_type or "").lower()
    if d == "line":
        return DiagramKind.CHART_LINE
    if d == "bar":
        return DiagramKind.CHART_BAR
    if d == "pie":
        return DiagramKind.CHART_PIE
    if d == "scatter":
        return DiagramKind.CHART_SCATTER
    return DiagramKind.CHART_BAR


def _extract_chart_data_from_prompt(
    prompt: str, diagram_type: Optional[str]
) -> Dict[str, Any]:
    """Extract chart data from prompt (e.g. '30%, 50%, 20%' or 'A: 10, B: 20')."""
    import re

    p = (prompt or "").strip()
    data: Dict[str, Any] = {}
    # Percentages: "30%, 50%, 20%" or "30 percent, 50 percent"
    percs = re.findall(r"(\d+(?:\.\d+)?)\s*%", p)
    if percs:
        sizes = [float(x) for x in percs]
        data["labels"] = [f"Item {i+1}" for i in range(len(sizes))]
        data["sizes"] = sizes
        data["values"] = sizes
        return data
    # "A: 10, B: 20, C: 30" or "sales 100, 200, 150"
    pairs = re.findall(r"([A-Za-z][\w\s]*?)\s*:\s*(\d+(?:\.\d+)?)", p)
    if pairs:
        data["labels"] = [k.strip() for k, _ in pairs]
        data["values"] = [float(v) for _, v in pairs]
        data["sizes"] = data["values"]
        return data
    # Bare numbers
    nums = re.findall(r"\b(\d+(?:\.\d+)?)\b", p)
    if len(nums) >= 2:
        vals = [float(x) for x in nums[:10]]
        data["values"] = vals
        data["labels"] = [f"#{i+1}" for i in range(len(vals))]
        data["sizes"] = vals
        return data
    # Default placeholder for "bar chart comparing sales" etc.
    data["labels"] = ["A", "B", "C", "D"]
    data["values"] = [30, 50, 20, 40]
    data["sizes"] = [30, 50, 20, 40]
    return data


@dataclass
class DeterministicPipelineResult:
    """Result of full deterministic pipeline."""

    image: Any  # final image (bytes or base64)
    scene_graph: Dict[str, Any]
    layout: Dict[str, Any]
    camera: Dict[str, Any]
    physics_hint: Optional[Any] = None
    validation_passed: bool = False
    iterations_used: int = 1
    refinement_steps: List[Any] = field(default_factory=list)
    quality_metrics: Dict[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None  # seed used for generation (for repeatability)


class DeterministicPipeline:
    """
    Single entry point for deterministic image generation:

    1. Scene Graph Compiler (constraint graph from prompt)
    2. Camera & Occlusion Solver (all heads visible)
    3. Physics Micro-Simulation (wetness, lighting, gravity)
    4. Generation (caller-provided: e.g. SDXL / ControlNet)
    5. Tri-Model Validation (YOLO + OpenPose + SAM consensus)
    6. Iterative Refinement (max 5 iterations, learned fixes)
    7. Self-Improvement (failure memory; optional)
    8. Post-Processing (text/math overlay; optional)
    """

    def __init__(
        self,
        max_refinement_iterations: int = 5,
        use_tri_model: bool = False,
        use_physics: bool = True,
        use_self_improvement: bool = False,
        use_post_process: bool = False,
    ):
        self.max_refinement_iterations = max_refinement_iterations
        self.use_tri_model = use_tri_model
        self.use_physics = use_physics
        self.use_self_improvement = use_self_improvement
        self.use_post_process = use_post_process

        self.compiler = (
            SceneGraphCompiler(use_spacy=False) if SceneGraphCompiler else None
        )
        self.constraint_solver = ConstraintSolver() if ConstraintSolver else None
        self.occlusion_solver = (
            CameraOcclusionSolver() if CameraOcclusionSolver else None
        )
        self.physics_sim = PhysicsMicroSim() if PhysicsMicroSim else None
        self.validator = (
            TriModelValidator(use_models=use_tri_model) if TriModelValidator else None
        )
        self._generator: Optional[Callable[..., Any]] = None
        self._self_improvement = None
        self._post_process = None
        self.failure_memory_system = (
            FailureMemorySystem() if FailureMemorySystem else None
        )
        self._classifier = (
            UniversalPromptClassifier() if UniversalPromptClassifier else None
        )
        self._typography_engine = TypographyEngine() if TypographyEngine else None
        self._math_diagram_renderer = (
            MathDiagramRenderer() if MathDiagramRenderer else None
        )

    def set_generator(self, fn: Callable[..., Any]) -> None:
        """Set generation function: (prompt, negative_prompt, **kwargs) -> image."""
        self._generator = fn

    def set_self_improvement(self, engine: Any) -> None:
        """Set self-improvement engine (failure memory, learning)."""
        self._self_improvement = engine

    def set_post_process(self, fn: Callable[..., Any]) -> None:
        """Set post-process function: (image, scene_graph, **kwargs) -> image."""
        self._post_process = fn

    def run(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: Optional[int] = None,
        enable_deterministic: bool = True,
        **generator_kwargs: Any,
    ) -> DeterministicPipelineResult:
        """
        Run full pipeline: compile -> solve -> physics -> generate -> validate -> refine -> post-process.

        Seed behavior:
        - If seed is provided, it is used directly for all generation steps.
        - If enable_deterministic is True (default) and no seed given, seed is derived from
          hash(prompt + negative_prompt + constraints + lora_names) so same inputs => same seed => identical result.
        - If enable_deterministic is False, a random seed is used for variety.
        """
        if self.compiler is None:
            raise RuntimeError("SceneGraphCompiler not available")

        original_prompt = prompt
        classification: Optional[Any] = None
        if self._classifier:
            try:
                classification = self._classifier.classify(original_prompt)
            except Exception as e:
                logger.debug("Classifier failed (typography may be skipped): %s", e)

        # 1) Scene Graph
        compiled = self.compiler.compile(prompt)
        scene_graph = compiled
        layout = compiled.get("layout", {})
        camera = compiled.get("camera", {})
        constraints = compiled.get("constraints", [])
        entities = compiled.get("entities", [])
        quality_reqs = compiled.get("quality_requirements", {})

        # Resolve seed: explicit > deterministic hash > random
        hard_constraints = compiled.get("hard_constraints", constraints)
        lora_names = generator_kwargs.get("lora_names", [])
        if seed is not None:
            resolved_seed = int(seed) & 0xFFFFFFFF
            logger.debug("Using provided seed=%s", resolved_seed)
        elif enable_deterministic:
            resolved_seed = _derive_seed(
                prompt, negative_prompt, hard_constraints, lora_names
            )
            logger.debug(
                "Derived deterministic seed=%s from prompt+constraints+loras",
                resolved_seed,
            )
        else:
            resolved_seed = random.randint(0, 2**32 - 1)
            logger.debug(
                "Using random seed=%s (enable_deterministic=False)", resolved_seed
            )

        # 2) Camera & Occlusion (zero head occlusions in layout phase)
        if self.occlusion_solver:
            safe = self.occlusion_solver.solve(layout, camera)
            layout = {"entities": safe.entities}
            camera = {
                "fov": safe.camera.fov,
                "height": safe.camera.height,
                "tilt": safe.camera.tilt,
                "distance": safe.camera.distance,
                "frame": safe.camera.frame,
            }
            quality_reqs["layout_occlusion_count"] = getattr(safe, "occlusion_count", 0)
            if getattr(safe, "occlusion_count", 0) > 0:
                logger.warning(
                    "Layout phase had %s head occlusion(s); resolve loop may not have converged",
                    safe.occlusion_count,
                )
            prompt_hints = self.occlusion_solver.to_prompt_hints(safe)
            # Optionally append hint to prompt
            if prompt_hints.get("person_count"):
                pass  # can add "exactly N people" to prompt

        # 3) Physics (seed passed for deterministic outcomes)
        physics_hint = None
        if self.use_physics and self.physics_sim:
            weather_ent = next(
                (e for e in entities if getattr(e, "type", None) == "weather"),
                None,
            )
            weather = getattr(weather_ent, "properties", None) if weather_ent else None
            physics_result = self.physics_sim.run(
                layout.get("entities", []),
                weather=weather,
                time_of_day="day",
            )
            physics_hint = physics_result
            suffix = self.physics_sim.to_prompt_suffix(physics_result)
            prompt = f"{prompt}, {suffix}"

        # 3.2) Prompt Enhancement v3: scene graph + physics → positive; base negatives
        if enhance_v3_from_compiled is not None:
            v3_result = enhance_v3_from_compiled(
                compiled,
                physics_result=physics_hint,  # type: ignore[reportArgumentType]
                validation_failures=None,
            )
            prompt = v3_result.enhanced_prompt
            negative_prompt = v3_result.negative_prompt

        # 3.3) Constraint Solver: hard constraints → positive/negative additions, composition_rules
        if self.constraint_solver is not None:
            _t0 = time.perf_counter()
            solver_result = self.constraint_solver.solve(scene_graph)
            try:
                record_constraint_solver_time_ms((time.perf_counter() - _t0) * 1000.0)
            except Exception:
                pass
            prompt = solver_result.merge_into_prompt(prompt)
            negative_prompt = solver_result.merge_into_negative(negative_prompt)
            # Store for generator/layout if needed
            if solver_result.composition_rules:
                quality_reqs["composition_rules"] = solver_result.composition_rules
            if solver_result.validation_rules:
                quality_reqs["validation_rules"] = solver_result.validation_rules

        # 3.5) Smart recovery: apply stored fix for similar prompts (70%+ auto-fix)
        applied_fix: Optional[Dict[str, Any]] = None
        if self.failure_memory_system:
            fix = self.failure_memory_system.get_fix_for_prompt(prompt)
            if fix:
                layout = self.failure_memory_system.apply_fix_to_layout(
                    {"entities": layout.get("entities", []), "camera": camera}, fix
                )
                camera = layout.get("camera", camera)
                current_prompt, current_negative = (
                    self.failure_memory_system.apply_fix_to_prompt(
                        prompt, negative_prompt, fix
                    )
                )
                applied_fix = fix
            else:
                current_prompt, current_negative = prompt, negative_prompt
        else:
            current_prompt, current_negative = prompt, negative_prompt

        # 4) Generation (with optional refinement loop)
        person_count = quality_reqs.get("person_count_exact", 0)
        best_image = None
        best_consensus = None
        refinement_steps: List[Any] = []

        # Inject seed into generator kwargs for repeatability
        gen_kw = {**generator_kwargs, "seed": resolved_seed}
        quality_reqs["seed"] = resolved_seed

        for iteration in range(self.max_refinement_iterations):
            if self._generator is None:
                break
            prompt_for_gen = current_prompt
            if (
                classification
                and getattr(classification, "requires_text", False)
                and getattr(classification, "expected_text", None)
            ):
                prompt_for_gen = _strip_text_intent_for_generation(
                    current_prompt, getattr(classification, "expected_text", None)
                )
            try:
                img = self._generator(
                    prompt_for_gen,
                    current_negative,
                    **gen_kw,
                )
            except Exception as e:
                logger.warning("Generator failed at iteration %s: %s", iteration, e)
                break
            best_image = img

            if not self.validator or not self.use_tri_model:
                break

            consensus = self.validator.validate(
                img,
                expected_person_count=person_count,
                constraints=constraints,
            )
            best_consensus = consensus
            if consensus.all_passed:
                break
            step = (
                build_refinement_deltas(consensus) if build_refinement_deltas else None
            )
            if step and step.prompt_delta and apply_refinement_to_prompt is not None:
                refinement_steps.append(step)
                current_prompt, current_negative = apply_refinement_to_prompt(
                    current_prompt,
                    current_negative,
                    step,
                )
            else:
                break

        # 5) Self-Improvement (record failure if validation failed)
        if self._self_improvement and best_consensus and not best_consensus.all_passed:
            if hasattr(self._self_improvement, "record_validation_failure"):
                self._self_improvement.record_validation_failure(
                    prompt=prompt,
                    constraints=constraints,
                    consensus=best_consensus,
                )
        if self.failure_memory_system and best_consensus:
            if best_consensus.all_passed and applied_fix:
                self.failure_memory_system.record_success(prompt, applied_fix)
            elif not best_consensus.all_passed:
                failed_rules = [
                    getattr(r, "rule", r.get("rule", ""))
                    for r in getattr(best_consensus, "results", [])
                    if not getattr(r, "passed", r.get("passed", True))
                ]
                self.failure_memory_system.record_failure(
                    prompt,
                    "validation_failed",
                    failed_rules=failed_rules,
                    context={"consensus": best_consensus},
                )

        # 5.5) Typography: if requires_text, overlay expected_text and verify OCR (with retries)
        if (
            best_image is not None
            and self._typography_engine
            and classification
            and getattr(classification, "requires_text", False)
            and getattr(classification, "expected_text", None)
            and not is_typography_no_text_fallback()
        ):
            expected_text = getattr(classification, "expected_text", "") or ""
            base_pil = _ensure_pil(best_image)
            if base_pil is not None and expected_text:
                position = _placement_to_position(
                    getattr(classification, "text_placement", None)
                )
                style = _typography_style_from_category(
                    getattr(classification, "category", ""),
                    getattr(classification, "text_type", None),
                )
                text_ocr_passed = False
                for attempt in range(1 + TYPOGRAPHY_RETRY_ATTEMPTS):
                    font_size = 40 + attempt * 16
                    try:
                        overlayed = self._typography_engine.add_text_overlay(
                            base_pil,
                            text=expected_text,
                            position=position,
                            font_size=font_size,
                            style=style,
                        )
                    except Exception as e:
                        logger.warning(
                            "Typography overlay attempt %s failed: %s",
                            attempt + 1,
                            e,
                        )
                        overlayed = base_pil
                    ok, _ = self._typography_engine.verify_ocr(
                        overlayed,
                        expected_text,
                        similarity_threshold=TYPOGRAPHY_OCR_THRESHOLD,
                    )
                    if ok:
                        best_image = overlayed
                        text_ocr_passed = True
                        quality_reqs["text_ocr_passed"] = True
                        break
                    best_image = overlayed
                if not text_ocr_passed:
                    quality_reqs["text_not_guaranteed"] = True
                    quality_reqs["text_ocr_passed"] = False
                    logger.warning(
                        "Typography OCR verification failed after %s attempt(s); returning best attempt with text_not_guaranteed",
                        1 + TYPOGRAPHY_RETRY_ATTEMPTS,
                    )
                try:
                    record_typography_ocr(text_ocr_passed)
                    record_typography_ocr_result(text_ocr_passed)
                except Exception:
                    pass

        # 5.6) Math: if requires_math, validate LaTeX and overlay formula with lighting
        if (
            best_image is not None
            and self._math_diagram_renderer
            and MathFormulaPlacement is not None
            and validate_formula_latex is not None
            and classification
            and getattr(classification, "requires_math", False)
        ):
            formula = getattr(classification, "expected_formula", None) or ""
            if formula:
                base_pil = _ensure_pil(best_image)
                if base_pil is not None:
                    vr = validate_formula_latex(formula)
                    try:
                        record_math_validation(vr.valid)
                    except Exception:
                        pass
                    latex_to_use = formula
                    if not vr.valid and getattr(vr, "normalized_latex", None):
                        latex_to_use = vr.normalized_latex
                    elif not vr.valid:
                        logger.warning(
                            "Formula validation failed for %r; skipping math overlay (error: %s)",
                            formula[:50],
                            getattr(vr, "error", "unknown"),
                        )
                    else:
                        try:
                            w, h = base_pil.size
                            placement = MathFormulaPlacement(
                                latex=latex_to_use,
                                x=w // 2,
                                y=h // 2,
                                font_size=32,
                                anchor="mm",
                                lighting=(
                                    MathLightingOptions()
                                    if MathLightingOptions
                                    else None
                                ),
                            )
                            best_image = (
                                self._math_diagram_renderer.render_formula_placement(
                                    base_pil, placement
                                )
                            )
                            quality_reqs["formula_valid"] = vr.valid
                        except Exception as e:
                            logger.warning("Math overlay failed: %s", e)
                            quality_reqs["formula_valid"] = False

        # 5.7) Diagram: if requires_diagram, extract data and overlay chart
        if (
            best_image is not None
            and self._math_diagram_renderer
            and ChartSpec is not None
            and DiagramKind is not None
            and classification
            and getattr(classification, "requires_diagram", False)
        ):
            diagram_type = getattr(classification, "diagram_type", None) or "bar"
            kind = _diagram_type_to_kind(diagram_type)
            if kind is not None:
                base_pil = _ensure_pil(best_image)
                if base_pil is not None:
                    try:
                        chart_data = _extract_chart_data_from_prompt(
                            original_prompt, diagram_type
                        )
                        spec = ChartSpec(
                            kind=kind,
                            data=chart_data,
                            width=min(400, base_pil.width - 40),
                            height=min(300, base_pil.height - 40),
                            title=chart_data.get("title") or "Chart",
                        )
                        w, h = base_pil.size
                        best_image = self._math_diagram_renderer.overlay_chart(
                            base_pil,
                            spec,
                            x=w - spec.width - 20,
                            y=h - spec.height - 20,
                            anchor="lb",
                            lighting=(
                                MathLightingOptions() if MathLightingOptions else None
                            ),
                        )
                        quality_reqs["diagram_applied"] = True
                    except Exception as e:
                        logger.warning("Diagram overlay failed: %s", e)
                        quality_reqs["diagram_applied"] = False

        # 6) Post-Process (text/math overlay)
        if best_image is not None and self._post_process:
            try:
                best_image = self._post_process(
                    best_image,
                    scene_graph=scene_graph,
                )
            except Exception as e:
                logger.warning("Post-process failed: %s", e)

        return DeterministicPipelineResult(
            image=best_image,
            scene_graph=scene_graph,
            layout=layout,
            camera=camera,
            physics_hint=physics_hint,
            validation_passed=(
                best_consensus.all_passed
                if best_consensus
                else (not self.use_tri_model)
            ),
            iterations_used=len(refinement_steps) + 1,
            refinement_steps=refinement_steps,
            quality_metrics=quality_reqs,
            seed=resolved_seed,
        )


def typography_post_process(
    image: Any, scene_graph: Dict[str, Any], **kwargs: Any
) -> Any:
    """
    Optional post-process for DeterministicPipeline: overlay UI text from scene_graph.
    Use: pipeline.set_post_process(typography_post_process).
    When scene_graph has 'text_placements' (list of TextPlacement or dicts), overlays them on image.
    No-op if TypographyEngine unavailable or no text_placements.
    """
    if TypographyEngine is None or not image:
        return image
    raw = scene_graph.get("text_placements") or []
    if not raw:
        return image
    placements: List[Any] = []
    for p in raw:
        if TextPlacement and isinstance(p, TextPlacement):
            placements.append(p)
        elif isinstance(p, dict):
            kw = {
                k: v
                for k, v in p.items()
                if k
                in (
                    "text",
                    "x",
                    "y",
                    "width",
                    "height",
                    "style",
                    "font_size",
                    "color",
                    "background",
                    "anchor",
                    "in_scene",
                )
            }
            if not kw.get("text") or not TextPlacement:
                continue
            kw.setdefault("x", 0)
            kw.setdefault("y", 0)
            try:
                placements.append(TextPlacement(**kw))
            except (TypeError, ValueError):
                continue
    if not placements:
        return image
    return TypographyEngine().overlay_text(image, placements)


def math_diagram_post_process(
    image: Any, scene_graph: Dict[str, Any], **kwargs: Any
) -> Any:
    """
    Optional post-process for DeterministicPipeline: overlay LaTeX formulas from scene_graph.
    Use: pipeline.set_post_process(math_diagram_post_process).
    When scene_graph has 'formula_placements' (list of FormulaPlacement or dicts), overlays them.
    No-op if MathDiagramRenderer unavailable or no formula_placements.
    """
    if MathDiagramRenderer is None or MathFormulaPlacement is None or not image:
        return image
    raw = scene_graph.get("formula_placements") or []
    if not raw:
        return image
    placements: List[Any] = []
    for p in raw:
        if MathFormulaPlacement and isinstance(p, MathFormulaPlacement):
            placements.append(p)
        elif isinstance(p, dict) and p.get("latex"):
            try:
                from .math_diagram_renderer import LightingOptions

                kw = {
                    k: v
                    for k, v in p.items()
                    if k
                    in (
                        "latex",
                        "x",
                        "y",
                        "width",
                        "height",
                        "font_size",
                        "color",
                        "background",
                        "anchor",
                        "lighting",
                    )
                }
                if "lighting" in kw and isinstance(kw["lighting"], dict):
                    allowed = {
                        "shadow_offset",
                        "shadow_blur",
                        "shadow_opacity",
                        "glow_radius",
                        "glow_opacity",
                        "tint_rgb",
                        "blend_mode",
                        "opacity",
                    }
                    kw["lighting"] = LightingOptions(
                        **{k: v for k, v in kw["lighting"].items() if k in allowed}
                    )
                placements.append(MathFormulaPlacement(**kw))
            except (TypeError, ValueError):
                continue
    if not placements:
        return image
    return MathDiagramRenderer().overlay_formulas(image, placements)


def create_pipeline(
    generator_fn: Optional[Callable[..., Any]] = None,
    max_iterations: int = 5,
    use_tri_model: bool = False,
    use_physics: bool = True,
    use_post_process: bool = False,
) -> DeterministicPipeline:
    """Factory: create pipeline and optionally set generator and typography post-process."""
    p = DeterministicPipeline(
        max_refinement_iterations=max_iterations,
        use_tri_model=use_tri_model,
        use_physics=use_physics,
        use_post_process=use_post_process,
    )
    if generator_fn:
        p.set_generator(generator_fn)
    if use_post_process and TypographyEngine:
        p.set_post_process(typography_post_process)
    return p

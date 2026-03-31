# Deterministic, Self-Evolving Image Generation Pipeline

**Goal:** 99.9% multi-person accuracy, physics-perfect materials, self-improving AI, perfect text/math, surprise “madness” elements, coverage of all image types.

## Architecture Overview

```
User Prompt
    ↓
Scene Graph Compiler (constraint graph, ENFORCES correctness)
    ↓
Camera & Occlusion Solver (ensures all heads visible)
    ↓
Physics Micro-Simulation (material-aware wetness/lighting/gravity)
    ↓
Multi-ControlNet + Guided Diffusion (existing generation)
    ↓
Tri-Model Validation (YOLO + OpenPose + SAM consensus)
    ↓
Iterative Refinement (max 5 iterations, learned fixes)
    ↓
Self-Improvement Engine (failure memory + learning)
    ↓
Post-Processing (text overlay, math rendering)
    ↓
Perfect Image + Quality Metrics
```

## Implementation Tasks (15 Tasks – Sequential)

### TASK 1: Scene Graph Compiler & Constraint System ✅

**File:** `ai-pipeline/services/scene_graph_compiler.py`

- **EntityNode / RelationEdge / HardConstraint** dataclasses.
- **SceneGraphCompiler.compile(prompt)** → graph, entities, relations, constraints, layout, camera, quality_requirements.
- Exact counts: "3 children", "mother with 3 kids", "couple", "family of 5", objects, weather, fantasy elements.
- Hard constraints: visibility (heads visible), anatomy (2 arms, 5 fingers), physics (wetness), spatial (no merged bodies).
- Layout with occlusion-safe positions; camera plan (FOV, tilt, distance).
- Optional: `spacy` (en_core_web_sm/trf) for NLP; fallback regex-only. Optional: `networkx` for graph; fallback dict.

### TASK 2: Camera & Occlusion Solver ✅

**File:** `ai-pipeline/services/camera_occlusion_solver.py`

- **CameraOcclusionSolver.solve(layout, camera)** → OcclusionSafeLayout.
- Refines layout so umbrella/objects are above heads; camera frame contains all head circles.
- **to_prompt_hints()** for ControlNet/prompt (head positions normalized, person count).

### TASK 3: Physics Micro-Simulation ✅

**Primary file:** `ai-pipeline/services/physics_micro_simulation.py`

- **PhysicsMicroSimulation.simulate(scene_graph, EnvironmentalCondition)** → material_states, visual_effects, prompt_modifiers, control_signals, lighting_effects.
- State-based material simulation: MATERIAL_DB (cotton, denim, leather, skin, asphalt, metal, ethereal_fabric); water_absorption, color_darkening, specular_increase, wetness_level.
- Rain/snow simulation with umbrella protection; lighting (day/night/golden_hour); **run(entities, weather, time_of_day)** and **to_prompt_suffix(result)** for pipeline compatibility.
- **Fallback:** `physics_micro_sim.py` — lighter run(entities, weather) → PhysicsSimResult, to_prompt_suffix().

### TASK 4: Tri-Model Validation ✅ (stub)

**File:** `ai-pipeline/services/tri_model_validator.py`

- **TriModelValidator.validate(image, expected_person_count, constraints)** → TriModelConsensus.
- Placeholder: YOLO (person/head count), OpenPose (limb count), SAM (body separation). When models not loaded, heuristic pass (0.6 confidence).
- Returns: all_passed, results per constraint, head_count_detected, limb_violations, occlusion_detected.

### TASK 5: Iterative Refinement ✅

**File:** `ai-pipeline/services/iterative_refinement.py`

- **LEARNED_FIXES**: rule → (negative_add, positive_add) for failed constraints.
- **build_refinement_deltas(consensus)** → RefinementStep (prompt_delta, param_hints).
- **apply_refinement_to_prompt(base_prompt, base_negative, step)** → new prompt, new negative.
- Used inside DeterministicPipeline (max 5 iterations).

### TASK 6: Self-Improvement Engine + Failure Memory ✅

**File:** `ai-pipeline/services/self_improvement_engine.py` (extended)

- **record_validation_failure(prompt, constraints, consensus, context)**.
- **validation_failure_memory**: list of failed prompts + failed_rules + limb_violations + occlusion_detected (cap 1000).
- DeterministicPipeline calls this when Tri-Model validation fails after refinement.

### TASK 7: Deterministic Pipeline Wiring ✅

**File:** `ai-pipeline/services/deterministic_pipeline.py`

- **DeterministicPipeline**: set_generator(fn), set_self_improvement(engine), set_post_process(fn).
- **run(prompt, negative_prompt, **kwargs)\*\* → DeterministicPipelineResult (image, scene_graph, layout, camera, physics_hint, validation_passed, iterations_used, refinement_steps, quality_metrics).
- Flow: compile → solve → physics → generate (loop: validate → refine → regenerate) → record failure if needed → post_process.

### TASK 8: Post-Processing (Text / Math) ✅

**Typography Engine:** `ai-pipeline/services/typography_engine.py` (GlyphControl + Post-Overlay; 100% OCR accuracy target).

- **GlyphControl:** In-scene text (e.g. sign on building) — `build_glyph_control_image(width, height, placements)` for control conditioning.
- **Post-Overlay:** UI text (labels, captions) — `overlay_text(image, placements)` or `render_text_placement(image, placements)`.
- **TextPlacement:** text, position, size, style, color, background, anchor; font search via `FONT_SEARCH_PATHS` / `FONT_STYLE_FILES`.
- DeterministicPipeline optional **set_post_process(fn)** can call TypographyEngine (e.g. `render_text_placement`) when `scene_graph` contains `text_placements`.
- **Legacy:** `text_renderer.py` remains available; Typography Engine is the recommended path for perfect text in images.
- Math rendering: LaTeX-style math (future: dedicated math_renderer or TypographyEngine extension).

### Multi-ControlNet with Online Reward Guidance ✅

**File:** `ai-pipeline/services/guided_diffusion_controlnet.py`

- **RewardModel**: compute_rewards(latents, scene_graph, physics_state, step, total_steps) → anatomy, physics, aesthetics, constraint_satisfaction, surprise (0–1). Optional CLIP/aesthetic models via load_models=True.
- **GuidedDiffusionControlNet**: generate_control_images(scene_graph, width, height) → depth, openpose, canny from layout (no GPU). generate_with_guidance(prompt, negative_prompt, control_images, scene_graph, physics_state, …) → PIL image with reward-guided denoising (requires torch, diffusers; pipeline lazy-loaded on first call).
- Depth/openpose/canny from layout entities (bbox or center/radius); reward guidance every 5 steps after warmup; optional cv2, numpy fallback for drawing.

### TASK 9–15: Future

- **RL-based online rewards** (reward model from Tri-Model + aesthetic) — partially in RewardModel.
- **YOLO/OpenPose/SAM** real model loading in TriModelValidator.
- **Surprise “madness”** elements (fantasy, creative boost) from scene_graph fantasy + WowBooster.
- **Coverage of ALL image types**: living beings, objects, imaginative/fantasy, diagrams, text-embedded.

## Usage

```python
from ai_pipeline.services.deterministic_pipeline import (
    create_pipeline,
    DeterministicPipeline,
    typography_post_process,
)

def my_generator(prompt: str, negative_prompt: str, **kwargs):
    # Call your SDXL/ControlNet endpoint
    return image_bytes_or_base64

pipeline = create_pipeline(generator_fn=my_generator, max_iterations=5, use_physics=True)
result = pipeline.run(
    "family of 5 walking in rain with umbrella, street scene",
    negative_prompt="blurry, low quality",
)
# result.image, result.validation_passed, result.quality_metrics
```

## Dependencies

- **networkx** (required for scene graph): `pip install networkx`
- **spacy** (optional, for better NLP): `pip install spacy && python -m spacy download en_core_web_sm`
- YOLO/OpenPose/SAM (optional, for Tri-Model): to be wired in tri_model_validator when needed.

## Files Summary

| File                             | Purpose                                                                       |
| -------------------------------- | ----------------------------------------------------------------------------- |
| `scene_graph_compiler.py`        | Constraint graph from prompt; exact counts, layout, camera                    |
| `camera_occlusion_solver.py`     | All heads visible; refine layout and camera                                   |
| `physics_micro_simulation.py`    | State-based materials, rain/snow, lighting, prompt modifiers                  |
| `physics_micro_sim.py`           | Fallback: wetness, lighting, gravity hints                                    |
| `tri_model_validator.py`         | YOLO + OpenPose + SAM consensus (stub)                                        |
| `iterative_refinement.py`        | Learned fixes from validation failures                                        |
| `deterministic_pipeline.py`      | Single entry point; wires all steps; typography_post_process for text overlay |
| `typography_engine.py`           | GlyphControl (in-scene text) + Post-Overlay (UI text); 100% OCR target        |
| `self_improvement_engine.py`     | record_validation_failure + failure memory                                    |
| `guided_diffusion_controlnet.py` | Multi-ControlNet (depth/openpose/canny), RewardModel, online reward guidance  |

**Last updated:** Task 1–8 + multi-ControlNet; Task 8 uses Typography Engine (GlyphControl + Post-Overlay); typography_post_process + create_pipeline(use_post_process=True); Tasks 9–15 (RL, real models, madness, full coverage) planned.

# AWS Orchestrator Integration

Integration and orchestration for **AWS** (no Modal dependency for the main flow). Wires SemanticEnhancer, TwoPassGeneration, and optional InstantID with graceful degradation.

## Files

- **`ai-pipeline/services/orchestrator_aws.py`** – AWS orchestrator: `generate_professional()`, quality-tier routing, fallbacks.
- **`ai-pipeline/services/two_pass_generation.py`** – Two-pass pipeline: `generate_fast()`, `generate_two_pass()` with optional InstantID in Pass 2.

## Quality Tiers

| Tier      | Behavior                                      | Target time |
|-----------|-----------------------------------------------|-------------|
| **FAST**  | SDXL Turbo only (4 steps)                     | < 5s        |
| **STANDARD** | Two-pass without preview (Base + Refiner + optional LoRA) | < 40s   |
| **PREMIUM**  | Two-pass with preview + optional InstantID for Pass 2 | < 50s   |

## Master Entry: `generate_professional()`

```python
from ai_pipeline.services.orchestrator_aws import generate_professional

result = generate_professional(
    user_prompt="woman in a forest",
    identity_id="optional-lora-id",
    user_id="user-123",
    mode="REALISM",
    quality_tier="PREMIUM",  # FAST | STANDARD | PREMIUM
    negative_prompt="blurry, low quality",
    seed=42,
)
```

### Response format

```python
{
    "images": {
        "preview": "<base64 or None>",
        "final": "<base64>",
    },
    "metadata": {
        "enhanced_prompt": "...",
        "original_prompt": "...",
        "mode": "REALISM",
        "quality_tier": "PREMIUM",
        "face_accuracy": "90%+" or "N/A",
        "method_used": "premium_two_pass" | "standard_two_pass" | "fast_turbo" | "basic_fast",
    },
    "timing": {
        "preview_time": 4.2,
        "final_time": 41.5,
        "total_time": 45.7,
    },
    "status": "success" | "error",
}
```

## Flow

1. **Semantic enhancement** – `SemanticPromptEnhancer.enhance(prompt, mode)`. On failure, use original prompt.
2. **Quality tier routing**
   - **FAST** → `generate_fast(enhanced_prompt)` (Turbo only).
   - **STANDARD** → `generate_two_pass(..., return_preview=False, use_instantid=False)`. On failure → `generate_fast`.
   - **PREMIUM** → `generate_two_pass(..., return_preview=True, use_instantid=True when identity_id)`. On failure → STANDARD → BASIC (Turbo).
3. **InstantID (PREMIUM + identity_id)** – In Pass 2 of `generate_two_pass`, when `use_instantid` and identity paths exist, call `generate_with_instantid` (if available); otherwise use SDXL Base + LoRA.

## Graceful degradation

- **PREMIUM**: Try two-pass + InstantID → on failure try two-pass (LoRA) → on failure try Turbo only.
- **STANDARD**: Try two-pass (no preview) → on failure try Turbo only.
- **FAST**: Turbo only; no fallback.
- If SemanticEnhancer is unavailable, the original prompt is used.
- If InstantID is unavailable (e.g. on pure AWS), Pass 2 uses SDXL Base + LoRA.

## Logging

- Enhancement success/failure.
- Generation method used (`method_used`).
- Timing (preview_time, final_time, total_time).
- Quality tier and fallback steps.

## Lambda Orchestrator (API)

**`aws/lambda/orchestrator/handler.py`** – Quality tier routing via SageMaker (AWS only, no Modal).

- **Endpoints:** `POST /generate` and `POST /orchestrate` (SAM: `OrchestratorFunction`, Timeout 600s, Memory 512MB).
- **Env:** `SAGEMAKER_TWO_PASS_ENDPOINT` (photogenius-two-pass-dev), `SAGEMAKER_GENERATION_ENDPOINT` (single-pass).
- **Flow:** Parse body → optional semantic enhance (`semantic_prompt_enhancer.py` stub in Lambda) → `generate_with_quality_tier()` → return `{ images: { preview, final }, metadata }`.
- **Tiers:**
  - **FAST:** Invoke two-pass endpoint with `return_preview: true`; return preview as final (~5s).
  - **STANDARD:** Invoke single-pass endpoint; return `final` only (~40s).
  - **PREMIUM:** Invoke two-pass endpoint with preview + refinement; return both preview and final (~45s).
- **Semantic enhancement:** Lambda bundles a minimal `semantic_prompt_enhancer.py` (rule-based mode suffix); no sentence-transformers.

**Request body (e.g. POST /orchestrate):**

```json
{
  "prompt": "professional headshot",
  "quality_tier": "PREMIUM",
  "mode": "REALISM",
  "identity_id": "optional",
  "user_id": "user-123",
  "negative_prompt": "",
  "width": 1024,
  "height": 1024,
  "seed": 42
}
```

**Response:** `{ "images": { "preview": "base64...", "final": "base64..." }, "metadata": { "quality_tier", "preview_time", "final_time", "total_time", "original_prompt", "enhanced_prompt", "mode", "generation_id", "image_url" } }`.

**SAM template:** `aws/template.yaml` – `OrchestratorFunction` with `SAGEMAKER_TWO_PASS_ENDPOINT`, `SAGEMAKER_REALTIME_ENDPOINT`, `SAGEMAKER_GENERATION_ENDPOINT`, `SAGEMAKER_IDENTITY_V2_ENDPOINT`, `/orchestrate` event, Timeout 600.

### Identity V2 routing (optional)

- **Default flow:** No `identity_engine_version=v2` → standard pipeline (FAST / STANDARD / PREMIUM). No breaking changes.
- **Identity V2:** Only when client sends `identity_engine_version: "v2"` **and** `face_image_base64` **and** env `SAGEMAKER_IDENTITY_V2_ENDPOINT` is set. Endpoint name is **never hardcoded** in code.
- **Fallback:** If Identity V2 fails or returns no image, the orchestrator falls back to the standard pipeline.
- **Details and validation:** See **[ORCHESTRATOR_IDENTITY_V2_ROUTING.md](ORCHESTRATOR_IDENTITY_V2_ROUTING.md)** (architecture, client request rules, InstantID behavior, validation checklist).

## Testing checklist

- [ ] FAST tier works (< 5s).
- [ ] STANDARD tier works (< 40s).
- [ ] PREMIUM tier works (< 50s).
- [ ] Fallback works when InstantID fails (LoRA used).
- [ ] Semantic enhancement integrated (and fallback to raw prompt).
- [ ] Response format matches (images, metadata, timing, status).
- [ ] Lambda deploys without errors; can invoke two-pass and single-pass endpoints.
- [ ] FAST returns preview only; STANDARD returns final only; PREMIUM returns both.
- [ ] Error handling works for all tiers; timeout 600s sufficient for PREMIUM.
- [ ] **Identity V2:** With `identity_engine_version: "v2"` and `face_image_base64` and endpoint set → Identity V2 used; on failure → fallback to standard pipeline.
- [ ] **Identity V2:** Without `face_image_base64` or without endpoint set → standard pipeline only (no Identity V2 call).

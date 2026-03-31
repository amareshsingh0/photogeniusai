# 🎯 Orchestrator Service - The Brain of PhotoGenius AI

## Overview

The Orchestrator is the master controller that transforms simple user prompts (like "beach" or "office portrait") into perfect professional images. It uses Claude Sonnet 4 for intelligent prompt parsing and routing decisions.

## Architecture

```
User Input: "beach"
    ↓
[1] Parse: Claude expands to full professional spec
    ↓
[2] Plan: Decide which engines to use (Identity, Creative, Composition, Finish)
    ↓
[3] Execute: Call engines in sequence
    ↓
[4] Rerank: Use LLM intelligence to pick best result
    ↓
Perfect Image 🎯
```

## Features

### 1. Intelligent Prompt Parsing (`_parse_prompt`)
- Expands minimal prompts (2 words) → Full professional photography specification
- Uses Claude Sonnet 4 to extract 10 components:
  - **subject**: Who/what is the main subject
  - **action**: What they're doing, pose, movement
  - **setting**: Location, environment, background
  - **time**: Time of day, golden hour, etc.
  - **lighting**: Type, quality, direction (backlight, rim lighting, etc.)
  - **camera**: Shot type, lens, focal length, aperture
  - **mood**: Emotional tone, feeling, atmosphere
  - **color**: Color palette, grading, tones
  - **style**: Artistic references, inspiration
  - **technical**: Film stock, grain, aesthetic details

**Example:**
- Input: `"beach"`
- Output: Full spec with "person at water's edge, golden hour, 85mm f/2.0, warm golden backlight, Peter Lindbergh style..."

### 2. Execution Planning (`_create_execution_plan`)
- Mode-specific routing weights:
  - **REALISM**: Identity 0.92, Finish 1.0
  - **CREATIVE**: Identity 0.72, Creative 1.0, Finish 1.0
  - **ROMANTIC**: Identity 0.80, Creative 0.5, Finish 1.0
  - **FASHION**: Identity 0.85, Creative 0.6, Finish 1.0
  - **CINEMATIC**: Identity 0.76, Creative 0.8, Finish 1.0
- Automatically detects action words (jumping, dancing, yoga) → **requires_composition**; when **reference_images** are provided, Composition Engine (pose + depth + canny) is used.
- Returns execution plan with engine configurations

### 3. Intelligent Reranking (`_intelligent_rerank`)
- Scores all candidates numerically first
- If top 3 scores within 5 points → uses Claude tiebreaker
- LLM judges based on:
  - Composition quality
  - Mood match
  - Story/intent alignment
  - Overall appeal
- Returns best candidates ranked by intelligence, not just scores

### 4. Error Handling & Fallbacks
- Graceful fallback if Claude API unavailable
- Fallback parser for basic prompt expansion
- Direct generation fallback if orchestration fails
- Comprehensive error logging

### 5. Identity Engine V2 Integration (99%+ face)
- **Priority:** V2 → V1 → GenerationService. When `identity_id` is present, the orchestrator calls **Identity Engine V2** first (`photogenius-identity-v2` / `IdentityEngineV2.generate_ultimate`).
- **Quality gate:** 99% minimum face similarity (`quality_threshold=0.99`). If below, retry once with `max_attempts=7`.
- **Ensemble:** V2 uses InstantID → FaceSwap → Pure LoRA and ensemble verification (InsightFace, DeepFace, FaceNet). Logs `best_similarity`, `paths`, and `guaranteed_quality`.
- **Fallback:** On V2 exception or missing identity, falls back to V1 then GenerationService.
- **Deploy V2:** `modal deploy ai-pipeline/services/identity_engine_v2.py`. Ensure Identity Engine V2 is deployed before the orchestrator for 99%+ identity runs.
- **Validation:** Test with 10+ identities; verify results have >99% face similarity where possible; ensure fallback chain (V2 → V1 → GenService) works when V2 is unavailable or identity missing.

### 6. Quality tier → engine routing & Realtime (FAST/STANDARD)
- **`QUALITY_TIER_CONFIG`** maps tier → engine, steps, resolution, guidance:
  - **FAST:** realtime, 4 steps, 1024, ~8–10s. **STANDARD:** realtime, 8 steps, 1024, ~15s.
  - **BALANCED / PREMIUM:** sdxl (identity path). **ULTRA:** ultra_high_res (when wired).
- **`_select_engine(quality_tier, width, height)`** returns engine + config; caps resolution by tier.
- **`preview=True`** forces `quality_tier=FAST` for fast iterations (8–10s previews).
- Realtime path uses `generate_realtime_batch` with tier-specific `num_steps`, `guidance_scale`, `width`/`height`, and `negative_prompt` (`REALTIME_NEGATIVE`). **`generate_fast`** exists (4 steps, guidance 5.0) for direct use.
- **Cache:** Tier-aware key and TTL. FAST/STANDARD → 1h TTL; else 7d. Cache keys include `tier=` so fast vs full-quality results are stored separately. **Deploy:** `modal deploy ai-pipeline/services/realtime_engine.py`.
- **Validation:** FAST tier &lt;10s; resolution capping by tier; cache separation (fast vs full); measure generation times per tier.

### 7. Batch quality scoring (orchestrator ↔ quality scorer)
- When **2+ candidates** and **Quality Scorer** is available, the orchestrator calls `score_batch` (ML aesthetic, etc.) before reranking.
- Replaces engine scores with scorer output for rerank. **Deploy:** `modal deploy ai-pipeline/services/quality_scorer.py`.

### 8. Composition engine (pose + depth + canny)
- When **requires_composition** (action words) and **reference_images** are provided, the orchestrator calls the **Composition Engine** before identity/generation.
- Uses first reference for pose (OpenPose), depth (MiDaS), and Canny; multi-ControlNet SDXL. Falls back to identity/gen if composition fails or no refs.
- **composition_params** optional: `{"identity_ids": [...], "identity_positions": [{"x","y","scale"}, ...]}`. If **&gt;1 identity_ids** (and matching positions), orchestrator calls **compose_multi_identity**; else **compose**.
- **reference_images** / **composition_params** via `orchestrate`, `orchestrate_with_cache`, `orchestrate_multimodal`, or web endpoints.
- **Deploy:** `modal deploy ai-pipeline/services/composition_engine.py`. See `COMPOSITION_ENGINE_README.md`.

### 9. Finish engine (post-processing)
- When the plan includes a **finish** engine, the orchestrator runs **Finish Engine** after rerank on the best images.
- Uses plan params: `upscale`, `face_fix`, `color_grade`, `enhance_details`. LUT chosen by mode (e.g. REALISM→neutral, CINEMATIC→cinematic).
- **Deploy:** `modal deploy ai-pipeline/services/finish_engine.py`. See `FINISH_ENGINE_README.md`.

## Setup

### 1. Create Anthropic Secret

```bash
modal secret create anthropic ANTHROPIC_API_KEY=sk-ant-...
```

Or use the PowerShell script:
```powershell
.\scripts\setup-modal-secrets.ps1
```

### 2. Deploy

```bash
cd ai-pipeline
modal deploy services/orchestrator.py
```

### 3. Test

```bash
modal run services/orchestrator.py::test_orchestrator
```

## Usage

### Python SDK

```python
from ai_pipeline.services.orchestrator import Orchestrator

orchestrator = Orchestrator()

result = await orchestrator.orchestrate.remote(
    user_prompt="beach sunset",
    mode="REALISM",
    identity_id="identity_123",
    user_id="user_456",
    num_candidates=4,
    seed=42,
)

print(f"Generated {len(result['images'])} images")
print(f"Parsed prompt: {result['parsed_prompt']['full_prompt']}")
```

### Web Endpoint

```bash
curl -X POST https://amareshsingh0--photogenius-orchestrator-orchestrate-web.modal.run \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "beach",
    "mode": "REALISM",
    "identity_id": "identity_123",
    "num_candidates": 4
  }'
```

## Response Format

```json
{
  "images": [
    {
      "image_base64": "...",
      "seed": 42,
      "prompt": "Full expanded prompt...",
      "scores": {
        "face_match": 92.5,
        "aesthetic": 88.3,
        "technical": 91.2,
        "total": 90.8
      }
    }
  ],
  "parsed_prompt": {
    "subject": "person standing at water's edge",
    "action": "gazing at horizon",
    "setting": "pristine beach, gentle waves",
    "time": "golden hour, 20 minutes before sunset",
    "lighting": "warm golden backlight, rim lighting",
    "camera": "85mm lens, f/2.0 shallow DOF",
    "mood": "peaceful contemplation",
    "color": "warm orange and gold tones",
    "style": "inspired by Peter Lindbergh",
    "technical": "slight film grain, Kodak Portra 400",
    "full_prompt": "Complete professional prompt..."
  },
  "execution_plan": {
    "engines": [
      {"name": "identity", "weight": 0.92},
      {"name": "finish", "weight": 1.0}
    ],
    "requires_composition": false
  },
  "rerank_used": true
}
```

## Integration with Generation Service

The orchestrator calls the `GenerationService` (identity engine) via Modal's remote mechanism:

```python
from .generation_service import GenerationService

generation_service = GenerationService()
candidates = generation_service.generate_images.remote(...)
```

## Future Enhancements

1. **Creative Engine**: MJ-style aesthetic magic for Play mode
2. **Composition Engine**: ControlNets for pose/depth/action shots
3. **Finish Engine**: 4x upscale, face fix, color grading, film grain
4. **Multi-engine Pipeline**: Sequential execution with intermediate results
5. **Caching**: Cache parsed prompts for common inputs

## Testing Checklist

- ✅ "beach" → expands to full spec with lighting, camera, mood
- ✅ "office portrait" → infers LinkedIn style, professional lighting
- ✅ "dancing in rain" → triggers composition engine flag
- ✅ "romantic couple" → sets ROMANTIC mode parameters
- ✅ Fallback works when Claude unavailable
- ✅ Reranking works when scores are close

## Troubleshooting

### Claude API Errors
- Check `ANTHROPIC_API_KEY` in Modal secrets
- Verify Anthropic account has credits
- Check API rate limits

### Generation Service Not Found
- Ensure `generation_service.py` is deployed
- Check import paths are correct
- Verify both apps are in same Modal workspace

### Import Errors
- Ensure all dependencies installed in `orchestrator_image`
- Check Python version compatibility (3.11)
- Verify Modal apps are properly structured

## Cost Considerations

- Claude Sonnet 4: ~$0.003 per prompt parse
- LLM Reranking: ~$0.001 per rerank (only when scores close)
- Total overhead: ~$0.004 per orchestrated generation
- **Worth it**: Transforms 2-word prompts into perfect images

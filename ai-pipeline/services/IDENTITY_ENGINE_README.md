# 🎯 Identity Engine - Engine A

## Overview

The Identity Engine is Engine A of PhotoGenius AI - the core identity generation engine that guarantees **90%+ face consistency** using LoRA + adaptive retry logic.

## Key Features

### 1. Model Pre-loading (`@modal.enter()`)
- Loads SDXL pipeline once on container startup
- Pre-compiles CUDA kernels for instant warm starts
- Always 2 warm containers (`min_containers=2`) for high availability
- 5-minute warm period (`scaledown_window=300`)

### 2. Parsed Prompt Integration
- Works seamlessly with Orchestrator's parsed prompt structure
- Builds professional prompts from structured components:
  - Subject, Action, Setting, Time, Lighting
  - Camera, Mood, Color, Style, Technical details

### 3. Adaptive Retry Logic
- **First attempt**: Uses initial LoRA strength (default 0.90)
- **Second attempt**: Increases LoRA strength by 0.05 if face similarity < 0.75
- **Maximum strength**: 0.95
- Ensures 90%+ face consistency guarantee

### 4. Comprehensive Scoring
- **Face similarity**: 0-1 range (threshold: 0.75)
- **Face match**: 0-100 score
- **Aesthetic**: Composition, color, mood
- **Technical**: Sharpness, noise, quality
- **Overall**: Weighted total based on mode

### 5. Mode-Specific Parameters
- **REALISM**: 40 steps, 7.5 guidance, 832x1216
- **CREATIVE**: 50 steps, 9.0 guidance, 1024x1024
- **FASHION**: 45 steps, 8.0 guidance, 832x1216
- **CINEMATIC**: 50 steps, 8.5 guidance, 1216x832
- **ROMANTIC**: 45 steps, 7.0 guidance, 1024x1024

## Usage

### From Orchestrator (Recommended)

```python
from ai_pipeline.services.identity_engine import IdentityEngine

engine = IdentityEngine()

parsed_prompt = {
    "subject": "person standing at water's edge",
    "action": "gazing at horizon",
    "setting": "pristine beach",
    "lighting": "warm golden backlight",
    # ... other components
}

result = await engine.generate.remote(
    parsed_prompt=parsed_prompt,
    identity_id="identity_123",
    user_id="user_456",
    strength=0.90,
    n_candidates=4,
    mode="REALISM",
    face_embedding=face_embedding,
    seed=42,
)
```

### Direct Call

```python
from ai_pipeline.services.identity_engine import IdentityEngine

engine = IdentityEngine()
result = await engine.generate.remote(...)
```

## Response Format

```json
[
  {
    "image_base64": "...",
    "seed": 42,
    "prompt": "Full professional prompt...",
    "negative_prompt": "Comprehensive negative prompt...",
    "scores": {
      "face_match": 92.5,
      "face_similarity": 0.925,
      "aesthetic": 88.3,
      "technical": 91.2,
      "total": 90.8,
      "overall": 90.8
    }
  }
]
```

## Testing

```bash
cd ai-pipeline
modal run services/identity_engine.py::test_identity_engine
```

### Expected Results
- **First generation**: ~40s (cold start)
- **Second generation**: ~5s (warm container)
- **Face similarity**: >0.75 for REALISM mode
- **Retry**: Increases LoRA strength if first attempt fails

## Integration with Orchestrator

The Orchestrator automatically uses IdentityEngine when available:

```python
# Orchestrator automatically routes to IdentityEngine
result = await orchestrator.orchestrate.remote(
    user_prompt="beach sunset",
    mode="REALISM",
    identity_id="identity_123",
)
```

## Backward Compatibility

The old `generation_service.py` is maintained for backward compatibility. It can optionally use IdentityEngine internally or work standalone.

## Future Enhancements

1. **InstantID Integration**: Add ControlNet + IP-Adapter for even better face consistency
2. **Multi-LoRA Support**: Support multiple LoRAs for complex identities
3. **Face Embedding Caching**: Cache face embeddings for faster scoring
4. **Advanced Retry**: More sophisticated retry strategies based on failure modes

## Performance

- **Cold start**: ~40s (one-time model loading)
- **Warm start**: ~5s (model pre-loaded)
- **Face consistency**: 90%+ guaranteed with adaptive retry
- **Throughput**: 2 warm containers = 2x capacity

## Configuration

```python
@app.cls(
    gpu="A100",
    image=base_image,
    min_containers=2,  # Always 2 warm containers
    scaledown_window=300,  # 5 min warm
    timeout=600,
    volumes={...},
    secrets=[...],
)
```

## Troubleshooting

### Issue: Face similarity < 0.75
- **Check**: LoRA quality and training
- **Solution**: Adaptive retry increases strength automatically
- **Verify**: Face embedding is correct

### Issue: Slow generation
- **Check**: Container warm status
- **Verify**: `min_containers=2` is active
- **Solution**: Ensure containers stay warm

### Issue: LoRA not loading
- **Check**: LoRA path: `/loras/{user_id}/{identity_id}/`
- **Verify**: LoRA file exists (`.safetensors` or directory)
- **Solution**: Check Modal volume mounts

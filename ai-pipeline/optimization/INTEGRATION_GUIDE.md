# Model Distillation - Integration Guide

## Quick Integration

### Step 1: Use SDXL-Turbo (Immediate)

**Deploy distilled service:**
```bash
modal deploy ai-pipeline/optimization/distilled_models.py
```

**Use in code:**
```python
import modal

distilled = modal.Cls.from_name("photogenius-distillation", "DistilledModelService")

# Generate with distilled model
result = distilled.generate_fast.remote(
    prompt="professional headshot",
    num_inference_steps=4,  # vs 40-50 for SDXL
)
```

### Step 2: Integrate with Orchestrator

**Add quality tier support:**

```python
# In orchestrator.py

from ai_pipeline.optimization.distilled_models import DistilledModelService

class Orchestrator:
    def __init__(self):
        # ... existing code ...
        self.distilled_service = None
        try:
            DistilledCls = modal.Cls.from_name("photogenius-distillation", "DistilledModelService")
            self.distilled_service = DistilledCls()
        except:
            pass
    
    def _execute_plan(self, plan, quality_tier="balanced", ...):
        # Use distilled for standard tier
        if quality_tier == "standard" and self.distilled_service:
            return self._generate_with_distilled(...)
        else:
            return self._generate_with_sdxl(...)
```

### Step 3: Add to API v1

**Update API to support quality tiers:**

```python
# In api/v1/main.py

async def process_generation(..., quality_tier="balanced"):
    if quality_tier == "standard":
        # Use distilled model
        distilled = DistilledModelService()
        result = distilled.generate_fast.remote(...)
    else:
        # Use full SDXL
        result = orchestrator.orchestrate.remote(...)
```

## Cost Optimization Strategy

### Tiered Pricing

| Tier | Model | Cost | Quality | Use Case |
|------|-------|------|---------|----------|
| **Standard** | Distilled | $0.005/image | High | Previews, non-critical |
| **Balanced** | SDXL (30 steps) | $0.01/image | Very High | General use |
| **Premium** | SDXL (50 steps) | $0.02/image | Maximum | Professional work |

### Implementation

```python
def estimate_cost(time_seconds: float, quality_tier: str) -> float:
    """Estimate cost based on tier"""
    base_cost_per_second = 0.000028  # A10G
    
    multipliers = {
        "standard": 0.5,  # Distilled: 50% cost
        "balanced": 1.0,  # SDXL standard
        "premium": 1.5,   # SDXL high quality
    }
    
    return time_seconds * base_cost_per_second * multipliers.get(quality_tier, 1.0)
```

## Quality Validation

### Compare Distilled vs SDXL

```python
# Run comparison test
comparison = distilled.compare_with_sdxl.remote(
    prompt="professional headshot",
    seed=42,
)

# Evaluate:
# 1. Visual quality (side-by-side)
# 2. Face similarity scores
# 3. User ratings
# 4. Cost difference
```

### Monitor Quality Metrics

```python
# In monitoring system
from ai_pipeline.monitoring.logger import log_generation

log_generation(
    ...,
    model_type="distilled",  # or "sdxl"
    cost=estimate_cost(time, "standard"),
)
```

## Best Practices

1. **Start with SDXL-Turbo** - Immediate cost savings, no training needed
2. **Validate quality** - Compare against SDXL before full deployment
3. **Monitor metrics** - Track quality, cost, user satisfaction
4. **Tiered approach** - Use distilled for standard, SDXL for premium
5. **Train custom later** - Only after product-market fit and high volume

## Expected Results

- **Cost reduction**: 50% per image
- **Speed improvement**: 2x faster
- **Quality**: Maintained (high, suitable for most use cases)
- **ROI**: Break-even at 500K-1M images

---

**Status**: ✅ Ready for integration with SDXL-Turbo

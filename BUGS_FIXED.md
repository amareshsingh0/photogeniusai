# Critical Bugs Fixed - February 15, 2026

## Issue Discovery
After initial deployment completed successfully, code review revealed 2 critical bugs that would cause endpoint failures.

## Bug #1: Indentation Error (Lines 555-571)

### Problem
```python
image = pipe(**gen_kwargs).images[0]

    gen_time = time.time() - gen_start    # ← Extra indentation!

    logger.info("[LOCK] Releasing GPU lock")

    return {                               # ← Extra indentation!
        "status": "success",
        ...
    }
```

### Impact
- Python IndentationError on first request
- Endpoint would crash immediately
- No images could be generated

### Fix
Removed extra indentation from lines 555-571 to align with surrounding code:
```python
image = pipe(**gen_kwargs).images[0]

gen_time = time.time() - gen_start    # ← Fixed indentation

logger.info("[LOCK] Releasing GPU lock")

return {                               # ← Fixed indentation
    "status": "success",
    ...
}
```

## Bug #2: GPU_LOCK Scope Too Narrow

### Problem
```python
with GPU_LOCK:
    logger.info("[LOCK] Acquired GPU lock")
    model_name, steps, guidance = select_model(tier, prompt, requested_model)
    # Lock automatically released here!

# All generation code OUTSIDE the lock - concurrent access possible!
pipe = load_generator(model_name)
generator = torch.Generator(device="cpu")
# ... setup code ...
image = pipe(**gen_kwargs).images[0]  # ← Multiple requests can run simultaneously!
```

### Impact
- GPU_LOCK released after model selection only
- Actual model loading and generation happened OUTSIDE the lock
- Concurrent requests could load models simultaneously → OOM crash
- Defeats entire purpose of concurrency control
- 24GB VRAM limit could be exceeded

### Fix
Moved ALL generation code inside GPU_LOCK:
```python
with GPU_LOCK:
    logger.info("[LOCK] Acquired GPU lock")

    # Model selection
    model_name, steps, guidance = select_model(tier, prompt, requested_model)

    # Strategy overrides
    if guidance_override is not None:
        guidance = float(guidance_override)
    if steps_override is not None:
        steps = int(steps_override)

    # Memory safety
    max_pixels = 1024 * 1024
    if width * height > max_pixels:
        ratio = (max_pixels / (width * height)) ** 0.5
        width = int(width * ratio) // 8 * 8
        height = int(height * ratio) // 8 * 8

    # Load model (with hot-swap if needed)
    pipe = load_generator(model_name)

    # Setup generator
    generator = torch.Generator(device="cpu")
    if seed:
        generator.manual_seed(int(seed))
    else:
        generator.manual_seed(int(time.time() * 1000) % (2**32))
    actual_seed = generator.initial_seed()

    # Build kwargs
    gen_kwargs = {
        "prompt": prompt,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "width": width,
        "height": height,
        "generator": generator,
    }

    # Model-specific options
    if model_name == "pixart-sigma" and negative:
        gen_kwargs["negative_prompt"] = negative

    # GENERATE (inside lock!)
    logger.info(f"Generating: model={model_name}, steps={steps}, guidance={guidance}, seed={actual_seed}")
    image = pipe(**gen_kwargs).images[0]

    gen_time = time.time() - gen_start
    logger.info("[LOCK] Releasing GPU lock")

    return {
        "status": "success",
        "image": image_to_base64(image),
        ...
    }
```

## Root Cause Analysis

### Why These Bugs Occurred
1. **Indentation Bug:** Code editor auto-formatting during GPU_LOCK edits added extra spaces
2. **Scope Bug:** Initially planned to only lock model selection, but forgot g5.2xlarge constraint requires locking entire generation

### Why They Weren't Caught Earlier
1. No local Python syntax check before packaging
2. SageMaker deployment succeeded (syntax checked at runtime, not deploy time)
3. No test requests sent before discovering bugs

## Prevention Measures

### Immediate
- [x] Python syntax validation before packaging
- [x] Code review of critical sections (GPU, memory, locks)
- [ ] Test endpoint immediately after deployment
- [ ] Automated syntax check in deploy script

### Future
- [ ] Add pre-commit hook for Python syntax check
- [ ] Add unit tests for inference.py
- [ ] Add integration tests with mock SageMaker
- [ ] CI/CD pipeline with automated testing

## Deployment Timeline

| Time | Event | Status |
|------|-------|--------|
| 19:07 | Initial deployment started | Creating |
| 19:12 | Initial deployment complete | InService (with bugs) |
| 19:15 | Bugs discovered during code review | - |
| 19:16 | Bugs fixed, re-packaged | - |
| 19:17 | Re-deployment started | Updating |
| 19:22 (est) | Re-deployment complete | InService (fixed) |

## Testing Plan

Once endpoint reaches InService:

1. **Syntax Validation:** Verify no IndentationError
2. **Basic Generation:** Single request for PixArt
3. **Hot-Swap Test:** Architecture → Portrait (PixArt → FLUX)
4. **Concurrency Test:** 2 simultaneous requests (GPU_LOCK verification)
5. **Full Flow Test:** Frontend → API → SageMaker → Response

## Lessons Learned

1. **Always validate Python syntax** before deploying to SageMaker
2. **Test immediately** after deployment, don't assume success
3. **Locks must wrap entire critical section**, not just selection logic
4. **Code review critical for GPU memory management** on constrained hardware
5. **Indentation matters in Python** - use consistent editor settings

---

**Bugs Fixed By:** Claude Sonnet 4.5
**Status:** Re-deployed, waiting for InService
**Next:** Test endpoint once ready

# Hot-Swapping Implementation for g5.2xlarge

**Status:** IMPLEMENTED AND DEPLOYING
**Date:** February 15, 2026
**Instance:** ml.g5.2xlarge (A10G 24GB VRAM)

## Summary

Implemented intelligent model hot-swapping for g5.2xlarge deployment to handle both PixArt-Sigma and FLUX.1-schnell models within 24GB VRAM constraint.

## Features Implemented

### 1. Global State for Hot-Swapping
```python
CURRENT_MODEL = None  # Name of loaded model
PIPE = None  # Loaded pipeline
LAST_ACTIVITY_TIME = None  # For idle timeout tracking
GPU_LOCK = threading.Lock()  # Concurrency control
```

### 2. Smart Router with Human Detection
- **Human Keywords:** person, people, family, face, portrait, wedding, etc.
- **Routing Logic:**
  - Prompt has human keywords -> Route to FLUX.1-schnell (photorealism)
  - No human keywords -> Route to PixArt-Sigma (architecture/scenes/text)
  - Explicit model request -> Honor the request

```python
HUMAN_KEYWORDS = [
    "person", "people", "human", "man", "woman", "child", "family", "group",
    "face", "portrait", "selfie", "headshot", "profile",
    "wedding", "bride", "groom", "couple",
    "crowd", "audience", "team", "friends",
]
```

### 3. Aggressive Memory Cleanup
Enhanced `clear_gpu_memory()` and `unload_generator()`:
- Double `gc.collect()` for better cleanup
- Added `torch.cuda.ipc_collect()` to clean shared memory
- Complete pipeline deallocation before loading new model

### 4. GPU Concurrency Lock
- Only ONE generation at a time (prevents OOM from concurrent requests)
- Thread-safe model loading/unloading
- Automatic lock acquisition in `predict_fn()`

### 5. Warmup + Background Downloads
- Background thread downloads ALL models from S3
- Default model (PixArt-Sigma) pre-loaded during warmup for fast first request
- FLUX.1-schnell downloaded but not loaded (loaded on-demand when needed)

### 6. Automatic Model Swapping
- Detects when different model is needed
- Automatically unloads current model
- Loads requested model
- Updates `CURRENT_MODEL` and `PIPE` state

## How It Works

### Flow Diagram
```
Request arrives
    |
Acquire GPU_LOCK
    |
Smart Router analyzes prompt
    |- Human keywords? -> FLUX.1-schnell
    └- Architecture/text? -> PixArt-Sigma
    |
Check if model loaded
    |- Same model? -> Use it
    └- Different model? -> HOT-SWAP
        |
        Unload current
        |
        gc.collect() x 2 + ipc_collect()
        |
        Load new model
    |
Generate image
    |
Release GPU_LOCK
```

## Deployment

### Current Status
```
Endpoint: photogenius-production
Instance: ml.g5.2xlarge (A10G 24GB GPU)
Region: us-east-1
Status: DEPLOYING (10-15 minutes)
```

### Files
- `aws/sagemaker/model/code/inference.py` - Updated with hot-swap features
- `aws/sagemaker/model.tar.gz` - Packaged and uploaded to S3
- `s3://photogenius-models-dev/model.tar.gz` - Deployed artifact

## Next Steps

### Phase 1: Basic Validation (TODAY)
- [x] Implement hot-swapping features
- [x] Package and upload to S3
- [ ] Deploy endpoint (in progress)
- [ ] Test basic generation
- [ ] Test model swapping
- [ ] Verify memory cleanup

### Phase 2: Queue System (NEXT)
- [ ] Add Redis queue (Celery/RQ)
- [ ] Request queuing for multi-user
- [ ] Position tracking in queue

### Phase 3: Usage Limits (NEXT)
- [ ] Free tier: 10 generations/day
- [ ] Starter tier: 100 generations/day
- [ ] Pro tier: 500 generations/day

---

**Implementation Complete:** February 15, 2026
**Status:** Deployment in progress (check AWS Console)

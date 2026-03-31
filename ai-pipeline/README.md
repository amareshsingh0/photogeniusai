# AI Pipeline - Modal GPU Services

Modal-based GPU services for model downloading, LoRA training, and image generation.

## ⚠️ Quick Start

```bash
# 1. Install Modal CLI
pip install modal
modal token new

# 2. Create HuggingFace secret (CRITICAL!)
# Option 1: Use PowerShell script (reads from apps/api/.env.local)
.\scripts\setup-modal-secrets.ps1

# Option 2: Manual command
modal secret create huggingface HUGGINGFACE_TOKEN=hf_your_token_here

# 3. Pre-download models (one-time, 5-10 min)
cd ai-pipeline
modal run models/download_models.py

# 4. Test generation
modal run services/generation_service.py::test_generation
```

**📖 For detailed deployment guide, see [DEPLOYMENT.md](./DEPLOYMENT.md)**

## 🎯 Invocation Modes

### SDK Mode (Recommended) ✅

**FastAPI uses Modal Python SDK directly:**

```python
from ai_pipeline.services.generation_service import generate_images

result = await generate_images.remote(
    user_id="user_123",
    identity_id="identity_456",
    prompt="professional headshot",
    mode="REALISM",
)
```

**Configuration:**
- ✅ No `MODAL_API_URL` needed
- ✅ No manual tokens needed
- ✅ Modal CLI auth sufficient
- ✅ Use `modal run` for testing

### HTTP Endpoints (Optional)

**For external services:**

```bash
# Deploy HTTP endpoints
modal deploy services/generation_service.py
modal deploy services/lora_trainer.py

# Get URLs
modal app list
```

**Configuration:**
```env
MODAL_API_URL=https://api.modal.com
MODAL_TOKEN_ID=ak-xxx
MODAL_TOKEN_SECRET=as-xxx
```

## 📦 Prerequisites

### 1. Modal CLI Authentication

```bash
pip install modal
modal token new
```

### 2. HuggingFace Token (CRITICAL) ⚠️

**Why Required:**
- Bypasses rate limits
- Required for gated models
- Essential for CI/CD

**Setup:**
```bash
modal secret create huggingface HUGGINGFACE_TOKEN=hf_your_token_here
```

**Without Token:**
- ❌ Model downloads may fail
- ❌ CI/CD pipelines will fail
- ❌ Production deployments will fail

## 🔄 Job Lifecycle

### LoRA Training (Asynchronous)

**Reality:**
- Training takes 15-20 minutes
- Function returns immediately
- Frontend must poll status

**Flow:**
```
API call → Returns job_id immediately
         → Training runs in background (15-20 min)
         → Frontend polls /api/v1/identities/{id}/training-status
```

### Image Generation

**Sync Mode (Default):**
- Waits for result (30-60 seconds)
- Returns images directly

**Async Mode:**
- Returns job_id immediately
- Poll `/api/v1/generation/{job_id}` for status

## 🔄 Fallback Behavior

### LoRA Not Found

**What Happens:**
```
[WARN] LoRA not found, using base model only
```

**Behavior:**
- ✅ Generation continues with base SDXL
- ✅ No error thrown
- ⚠️ Lower identity consistency

### Model Download Failure

**Behavior:**
- ✅ Automatic retry (3 attempts)
- ✅ Falls back to cached model
- ❌ Fails if no cache

**Prevention:**
- Pre-download models: `modal run models/download_models.py`
- Use HuggingFace token

## 🛡️ Safety Pipeline

### Two-Phase Safety

**Phase 1: Pre-Generation (Prompt Safety)**
- Checks prompt before generation
- Blocks unsafe prompts
- Returns suggested alternatives

**Phase 2: Post-Generation (Image Safety)**
- Checks each generated image
- Drops unsafe images automatically
- Returns only safe images

**Thresholds:**
- REALISM: NSFW threshold = 0.60
- CREATIVE: NSFW threshold = 0.70
- ROMANTIC: NSFW threshold = 0.30 (strictest)

## 📁 Files

- `models/download_models.py` - Pre-download all models
- `services/generation_service.py` - Image generation with LoRA
- `services/lora_trainer.py` - LoRA training service
- `services/safety_service.py` - Safety checks

## 💾 Volumes

- `photogenius-models` - Cached model weights (~8GB)
- `photogenius-loras` - Trained LoRA weights

## 💰 Costs

- **A10G**: ~$0.50/hour
- **A100**: ~$2.00/hour
- **LoRA Training**: 15-20 min → ~$0.50-0.67
- **Image Generation**: 30-60 sec → ~$0.03-0.06

## ✅ Deployment Checklist

- [ ] Modal CLI authenticated (`modal token new`)
- [ ] HuggingFace secret created (`modal secret create huggingface`)
- [ ] Models pre-downloaded (`modal run models/download_models.py`)
- [ ] FastAPI configured (SDK or HTTP mode)
- [ ] Frontend polls async jobs (training status)
- [ ] Error handling for fallbacks

## 📚 Documentation

- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Complete deployment guide
- **[README.md](../README.md)** - Main project README

## 🐛 Troubleshooting

See [DEPLOYMENT.md](./DEPLOYMENT.md#troubleshooting) for common issues and solutions.

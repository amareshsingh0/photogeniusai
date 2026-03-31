# 🚀 Enhanced Modal Deployment Guide

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Invocation Modes](#invocation-modes)
3. [Setup Steps](#setup-steps)
4. [Job Lifecycle Management](#job-lifecycle-management)
5. [Fallback Behavior](#fallback-behavior)
6. [Safety Pipeline](#safety-pipeline)
7. [Troubleshooting](#troubleshooting)

---

## 🔑 Prerequisites

### 1. Modal CLI Authentication

```bash
pip install modal
modal token new
```

**Note**: Modal CLI authentication is sufficient for SDK-based invocation. No manual token env vars needed.

### 2. HuggingFace Token (CRITICAL) ⚠️

**Why Required:**
- Bypasses rate limits for model downloads
- Required for gated models
- Essential for CI/CD and production deployments

**Setup:**

**Option 1: Using PowerShell Script (Recommended)**
```powershell
# From project root - reads HUGGINGFACE_TOKEN from apps/api/.env.local
.\scripts\setup-modal-secrets.ps1
```

**Option 2: Manual Command**
```bash
# Create Modal secret with HuggingFace token
modal secret create huggingface HUGGINGFACE_TOKEN=hf_your_token_here
```

**Verify:**
```bash
modal secret list
# Should show: huggingface
```

**Without Token:**
- Model downloads may fail silently
- Rate limits may block downloads
- CI/CD pipelines will fail
- Production deployments will fail

---

## 🎯 Invocation Modes

### Option A: SDK-Based (Recommended) ✅

**When to Use:**
- FastAPI backend in same repo
- Direct Python function calls
- Better error handling
- Type safety

**How It Works:**
```python
# FastAPI uses Modal Python SDK
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
- ✅ No manual `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` needed
- ✅ Modal CLI auth sufficient
- ✅ Uses `modal run` for testing

**Testing:**
```bash
# Test generation
modal run services/generation_service.py::test_generation

# Test LoRA training
modal run services/lora_trainer.py::test_training
```

### Option B: HTTP Endpoints

**When to Use:**
- External services calling Modal
- Cross-language integration
- Webhook-based workflows

**How It Works:**
```bash
# Deploy HTTP endpoints
modal deploy services/generation_service.py
modal deploy services/lora_trainer.py
```

**Get Endpoint URLs:**
```bash
modal app list
# Copy URLs like:
# https://username--photogenius-generation-generate-images-web.modal.run
```

**Configuration:**
```env
# Required for HTTP endpoints
MODAL_API_URL=https://api.modal.com
MODAL_TOKEN_ID=ak-xxx
MODAL_TOKEN_SECRET=as-xxx
MODAL_USERNAME=your_username
```

**Testing:**
```bash
curl -X POST https://username--photogenius-generation-generate-images-web.modal.run \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "identity_id": "test", "prompt": "test"}'
```

---

## 📦 Setup Steps

### Step 1: Create Modal Secrets

```bash
# HuggingFace token (REQUIRED)
modal secret create huggingface HUGGINGFACE_TOKEN=hf_your_token_here

# Optional: AWS credentials for S3 access
modal secret create aws-credentials \
  AWS_ACCESS_KEY_ID=xxx \
  AWS_SECRET_ACCESS_KEY=xxx
```

### Step 2: Pre-download Models (One-time)

```bash
cd ai-pipeline
modal run models/download_models.py
```

**What Happens:**
- Downloads SDXL base model (~7GB) to persistent volume
- Downloads InstantID models (~1GB)
- Downloads InsightFace models (~500MB)
- Cached in `photogenius-models` volume

**Time:** 5-10 minutes (one-time)

### Step 3: Deploy Services (SDK Mode)

**No deployment needed!** FastAPI calls functions directly via SDK.

**For HTTP Endpoints (Optional):**
```bash
modal deploy services/generation_service.py
modal deploy services/lora_trainer.py
modal deploy services/safety_service.py
```

### Step 4: Configure FastAPI Backend

**For SDK Mode (Recommended):**
```env
# apps/api/.env.local
# No MODAL_API_URL needed
# No MODAL_TOKEN_ID/SECRET needed
# Modal CLI auth is sufficient
```

**For HTTP Mode:**
```env
# apps/api/.env.local
MODAL_API_URL=https://api.modal.com
MODAL_TOKEN_ID=ak-xxx
MODAL_TOKEN_SECRET=as-xxx
MODAL_USERNAME=your_username
```

---

## ⏱️ Job Lifecycle Management

### LoRA Training (Asynchronous)

**Reality:**
- Training takes 15-20 minutes on A100
- Function returns immediately with job ID
- Training runs in background

**Flow:**
```
1. API call → train_lora.remote()
   ↓
2. Returns immediately: { job_id: "train_xxx", status: "queued" }
   ↓
3. Training runs in background (15-20 min)
   ↓
4. Frontend polls status or receives webhook
```

**Status Endpoints:**
```python
# Check training status
GET /api/v1/identities/{identity_id}/training-status

# Response:
{
  "status": "queued" | "processing" | "completed" | "failed",
  "progress": 0.0-1.0,
  "estimated_completion": "2024-01-27T10:30:00Z",
  "error": null
}
```

**Frontend Implementation:**
```typescript
// Poll every 5 seconds
const pollTrainingStatus = async (identityId: string) => {
  const response = await fetch(`/api/v1/identities/${identityId}/training-status`)
  const data = await response.json()
  
  if (data.status === "completed") {
    // Training done, enable generation
  } else if (data.status === "failed") {
    // Show error
  } else {
    // Continue polling
    setTimeout(() => pollTrainingStatus(identityId), 5000)
  }
}
```

### Image Generation (Synchronous or Async)

**Sync Mode (Default):**
```python
# Waits for result (30-60 seconds)
result = await generate_images.remote(...)
# Returns: { images: [...], scores: {...} }
```

**Async Mode:**
```python
# Returns immediately with job_id
job = await create_generation(...)
# Poll for status
status = await get_generation_status(job.job_id)
```

---

## 🔄 Fallback Behavior

### LoRA Not Found

**What Happens:**
```
[WARN] LoRA not found at /loras/user_123/identity_456.safetensors
[WARN] Using base model only
```

**Behavior:**
- ✅ Generation continues with base SDXL
- ✅ No error thrown
- ✅ User gets images (without identity consistency)
- ⚠️ Quality may be lower

**When This Occurs:**
- LoRA training not completed
- LoRA training failed
- LoRA file deleted/corrupted

**Frontend Handling:**
```typescript
if (result.warnings?.includes("lora_not_found")) {
  showWarning("Identity not trained yet. Using base model.")
}
```

### Model Download Failure

**What Happens:**
```
[ERROR] Failed to download model from HuggingFace
[RETRY] Retrying in 5 seconds...
```

**Behavior:**
- ✅ Automatic retry (up to 3 attempts)
- ✅ Falls back to cached model if available
- ❌ Fails if no cache and download fails

**Prevention:**
- Pre-download models: `modal run models/download_models.py`
- Use HuggingFace token to bypass rate limits

### Safety Check Failures

**Prompt Safety (Pre-generation):**
```
[BLOCKED] Prompt failed safety check
Reason: blocked_keyword
Violations: ["explicit", "nsfw"]
```

**Behavior:**
- ❌ Generation blocked
- ✅ User receives error with suggested prompt
- ✅ No charges/credits deducted

**Image Safety (Post-generation):**
```
[BLOCKED] Image failed safety check
NSFW Score: 0.85 (threshold: 0.60)
```

**Behavior:**
- ✅ Unsafe images automatically dropped
- ✅ Only safe images returned to user
- ✅ If all images unsafe → error returned

---

## 🛡️ Safety Pipeline

### Two-Phase Safety Enforcement

#### Phase 1: Pre-Generation (Prompt Safety)

**When:** Before generation starts

**Checks:**
- Blocked keywords (explicit, violence, hate)
- Mode-specific rules (stricter for ROMANTIC)
- Age indicators

**Result:**
- ✅ `allowed: true` → Generation proceeds
- ❌ `allowed: false` → Generation blocked

**Example:**
```python
prompt = "nude person in bedroom"
result = check_prompt_safety(prompt, mode="REALISM")
# Returns: { allowed: false, violations: ["explicit"] }
```

#### Phase 2: Post-Generation (Image Safety)

**When:** After images generated

**Checks:**
- NSFW detection (NudeNet)
- Age estimation
- Violence detection

**Result:**
- ✅ Safe images → Returned to user
- ❌ Unsafe images → Dropped automatically

**Example:**
```python
for image in generated_images:
    safety = check_image_safety(image.base64, mode="REALISM")
    if safety.safe:
        safe_images.append(image)
    else:
        logger.warning(f"Image blocked: {safety.violations}")
```

**Thresholds by Mode:**
- REALISM: NSFW threshold = 0.60
- CREATIVE: NSFW threshold = 0.70
- ROMANTIC: NSFW threshold = 0.30 (strictest)

---

## 🐛 Troubleshooting

### Model Download Fails

**Symptoms:**
```
[ERROR] 401 Unauthorized
[ERROR] Rate limit exceeded
```

**Solutions:**
1. ✅ Create HuggingFace secret: `modal secret create huggingface HUGGINGFACE_TOKEN=hf_xxx`
2. ✅ Pre-download models: `modal run models/download_models.py`
3. ✅ Check token validity: `curl -H "Authorization: Bearer hf_xxx" https://huggingface.co/api/whoami`

### LoRA Training Hangs

**Symptoms:**
- Training status stuck at "processing"
- No progress updates

**Solutions:**
1. ✅ Check Modal logs: `modal app logs photogenius-lora-trainer`
2. ✅ Verify GPU availability: `modal app list`
3. ✅ Check training images: Ensure 5+ valid images
4. ✅ Retry with fewer steps for testing: `training_steps=100`

### Generation Returns Empty Results

**Symptoms:**
- `images: []` in response
- All images blocked by safety

**Solutions:**
1. ✅ Check safety logs for violations
2. ✅ Try different prompt (less explicit)
3. ✅ Check mode-specific thresholds
4. ✅ Verify LoRA exists (if using identity)

### Modal SDK Calls Fail

**Symptoms:**
```
ModalClientError: Authentication failed
```

**Solutions:**
1. ✅ Re-authenticate: `modal token new`
2. ✅ Check Modal CLI: `modal app list` (should work)
3. ✅ Verify environment: SDK mode doesn't need API URL

---

## 📊 Cost Estimation

### GPU Costs (Modal)

- **A10G**: ~$0.50/hour
- **A100**: ~$2.00/hour

### Typical Usage

- **Model Download**: 1x (one-time) → ~$0.10
- **LoRA Training**: 15-20 min → ~$0.50-0.67
- **Image Generation**: 30-60 sec → ~$0.03-0.06

### Monthly Estimate (1000 generations)

- Generations: 1000 × $0.05 = $50
- Training: 50 × $0.60 = $30
- **Total**: ~$80/month

---

## ✅ Checklist

Before deploying to production:

- [ ] HuggingFace token stored as Modal secret
- [ ] Models pre-downloaded to volume
- [ ] Modal CLI authenticated (`modal token new`)
- [ ] FastAPI configured (SDK or HTTP mode)
- [ ] Frontend polls training status (async)
- [ ] Error handling for fallback scenarios
- [ ] Safety thresholds configured
- [ ] Monitoring/logging set up

---

## 🎓 Key Takeaways

1. **SDK Mode (Recommended)**: No API URL, no manual tokens, CLI auth sufficient
2. **HuggingFace Token**: Critical for CI/CD, create Modal secret
3. **LoRA Training**: Async, frontend must poll status
4. **Fallback Behavior**: System gracefully degrades (base model if LoRA missing)
5. **Two-Phase Safety**: Prompt check before, image check after generation
6. **Pre-download Models**: One-time setup saves time and money

---

**Last Updated:** 2026-01-27

# PhotoGenius AI – AI-Only Implementation Plan

**Focus:** Accuracy, deployment cost, image quality. No business/marketing.
**Scope:** Sirf AI pipeline, models, safety, quality. Website updates baad mein.
**Last Updated:** Project setup is AWS-only (no Modal).

> **📋 NOTE:** For complete enhanced masterplan with Phase 2-4 features, see `docs/ULTIMATE_MASTERPLAN.md`.  
> **Architecture & deployment:** See `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT_MODAL_VS_AWS.md`, `docs/AWS_SETUP.md`. Modal is reference only (docs/MODAL_SETUP.md).

---

## 0. Current implementation status (post-plan)

| Area | Status | Where |
|------|--------|-------|
| **InstantID** | ✅ Done | `ai-pipeline/services/instantid_service.py` (Modal A10G); `generation_service.generate_image_v2` (optional InstantID) |
| **Semantic enhancer** | ✅ Done | `ai-pipeline/services/semantic_prompt_enhancer.py`; used by orchestrator_aws |
| **Two-pass (preview + final)** | ✅ Done | `ai-pipeline/services/two_pass_generation.py` (AWS); SageMaker `inference_two_pass.py` |
| **Orchestrator AWS** | ✅ Done | `ai-pipeline/services/orchestrator_aws.py`; `generate_professional(quality_tier=FAST/STANDARD/PREMIUM)` |
| **AWS model download** | ✅ Done | `aws/scripts/download_models.py` (SDXL Base/Turbo/Refiner, InstantID, InsightFace, Sentence Transformer) |
| **Tests** | ✅ Done | `ai-pipeline/tests/test_improvements.py` (face accuracy, semantic, two-pass timing, fallback) |

**Setup (AWS):** orchestrator_aws, two_pass_generation, semantic_enhancer; SageMaker + Lambda. See **docs/DEPLOYMENT_MODAL_VS_AWS.md**.  
Modal code (generation_service, instantid_service, orchestrator, lora_trainer, safety) is reference only; not used for setup.

---

## 1. Abhi Kya Deploy / Implement Ho Chuka Hai

### 1.1 Generation Pipeline (ai-pipeline/services/generation_service.py)

| Component | Status | Detail |
|-----------|--------|--------|
| **SDXL 1.0 base** | ✅ Done | `stabilityai/stable-diffusion-xl-base-1.0`, Modal A100, fp16 |
| **LoRA training** | ✅ Done | Modal A100, InsightFace buffalo_l face crop → LoRA, trigger `sks` |
| **LoRA in generation** | ✅ Done | Load user LoRA from volume, smart trigger word insertion for multiple nouns |
| **Compel prompt weighting** | ✅ Done | SDXL dual text encoder weighting via `compel==2.0.2` |
| **5 Modes** | ✅ Done | REALISM, CREATIVE, ROMANTIC, FASHION, CINEMATIC – each with prefix, quality_boost, technical, negative prompts |
| **Mode-specific params** | ✅ Done | Per-mode guidance_scale, steps, width×height (portrait for FASHION, landscape for CINEMATIC) |
| **Best-of-N scoring** | ✅ Done | 4 candidates → score → top 2 return |
| **Image scoring** | ✅ Done | Face match (InsightFace cosine), aesthetic (brightness+contrast+saturation+color harmony), technical (Laplacian sharpness + noise estimation) |
| **Mode-specific score weights** | ✅ Done | REALISM: face 50%, CREATIVE: aesthetic 50%, CINEMATIC: aesthetic 50% + technical 30% |
| **Modal deploy** | ✅ Done | `photogenius-generation` (A100), `photogenius-lora-trainer` (A100), `photogenius-safety` (CPU+T4) |
| **Next.js → Modal direct** | ✅ Done | `/api/generate` route calls Modal endpoints directly, no FastAPI dependency |

### 1.2 Safety (ai-pipeline/services/safety_service.py)

| Component | Status | Detail |
|-----------|--------|--------|
| **Context-aware prompt safety** | ✅ Done | Word boundary regex, safe context exceptions ("childhood" OK, "child" blocked), dangerous combo detection |
| **Image safety (NudeNet)** | ✅ Done | NSFW detection with mode-specific thresholds |
| **Age estimation** | ⚠️ Basic | OpenCV Haar cascade + Laplacian heuristic (not accurate) |
| **Violence detection** | ⚠️ Basic | Red channel + edge density heuristic (not accurate) |

### 1.3 LoRA Training (ai-pipeline/services/lora_trainer.py)

| Component | Status | Detail |
|-----------|--------|--------|
| **Face detection + crop** | ✅ Done | InsightFace buffalo_l, largest face crop |
| **LoRA fine-tune** | ✅ Done | DreamBooth-style, 500 steps, lr 1e-4, rank 4 |
| **Volume save** | ✅ Done | `/loras/{user_id}/{identity_id}.safetensors` |

### 1.4 Jo EXIST Karta Hai / Ab Use Ho Raha Hai

| Component | Location | Status | Detail |
|-----------|----------|--------|--------|
| **InstantID pipeline** | `ai-pipeline/services/instantid_service.py` | ✅ Done | Modal A10G; `generate_with_instantid`; 90%+ face. Also `generation_service.generate_image_v2` (optional InstantID). |
| **InstantID model download** | `ai-pipeline/models/download_instantid.py`; `aws/scripts/download_models.py` | ✅ Done | ai-pipeline for Modal/EFS; aws/scripts for AWS (no Modal). |
| **Two-pass (Turbo + Base + Refiner)** | `ai-pipeline/services/two_pass_generation.py` | ✅ Done | AWS path; `generate_fast`, `generate_two_pass`; SageMaker inference_two_pass. |
| **Semantic enhancer** | `ai-pipeline/services/semantic_prompt_enhancer.py` | ✅ Done | Sentence-transformers; used by orchestrator_aws. |
| **Orchestrator AWS** | `ai-pipeline/services/orchestrator_aws.py` | ✅ Done | `generate_professional`; FAST/STANDARD/PREMIUM; fallbacks. |
| **Quality scorer** | `apps/ai-service` / `ai-pipeline/services/quality_scorer.py` | ⚠️ Varies | Real scoring in ai-pipeline; apps/ai-service may still have placeholder. |
| **SDXL-Turbo preview** | `two_pass_generation.generate_fast` (AWS) | ✅ Done | Turbo-only <5s; AWS path. Modal path uses generation_service. |
| **Face embedding in gen** | generation_service.py | ⚠️ Scoring | `face_embedding` for scoring; InstantID used for face conditioning in generate_image_v2. |
| **FastAPI backend** | `apps/api` | ✅ Used | Can use Modal client or AWS GPU client; orchestrator_aws for AWS path. |

### 1.5 Current Deployment Cost

| Item | Current | Monthly Est. (low usage) |
|------|---------|--------------------------|
| **Gen GPU** | A100 per request | ~$0.03/image (40s × $3.06/hr) |
| **Train GPU** | A100 per training | ~$0.25/training (5min × $3.06/hr) |
| **Safety** | CPU (prompt) + T4 (image) | ~$0.002/check |
| **Scaling** | Modal serverless, scale-to-zero | $0 idle |
| **Storage** | 2 Modal volumes (models + loras) | ~$0.50/month |

---

## 2. Kya Enhance Karna Hai (Priority Order)

### Phase 1: InstantID + Face Consistency (ACCURACY – HIGHEST PRIORITY)

**Problem:** Abhi sirf LoRA se face control ho rha hai. LoRA alone gives ~60-70% face consistency. InstantID se 90%+ possible hai.

**Steps:**

- [ ] **1.1** Run `download_models.py` to download InstantID artifacts to Modal volume
  - `ip-adapter.bin` (IP-Adapter weights)
  - `ControlNetModel/config.json` + `diffusion_pytorch_model.safetensors`
  - File: `ai-pipeline/models/download_models.py`

- [ ] **1.2** Add InstantID to generation_service.py
  - Import `ip_adapter` from diffusers
  - Load ControlNet model from volume
  - Load IP-Adapter weights
  - Wire face_embedding → IP-Adapter conditioning
  - Add `controlnet_conditioning_scale` per mode:
    - REALISM: 0.88–0.92
    - CREATIVE: 0.65–0.75
    - ROMANTIC: 0.75–0.82
    - FASHION: 0.80–0.85
    - CINEMATIC: 0.70–0.78

- [ ] **1.3** Save face embedding during LoRA training
  - In `lora_trainer.py`: after face crop, compute InsightFace embedding
  - Save as `{lora_dir}/face_embedding.npy`
  - In `generation_service.py`: load embedding from volume before gen

- [ ] **1.4** Upgrade face match reranker
  - Use ArcFace/InsightFace embedding cosine similarity (already partly done)
  - Add minimum face threshold per mode:
    - REALISM: min 0.75 similarity, else retry with higher identity_scale
    - CREATIVE: min 0.60
  - Max 2 retries with +0.05 identity_scale bump each retry

### Phase 2: Quality Scoring Upgrade

- [ ] **2.1** Replace placeholder quality_scorer.py with real implementation
  - Face similarity: InsightFace embedding cosine (0-100)
  - Aesthetic: LAION aesthetic predictor V2 (`laion/CLIP-ViT-H-14-laion2B-s32B-b79K` + linear head)
  - Technical: Laplacian sharpness + noise (already done in ai-pipeline)
  - Prompt adherence: CLIP similarity between prompt and generated image
  - File: create new `ai-pipeline/services/quality_scorer.py` (Modal function)

- [ ] **2.2** Wire quality scorer into generation pipeline
  - After generation, before returning: run quality check
  - Reject images below threshold (face < 0.5, aesthetic < 4.0/10)
  - Auto-regenerate rejected images (max 1 retry)

- [ ] **2.3** Best-of-N tuning per mode
  - REALISM: best-of-2 (speed matters, face lock strong)
  - CREATIVE: best-of-4 + reranker
  - FASHION: best-of-3
  - CINEMATIC: best-of-3
  - Return scores in API response (already partially done)

### Phase 3: SDXL-Turbo Preview

- [ ] **3.1** Add SDXL-Turbo model to download script
  - `stabilityai/sdxl-turbo` → Modal volume
  - ~3GB additional storage

- [ ] **3.2** Create preview endpoint in generation_service.py
  - Separate `@app.function` with lower GPU (T4 or A10G)
  - 4 steps, guidance_scale=1.0
  - Single image, no scoring
  - Target: <5 seconds response

- [ ] **3.3** Wire preview into API
  - `/api/generate/preview` endpoint
  - Returns 512×512 preview image
  - User sees preview → confirms → full generation starts

### Phase 4: Cost Optimization

- [ ] **4.1** GPU benchmarking
  - Test A10G vs A100 for generation quality
  - Test L4 for generation
  - If A10G quality ≥ 95% of A100: switch (saves ~60% cost)
  - Keep A100 for training

- [ ] **4.2** Model pre-loading with `@modal.enter()`
  - Convert generation_service to `@app.cls()` with `@modal.enter()` method
  - Load SDXL model once, reuse across requests
  - Eliminates ~30s model loading on each request
  - **Impact: 30s → instant for warm containers**

- [ ] **4.3** Preview cache
  - Key: hash(prompt + identity_id + mode)
  - Store in Modal Dict or Redis
  - TTL: 7 days
  - Skip generation if cache hit

- [ ] **4.4** Modal container tuning
  - `keep_warm=1` for generation function (always 1 warm container)
  - `concurrency_limit=2` per container
  - `scaledown_window=120` seconds

### Phase 5: Safety Hardening

- [ ] **5.1** Upgrade age estimator
  - Replace OpenCV heuristic with DeepFace or dedicated age model
  - Run on upload (before training) AND post-generation
  - Block any face estimated < 18

- [ ] **5.2** Prompt safety enhancements
  - Unicode/homoglyph obfuscation detection (e.g., "сhild" with Cyrillic "с")
  - Celebrity/politician name blocklist
  - Segment/split detection ("ch" + "ild")

- [ ] **5.3** Post-generation safety
  - Mode-specific NudeNet thresholds (ROMANTIC: 0.7, others: 0.4)
  - Already partially implemented, needs threshold tuning

- [ ] **5.4** Adversarial testing
  - Create test suite with known adversarial prompts
  - Automated monthly blocklist update process

---

## 3. Architecture Diagram

```
User Prompt + Identity
        │
        ▼
┌─────────────────┐
│  Next.js API     │  /api/generate
│  (Vercel/local)  │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────────────────────────┐
│ Safety │ │ Generation (Modal A100)       │
│ (CPU)  │ │                              │
│        │ │ 1. Load SDXL (@modal.enter)  │
│ Prompt │ │ 2. Load LoRA (user volume)   │
│ Check  │ │ 3. Load InstantID ← TODO     │
│        │ │ 4. Face embedding → IP-Adapter│
└────┬───┘ │ 5. Compel prompt weighting   │
     │     │ 6. Generate N candidates     │
  allowed? │ 7. Score (face+aesthetic+tech)│
     │     │ 8. Return top 2              │
     ▼     └──────────────┬───────────────┘
  blocked →               │
  return 403              ▼
                   ┌──────────────┐
                   │ Image Safety │  (Modal T4)
                   │ NudeNet      │
                   │ Age check    │
                   └──────┬───────┘
                          │
                     safe? return images
                     unsafe? return blocked
```

**Training Flow:**
```
User Photos (5-20)
        │
        ▼
┌─────────────────┐
│ Upload + Validate│  Face detection, quality, same-person check
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│ LoRA Training (Modal A100)      │
│                                 │
│ 1. InsightFace face detection   │
│ 2. Face crop + alignment        │
│ 3. Compute face embedding       │
│ 4. Save embedding (.npy) ← TODO│
│ 5. DreamBooth LoRA fine-tune    │
│ 6. Save to /loras/{user}/{id}   │
└─────────────────────────────────┘
```

---

## 4. Files Ka Map (Kya Kahan Hai)

### Active Pipeline (Modal pe deploy)
```
ai-pipeline/
├── models/
│   └── download_models.py          # Downloads SDXL + InstantID to Modal volume
├── services/
│   ├── generation_service.py       # ✅ MAIN – SDXL gen, LoRA, Compel, scoring
│   ├── safety_service.py           # ✅ Context-aware prompt + NudeNet image
│   └── lora_trainer.py             # ✅ DreamBooth LoRA training
```

### Legacy (apps/ai-service – NOT in active pipeline)
```
apps/ai-service/
├── app/services/ai/
│   ├── instantid.py                # Stub – InstantID class (not wired)
│   ├── quality_scorer.py           # Placeholder – hardcoded scores
│   ├── sdxl_pipeline.py            # Preview/Full config + generate functions
│   ├── sdxl_service.py             # SDXL service class
│   ├── lora_trainer.py             # Older trainer (Modal uses ai-pipeline version)
│   └── download_models.py          # SDXL + safety model downloads
├── app/services/safety/
│   ├── safety_service.py           # Older safety (Modal uses ai-pipeline version)
│   ├── nsfw_classifier.py          # NudeNet wrapper
│   ├── age_estimator.py            # OpenCV age estimation
│   ├── dual_pipeline.py            # Pre+post gen safety pipeline
│   └── prompt_sanitizer.py         # Prompt cleaning
├── modal_app.py                    # Older Modal app config (photogenius-ai)
```

### Website API (calls Modal directly)
```
apps/web/
├── app/api/generate/route.ts       # ✅ POST → Modal safety + generation
├── lib/stores/generation-store.ts  # ✅ Frontend state, calls /api/generate
```

---

## 5. Implementation Order Summary

| # | Task | Impact | Difficulty | Est. Cost |
|---|------|--------|------------|-----------|
| 1 | **Model pre-loading (@modal.enter)** | 30s faster per request | Medium | $0 |
| 2 | **InstantID integration** | 60→90%+ face accuracy | Hard | $0 (models free) |
| 3 | **Face embedding save in training** | Required for InstantID | Easy | $0 |
| 4 | **Quality scorer upgrade** | Better image selection | Medium | $0 |
| 5 | **SDXL-Turbo preview** | <5s user feedback | Medium | ~$0.005/preview |
| 6 | **GPU benchmarking (A10G)** | ~60% cost reduction | Easy | Test credits |
| 7 | **Age model upgrade** | Safety compliance | Medium | $0 |
| 8 | **Prompt obfuscation detection** | Adversarial safety | Easy | $0 |

**Recommended order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8**

Start with #1 (model pre-loading) because it's the biggest UX improvement with least effort. Then #2 (InstantID) for the biggest accuracy jump. Everything else follows.

---

## 6. Kya Nahi Karna (Is Plan Me)

- Website / UI changes
- Pricing, credits, marketing
- New product features (style mixer, marketplace)
- B2B / enterprise flows
- Mobile app / PWA
- FastAPI backend (bypassed, Modal direct)

---

## 7. Key Metrics to Track

| Metric | Current | Target |
|--------|---------|--------|
| **Face consistency** | ~60-70% (LoRA only) | 90%+ (LoRA + InstantID) |
| **Generation time** | ~70s (30s load + 40s gen) | ~40s (pre-loaded + 40s gen) |
| **Preview time** | N/A | <5s |
| **Cost per image** | ~$0.03 | ~$0.01-0.02 (A10G) |
| **Safety false positives** | ~15% (old keyword) | <5% (context-aware) ✅ |
| **NSFW detection** | NudeNet basic | NudeNet + mode thresholds ✅ |

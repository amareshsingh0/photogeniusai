# PhotoGenius AI – Frontend, Backend & AI Pipeline Connections

How the frontend, backend, and AI pipeline connect. **Project setup is AWS-only** (no Modal). See [ARCHITECTURE.md](ARCHITECTURE.md) and [DEPLOYMENT_MODAL_VS_AWS.md](DEPLOYMENT_MODAL_VS_AWS.md).

---

## 1. Single source of truth (no divergent duplicates)

- **Prompt enhancement (Midjourney-style):**  
  **Canonical:** `ai-pipeline/services/midjourney_concepts.py` and `ai-pipeline/services/midjourney_prompt_enhancer.py`  
  **Synced for deployment:**  
  - `aws/lambda/generation/midjourney_concepts.py` and `midjourney_prompt_enhancer.py` (Lambda)  
  - `apps/api/app/services/midjourney_concepts.py` and `midjourney_prompt_enhancer.py` (FastAPI)  
  Update ai-pipeline first, then sync to aws and apps/api.

- **Semantic enhancement:**  
  **Canonical:** `ai-pipeline/services/semantic_prompt_enhancer.py`  
  Used by `orchestrator_aws.py` (AWS path). Can be included in Modal image if needed.

- **Two-pass generation:**  
  **Canonical:** `ai-pipeline/services/two_pass_generation.py`  
  **AWS:** `aws/sagemaker/model/code/two_pass_generation.py` (copy for SageMaker package). Used by SageMaker `inference_two_pass.py`.

---

## 2. Request flow

### 2.1 Frontend (Next.js – `apps/web`)

- **Create / Generate:** `app/(dashboard)/generate/` → user enters prompt and mode.
- **API route:** `POST /api/generate` (`app/api/generate/route.ts`).
  - **If FastAPI backend:** calls `POST {FASTAPI_URL}/api/v1/generation/sync` (safety + generation).
  - **Else:** `AIService.generate()` via `lib/cloud-config.ts` → **Modal** URL or **AWS** (Lambda / API Gateway / SageMaker).

### 2.2 Cloud config (`apps/web/lib/cloud-config.ts`)

- `getServiceUrl("generation")`: **backend** (FastAPI) / **aws** (Lambda, API Gateway, SageMaker — default) / optional modal.
- Same idea for safety, refinement, training. Setup is AWS-only.

### 2.3 Backend – FastAPI (`apps/api`)

- **Generation:** `POST /api/v1/generation/sync` (or unified generate):
  - **Default (AWS):** `app/services/aws_gpu_client.py` → SageMaker (and optional Lambda); uses `midjourney_prompt_enhancer`; can call orchestrator_aws / two-pass flow.
  - Optional: `app/services/modal_client.py` only if `GPU_WORKER_PRIMARY=modal`.
- **Prompt enhancement:** Inside aws_gpu_client; no separate “enhance” endpoint for main Create flow.

### 2.4 AI pipeline (`ai-pipeline`)

- **Modal path:** `generation_service.py`, `instantid_service.py`, `orchestrator.py`, `lora_trainer.py`, `safety_service.py` (Modal stubs + volumes).
- **AWS path:** `orchestrator_aws.py` (`generate_professional`), `two_pass_generation.py` (`generate_fast`, `generate_two_pass`), `semantic_prompt_enhancer.py`; no Modal; models via `aws/scripts/download_models.py` and S3/EFS.
- **Shared:** `midjourney_concepts.py`, `midjourney_prompt_enhancer.py`; used by generation_service (Modal) and synced to Lambda/apps/api.

### 2.5 AWS Lambda (`aws/lambda`)

- **Generation:** `lambda/generation/handler.py` → SageMaker; uses synced `midjourney_*` in `lambda/generation/`.
- **Orchestrator:** `lambda/orchestrator/handler.py` can chain Prompt Enhancer → SageMaker → Post-Processor.

---

## 3. Summary

| Layer        | Role |
|-------------|------|
| **Frontend** | Create UI → `/api/generate` → FastAPI sync or AIService (AWS default). |
| **Cloud config** | Default **aws**; optional backend / modal. |
| **FastAPI** | Sync generation via **AWS GPU client** (SageMaker/Lambda); midjourney_prompt_enhancer, orchestrator_aws/two-pass. |
| **AI pipeline** | Canonical enhancers and generation; **AWS** (orchestrator_aws, two_pass, semantic_enhancer). |
| **AWS Lambda** | Generation/orchestrator use synced midjourney_* and SageMaker. |

Keep **one canonical implementation** in ai-pipeline; **sync** into `aws/lambda/generation/` and `apps/api/app/services/` where needed.

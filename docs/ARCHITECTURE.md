# PhotoGenius AI – Architecture (A–Z)

Full project architecture: monorepo layout, data flow, services, APIs, database, and infra. **Setup is AWS-only** (no Modal); see [DEPLOYMENT_MODAL_VS_AWS.md](DEPLOYMENT_MODAL_VS_AWS.md).

---

## 1. Monorepo Layout

```
PhotoGenius AI/
├── apps/
│   ├── web/                 # Next.js 14 App Router, React, Tailwind, shadcn/ui
│   ├── api/                 # FastAPI backend (PostgreSQL, S3, Redis, AI clients)
│   └── ai-service/          # Optional FastAPI AI service (SDXL, LoRA, Modal app)
├── ai-pipeline/             # Canonical AI services (generation, safety, LoRA, InstantID, etc.)
│   ├── api/                 # Standalone API (health, v1 endpoints)
│   ├── services/            # Generation, InstantID, two-pass, semantic enhancer, orchestrator
│   ├── models/              # Model download scripts (InstantID, base models)
│   ├── caching/             # Smart cache
│   ├── monitoring/          # Logging, metrics, alerts
│   └── tests/               # Pytest (test_improvements, integration)
├── aws/                     # AWS-only: no Modal
│   ├── lambda/              # Generation, orchestrator, post-processor, prompt enhancer, safety
│   ├── sagemaker/           # SDXL / two-pass inference (deploy_model, inference.py, inference_two_pass.py)
│   └── scripts/             # download_models.py (populate models for SageMaker/EFS)
├── packages/
│   ├── database/            # Prisma schema, migrations, seed
│   ├── types/               # Shared TypeScript types
│   └── ui/                  # Shared UI components
├── config/                  # Python tier_config
├── infra/                   # Docker, Terraform, k8s
├── scripts/                 # Setup, deploy, verify (Modal + AWS)
└── docs/                    # All .md documentation
```

---

## 2. Data Flow (End-to-End)

1. **Web (Next.js)**  
   User enters prompt and mode → `POST /api/generate` or proxy to FastAPI.

2. **Generation path**
   - **Backend = FastAPI:** `apps/api` → `POST /api/v1/generation/sync` (or unified generate) → **AWS GPU client** (SageMaker/Lambda) by default; optional Modal.
   - **Direct:** Web → `lib/cloud-config.ts` → **AWS** (API Gateway + Lambda/SageMaker) by default.

3. **AI pipeline**
   - **Setup (AWS):** `ai-pipeline` logic used inside SageMaker/Lambda (two_pass_generation, semantic_prompt_enhancer, orchestrator_aws). Models in S3/EFS; download via `aws/scripts/download_models.py`.
   - **Reference only:** Modal stubs (generation_service, instantid_service, orchestrator, lora_trainer, safety) exist in repo; not used for project setup.

4. **Database**  
   PostgreSQL (Supabase or self-hosted). Prisma in Next.js; SQLAlchemy/Alembic in FastAPI. Tables: users, generations, identities, safety_audit_logs, credit_transactions.

5. **Storage**  
   S3/R2 for images and LoRA artifacts. Setup uses S3/EFS (no Modal volumes).

---

## 3. Where things run (AWS-only setup)

| Area | Where (AWS) |
|------|-------------|
| **Generation (SDXL + LoRA)** | SageMaker endpoint (inference.py) or two-pass (inference_two_pass.py) |
| **InstantID (face 90%+)** | Same logic on SageMaker/EC2 with models in S3/EFS |
| **Two-pass (preview + final)** | two_pass_generation.py, SageMaker inference_two_pass.py |
| **Orchestrator** | orchestrator_aws.py (generate_professional); Lambda or backend |
| **Semantic enhancer** | semantic_prompt_enhancer.py (used by orchestrator_aws) |
| **LoRA training** | Lambda/ECS or SageMaker training job |
| **Safety** | Lambda (safety handler) |
| **Model storage** | S3 + optional EFS; download via aws/scripts/download_models.py |
| **API gateway** | API Gateway + Lambda / ECS |

**No Modal setup.** See **docs/DEPLOYMENT_MODAL_VS_AWS.md** and **docs/AWS_SETUP.md**.

---

## 4. Apps

### 4.1 apps/web (Next.js)

- **Stack:** Next.js 14, TypeScript, Tailwind, shadcn/ui.
- **Routes:** Dashboard, generate, identity-vault, gallery; API routes under `app/api/` (generate, identities, preferences, variants).
- **Config:** `lib/cloud-config.ts` – backend URL, generation/safety/training URLs; default **AWS** (no Modal setup).
- **Auth:** Clerk (optional) or stub.

### 4.2 apps/api (FastAPI)

- **Role:** Main backend API (auth, generations, identities, storage, tier enforcement).
- **AI:** Uses **aws_gpu_client.py** (SageMaker, Lambda); prompt enhancement via `midjourney_prompt_enhancer.py` (synced from ai-pipeline). Project setup is AWS-only; no Modal.
- **DB:** PostgreSQL via SQLAlchemy/Alembic; Prisma types shared with web.
- **Storage:** S3/R2 via `storage/s3_service.py`.

### 4.3 apps/ai-service (Optional FastAPI)

- **Role:** Dedicated AI API (generation, safety, training). Can run on AWS (ECS/Lambda) or locally; no Modal setup in project.

---

## 5. AI Pipeline (ai-pipeline)

### 5.1 Core generation

- **generation_service.py** – SDXL + LoRA on Modal (A100); `generate_images`, `generate_image` (deprecated), `generate_image_v2` (InstantID optional).
- **instantid_service.py** – InstantID on Modal (A10G); `generate_with_instantid`; face consistency 90%+.
- **two_pass_generation.py** – No Modal: Pass 1 Turbo (~5s), Pass 2 Base+LoRA/InstantID, Pass 3 Refiner; `generate_fast`, `generate_two_pass`; for AWS/SageMaker.

### 5.2 Orchestration

- **orchestrator.py** – Modal orchestrator (multimodal, cache, identity v2, creative, ultra).
- **orchestrator_aws.py** – AWS orchestrator (no Modal): `generate_professional(user_prompt, identity_id, user_id, mode, quality_tier)`; semantic enhancement → FAST/STANDARD/PREMIUM routing with fallbacks.

### 5.3 Prompt & quality

- **semantic_prompt_enhancer.py** – Sentence-transformers; semantic categories; contradiction removal; used by orchestrator_aws.
- **midjourney_concepts.py** + **midjourney_prompt_enhancer.py** – Canonical prompt concepts; synced to Lambda and apps/api.
- **quality_scorer.py**, **quality_assessment.py** – Scoring and verdicts.

### 5.4 Other services

- **lora_trainer.py** – LoRA training (Modal A100 or AWS).
- **safety_service.py** – Prompt + image safety (Modal or Lambda).
- **identity_engine.py** / **identity_engine_v2.py** – Identity and face pipelines.
- **realtime_engine.py**, **ultra_high_res_engine.py**, **creative_engine.py** – Specialized generation paths.

---

## 6. AWS (aws/)

- **Lambda:** generation, orchestrator, post_processor, prompt_enhancer, safety – handlers and synced enhancer/concepts.
- **SageMaker:** `sagemaker/deploy_model.py`, `sagemaker/model/code/inference.py` (single-pass SDXL), `inference_two_pass.py` + `two_pass_generation.py` (two-pass).
- **Scripts:** `aws/scripts/download_models.py` – download SDXL Base/Turbo/Refiner, InstantID, InsightFace, Sentence Transformer to local/EFS; optional S3 sync. No Modal.

---

## 7. Database & storage

- **PostgreSQL:** Users, generations, identities, safety_audit_logs, credit_transactions (Alembic migrations in apps/api).
- **Prisma:** packages/database for schema and seed; used by web.
- **S3/R2:** Generated images, LoRA artifacts, uploads. Modal volumes for Modal-only assets.

---

## 8. Auth & compliance

- **Auth:** Clerk (when enabled); webhooks for Clerk, Stripe.
- **Compliance:** Consent records; safety audit logs; configurable retention (e.g. 180 days). See schema and SafetyAuditLog.

---

## 9. Infra

- **Docker:** infra/docker – docker-compose (dev, prod, observability).
- **K8s:** infra/k8s – deployment and service manifests.
- **Terraform:** infra/terraform – AWS, Cloudflare.

---

## 10. Key documentation

| Doc | Purpose |
|-----|---------|
| **ARCHITECTURE.md** (this file) | Full A–Z architecture |
| **DEPLOYMENT_MODAL_VS_AWS.md** | Project setup is AWS-only; no Modal setup |
| **AWS_SETUP.md** | AWS setup (Lambda, SageMaker, S3, download script) |
| **CONNECTIONS.md** | Frontend ↔ Backend ↔ AI pipeline; canonical enhancer |
| **ORCHESTRATOR_AWS_INTEGRATION.md** | orchestrator_aws, generate_professional, quality tiers |
| **AWS_TWO_PASS.md** | Two-pass pipeline on SageMaker |
| **CURRENT_STATUS.md** | Current status and next steps |

---

**Last updated:** Full setup on AWS; no Modal setup in project.

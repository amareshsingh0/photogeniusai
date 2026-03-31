# 📊 Current Status – PhotoGenius AI

**Full setup is AWS-only (no Modal).** Status: orchestrator_aws, two-pass, semantic enhancer, AWS download, tests.

---

## ✅ Completed

### Core stack
1. **Prompt builder** – All tests passing; Midjourney-style enhancer canonical in ai-pipeline; synced to Lambda and apps/api.
2. **Redis** – Upstash (when configured).
3. **Database** – PostgreSQL (Supabase or self-hosted); Prisma + Alembic.
4. **Environment** – Env vars documented; verify via pnpm verify-env / scripts.
5. **Docker** – infra/docker (dev, prod, observability).

### AI pipeline (ai-pipeline)
6. **Generation service (reference)** – Modal stubs in `generation_service.py`; not used for setup.
7. **InstantID (reference)** – `instantid_service.py` (Modal stub); setup uses AWS/SageMaker path.
8. **Two-pass generation (AWS)** – `two_pass_generation.py` (no Modal): `generate_fast` (Turbo), `generate_two_pass` (Base + Refiner, optional InstantID in Pass 2); for SageMaker.
9. **Semantic prompt enhancer** – `semantic_prompt_enhancer.py`; sentence-transformers; pattern DB; contradiction removal; used by orchestrator_aws.
10. **Orchestrator AWS** – `orchestrator_aws.py`; `generate_professional(user_prompt, identity_id, user_id, mode, quality_tier)`; FAST/STANDARD/PREMIUM; semantic enhancement + fallbacks (PREMIUM → STANDARD → BASIC).
11. **LoRA training** – AWS path (Lambda/ECS or SageMaker); face crop, LoRA save to S3.

### AWS (no Modal)
12. **AWS download script** – `aws/scripts/download_models.py`: SDXL Base/Turbo/Refiner, InstantID, InsightFace, Sentence Transformer; optional S3 sync; verify via `--verify-only`.
13. **SageMaker** – `deploy_model.py`; `inference.py` (single-pass); `inference_two_pass.py` + `two_pass_generation.py` (two-pass).
14. **Lambda** – generation, orchestrator, post_processor, prompt_enhancer, safety (handlers + synced enhancer).

### Tests
15. **Improvements test suite** – `ai-pipeline/tests/test_improvements.py`: InstantID accuracy, semantic enhancement, two-pass timing, quality comparison, graceful degradation, contradiction removal; pytest; `-m "not gpu"` for non-GPU tests.

### Docs
16. **Architecture** – `docs/ARCHITECTURE.md` (A–Z: monorepo, AWS-only setup, services, APIs, DB).
17. **Modal (reference)** – `docs/MODAL_SETUP.md` – not used for project setup.
18. **AWS setup** – `docs/DEPLOYMENT_MODAL_VS_AWS.md` (AWS-only; no Modal setup).

---

## ⚠️ In progress / optional

- **AWS SageMaker** – Deploy two-pass endpoint; run `aws/scripts/download_models.py` and sync to S3; use `inference_two_pass.py` as entrypoint.
- **Frontend variant UI** – Variants and preference tracking APIs exist; frontend for 6 variants and “copy for MJ/Flux/DALL-E/SD” optional.

---

## 📍 Service URLs (AWS)

| Service | URL |
|---------|-----|
| **Web** | http://localhost:3000 or CloudFront |
| **API** | http://localhost:8000 or API Gateway |
| **Generation** | SageMaker endpoint or Lambda + SageMaker |
| **Orchestration** | Lambda orchestrator or backend calling orchestrator_aws |

AWS URLs from API Gateway and SageMaker. **No Modal setup.**

---

## 🚀 Next steps

1. **AWS:** Run `aws/scripts/download_models.py`; deploy SageMaker (and Lambda if used); point backend to AWS (aws_gpu_client).
2. **Tests:** Run `pytest ai-pipeline/tests/test_improvements.py -v -s -m "not gpu"` for non-GPU tests; run GPU tests where GPU available.
3. **Docs:** Use ARCHITECTURE.md, DEPLOYMENT_MODAL_VS_AWS.md, AWS_SETUP.md for full setup. **No Modal setup.**

---

## 🆘 Troubleshooting

- **AWS SageMaker:** Ensure models in S3/EFS (run `aws/scripts/download_models.py`); entrypoint `inference.py` or `inference_two_pass.py`; IAM and timeout (e.g. 600s).
- **Tests:** GPU tests need GPU; use `-m "not gpu"` for CI; optional deps (sentence-transformers, insightface) may skip tests.

---

**Last updated:** Full setup on AWS; no Modal setup.

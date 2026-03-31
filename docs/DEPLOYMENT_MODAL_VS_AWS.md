# Deployment: AWS Only (No Modal Setup)

**PhotoGenius AI project setup is full AWS.** No Modal setup required. All generation, orchestration, models, and API run on AWS (SageMaker, Lambda, S3).

---

## 1. Project setup: AWS only

| Area | Where it runs | Docs |
|------|----------------|------|
| **GPU / inference** | SageMaker (SDXL, two-pass); `inference.py`, `inference_two_pass.py` | AWS_SETUP.md, AWS_TWO_PASS.md |
| **Model storage** | S3 + optional EFS; download via `aws/scripts/download_models.py` | AWS_SETUP.md, aws/scripts/README.md |
| **Orchestration** | orchestrator_aws.py (generate_professional); Lambda or backend | ORCHESTRATOR_AWS_INTEGRATION.md |
| **Two-pass (preview + final)** | two_pass_generation.py; SageMaker inference_two_pass.py | AWS_TWO_PASS.md |
| **InstantID** | Same logic can run on SageMaker/EC2 with models in S3/EFS | AWS_SETUP.md |
| **Semantic enhancer** | semantic_prompt_enhancer.py; used by orchestrator_aws | ORCHESTRATOR_AWS_INTEGRATION.md |
| **LoRA training** | Lambda/ECS or SageMaker training job | AWS_SETUP.md, LORA_TRAINING_SERVICE.md |
| **Safety** | Lambda (safety handler) | AWS_SETUP.md |
| **API entry** | API Gateway + Lambda and/or SageMaker | AWS_SETUP.md |

---

## 2. What you use for setup (AWS)

- **aws/scripts/download_models.py** – Download SDXL Base/Turbo/Refiner, InstantID, InsightFace, Sentence Transformer; optional S3 sync.
- **aws/sagemaker/** – deploy_model, inference.py, inference_two_pass.py, two_pass_generation.py.
- **ai-pipeline/services/orchestrator_aws.py** – generate_professional (FAST/STANDARD/PREMIUM).
- **ai-pipeline/services/two_pass_generation.py** – generate_fast, generate_two_pass.
- **ai-pipeline/services/semantic_prompt_enhancer.py** – Used by orchestrator_aws.
- **aws/lambda/** – generation, orchestrator, post_processor, prompt_enhancer, safety.

**Docs:** [AWS_SETUP.md](AWS_SETUP.md), [AWS_TWO_PASS.md](AWS_TWO_PASS.md), [ORCHESTRATOR_AWS_INTEGRATION.md](ORCHESTRATOR_AWS_INTEGRATION.md), [AWS_GPU_SETUP.md](AWS_GPU_SETUP.md).

---

## 3. Modal in this project

- **Modal is not used for setup.** No Modal deploy or Modal volumes required.
- **Modal-only code** (e.g. `generation_service.py`, `instantid_service.py`, `orchestrator.py`, `lora_trainer.py`, `safety_service.py` with Modal stubs) exists in the repo for **reference/legacy** only. The project does **not** depend on Modal for deployment.
- **Backend and web** should use **AWS** (aws_gpu_client, SageMaker, Lambda). Do not point cloud-config or API to Modal URLs for project setup.

---

## 4. Setup steps (AWS)

1. Run **aws/scripts/download_models.py**; optionally sync to S3.
2. Deploy **SageMaker** (inference.py or inference_two_pass.py).
3. Deploy **Lambda** (generation, orchestrator, post_processor, prompt_enhancer, safety) if used.
4. Point **apps/api** to AWS (aws_gpu_client, SageMaker endpoint, Lambda).
5. Point **apps/web** (cloud-config) to AWS API Gateway / SageMaker URLs.

See **docs/AWS_SETUP.md** for full AWS setup.

---

**Last updated:** Project setup is AWS-only; no Modal setup.

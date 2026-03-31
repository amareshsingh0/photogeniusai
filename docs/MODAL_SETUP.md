# Modal – Reference Only (Not Used for Project Setup)

**PhotoGenius AI project setup is full AWS.** This doc describes Modal-related code in the repo for **reference/legacy only**. Do **not** use Modal for project setup or deployment.

---

## Project setup: use AWS

- **Setup and deployment:** Use **AWS** (SageMaker, Lambda, S3). See [AWS_SETUP.md](AWS_SETUP.md), [DEPLOYMENT_MODAL_VS_AWS.md](DEPLOYMENT_MODAL_VS_AWS.md).
- **Backend and web:** Point to **AWS** (aws_gpu_client, SageMaker, Lambda). Do not point cloud-config or API to Modal URLs for project setup.

---

## Modal code in repo (reference only)

The following files contain Modal stubs. They are **not** used for project setup; equivalent or better functionality runs on AWS.

| File | Modal stub | AWS equivalent |
|------|------------|----------------|
| ai-pipeline/services/generation_service.py | photogenius-generation (A100) | SageMaker inference.py / inference_two_pass.py |
| ai-pipeline/services/instantid_service.py | photogenius-instantid (A10G) | Same logic on SageMaker/EC2 with S3/EFS models |
| ai-pipeline/services/orchestrator.py | photogenius-orchestrator | orchestrator_aws.py (generate_professional) |
| ai-pipeline/services/lora_trainer.py | photogenius-lora-trainer (A100) | Lambda/ECS or SageMaker training |
| ai-pipeline/services/safety_service.py | photogenius-safety | Lambda (safety handler) |

Modal volumes (photogenius-models, photogenius-loras) are **not** used; models are in S3/EFS via **aws/scripts/download_models.py**.

---

**Last updated:** Project setup is AWS-only; Modal is reference only.

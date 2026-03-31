# 📚 PhotoGenius AI Documentation

## 🎯 Quick Start

### Architecture & deployment (read first)
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** – Full A–Z: monorepo, AWS-only setup, services, APIs, DB
- **[DEPLOYMENT_MODAL_VS_AWS.md](./DEPLOYMENT_MODAL_VS_AWS.md)** – AWS-only setup (no Modal)
- **[MODAL_SETUP.md](./MODAL_SETUP.md)** – Reference only (Modal not used for project setup)
- **[AWS_SETUP.md](./AWS_SETUP.md)** – AWS setup (Lambda, SageMaker, S3, download script)
- **[CURRENT_STATUS.md](./CURRENT_STATUS.md)** – Current status and next steps

### Setup & installation
- **[INSTALLATION_GUIDE.md](./INSTALLATION_GUIDE.md)** – Installation instructions
- **[ENVIRONMENT_SETUP.md](./ENVIRONMENT_SETUP.md)** – Env vars and config
- **[SETUP_COMPLETE.md](./SETUP_COMPLETE.md)** – Setup status and service URLs

### Development
- **[SERVICES_START_GUIDE.md](./SERVICES_START_GUIDE.md)** – How to start all services
- **[CONNECTIONS.md](./CONNECTIONS.md)** – Frontend ↔ Backend ↔ AI pipeline; canonical enhancer
- **[DEVELOPMENT.md](./DEVELOPMENT.md)** – Dev workflow

### AI pipeline & AWS
- **[AI_IMPLEMENTATION_PLAN.md](./AI_IMPLEMENTATION_PLAN.md)** – AI plan; InstantID, two-pass, semantic enhancer
- **[ORCHESTRATOR_AWS_INTEGRATION.md](./ORCHESTRATOR_AWS_INTEGRATION.md)** – orchestrator_aws, generate_professional, quality tiers
- **[AWS_TWO_PASS.md](./AWS_TWO_PASS.md)** – Two-pass pipeline on SageMaker
- **[AWS_GPU_SETUP.md](./AWS_GPU_SETUP.md)** – AWS GPU / SageMaker setup
- **[LORA_TRAINING_SERVICE.md](./LORA_TRAINING_SERVICE.md)** – LoRA training

### Deployment & ops
- **[CLOUD_MIGRATION_GUIDE.md](./CLOUD_MIGRATION_GUIDE.md)** – Cloud migration
- **[MODAL_ENDPOINT_FIX.md](./MODAL_ENDPOINT_FIX.md)** – Modal troubleshooting
- **[API.md](./API.md)** – API reference

---

## 📋 Index (selected)

| Document | Purpose |
|----------|---------|
| **ARCHITECTURE.md** | Full architecture (A–Z); AWS-only setup |
| **DEPLOYMENT_MODAL_VS_AWS.md** | AWS-only setup (no Modal) |
| **MODAL_SETUP.md** | Reference only (not used for setup) |
| **AWS_SETUP.md** | AWS setup (Lambda, SageMaker, S3) |
| **CURRENT_STATUS.md** | Status and next steps |
| **CONNECTIONS.md** | Request flow; canonical enhancer |
| **ORCHESTRATOR_AWS_INTEGRATION.md** | AWS orchestrator (generate_professional) |
| **AWS_TWO_PASS.md** | Two-pass on SageMaker |

---

## 🚀 Quick links

- **Start services:** `.\scripts\run-all-services.ps1`
- **Install deps:** `.\scripts\install-dependencies.ps1`
- **Test Modal:** `python scripts/test-modal-connection.py`
- **AWS download models:** `python aws/scripts/download_models.py --model-dir ./models`
- **Verify models:** `python aws/scripts/download_models.py --verify-only`

---

**Last updated:** Architecture, AWS-only setup, CURRENT_STATUS, CONNECTIONS.

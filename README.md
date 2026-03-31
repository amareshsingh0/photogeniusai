# PhotoGenius AI

Production-grade AI avatar generation platform: SDXL, LoRA, InstantID, two-pass generation, semantic prompt enhancement. **Project setup is AWS-only** (no Modal).

## Tech stack

- **Frontend:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui
- **Backend:** FastAPI, Python 3.11, PostgreSQL
- **AI:** SDXL, LoRA, InstantID, two-pass (Turbo + Base + Refiner), semantic enhancer
- **Infrastructure:** **AWS** (SageMaker, Lambda, S3) for generation, orchestration, LoRA, safety; Clerk optional

## Getting started

### Prerequisites

- Node.js 18+
- Python 3.11+
- pnpm 8+
- PostgreSQL 15

### Installation

```bash
git clone https://github.com/your-org/photogenius-ai.git
cd photogenius-ai

chmod +x scripts/setup-dev.sh
./scripts/setup-dev.sh

# Ensure apps/web/.env.local and apps/api/.env.local exist (see docs/ENVIRONMENT_SETUP.md)
# For SageMaker deploy: aws/sagemaker/.env.local when running from aws/sagemaker/
pnpm verify-env   # or pnpm verify-env:win on Windows
```

### Development

```bash
pnpm dev
# Or: pnpm dev --filter=web  (http://localhost:3000)
#     pnpm dev --filter=api (http://localhost:8000)
```

### Testing

```bash
pnpm test
# AI pipeline: cd ai-pipeline && pytest tests/ -v -s -m "not gpu"
```

## Deployment: AWS only

- **Setup is AWS-only.** SageMaker (SDXL, two-pass), Lambda (orchestrator, post-process, enhancer), S3. See [docs/AWS_SETUP.md](docs/AWS_SETUP.md), [docs/AWS_TWO_PASS.md](docs/AWS_TWO_PASS.md), [docs/ORCHESTRATOR_AWS_INTEGRATION.md](docs/ORCHESTRATOR_AWS_INTEGRATION.md).
- **Reference:** [docs/DEPLOYMENT_MODAL_VS_AWS.md](docs/DEPLOYMENT_MODAL_VS_AWS.md) (AWS-only setup; Modal code is reference/legacy). [docs/MODAL_SETUP.md](docs/MODAL_SETUP.md) – Modal not used for project setup.

## Project structure & docs

- **Architecture (A–Z):** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Current status:** [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md)
- **Connections (frontend ↔ backend ↔ AI):** [docs/CONNECTIONS.md](docs/CONNECTIONS.md)
- **API:** [docs/API.md](docs/API.md)

## License

Proprietary

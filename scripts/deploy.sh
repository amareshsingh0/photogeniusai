#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo ">>> PhotoGenius AI – deploy"
echo ">>> Build web..."
npm run build

echo ">>> Build ai-service (Docker)..."
docker build -t photogenius-ai-service -f apps/ai-service/Dockerfile .

echo ">>> Optionally apply Terraform (infra/terraform) and push images."
echo ">>> Done."

#!/usr/bin/env bash
# Deploy to staging. Customize for your infra (e.g. Vercel + Railway).
set -e
cd "$(dirname "$0")/.."

echo ">>> Build..."
pnpm run build

echo ">>> Run staging deploy (e.g. vercel --env=staging, or docker push + k8s apply)"
echo ">>> Configure for your staging target."

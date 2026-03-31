#!/usr/bin/env bash
# Deploy to production. Customize for your infra.
set -e
cd "$(dirname "$0")/.."

echo ">>> Build..."
pnpm run build

echo ">>> Run production deploy (e.g. docker push, k8s apply, or Vercel prod)"
echo ">>> Configure for your production target."

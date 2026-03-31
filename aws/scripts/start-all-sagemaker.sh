#!/usr/bin/env bash
# Start (deploy) ALL PhotoGenius SageMaker tiers in one command.
# Usage: ./start-all-sagemaker.sh [us-east-1]
# From repo root: ./aws/scripts/start-all-sagemaker.sh
set -e
REGION="${1:-us-east-1}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -f "$ROOT/aws/scripts/start-all-sagemaker.sh" ]; then
  ROOT="$(cd "$ROOT/../.." && pwd)"
fi
DEPLOY="$ROOT/deploy/sagemaker_deployment.py"
if [ ! -f "$DEPLOY" ]; then
  echo "Not found: deploy/sagemaker_deployment.py. Run from repo root."
  exit 1
fi
if [ -f "$ROOT/aws/sagemaker/.env.local" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ROOT/aws/sagemaker/.env.local" 2>/dev/null || true
  set +a
  echo "Loaded env from aws/sagemaker/.env.local"
fi
if [ -z "$SAGEMAKER_ROLE" ]; then
  echo "SAGEMAKER_ROLE not set. Set it or add to aws/sagemaker/.env.local"
  exit 1
fi
export AWS_REGION="$REGION"
echo "Deploying all tiers (STANDARD, PREMIUM, PERFECT)..."
cd "$ROOT"
python "$DEPLOY" --tier all

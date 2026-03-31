#!/bin/bash
# Package Identity Engine V2 model code for SageMaker (99%+ face consistency).
# Run from repo root: bash aws/sagemaker/package_identity_v2.sh
# Requires: model/code/inference_identity_v2.py and identity_engine_v2_aws.py

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null || cd ../..; pwd)"
SAGEMAKER_DIR="${REPO_ROOT}/aws/sagemaker"
MODEL_CODE="${SAGEMAKER_DIR}/model/code"

echo "📦 Packaging Identity V2 model for SageMaker..."

cd "$SAGEMAKER_DIR"

for f in inference_identity_v2.py identity_engine_v2_aws.py requirements.txt; do
  if [ ! -f "$MODEL_CODE/$f" ]; then
    echo "❌ Missing $MODEL_CODE/$f"
    exit 1
  fi
done

mkdir -p build
rm -rf build/code
cp -r model/code build/
cd build
tar -czvf ../model_identity_v2.tar.gz code
cd ..
rm -rf build

echo "✅ Model package created: ${SAGEMAKER_DIR}/model_identity_v2.tar.gz"
echo "📤 Upload and deploy: use deploy_identity_v2.py or AWS Console (SageMaker endpoint)."
echo "   Env: IDENTITY_ENGINE_VERSION=v2, IDENTITY_METHOD=ensemble, SAGEMAKER_IDENTITY_V2_ENDPOINT=<endpoint>"

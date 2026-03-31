#!/bin/bash
# Package two-pass model code for SageMaker (AWS only, no Modal).
# Run from repo root: bash aws/sagemaker/package_two_pass.sh
# Or from aws/sagemaker: bash package_two_pass.sh

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null || cd ../..; pwd)"
SAGEMAKER_DIR="${REPO_ROOT}/aws/sagemaker"
MODEL_CODE="${SAGEMAKER_DIR}/model/code"

echo "📦 Packaging two-pass model for SageMaker..."

# Ensure we're in the right place
cd "$SAGEMAKER_DIR"

# Sync canonical two_pass_generation.py from ai-pipeline (optional fallback; inference_two_pass is self-contained)
if [ -f "${REPO_ROOT}/ai-pipeline/services/two_pass_generation.py" ]; then
  cp "${REPO_ROOT}/ai-pipeline/services/two_pass_generation.py" "$MODEL_CODE/"
  echo "  Synced two_pass_generation.py from ai-pipeline"
fi

# Ensure required files exist
for f in inference_two_pass.py requirements.txt; do
  if [ ! -f "$MODEL_CODE/$f" ]; then
    echo "❌ Missing $MODEL_CODE/$f"
    exit 1
  fi
done

# Create tarball: contents of model/code as top-level (SageMaker expects code/ inside model.tar.gz)
# SageMaker HuggingFace container expects: model.tar.gz contains ./code/inference_two_pass.py etc.
mkdir -p build
rm -rf build/code
cp -r model/code build/
cd build
tar -czvf ../model_two_pass.tar.gz code
cd ..
rm -rf build

echo "✅ Model package created: ${SAGEMAKER_DIR}/model_two_pass.tar.gz"
echo "📤 Upload to S3:"
echo "   aws s3 cp model_two_pass.tar.gz s3://YOUR_BUCKET/models/two-pass/model.tar.gz"

#!/bin/bash
# Package realtime (LCM) model code for SageMaker (8–10s preview).
# Run from repo root: bash aws/sagemaker/package_realtime.sh
# Instance: ml.g5.xlarge (cheaper GPU for previews). Endpoint: photogenius-realtime-dev

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null || cd ../..; pwd)"
SAGEMAKER_DIR="${REPO_ROOT}/aws/sagemaker"
MODEL_CODE="${SAGEMAKER_DIR}/model/code"

echo "Packaging realtime model for SageMaker..."

cd "$SAGEMAKER_DIR"

for f in inference_realtime.py requirements.txt; do
  if [ ! -f "$MODEL_CODE/$f" ]; then
    echo "Missing $MODEL_CODE/$f"
    exit 1
  fi
done

mkdir -p build
rm -rf build/code
cp -r model/code build/
cd build
tar -czvf ../model_realtime.tar.gz code
cd ..
rm -rf build

echo "Model package created: ${SAGEMAKER_DIR}/model_realtime.tar.gz"
echo "Upload and deploy: ml.g5.xlarge, endpoint photogenius-realtime-dev"
echo "Lambda: set SAGEMAKER_REALTIME_ENDPOINT for FAST tier to use realtime."

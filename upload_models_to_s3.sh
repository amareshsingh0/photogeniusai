#!/bin/bash
# Upload SDXL models to S3 (Linux/Ubuntu)
# Run this ONLY if you want faster SageMaker startup times

set -e

BUCKET="photogenius-models-dev"
CACHE_DIR="${HOME}/.cache/huggingface/hub"

echo "=========================================="
echo "Upload HuggingFace Models to S3"
echo "=========================================="

# Check if models exist locally
if [ ! -d "$CACHE_DIR" ]; then
    echo "ERROR: HuggingFace cache not found at $CACHE_DIR"
    echo "Download models first using test_local_generation.py"
    exit 1
fi

echo ""
echo "Step 1: Find SDXL-Turbo model"
TURBO_DIR=$(find "$CACHE_DIR" -type d -name "models--stabilityai--sdxl-turbo" | head -1)
if [ -z "$TURBO_DIR" ]; then
    echo "ERROR: SDXL-Turbo not found. Download it first!"
    exit 1
fi
echo "Found: $TURBO_DIR"

echo ""
echo "Step 2: Find SDXL-Base model"
BASE_DIR=$(find "$CACHE_DIR" -type d -name "models--stabilityai--stable-diffusion-xl-base-1.0" | head -1)
if [ -z "$BASE_DIR" ]; then
    echo "ERROR: SDXL-Base not found. Download it first!"
    exit 1
fi
echo "Found: $BASE_DIR"

echo ""
echo "Step 3: Find SDXL-Refiner model"
REFINER_DIR=$(find "$CACHE_DIR" -type d -name "models--stabilityai--stable-diffusion-xl-refiner-1.0" | head -1)
if [ -z "$REFINER_DIR" ]; then
    echo "ERROR: SDXL-Refiner not found. Download it first!"
    exit 1
fi
echo "Found: $REFINER_DIR"

echo ""
echo "=========================================="
echo "Uploading to S3 (this will take 30-60 minutes)"
echo "=========================================="

# Upload SDXL-Turbo
echo ""
echo "[1/3] Uploading SDXL-Turbo (~7GB)..."
aws s3 sync "${TURBO_DIR}/snapshots/" s3://${BUCKET}/models/sdxl-turbo/ \
    --exclude "*.gitattributes" \
    --exclude "README.md" \
    --exclude ".git*"
echo "✅ SDXL-Turbo uploaded"

# Upload SDXL-Base
echo ""
echo "[2/3] Uploading SDXL-Base (~14GB)..."
aws s3 sync "${BASE_DIR}/snapshots/" s3://${BUCKET}/models/sdxl-base-1.0/ \
    --exclude "*.gitattributes" \
    --exclude "README.md" \
    --exclude ".git*"
echo "✅ SDXL-Base uploaded"

# Upload SDXL-Refiner
echo ""
echo "[3/3] Uploading SDXL-Refiner (~14GB)..."
aws s3 sync "${REFINER_DIR}/snapshots/" s3://${BUCKET}/models/sdxl-refiner-1.0/ \
    --exclude "*.gitattributes" \
    --exclude "README.md" \
    --exclude ".git*"
echo "✅ SDXL-Refiner uploaded"

echo ""
echo "=========================================="
echo "UPLOAD COMPLETE!"
echo "=========================================="
echo ""
echo "Verify:"
echo "  aws s3 ls s3://${BUCKET}/models/ --recursive --human-readable --summarize | tail -2"
echo ""
echo "Total size should be ~35GB"

#!/bin/bash
# PhotoGenius AI - Build Artifacts Cleanup
# Removes build caches, Lambda zips, and temporary files

set -e
cd "$(dirname "$0")"

echo "========================================="
echo "PhotoGenius AI - Build Artifacts Cleanup"
echo "========================================="
echo ""

# Calculate sizes before cleanup
echo "Calculating current sizes..."
BUILD_SIZE=$(du -sh aws/.aws-sam 2>/dev/null | cut -f1 || echo "0")
CACHE_COUNT=$(find . -name "__pycache__" -type d | wc -l)

echo "Current sizes:"
echo "  - AWS SAM build: $BUILD_SIZE"
echo "  - Python caches: $CACHE_COUNT directories"
echo ""

echo "[1/5] Removing AWS SAM build artifacts (870MB)..."
rm -rf aws/.aws-sam

echo "[2/5] Removing duplicate Lambda zip files..."
cd aws
rm -fv generation.zip
rm -fv generation-v2.zip
rm -fv lambda-manual.zip
rm -fv temp_photogenius-*.zip
cd ..

echo "[3/5] Removing old deploy artifacts..."
rm -fv deploy/sagemaker/artifacts/model.tar.gz

echo "[4/5] Removing Python cache directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

echo "[5/5] Removing Node.js build artifacts..."
find apps/web -name ".next" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "tsconfig.tsbuildinfo" -delete 2>/dev/null || true

echo ""
echo "========================================="
echo "Build Artifacts Cleanup Complete!"
echo "========================================="
echo ""
echo "Removed:"
echo "  - AWS SAM build: $BUILD_SIZE"
echo "  - Lambda zips: 45MB"
echo "  - Python caches: $CACHE_COUNT directories"
echo "  - Node.js build caches"
echo ""
echo "Total space saved: ~920MB+"
echo ""
echo "Note: These will be regenerated on next build."
echo ""

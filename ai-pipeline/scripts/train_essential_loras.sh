#!/usr/bin/env bash
# Train the 3 essential LoRAs (skin_realism_v2, cinematic_lighting_v3, color_harmony_v1).
# Requires: GPU, datasets, torch, diffusers, peft. Optional: boto3 for --upload-s3.
#
# Usage:
#   ./scripts/train_essential_loras.sh              # Train all 3, output to ai-pipeline/models/loras/
#   ./scripts/train_essential_loras.sh --upload-s3  # Train all 3 and upload to s3://photogenius-models/loras/

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRAIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT="${OUTPUT:-$TRAIN_DIR/../models/loras}"
UPLOAD="${UPLOAD:-}"

if [ "$1" = "--upload-s3" ]; then
  UPLOAD="--upload-s3"
  shift
fi

cd "$TRAIN_DIR"

echo "Training skin_realism_v2 (500 portraits, ultra realistic skin texture)..."
python training/train_style_loras.py --style skin_realism_v2 \
  --dataset prithivMLmods/Realistic-Face-Portrait-1024px \
  --epochs 1000 \
  --output "$OUTPUT/skin_realism_v2.safetensors" \
  $UPLOAD

echo "Training cinematic_lighting_v3 (300 movie stills, cinematic lighting)..."
python training/train_style_loras.py --style cinematic_lighting_v3 \
  --dataset ChristophSchuhmann/improved_aesthetics_parquet \
  --epochs 1000 \
  --output "$OUTPUT" \
  $UPLOAD

echo "Training color_harmony_v1 (400 color-theory images, harmonious palette)..."
python training/train_style_loras.py --style color_harmony_v1 \
  --dataset laion/laion-art \
  --epochs 1000 \
  --output "$OUTPUT" \
  $UPLOAD

echo "Done. LoRAs in $OUTPUT (and S3 if --upload-s3 was used)."

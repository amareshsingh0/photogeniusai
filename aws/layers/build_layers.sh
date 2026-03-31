#!/bin/bash
# Build Lambda layers for PhotoGenius AI.
# Run from repo root or from aws/: ./layers/build_layers.sh  or  bash aws/layers/build_layers.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# When run from repo root (e.g. aws/layers/build_layers.sh), LAYERS_DIR = aws/
LAYERS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LAYERS_DIR"
echo "Layers root: $LAYERS_DIR"

echo "Building Lambda layers (from $LAYERS_DIR)..."

# ==================== POST-PROCESSING LAYER ====================
echo "Building post-processing layer..."
POST_DIR="$SCRIPT_DIR/post_processing"
mkdir -p "$POST_DIR/python"
if [ -f "$POST_DIR/requirements.txt" ]; then
  pip install -r "$POST_DIR/requirements.txt" -t "$POST_DIR/python" --upgrade
else
  echo "opencv-python-headless>=4.8.0" > "$POST_DIR/requirements.txt"
  echo "Pillow>=10.0.0" >> "$POST_DIR/requirements.txt"
  echo "numpy>=1.24.0,<2" >> "$POST_DIR/requirements.txt"
  pip install -r "$POST_DIR/requirements.txt" -t "$POST_DIR/python" --upgrade
fi
cd "$POST_DIR"
zip -r post_processing_layer.zip python -q
cd "$LAYERS_DIR"
echo "Post-processing layer: $POST_DIR/post_processing_layer.zip"

# ==================== PROMPT ENHANCEMENT LAYER ====================
echo "Building prompt enhancement layer..."
PROMPT_DIR="$SCRIPT_DIR/prompt_enhancement"
mkdir -p "$PROMPT_DIR/python"
if [ -f "$PROMPT_DIR/requirements.txt" ]; then
  pip install -r "$PROMPT_DIR/requirements.txt" -t "$PROMPT_DIR/python" --upgrade
else
  touch "$PROMPT_DIR/requirements.txt"
  pip install -t "$PROMPT_DIR/python" --upgrade
fi
cd "$PROMPT_DIR"
zip -r prompt_enhancement_layer.zip python -q
cd "$LAYERS_DIR"
echo "Prompt enhancement layer: $PROMPT_DIR/prompt_enhancement_layer.zip"

echo "Layers built successfully."

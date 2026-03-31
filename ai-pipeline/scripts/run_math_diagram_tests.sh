#!/usr/bin/env bash
# Full setup: install deps and run all math/diagram renderer tests (no skips).
# Run from ai-pipeline: ./scripts/run_math_diagram_tests.sh
# Or from repo root: ./ai-pipeline/scripts/run_math_diagram_tests.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_PIPELINE="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$AI_PIPELINE"

echo "Installing requirements (sympy, antlr4, matplotlib, Pillow)..."
pip install -r requirements.txt --quiet

echo "Running all 15 math/diagram renderer tests (no skips)..."
python -m pytest tests/test_math_diagram_renderer.py -v -p no:asyncio

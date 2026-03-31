#!/usr/bin/env bash
# Run AWS SAM CLI from project root; uses aws/template.yaml
# Usage: ./scripts/sam.sh build | ./scripts/sam.sh deploy | ./scripts/sam.sh list endpoints
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AWS_DIR="$ROOT/aws"
if [ ! -f "$AWS_DIR/template.yaml" ]; then
  echo "Template not found at $AWS_DIR/template.yaml" >&2
  exit 1
fi
cd "$AWS_DIR"
exec sam "$@"

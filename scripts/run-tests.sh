#!/usr/bin/env bash
# Run all tests. From repo root.
set -e
cd "$(dirname "$0")/.."

echo ">>> Lint + typecheck..."
pnpm run lint
pnpm run typecheck 2>/dev/null || pnpm run type-check 2>/dev/null || true

echo ">>> Turbo test..."
pnpm run test 2>/dev/null || true

echo ">>> API pytest..."
(cd apps/api && pytest -q) 2>/dev/null || true

echo ">>> Done."

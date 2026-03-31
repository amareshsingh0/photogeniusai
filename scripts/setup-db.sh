#!/usr/bin/env bash
# PhotoGenius AI – DB setup. Run from repo root.
set -e
cd "$(dirname "$0")/.."

echo ">>> Prisma generate..."
pnpm run db:generate

echo ">>> Push schema (or migrate)..."
pnpm run db:push 2>/dev/null || true

echo ">>> Seed..."
pnpm run db:seed 2>/dev/null || true

echo ">>> Done. Use pnpm run db:migrate for migrations."

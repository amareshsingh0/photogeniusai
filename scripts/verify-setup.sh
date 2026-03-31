#!/usr/bin/env bash
# PhotoGenius AI – setup verification.
# Checks: Node version, pnpm, Python, dependencies installed.
# Usage: ./scripts/verify-setup.sh   or   bash scripts/verify-setup.sh
set -e
cd "$(dirname "$0")/.."
FAIL=0

_check() {
  if eval "$@" >/dev/null 2>&1; then
    echo "  ✓ $1"
    return 0
  else
    echo "  ✗ $1"
    return 1
  fi
}

echo ">>> PhotoGenius AI – verify setup"
echo ""

echo "1. Node (required >=18, prefer 20 LTS)"
if _check "command -v node"; then
  V=$(node -v 2>/dev/null || true)
  echo "    $V"
  if node -e "process.exit(process.versions.node.split('.')[0] >= 18 ? 0 : 1)" 2>/dev/null; then
    :
  else
    echo "    ⚠ Use Node 18+ (20 LTS recommended). Do not use Node 24."
    FAIL=1
  fi
else
  FAIL=1
fi
echo ""

echo "2. pnpm (required >=8)"
if _check "command -v pnpm"; then
  pnpm -v
else
  echo "    Install: npm install -g pnpm"
  FAIL=1
fi
echo ""

echo "3. Python (required 3.11+)"
if _check "command -v python3.11 || command -v py"; then
  if command -v python3.11 >/dev/null 2>&1; then
    python3.11 --version
  elif command -v py >/dev/null 2>&1; then
    py -3.11 --version 2>/dev/null || py --version
  else
    echo "    Install Python 3.11. Do not use 3.14 for AI libs."
    FAIL=1
  fi
else
  echo "    Install Python 3.11 from https://www.python.org/downloads/"
  FAIL=1
fi
echo ""

echo "4. Dependencies (pnpm install)"
if _check "test -d node_modules"; then
  :
else
  echo "    Run: pnpm install"
  FAIL=1
fi
echo ""

echo "5. Prisma client (db generate)"
if _check "test -d node_modules/.prisma || test -d node_modules/@prisma/client"; then
  :
else
  echo "    Run: pnpm run db:generate"
  FAIL=1
fi
echo ""

echo "6. .env"
if _check "test -f .env"; then
  echo "    .env present"
else
  echo "    Create .env or ensure apps/web/.env.local and apps/api/.env.local exist."
  FAIL=1
fi
echo ""

if [ $FAIL -eq 1 ]; then
  echo ">>> Some checks failed. Fix the above and re-run."
  exit 1
fi
echo ">>> All checks passed."

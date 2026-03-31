#!/bin/bash

echo "🔍 Verifying environment configuration..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

errors=0
warnings=0

# Check if .env files exist
if [ ! -f "apps/web/.env.local" ]; then
    echo -e "${RED}❌ apps/web/.env.local not found${NC}"
    echo "   Create apps/web/.env.local (see docs/ENVIRONMENT_SETUP.md)"
    ((errors++))
fi

if [ ! -f "apps/api/.env.local" ] && [ ! -f "apps/api/.env" ]; then
    echo -e "${RED}❌ apps/api/.env.local or apps/api/.env not found${NC}"
    echo "   Create apps/api/.env.local (see docs/ENVIRONMENT_SETUP.md)"
    ((errors++))
elif [ -f "apps/api/.env.local" ]; then
    echo -e "${GREEN}✓ apps/api/.env.local found${NC}"
elif [ -f "apps/api/.env" ]; then
    echo -e "${YELLOW}⚠️  apps/api/.env found (consider using .env.local)${NC}"
    ((warnings++))
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not installed${NC}"
    ((errors++))
else
    node_version=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$node_version" -lt 18 ]; then
        echo -e "${YELLOW}⚠️  Node.js version should be 18+${NC}"
        ((warnings++))
    else
        echo -e "${GREEN}✓ Node.js $(node -v)${NC}"
    fi
fi

# Check Python
if ! command -v python3.11 &> /dev/null; then
    echo -e "${RED}❌ Python 3.11 not installed${NC}"
    ((errors++))
else
    echo -e "${GREEN}✓ Python 3.11${NC}"
fi

# Check pnpm
if ! command -v pnpm &> /dev/null; then
    echo -e "${YELLOW}⚠️  pnpm not installed${NC}"
    echo "   Install: npm install -g pnpm"
    ((warnings++))
else
    echo -e "${GREEN}✓ pnpm $(pnpm -v)${NC}"
fi

# Check PostgreSQL
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}⚠️  PostgreSQL client not found${NC}"
    ((warnings++))
else
    echo -e "${GREEN}✓ PostgreSQL client${NC}"
fi

# Check Redis (optional)
if ! command -v redis-cli &> /dev/null; then
    echo -e "${YELLOW}⚠️  Redis client not found (optional)${NC}"
    ((warnings++))
else
    echo -e "${GREEN}✓ Redis client${NC}"
fi

# Validate critical env vars if files exist
if [ -f "apps/web/.env.local" ]; then
    source apps/web/.env.local 2>/dev/null || true
    if [ -z "$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" ]; then
        echo -e "${YELLOW}⚠️  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY not set${NC}"
        ((warnings++))
    fi
    if [ -z "$CLERK_SECRET_KEY" ]; then
        echo -e "${YELLOW}⚠️  CLERK_SECRET_KEY not set${NC}"
        ((warnings++))
    fi
fi

if [ -f "apps/api/.env.local" ]; then
    source apps/api/.env.local 2>/dev/null || true
    if [ -z "$DATABASE_URL" ]; then
        echo -e "${YELLOW}⚠️  DATABASE_URL not set${NC}"
        ((warnings++))
    fi
    if [ -z "$CLERK_SECRET_KEY" ]; then
        echo -e "${YELLOW}⚠️  CLERK_SECRET_KEY not set${NC}"
        ((warnings++))
    fi
fi

# Summary
echo ""
echo "═══════════════════════════════════════"
if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    exit 0
elif [ $errors -eq 0 ]; then
    echo -e "${YELLOW}⚠️  ${warnings} warning(s) found${NC}"
    exit 0
else
    echo -e "${RED}❌ ${errors} error(s), ${warnings} warning(s)${NC}"
    exit 1
fi

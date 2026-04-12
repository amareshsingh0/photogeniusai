#!/bin/bash
# Deploy Claude Haiku 4.5 Migration to Server
# Run this on the server: bash deploy_claude_haiku.sh

set -e  # Exit on error

echo "=== Claude Haiku 4.5 Deployment Script ==="
echo ""

# Navigate to project directory
cd /home/ubuntu/PhotoGenius-AI

echo "✓ Step 1: Stash local changes (if any)"
git stash

echo "✓ Step 2: Pull latest code from repository"
git pull origin main

echo "✓ Step 3: Navigate to API directory"
cd apps/api

echo "✓ Step 4: Install Anthropic SDK"
pip install anthropic

echo "✓ Step 5: Update .env file with Claude settings"
# Check if .env exists, if not create from .env.local
if [ ! -f .env ]; then
    echo "Creating .env from .env.local..."
    cp .env.local .env
fi

# Update environment variables
echo "Updating environment variables..."
sed -i 's/USE_ANTHROPIC=false/USE_ANTHROPIC=true/' .env
sed -i 's/USE_GEMINI_ENGINE=true/USE_GEMINI_ENGINE=false/' .env

# Add USE_CLAUDE_ENGINE if not exists
if ! grep -q "USE_CLAUDE_ENGINE" .env; then
    echo "" >> .env
    echo "# Claude Haiku 4.5 Engine (Added $(date +%Y-%m-%d))" >> .env
    echo "USE_CLAUDE_ENGINE=true" >> .env
fi

echo "✓ Step 6: Clear Python cache"
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find . -name '*.pyc' -delete

echo "✓ Step 7: Restart API service"
cd /home/ubuntu/PhotoGenius-AI
pm2 restart photogenius-api

echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "Verification:"
echo "1. Check logs: pm2 logs photogenius-api --lines 50"
echo "2. Check status: pm2 status"
echo "3. Test endpoint: curl http://localhost:8003/api/v1/health"
echo ""
echo "Configuration applied:"
echo "  ✓ USE_ANTHROPIC=true"
echo "  ✓ USE_CLAUDE_ENGINE=true"
echo "  ✓ USE_GEMINI_ENGINE=false"
echo ""
echo "Model: Claude Haiku 4.5 (claude-haiku-4-5-20251001)"
echo "  - Stage A (Brief): Extended thinking mode (2000 token budget)"
echo "  - Stage B (Params): Standard mode"
echo "  - Critic: Standard mode"
echo ""

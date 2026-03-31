#!/usr/bin/env bash
# PhotoGenius AWS GPU Setup Script (Linux/Mac)
# No Modal, No Lightning - Pure AWS (SageMaker + Lambda)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== PhotoGenius AWS GPU Setup ==="
echo "Project root: $PROJECT_ROOT"

# 1. Create venv
echo ""
echo "[1/5] Creating Python venv..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  Venv created"
else
    echo "  Venv exists"
fi

# 2. Activate and install API deps
echo ""
echo "[2/5] Installing API dependencies (AWS, no Modal)..."
source .venv/bin/activate
if [ -f "apps/api/requirements-aws.txt" ]; then
    pip install -r apps/api/requirements-aws.txt -q
    echo "  Installed requirements-aws.txt"
else
    pip install -r apps/api/requirements.txt -q
    echo "  Installed requirements.txt"
fi

# 3. Install web deps
echo ""
echo "[3/5] Installing web dependencies..."
cd apps/web
if command -v pnpm &> /dev/null; then
    pnpm install
else
    npm install
fi
cd "$PROJECT_ROOT"
echo "  Web deps installed"

# 4. AWS CLI check
echo ""
echo "[4/5] Checking AWS CLI..."
if command -v aws &> /dev/null; then
    aws --version
else
    echo "  AWS CLI not found. Install: https://aws.amazon.com/cli/"
fi

# 5. SAM (optional)
echo ""
echo "[5/5] SAM deploy: run manually with --deploy-sam"
if [ "$1" == "--deploy-sam" ]; then
    cd aws
    sam build
    sam deploy --guided
    cd "$PROJECT_ROOT"
fi

echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "  1. Configure apps/api/.env.local (see docs/AWS_GPU_SETUP.md)"
echo "  2. Deploy SageMaker endpoint (aws/sagemaker/)"
echo "  3. Run API: cd apps/api && uvicorn app.main:app --reload"
echo "  4. Run Web: cd apps/web && pnpm dev"

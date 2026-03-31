#!/bin/bash

echo "🚀 Setting up PhotoGenius AI development environment..."

# Check Node version
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi

# Check pnpm
if ! command -v pnpm &> /dev/null; then
    echo "📦 Installing pnpm..."
    npm install -g pnpm
fi

# Check Python version
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11 not found. Please install Python 3.11+"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pnpm install

# Setup database
echo "🗄️  Setting up database..."
cd packages/database
pnpm prisma generate
pnpm prisma migrate dev
pnpm prisma db seed

# Setup Python environment
echo "🐍 Setting up Python environment..."
cd ../../apps/api
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

echo "✅ Setup complete!"
echo ""
echo "To start development:"
echo "  pnpm dev        # Start all services"
echo "  pnpm dev --filter=web   # Start frontend only"
echo "  pnpm dev --filter=api   # Start backend only"

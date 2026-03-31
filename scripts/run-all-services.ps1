# Run all PhotoGenius AI services (Web + API)
# AI Service runs on Modal.com (cloud)
# Usage: .\scripts\run-all-services.ps1

Write-Host "🚀 Starting PhotoGenius AI Services..." -ForegroundColor Green
Write-Host ""

# Navigate to project root
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

# Check if Docker is running
$dockerRunning = docker info 2>$null
if (-not $dockerRunning) {
    Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Option 1: Use Docker Compose (recommended for full stack)
Write-Host "📦 Option 1: Starting with Docker Compose..." -ForegroundColor Yellow
Write-Host "   This will start: Postgres, Redis, Web, API" -ForegroundColor Cyan
Write-Host "   AI Service: Modal.com (cloud)" -ForegroundColor Cyan
Write-Host ""

$useDocker = Read-Host "Use Docker Compose? (Y/n)"
if ($useDocker -ne "n" -and $useDocker -ne "N") {
    & "$projectRoot\scripts\start-services.ps1"
    exit 0
}

# Option 2: Run locally (without Docker)
Write-Host ""
Write-Host "💻 Option 2: Starting services locally..." -ForegroundColor Yellow
Write-Host "   This will start: Web (Next.js), API (FastAPI)" -ForegroundColor Cyan
Write-Host "   Requires: Postgres & Redis running (or use Docker for these)" -ForegroundColor Cyan
Write-Host ""

# Start Web (Next.js)
Write-Host "Starting Web (Next.js) on port 3000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; pnpm --filter @photogenius/web dev"

# Wait a bit
Start-Sleep -Seconds 2

# Start API (FastAPI)
Write-Host "Starting API (FastAPI) on port 8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; pnpm --filter @photogenius/api dev"

Write-Host ""
Write-Host "✅ Services starting in separate windows!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 URLs:" -ForegroundColor Cyan
Write-Host "   Web:  http://localhost:3000" -ForegroundColor White
Write-Host "   API:  http://localhost:8000" -ForegroundColor White
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "🔗 AI Service: Modal.com (cloud)" -ForegroundColor Cyan
Write-Host "   Base:     https://amareshsingh0--photogenius-ai-fastapi-app.modal.run" -ForegroundColor White
Write-Host "   Health:   https://amareshsingh0--photogenius-ai-fastapi-app.modal.run/health" -ForegroundColor White
Write-Host "   Docs:     https://amareshsingh0--photogenius-ai-fastapi-app.modal.run/docs" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C in each window to stop services" -ForegroundColor Yellow

# Quick dependency installation script
# Usage: .\scripts\install-dependencies.ps1

Write-Host "📦 Installing PhotoGenius AI Dependencies..." -ForegroundColor Green
Write-Host ""

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

# ==================== Python Dependencies ====================
Write-Host "🐍 Installing Python dependencies (API service)..." -ForegroundColor Yellow
Write-Host "   Location: apps/api" -ForegroundColor Cyan
Write-Host ""

$apiDir = Join-Path $projectRoot "apps\api"
if (Test-Path $apiDir) {
    Set-Location $apiDir
    
    # Check if sentencepiece is already installed
    $sentencepieceInstalled = python -c "import sentencepiece" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ sentencepiece already installed" -ForegroundColor Green
    } else {
        Write-Host "   Installing sentencepiece..." -ForegroundColor Cyan
        pip install sentencepiece==0.1.99
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ sentencepiece installed" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  sentencepiece installation failed" -ForegroundColor Yellow
            Write-Host "   Try: pip install -r requirements.txt" -ForegroundColor Yellow
        }
    }
    
    Set-Location $projectRoot
} else {
    Write-Host "   ❌ apps/api directory not found" -ForegroundColor Red
}

Write-Host ""

# ==================== Node.js Dependencies ====================
Write-Host "📦 Installing Node.js dependencies (turbo only)..." -ForegroundColor Yellow
Write-Host "   Location: root" -ForegroundColor Cyan
Write-Host ""

# Check if turbo exists
$turboPath = Join-Path $projectRoot "node_modules\turbo\bin\turbo.js"
if (Test-Path $turboPath) {
    Write-Host "   ✅ turbo already installed" -ForegroundColor Green
} else {
    Write-Host "   Installing turbo (this may take a moment)..." -ForegroundColor Cyan
    
    # Try quick install (use -w flag for workspace root)
    pnpm add -D turbo --save-exact -w
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ turbo installed" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  turbo installation failed" -ForegroundColor Yellow
        Write-Host "   Try manually: pnpm install --network-timeout=60000" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "✅ Dependency installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Start services: .\scripts\run-all-services.ps1" -ForegroundColor White
Write-Host "   2. Or manually:" -ForegroundColor White
Write-Host "      - Web: pnpm --filter @photogenius/web dev" -ForegroundColor White
Write-Host "      - API: pnpm --filter @photogenius/api dev" -ForegroundColor White

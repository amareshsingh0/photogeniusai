# Setup Modal Secrets
# This script creates Modal secrets from your .env.local file

Write-Host "🔐 Setting up Modal Secrets..." -ForegroundColor Cyan
Write-Host ""

# Read HUGGINGFACE_TOKEN from .env.local
$envFile = "apps\api\.env.local"
if (-not (Test-Path $envFile)) {
    Write-Host "❌ Error: $envFile not found!" -ForegroundColor Red
    Write-Host "   Please create the file and add HUGGINGFACE_TOKEN" -ForegroundColor Yellow
    exit 1
}

# Parse .env.local to get HUGGINGFACE_TOKEN
$hfToken = $null
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^HUGGINGFACE_TOKEN=(.+)$') {
        $hfToken = $matches[1].Trim()
    }
}

if (-not $hfToken) {
    Write-Host "❌ Error: HUGGINGFACE_TOKEN not found in $envFile" -ForegroundColor Red
    Write-Host "   Please add: HUGGINGFACE_TOKEN=hf_your_token_here" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Found HUGGINGFACE_TOKEN in .env.local" -ForegroundColor Green
Write-Host ""

# Create Modal secret
Write-Host "Creating Modal secret 'huggingface'..." -ForegroundColor Yellow
Write-Host ""

$command = "modal secret create huggingface HUGGINGFACE_TOKEN=$hfToken"

Write-Host "Running: $command" -ForegroundColor Gray
Write-Host ""

Invoke-Expression $command

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Successfully created Modal secret 'huggingface'!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can verify with:" -ForegroundColor Cyan
    Write-Host "  modal secret list" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Now you can deploy Modal functions:" -ForegroundColor Cyan
    Write-Host "  cd ai-pipeline" -ForegroundColor Gray
    Write-Host "  modal deploy services/generation_service.py" -ForegroundColor Gray
    Write-Host "  modal deploy services/lora_trainer.py" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "❌ Failed to create secret. Check Modal CLI is installed and authenticated." -ForegroundColor Red
    Write-Host ""
    Write-Host "To authenticate Modal:" -ForegroundColor Yellow
    Write-Host "  modal token new" -ForegroundColor Gray
}

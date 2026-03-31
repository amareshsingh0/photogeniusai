# PhotoGenius AWS GPU Setup Script (Windows PowerShell)
# No Modal, No Lightning - Pure AWS (SageMaker + Lambda)

param(
    [switch]$SkipAws,
    [switch]$DeploySam
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path $ProjectRoot)) {
    $ProjectRoot = $PSScriptRoot
}

Write-Host "=== PhotoGenius AWS GPU Setup ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray

# 1. Create venv
Write-Host "`n[1/5] Creating Python venv..." -ForegroundColor Yellow
$venvPath = Join-Path $ProjectRoot ".venv"
if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
    Write-Host "  Venv created at $venvPath" -ForegroundColor Green
} else {
    Write-Host "  Venv exists" -ForegroundColor Green
}

# 2. Activate and install API deps (AWS-only)
Write-Host "`n[2/5] Installing API dependencies (AWS, no Modal)..." -ForegroundColor Yellow
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
& $activateScript
$apiReqPath = Join-Path $ProjectRoot "apps\api\requirements-aws.txt"
if (Test-Path $apiReqPath) {
    pip install -r $apiReqPath -q
    Write-Host "  Installed requirements-aws.txt" -ForegroundColor Green
} else {
    pip install -r (Join-Path $ProjectRoot "apps\api\requirements.txt") -q
    Write-Host "  Installed requirements.txt (Modal removed from config)" -ForegroundColor Green
}

# 3. Install web deps
Write-Host "`n[3/5] Installing web dependencies..." -ForegroundColor Yellow
$webPath = Join-Path $ProjectRoot "apps\web"
Set-Location $webPath
if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    pnpm install
    Write-Host "  Web deps installed" -ForegroundColor Green
} else {
    npm install
    Write-Host "  Web deps installed (npm)" -ForegroundColor Green
}
Set-Location $ProjectRoot

# 4. AWS CLI check
if (-not $SkipAws) {
    Write-Host "`n[4/5] Checking AWS CLI..." -ForegroundColor Yellow
    try {
        $awsVer = aws --version 2>&1
        Write-Host "  $awsVer" -ForegroundColor Green
    } catch {
        Write-Host "  AWS CLI not found. Install: https://aws.amazon.com/cli/" -ForegroundColor Red
    }
} else {
    Write-Host "`n[4/5] Skipping AWS check (-SkipAws)" -ForegroundColor Gray
}

# 5. SAM deploy (optional)
if ($DeploySam) {
    Write-Host "`n[5/5] Deploying SAM stack..." -ForegroundColor Yellow
    $awsPath = Join-Path $ProjectRoot "aws"
    Set-Location $awsPath
    sam build
    sam deploy --guided
    Set-Location $ProjectRoot
    Write-Host "  SAM deployed. Note the ApiEndpoint from output." -ForegroundColor Green
} else {
    Write-Host "`n[5/5] SAM deploy skipped. Run: .\scripts\setup-aws-gpu.ps1 -DeploySam" -ForegroundColor Gray
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Configure apps/api/.env.local (see docs/AWS_GPU_SETUP.md)" -ForegroundColor Gray
Write-Host "  2. Deploy SageMaker endpoint (aws/sagemaker/)" -ForegroundColor Gray
Write-Host "  3. Run API: cd apps/api && uvicorn app.main:app --reload" -ForegroundColor Gray
Write-Host "  4. Run Web: cd apps/web && pnpm dev" -ForegroundColor Gray

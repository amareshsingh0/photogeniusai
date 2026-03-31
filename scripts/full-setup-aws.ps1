# PhotoGenius AI - Full AWS setup: load .env.local, package & deploy SageMaker, deploy Lambda, optional model downloads
# Usage: .\scripts\full-setup-aws.ps1 [-SkipSageMaker] [-SkipLambda] [-SkipDownloads] [-DryRun]
# Run from repo root. Requires: AWS CLI configured, aws/sagemaker/.env.local with SAGEMAKER_ROLE, SAGEMAKER_BUCKET, etc.

param(
    [switch] $SkipSageMaker,
    [switch] $SkipLambda,
    [switch] $SkipDownloads,
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $ROOT

# Load .env.local from aws/sagemaker (primary) and optionally apps/api for API URLs
function Load-EnvFile {
    param([string] $Path)
    if (-not (Test-Path $Path)) { return }
    Write-Host "[ENV] Loading $Path"
    Get-Content $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $key = $matches[1]
            $val = $matches[2].Trim()
            if ($val.StartsWith('"') -and $val.EndsWith('"')) { $val = $val.Substring(1, $val.Length - 2) }
            if ($val.StartsWith("'") -and $val.EndsWith("'")) { $val = $val.Substring(1, $val.Length - 2) }
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

# Required values for deploy (from .env.local)
$EnvSage = Join-Path $ROOT "aws\sagemaker\.env.local"
$EnvApi = Join-Path $ROOT "apps\api\.env.local"

Load-EnvFile -Path $EnvSage
Load-EnvFile -Path $EnvApi

$role = $env:SAGEMAKER_ROLE
$bucket = $env:SAGEMAKER_BUCKET
$region = $env:AWS_REGION
if (-not $region) { $env:AWS_REGION = "us-east-1"; $region = "us-east-1" }

Write-Host ""
Write-Host "=== PhotoGenius Full AWS Setup ==="
Write-Host "  SAGEMAKER_ROLE: $(if ($role) { 'set' } else { 'NOT SET' })"
Write-Host "  SAGEMAKER_BUCKET: $(if ($bucket) { $bucket } else { 'NOT SET' })"
Write-Host "  AWS_REGION: $region"
Write-Host "  SkipSageMaker: $SkipSageMaker | SkipLambda: $SkipLambda | SkipDownloads: $SkipDownloads | DryRun: $DryRun"
Write-Host ""

if (-not $SkipSageMaker -and -not $role) {
    Write-Host "ERROR: SAGEMAKER_ROLE is required for SageMaker deploy. Set it in aws/sagemaker/.env.local" -ForegroundColor Red
    exit 1
}

# 0. Deploy dependencies (boto3, PyYAML for deploy scripts)
Write-Host "[0] Ensuring deploy dependencies..."
$reqPath = Join-Path $ROOT "deploy\requirements.txt"
if (Test-Path $reqPath) {
    pip install -q -r $reqPath 2>$null
    if ($LASTEXITCODE -ne 0) { pip install boto3 PyYAML }
}
Write-Host "  [OK]"
Write-Host ""

# 1. Package SageMaker model
if (-not $SkipSageMaker -and -not $DryRun) {
    Write-Host "[1] Packaging SageMaker model (deploy/sagemaker/package_model.py)..."
    python (Join-Path $ROOT "deploy\sagemaker\package_model.py")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "  [OK]"
    Write-Host ""

    Write-Host "[2] Uploading and deploying SageMaker (upload_and_deploy.py)..."
    $uploadScript = Join-Path $ROOT "deploy\sagemaker\upload_and_deploy.py"
    if ($DryRun) { python $uploadScript --dry-run } else { python $uploadScript }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "  [OK]"
    Write-Host ""
}
elseif ($DryRun -and -not $SkipSageMaker) {
    Write-Host "[1-2] [DRY-RUN] Would package and run upload_and_deploy.py"
    Write-Host ""
}

# 3. Deploy Lambda + API Gateway
if (-not $SkipLambda -and -not $DryRun) {
    Write-Host "[3] Deploying Lambda orchestrator (deploy/lambda/deploy.ps1)..."
    & (Join-Path $ROOT "deploy\lambda\deploy.ps1") -Region $region
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host ""
}
elseif ($DryRun -and -not $SkipLambda) {
    Write-Host "[3] [DRY-RUN] Would run deploy/lambda/deploy.ps1"
    Write-Host ""
}

# 4. Optional: download models (for local/EFS use; SageMaker container uses packaged code)
if (-not $SkipDownloads -and -not $DryRun) {
    Write-Host "[4] Downloading AI models (ai-pipeline) to local cache..."
    $modelDir = Join-Path $ROOT "ai-pipeline\models\cache"
    if (-not (Test-Path $modelDir)) { New-Item -ItemType Directory -Path $modelDir -Force | Out-Null }
    $env:MODEL_DIR = $modelDir
    if (-not $env:HF_TOKEN -and $env:HUGGINGFACE_TOKEN) { $env:HF_TOKEN = $env:HUGGINGFACE_TOKEN }

    $aiPipeline = Join-Path $ROOT "ai-pipeline"
    Push-Location $aiPipeline
    try {
        if (Test-Path "models\download_models.py") {
            Write-Host "  Running download_models.py..."
            python models\download_models.py 2>&1
        }
        if (Test-Path "models\download_instantid.py") {
            Write-Host "  Running download_instantid.py..."
            python models\download_instantid.py 2>&1
        }
    }
    finally { Pop-Location }
    Write-Host "  [OK] Downloads done (cache: $modelDir)"
    Write-Host ""
}
elseif ($DryRun -and -not $SkipDownloads) {
    Write-Host "[4] [DRY-RUN] Would run ai-pipeline models download_models.py and download_instantid.py"
    Write-Host ""
}

Write-Host "=== Full setup complete ==="
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Get API Gateway URL: aws cloudformation describe-stacks --stack-name photogenius-api --region $region --query 'Stacks[0].Outputs'"
Write-Host "  2. Set apps/api/.env.local: AWS_LAMBDA_GENERATION_URL=<API_URL>/generate"
Write-Host "  3. Set apps/web/.env.local: AWS_API_GATEWAY_URL=<API_URL>"
Write-Host ""

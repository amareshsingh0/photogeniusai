# Start (deploy) ALL PhotoGenius SageMaker tiers in one command.
# Runs deploy/sagemaker_deployment.py --tier all. Requires SAGEMAKER_ROLE.
# Usage: .\start-all-sagemaker.ps1 [-Region us-east-1]
# From repo root: .\aws\scripts\start-all-sagemaker.ps1
param([string]$Region = "us-east-1")
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
# If we're in aws/scripts, repo root is ../..
while ($root -and (Split-Path $root -Leaf) -eq "scripts") { $root = Split-Path $root -Parent }
while ($root -and (Split-Path $root -Leaf) -eq "aws")  { $root = Split-Path $root -Parent }
# If deploy script not found (e.g. run from repo root), use current directory as repo root
if (-not $root -or -not (Test-Path (Join-Path $root "deploy\sagemaker_deployment.py"))) {
    $cwd = (Get-Location).Path
    if (Test-Path (Join-Path $cwd "deploy\sagemaker_deployment.py")) { $root = $cwd }
}
$deployScript = Join-Path $root "deploy\sagemaker_deployment.py"
if (-not (Test-Path $deployScript)) {
    Write-Host "Not found: deploy\sagemaker_deployment.py. Run from repo root or aws/scripts." -ForegroundColor Red
    exit 1
}
# Load aws/sagemaker/.env.local if present (SAGEMAKER_ROLE, etc.)
$envLocal = Join-Path $root "aws\sagemaker\.env.local"
if (Test-Path $envLocal) {
    Get-Content $envLocal | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $key = $matches[1]
            $val = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
    Write-Host "Loaded env from aws/sagemaker/.env.local" -ForegroundColor Gray
}
if (-not $env:SAGEMAKER_ROLE) {
    Write-Host "SAGEMAKER_ROLE not set. Set it or add to aws/sagemaker/.env.local" -ForegroundColor Red
    exit 1
}
$env:AWS_REGION = $Region
Write-Host "Deploying all tiers (STANDARD, PREMIUM, PERFECT)..." -ForegroundColor Cyan
Set-Location $root
python $deployScript --tier all
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) { Write-Host "Deploy finished." -ForegroundColor Green } else { Write-Host "Deploy failed (exit $exitCode)." -ForegroundColor Red }
exit $exitCode

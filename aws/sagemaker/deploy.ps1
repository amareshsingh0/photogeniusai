# SageMaker deploy - MUST use own venv (sagemaker 2.x, main project has 3.x or none)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $scriptDir ".venv"

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating deploy venv..." -ForegroundColor Cyan
    python -m venv $venvPath
}

& "$venvPath\Scripts\Activate.ps1"
Write-Host "Installing sagemaker 2.x (required - v3 has no HuggingFaceModel)..." -ForegroundColor Gray
pip install -q --upgrade -r "$scriptDir\requirements.txt"

# Fix JumpStart region_config.json missing (sagemaker 2.x package bug)
$jsDir = Join-Path $venvPath "Lib\site-packages\sagemaker\jumpstart"
$targetConfig = Join-Path $jsDir "region_config.json"
$sourceConfig = Join-Path $scriptDir "region_config.json"
if (Test-Path $sourceConfig) {
    New-Item -ItemType Directory -Path $jsDir -Force | Out-Null
    Copy-Item $sourceConfig $targetConfig -Force
}

Write-Host "Deploying endpoint..." -ForegroundColor Cyan
& "$venvPath\Scripts\python.exe" "$scriptDir\deploy_endpoint.py"

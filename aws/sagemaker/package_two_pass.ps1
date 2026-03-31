# Package two-pass model code for SageMaker (AWS only, no Modal).
# Run from repo root: .\aws\sagemaker\package_two_pass.ps1
# Or from aws/sagemaker: .\package_two_pass.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path } else { (Get-Location).Path }
$SagemakerDir = Join-Path $RepoRoot "aws\sagemaker"
$ModelCode = Join-Path $SagemakerDir "model\code"

Set-Location $SagemakerDir

Write-Host "Packaging two-pass model for SageMaker..."

# Sync canonical two_pass_generation.py from ai-pipeline (optional)
$Canonical = Join-Path $RepoRoot "ai-pipeline\services\two_pass_generation.py"
if (Test-Path $Canonical) {
  Copy-Item $Canonical $ModelCode -Force
  Write-Host "  Synced two_pass_generation.py from ai-pipeline"
}

foreach ($f in @("inference_two_pass.py", "requirements.txt")) {
  if (-not (Test-Path (Join-Path $ModelCode $f))) {
    Write-Host "Missing $ModelCode\$f" -ForegroundColor Red
    exit 1
  }
}

$BuildDir = Join-Path $SagemakerDir "build"
if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $BuildDir "code") -Force | Out-Null
Copy-Item (Join-Path $ModelCode "*") (Join-Path $BuildDir "code") -Recurse -Force

$TarPath = Join-Path $SagemakerDir "model_two_pass.tar.gz"
# Use tar if available (Windows 10+)
if (Get-Command tar -ErrorAction SilentlyContinue) {
  Set-Location $BuildDir
  tar -czvf $TarPath code
  Set-Location $SagemakerDir
} else {
  # Fallback: create zip and rename; SageMaker expects tar.gz - user should use WSL or install tar
  Write-Host "tar not found. Install tar (e.g. via Git for Windows) or run: bash aws/sagemaker/package_two_pass.sh" -ForegroundColor Yellow
  Compress-Archive -Path (Join-Path $BuildDir "code") -DestinationPath ($TarPath -replace "\.tar\.gz", ".zip") -Force
  Write-Host "Created .zip; for SageMaker you need .tar.gz - run package_two_pass.sh in Git Bash" -ForegroundColor Yellow
}

Remove-Item $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Model package: $TarPath"
Write-Host "Upload: aws s3 cp model_two_pass.tar.gz s3://YOUR_BUCKET/models/two-pass/model.tar.gz"

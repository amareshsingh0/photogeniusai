# Package Identity Engine V2 model code for SageMaker (99%+ face consistency).
# Run from repo root: .\aws\sagemaker\package_identity_v2.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$SageMakerDir = Join-Path $RepoRoot "aws\sagemaker"
$ModelCode = Join-Path $SageMakerDir "model\code"

Write-Host "Packaging Identity V2 model for SageMaker..."

Set-Location $SageMakerDir

@("inference_identity_v2.py", "identity_engine_v2_aws.py", "requirements.txt") | ForEach-Object {
    if (-not (Test-Path (Join-Path $ModelCode $_))) {
        Write-Host "Missing $ModelCode\$_"
        exit 1
    }
}

$BuildDir = Join-Path $SageMakerDir "build"
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
New-Item -ItemType Directory -Path (Join-Path $BuildDir "code") -Force | Out-Null
Copy-Item -Path (Join-Path $ModelCode "*") -Destination (Join-Path $BuildDir "code") -Recurse -Force

$TarPath = Join-Path $SageMakerDir "model_identity_v2.tar.gz"
Push-Location $BuildDir
tar -czvf $TarPath code
Pop-Location
Remove-Item -Recurse -Force $BuildDir -ErrorAction SilentlyContinue

Write-Host "Model package created: $TarPath"
Write-Host "Env: IDENTITY_ENGINE_VERSION=v2, IDENTITY_METHOD=ensemble, SAGEMAKER_IDENTITY_V2_ENDPOINT=<endpoint>"

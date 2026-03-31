# Run AWS SAM CLI from project root; uses aws/template.yaml
# Usage: .\scripts\sam.ps1 build | .\scripts\sam.ps1 deploy | .\scripts\sam.ps1 list endpoints
$ErrorActionPreference = "Stop"
$root = (Get-Item $PSScriptRoot).Parent.FullName
$awsDir = Join-Path $root "aws"
if (-not (Test-Path (Join-Path $awsDir "template.yaml"))) {
    Write-Error "Template not found at $awsDir\template.yaml"
    exit 1
}
Set-Location $awsDir
& sam @args
exit $LASTEXITCODE

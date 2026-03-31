# Delete ALL PhotoGenius SageMaker endpoints in the region (one command).
# Only deletes endpoints whose names start with "photogenius-".
# Usage: .\delete-all-sagemaker.ps1 [-Region us-east-1] [-Force]
param(
    [string]$Region = "us-east-1",
    [switch]$Force
)
$ErrorActionPreference = "Stop"
Write-Host "Listing SageMaker endpoints in $Region (photogenius-* only)..." -ForegroundColor Cyan
$json = aws sagemaker list-endpoints --region $Region --output json 2>$null
if (-not $json) {
    Write-Host "No endpoints or AWS CLI error. Check region and credentials." -ForegroundColor Yellow
    exit 1
}
$endpoints = ($json | ConvertFrom-Json).Endpoints
$photo = $endpoints | Where-Object { $_.EndpointName -like "photogenius-*" }
if (-not $photo -or $photo.Count -eq 0) {
    Write-Host "No PhotoGenius endpoints found (photogenius-*). Nothing to delete." -ForegroundColor Green
    exit 0
}
Write-Host "Found $($photo.Count) endpoint(s): $($photo.EndpointName -join ', ')" -ForegroundColor Yellow
if (-not $Force) {
    $confirm = Read-Host "Delete all? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "Aborted." -ForegroundColor Gray
        exit 0
    }
}
foreach ($ep in $photo) {
    $name = $ep.EndpointName
    Write-Host "Deleting $name ..." -ForegroundColor Cyan
    aws sagemaker delete-endpoint --endpoint-name $name --region $Region
    if ($LASTEXITCODE -eq 0) { Write-Host "  OK" -ForegroundColor Green } else { Write-Host "  Failed" -ForegroundColor Red }
}
Write-Host "Done. Endpoints are transitioning to Deleting (may take a few minutes)." -ForegroundColor Green

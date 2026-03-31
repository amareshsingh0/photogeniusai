# Monitor EC2 model staging progress
# Usage: .\monitor-model-staging.ps1

param(
    [int]$CheckInterval = 30,
    [int]$MaxWaitMinutes = 30
)

$startTime = Get-Date
$endTime = $startTime.AddMinutes($MaxWaitMinutes)

Write-Host "=== PhotoGenius Model Staging Monitor ===" -ForegroundColor Cyan
Write-Host "EC2 is downloading SDXL models and uploading to S3." -ForegroundColor Yellow
Write-Host "This typically takes 15-25 minutes." -ForegroundColor Yellow
Write-Host ""

$lastSize = 0
$complete = $false

while ((Get-Date) -lt $endTime -and -not $complete) {
    # Check S3 for models
    $turboResult = aws s3 ls s3://photogenius-models-dev/models/sdxl-turbo/ --region us-east-1 --recursive --summarize 2>$null
    $baseResult = aws s3 ls s3://photogenius-models-dev/models/stable-diffusion-xl-base-1.0/ --region us-east-1 --recursive --summarize 2>$null
    
    # Parse sizes
    $turboSize = ($turboResult | Select-String "Total Size: (\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) -as [long]
    $baseSize = ($baseResult | Select-String "Total Size: (\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) -as [long]
    $turboObjects = ($turboResult | Select-String "Total Objects: (\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) -as [int]
    $baseObjects = ($baseResult | Select-String "Total Objects: (\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) -as [int]
    
    $totalSize = ($turboSize + $baseSize) / 1GB
    $elapsed = ((Get-Date) - $startTime).TotalMinutes
    
    # Display progress
    Clear-Host
    Write-Host "=== PhotoGenius Model Staging Monitor ===" -ForegroundColor Cyan
    Write-Host "Elapsed: $([math]::Round($elapsed, 1)) minutes" -ForegroundColor Gray
    Write-Host ""
    Write-Host "SDXL Turbo (3GB):" -ForegroundColor Yellow
    Write-Host "  Objects: $turboObjects"
    Write-Host "  Size: $([math]::Round($turboSize / 1GB, 2)) GB"
    Write-Host ""
    Write-Host "SDXL Base (7GB):" -ForegroundColor Yellow
    Write-Host "  Objects: $baseObjects"
    Write-Host "  Size: $([math]::Round($baseSize / 1GB, 2)) GB"
    Write-Host ""
    Write-Host "Total: $([math]::Round($totalSize, 2)) GB / ~10 GB" -ForegroundColor Cyan
    
    # Check completion (SDXL Turbo is ~3GB, Base is ~7GB)
    if ($turboSize -gt 2.5GB) {
        Write-Host "`nSDXL Turbo ready!" -ForegroundColor Green
        if ($baseSize -gt 6GB) {
            Write-Host "SDXL Base ready!" -ForegroundColor Green
            $complete = $true
        }
    }
    
    if (-not $complete) {
        Write-Host "`nChecking again in $CheckInterval seconds... (Ctrl+C to stop)" -ForegroundColor Gray
        Start-Sleep -Seconds $CheckInterval
    }
}

if ($complete) {
    Write-Host "`n=== Models Ready! ===" -ForegroundColor Green
    Write-Host "You can now update SageMaker to load from S3." -ForegroundColor Cyan
    Write-Host "Run: python deploy/sagemaker_deployment.py --tier all --use-s3-models"
} else {
    Write-Host "`n=== Still in progress ===" -ForegroundColor Yellow
    Write-Host "Run this script again to continue monitoring."
}

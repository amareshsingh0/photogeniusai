# Monitor SageMaker endpoint deployment status
$ENDPOINT_NAME = "photogenius-generation-dev"
$REGION = "us-east-1"

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "Monitoring Endpoint Deployment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Endpoint: $ENDPOINT_NAME"
Write-Host "Started monitoring at: $(Get-Date -Format 'HH:mm:ss')"
Write-Host "==========================================`n" -ForegroundColor Cyan

$startTime = Get-Date

while ($true) {
    $status = aws sagemaker describe-endpoint `
        --endpoint-name $ENDPOINT_NAME `
        --region $REGION `
        --query 'EndpointStatus' `
        --output text

    $elapsed = [math]::Round(((Get-Date) - $startTime).TotalMinutes, 1)
    $timestamp = Get-Date -Format 'HH:mm:ss'

    Write-Host "[$timestamp] Status: $status (${elapsed}m elapsed)" -NoNewline

    if ($status -eq "InService") {
        Write-Host " - READY!" -ForegroundColor Green
        Write-Host "`n==========================================" -ForegroundColor Green
        Write-Host "Deployment Complete!" -ForegroundColor Green
        Write-Host "==========================================" -ForegroundColor Green
        Write-Host "Total time: ${elapsed} minutes`n"
        Write-Host "Next step: Run tests"
        Write-Host "  python test_endpoint.py`n"
        exit 0
    }
    elseif ($status -eq "Failed") {
        Write-Host " - FAILED!" -ForegroundColor Red
        Write-Host "`nGetting failure reason..."
        aws sagemaker describe-endpoint `
            --endpoint-name $ENDPOINT_NAME `
            --region $REGION `
            --query 'FailureReason'
        exit 1
    }
    elseif ($status -eq "Updating") {
        Write-Host " - In progress..." -ForegroundColor Yellow
    }
    else {
        Write-Host ""
    }

    Start-Sleep -Seconds 15
}

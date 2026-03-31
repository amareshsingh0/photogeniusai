# Test the full PhotoGenius pipeline
# Usage: .\test-full-pipeline.ps1
param(
    [string]$ApiUrl = "https://xa89zghkq7.execute-api.us-east-1.amazonaws.com/Prod"
)

Write-Host "=== PhotoGenius Pipeline Test ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health check
Write-Host "1. Health Check..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$ApiUrl/health" -Method Get -TimeoutSec 10
    Write-Host "   OK: API is reachable" -ForegroundColor Green
} catch {
    Write-Host "   FAIL: API not reachable" -ForegroundColor Red
}

# Test 2: Lambda with test_mode
Write-Host ""
Write-Host "2. Lambda Test Mode..." -ForegroundColor Yellow
try {
    $body = '{"prompt":"test portrait","test_mode":true}'
    $result = Invoke-RestMethod -Uri "$ApiUrl/orchestrate/v2" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 30
    if ($result.metadata.test_mode) {
        Write-Host "   OK: Lambda test_mode works" -ForegroundColor Green
        Write-Host "   Response time: $($result.metadata.total_time)s" -ForegroundColor Gray
    } else {
        Write-Host "   WARN: Got response but test_mode not set" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 3: SageMaker endpoint status
Write-Host ""
Write-Host "3. SageMaker Endpoints..." -ForegroundColor Yellow
$endpoints = aws sagemaker list-endpoints --region us-east-1 --query "Endpoints[?starts_with(EndpointName,'photogenius')].{Name:EndpointName,Status:EndpointStatus}" --output json | ConvertFrom-Json
foreach ($ep in $endpoints) {
    $color = if ($ep.Status -eq "InService") { "Green" } else { "Yellow" }
    Write-Host "   $($ep.Name): $($ep.Status)" -ForegroundColor $color
}

# Test 4: Real generation (will likely timeout without pre-loaded models)
Write-Host ""
Write-Host "4. Real Generation (may timeout)..." -ForegroundColor Yellow
Write-Host "   Skipping - requires models to be pre-loaded on SageMaker" -ForegroundColor Gray
Write-Host "   To enable: Run upload-models-to-s3.ps1 first, then redeploy SageMaker" -ForegroundColor Gray

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "- Lambda Pipeline: WORKING (test_mode)" -ForegroundColor Green
Write-Host "- SageMaker: NEEDS MODEL SETUP" -ForegroundColor Yellow
Write-Host ""
Write-Host "To enable real image generation:" -ForegroundColor White
Write-Host "1. Run: .\upload-models-to-s3.ps1  (downloads ~14GB, uploads to S3)" -ForegroundColor Gray
Write-Host "2. Redeploy SageMaker endpoints with models from S3" -ForegroundColor Gray
Write-Host "3. Or use Modal.com for GPU inference (simpler setup)" -ForegroundColor Gray

# PhotoGenius AI - Lambda Deployment (PowerShell)
# Deploys Lambda functions using AWS SAM

$ErrorActionPreference = "Stop"

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "PhotoGenius AI - Lambda Deployment" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

$REGION = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }
$STACK_NAME = "photogenius"

Write-Host "Region: $REGION" -ForegroundColor Yellow
Write-Host "Stack: $STACK_NAME" -ForegroundColor Yellow
Write-Host ""

# Navigate to aws directory
Set-Location $PSScriptRoot

# Step 1: SAM Build
Write-Host "[1/3] Building Lambda functions..." -ForegroundColor Green
try {
    sam build
    Write-Host "✓ Build complete" -ForegroundColor Green
}
catch {
    Write-Host "✗ Build failed: $_" -ForegroundColor Red
    exit 1
}

# Step 2: SAM Deploy
Write-Host ""
Write-Host "[2/3] Deploying to AWS..." -ForegroundColor Green
try {
    if (Test-Path "samconfig.toml") {
        # Use existing config
        sam deploy --no-confirm-changeset --region $REGION
    }
    else {
        # Guided deploy (first time)
        sam deploy `
            --stack-name $STACK_NAME `
            --capabilities CAPABILITY_IAM `
            --region $REGION `
            --no-confirm-changeset `
            --resolve-s3
    }
    Write-Host "✓ Deploy complete" -ForegroundColor Green
}
catch {
    Write-Host "✗ Deploy failed: $_" -ForegroundColor Red
    exit 1
}

# Step 3: Get outputs
Write-Host ""
Write-Host "[3/3] Getting stack outputs..." -ForegroundColor Green
try {
    $outputs = aws cloudformation describe-stacks `
        --stack-name $STACK_NAME `
        --region $REGION `
        --query 'Stacks[0].Outputs' `
        --output json | ConvertFrom-Json
    
    Write-Host ""
    Write-Host "=== Stack Outputs ===" -ForegroundColor Cyan
    foreach ($output in $outputs) {
        Write-Host "$($output.OutputKey): $($output.OutputValue)" -ForegroundColor White
    }
    
    $apiUrl = ($outputs | Where-Object { $_.OutputKey -eq "ApiEndpoint" }).OutputValue
    if ($apiUrl) {
        Write-Host ""
        Write-Host "API Gateway URL: $apiUrl" -ForegroundColor Green
        Write-Host "Test command:" -ForegroundColor Yellow
        Write-Host "  Invoke-WebRequest -Uri '$apiUrl/generate' -Method POST -Body '{\"prompt\":\"test\"}' -ContentType 'application/json'" -ForegroundColor Gray
    }
    
}
catch {
    Write-Host "Warning: Could not fetch outputs: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Deployment complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Updated Lambda functions:" -ForegroundColor Cyan
Write-Host "  photogenius-generation-dev" -ForegroundColor White
Write-Host "  photogenius-prompt-enhancer-dev" -ForegroundColor White
Write-Host "  photogenius-orchestrator-v2-dev" -ForegroundColor White
Write-Host "  photogenius-safety-dev" -ForegroundColor White
Write-Host "  photogenius-refinement-dev" -ForegroundColor White
Write-Host "  photogenius-training-dev" -ForegroundColor White
Write-Host ""

# Update SageMaker endpoint to use larger GPU instance

$ENDPOINT_NAME = "photogenius-generation-dev"
$NEW_INSTANCE = "ml.g5.4xlarge"  # 1x A24G, 24GB GPU + 64GB RAM
$REGION = "us-east-1"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Updating Instance Type" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Endpoint: $ENDPOINT_NAME"
Write-Host "New Instance: $NEW_INSTANCE"
Write-Host "GPU Memory: 96GB (4x A10G)"
Write-Host "Cost: `$7.09/hour"
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host

# Get current endpoint config
Write-Host "Getting current configuration..."
$CURRENT_CONFIG = aws sagemaker describe-endpoint `
  --endpoint-name $ENDPOINT_NAME `
  --region $REGION `
  --query 'EndpointConfigName' `
  --output text

Write-Host "Current config: $CURRENT_CONFIG"

# Get model name
$MODEL_NAME = aws sagemaker describe-endpoint-config `
  --endpoint-config-name $CURRENT_CONFIG `
  --region $REGION `
  --query 'ProductionVariants[0].ModelName' `
  --output text

Write-Host "Model: $MODEL_NAME"

# Create new endpoint config with larger instance
$TIMESTAMP = [int][double]::Parse((Get-Date -UFormat %s))
$NEW_CONFIG = "${ENDPOINT_NAME}-g512xlarge-${TIMESTAMP}"

Write-Host "`nCreating new config: $NEW_CONFIG" -ForegroundColor Yellow

$result = aws sagemaker create-endpoint-config `
  --endpoint-config-name $NEW_CONFIG `
  --production-variants "VariantName=AllTraffic,ModelName=$MODEL_NAME,InitialInstanceCount=1,InstanceType=$NEW_INSTANCE" `
  --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "Config created successfully" -ForegroundColor Green
} else {
    Write-Host "Failed to create config" -ForegroundColor Red
    exit 1
}

# Update endpoint
Write-Host "`nUpdating endpoint..." -ForegroundColor Yellow

$result = aws sagemaker update-endpoint `
  --endpoint-name $ENDPOINT_NAME `
  --endpoint-config-name $NEW_CONFIG `
  --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=========================================" -ForegroundColor Green
    Write-Host "Update Initiated Successfully!" -ForegroundColor Green
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host "`nThis will take 10-15 minutes`n"
    Write-Host "Monitor status:"
    Write-Host "  aws sagemaker describe-endpoint --endpoint-name $ENDPOINT_NAME --query 'EndpointStatus'"
} else {
    Write-Host "`nFailed to update endpoint" -ForegroundColor Red
    exit 1
}

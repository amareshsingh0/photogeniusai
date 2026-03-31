# Deploy PhotoGenius AI Lambda Orchestrator to AWS (Windows PowerShell)
# Usage: .\deploy.ps1 [-StackName "photogenius-api"] [-Region "us-east-1"]
# Requires: AWS CLI configured (aws configure), same endpoint names as SageMaker (endpoint_config.yaml)

param(
    [string] $StackName = "photogenius-api",
    [string] $Region = "us-east-1"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$LambdaZip = "lambda-deployment.zip"

Write-Host "Deploying PhotoGenius AI Lambda Orchestrator..."
Write-Host "  Stack: $StackName"
Write-Host "  Region: $Region"
Write-Host ""

# Step 1: Package Lambda code
Write-Host "Step 1: Packaging Lambda code..."
if (Test-Path $LambdaZip) { Remove-Item $LambdaZip -Force }
Compress-Archive -Path "orchestrator.py" -DestinationPath $LambdaZip -Force
Write-Host "  [OK] Lambda package created: $LambdaZip"
Write-Host ""

# Step 2: Deploy CloudFormation stack (endpoint names must match deploy/endpoint_config.yaml)
Write-Host "Step 2: Deploying CloudFormation stack..."
aws cloudformation deploy `
  --template-file cloudformation.yaml `
  --stack-name $StackName `
  --capabilities CAPABILITY_NAMED_IAM `
  --region $Region `
  --parameter-overrides `
    StandardEndpoint=photogenius-standard `
    PremiumEndpoint=photogenius-two-pass `
    PerfectEndpoint=photogenius-perfect

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "  [OK] CloudFormation stack deployed"
Write-Host ""

# Step 3: Update Lambda function code
Write-Host "Step 3: Updating Lambda function code..."
aws lambda update-function-code `
  --function-name photogenius-orchestrator `
  --zip-file "fileb://$LambdaZip" `
  --region $Region `
  --no-cli-pager 2>$null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "  [OK] Lambda function updated"
Write-Host ""

# Step 4: Get API endpoint
Write-Host "Step 4: Getting API endpoint..."
$ApiOutput = aws cloudformation describe-stacks `
  --stack-name $StackName `
  --region $Region `
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" `
  --output text 2>$null

Write-Host ""
Write-Host "Deployment complete!"
Write-Host ""
if ($ApiOutput) {
    Write-Host "API Endpoint: $ApiOutput"
    Write-Host ""
    Write-Host "Test with:"
    Write-Host "  curl -X POST $ApiOutput/generate ``"
    Write-Host "    -H 'Content-Type: application/json' ``"
    Write-Host "    -d '{\"prompt\": \"Person standing in sunlight\"}'"
    Write-Host ""
} else {
    Write-Host "Run: aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].Outputs'"
    Write-Host "to get the API endpoint."
}

Remove-Item $LambdaZip -Force -ErrorAction SilentlyContinue
Write-Host "Done."

#!/bin/bash
# Deploy PhotoGenius AI Lambda Orchestrator to AWS
# Usage: ./deploy.sh [stack-name] [region]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
STACK_NAME="${1:-photogenius-api}"
REGION="${2:-us-east-1}"
LAMBDA_ZIP="lambda-deployment.zip"

echo "Deploying PhotoGenius AI Lambda Orchestrator..."
echo "  Stack: $STACK_NAME"
echo "  Region: $REGION"
echo ""

# Step 1: Package Lambda code
echo "Step 1: Packaging Lambda code..."
zip -r -q "$LAMBDA_ZIP" orchestrator.py
echo "  [OK] Lambda package created: $LAMBDA_ZIP"
echo ""

# Step 2: Deploy CloudFormation stack
echo "Step 2: Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --parameter-overrides \
    StandardEndpoint=photogenius-standard \
    PremiumEndpoint=photogenius-two-pass \
    PerfectEndpoint=photogenius-perfect

echo "  [OK] CloudFormation stack deployed"
echo ""

# Step 3: Update Lambda function code
echo "Step 3: Updating Lambda function code..."
aws lambda update-function-code \
  --function-name photogenius-orchestrator \
  --zip-file "fileb://$LAMBDA_ZIP" \
  --region "$REGION" \
  --no-cli-pager > /dev/null
echo "  [OK] Lambda function updated"
echo ""

# Step 4: Get API endpoint
echo "Step 4: Getting API endpoint..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text 2>/dev/null || true)

echo ""
echo "Deployment complete!"
echo ""
if [ -n "$API_ENDPOINT" ]; then
  echo "API Endpoint: $API_ENDPOINT"
  echo ""
  echo "Test with:"
  echo "  curl -X POST $API_ENDPOINT/generate \\"
  echo "    -H 'Content-Type: application/json' \\"
  echo "    -d '{\"prompt\": \"Person standing in sunlight\"}'"
  echo ""
else
  echo "Run: aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs'"
  echo "to get the API endpoint."
fi

# Clean up
rm -f "$LAMBDA_ZIP"

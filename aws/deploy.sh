#!/bin/bash
# PhotoGenius AI - Full deployment: SAM (Lambda + API + DynamoDB + S3) + optional SageMaker model.
# Run from repo root or from aws/:  ./aws/deploy.sh  or  cd aws && ./deploy.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-photogenius}"
DEPLOY_BUCKET="${DEPLOY_BUCKET:-photogenius-deploy-$(date +%s | tail -c 9)}"

echo "========================================"
echo "PhotoGenius AI - Full deployment"
echo "========================================"
echo "Region: $REGION | Stack: $STACK_NAME"
echo ""

# Step 1: Create S3 bucket for SAM deployment (if not exists)
if ! aws s3api head-bucket --bucket "$DEPLOY_BUCKET" --region "$REGION" 2>/dev/null; then
  echo "Creating deployment bucket: $DEPLOY_BUCKET"
  if [ "$REGION" = "us-east-1" ]; then
    aws s3 mb "s3://$DEPLOY_BUCKET" --region "$REGION"
  else
    aws s3 mb "s3://$DEPLOY_BUCKET" --region "$REGION" --create-bucket-configuration "LocationConstraint=$REGION"
  fi
fi

# Step 2: Build Lambda layers (optional; comment out if not using layers)
if [ -f "layers/build_layers.sh" ]; then
  echo "Building Lambda layers..."
  bash layers/build_layers.sh || true
fi

# Step 3: SAM build
echo "Running sam build..."
sam build --use-container 2>/dev/null || sam build

# Step 4: SAM deploy (guided first time; use samconfig.toml afterward)
echo "Running sam deploy..."
if [ -f "samconfig.toml" ]; then
  sam deploy --no-confirm-changeset --region "$REGION"
else
  sam deploy \
    --stack-name "$STACK_NAME" \
    --s3-bucket "$DEPLOY_BUCKET" \
    --capabilities CAPABILITY_IAM \
    --region "$REGION" \
    --no-confirm-changeset \
    --resolve-s3
fi

# Step 5: Outputs
echo ""
echo "Stack outputs:"
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output table 2>/dev/null || true

API_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text 2>/dev/null || true)
if [ -n "$API_URL" ] && [ "$API_URL" != "None" ]; then
  echo ""
  echo "API base: $API_URL"
  echo "Test: curl -X POST $API_URL/generate -H 'Content-Type: application/json' -d '{\"prompt\":\"epic warrior\",\"style\":\"cinematic\"}'"
fi

# Step 6: Deploy SageMaker model (optional; set SKIP_SAGEMAKER=1 to skip)
if [ -z "$SKIP_SAGEMAKER" ] && [ -f "sagemaker/deploy_model.py" ]; then
  echo ""
  read -p "Deploy SageMaker SDXL endpoint? (y/N) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Deploying SageMaker model..."
    (cd sagemaker && python deploy_model.py) || echo "SageMaker deploy failed or skipped (check SAGEMAKER_ROLE / credentials)."
  fi
fi

echo ""
echo "Deployment complete."

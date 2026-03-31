#!/bin/bash

# Update endpoint to use larger GPU instance

ENDPOINT_NAME="photogenius-generation-dev"
NEW_INSTANCE="ml.g5.12xlarge"  # 4x A10G, 96GB GPU

echo "========================================="
echo "Updating Instance Type"
echo "========================================="
echo "Endpoint: $ENDPOINT_NAME"
echo "New Instance: $NEW_INSTANCE"
echo "GPU Memory: 96GB (4x A10G)"
echo "Cost: \$7.09/hour"
echo "========================================="
echo

# Get current endpoint config
CURRENT_CONFIG=$(aws sagemaker describe-endpoint \
  --endpoint-name $ENDPOINT_NAME \
  --region us-east-1 \
  --query 'EndpointConfigName' \
  --output text)

echo "Current config: $CURRENT_CONFIG"

# Get model name
MODEL_NAME=$(aws sagemaker describe-endpoint-config \
  --endpoint-config-name $CURRENT_CONFIG \
  --region us-east-1 \
  --query 'ProductionVariants[0].ModelName' \
  --output text)

echo "Model: $MODEL_NAME"

# Create new endpoint config with larger instance
NEW_CONFIG="${ENDPOINT_NAME}-g512xlarge-$(date +%s)"

echo "Creating new config: $NEW_CONFIG"

aws sagemaker create-endpoint-config \
  --endpoint-config-name $NEW_CONFIG \
  --production-variants \
    VariantName=AllTraffic,ModelName=$MODEL_NAME,InitialInstanceCount=1,InstanceType=$NEW_INSTANCE \
  --region us-east-1

echo "Updating endpoint..."

aws sagemaker update-endpoint \
  --endpoint-name $ENDPOINT_NAME \
  --endpoint-config-name $NEW_CONFIG \
  --region us-east-1

echo
echo "✓ Update initiated"
echo "This will take 10-15 minutes"
echo
echo "Monitor status:"
echo "  aws sagemaker describe-endpoint --endpoint-name $ENDPOINT_NAME --query 'EndpointStatus'"

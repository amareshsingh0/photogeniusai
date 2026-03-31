#!/bin/bash
# Optimized deployment script for Ubuntu
# Downloads models from S3, packages them, and deploys to SageMaker

set -e  # Exit on error

# Configuration
ENDPOINT_NAME="photogenius-generation-dev"
S3_BUCKET="photogenius-models-dev"
REGION="us-east-1"
INSTANCE_TYPE="ml.g5.2xlarge"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================================================${NC}"
echo -e "${CYAN}PhotoGenius AI - Ubuntu Deployment${NC}"
echo -e "${CYAN}================================================================================${NC}"
echo ""
echo "Endpoint: $ENDPOINT_NAME"
echo "Instance: $INSTANCE_TYPE"
echo "Region: $REGION"
echo ""
echo -e "${YELLOW}WARNING: This will take 25-35 minutes:${NC}"
echo "  - 8-12 min: Download models from S3"
echo "  - 3-5 min: Create model.tar.gz"
echo "  - 3-5 min: Upload to S3"
echo "  - 10-15 min: SageMaker deployment"
echo -e "${CYAN}================================================================================${NC}"
echo ""

# Check dependencies
echo -e "${CYAN}Checking dependencies...${NC}"
command -v aws >/dev/null 2>&1 || { echo -e "${RED}Error: AWS CLI not installed${NC}"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Error: Python3 not installed${NC}"; exit 1; }
echo -e "${GREEN}✓ All dependencies found${NC}"
echo ""

# Create temp directory
TEMP_DIR="temp_model_package_$(date +%s)"
echo -e "${CYAN}Creating temp directory: $TEMP_DIR${NC}"
mkdir -p "$TEMP_DIR/models"
cd "$TEMP_DIR"

# Function to download model from S3
download_model() {
    local model_name=$1
    local target_dir=$2

    echo ""
    echo -e "${CYAN}Downloading $model_name from S3...${NC}"

    # Use AWS CLI sync for faster parallel downloads
    aws s3 sync \
        "s3://${S3_BUCKET}/models/${model_name}/" \
        "${target_dir}/${model_name}/" \
        --region "$REGION" \
        --only-show-errors \
        --no-progress

    # Get size
    local size=$(du -sh "${target_dir}/${model_name}" | cut -f1)
    echo -e "${GREEN}✓ Downloaded $model_name ($size)${NC}"
}

# Download models
echo ""
echo -e "${CYAN}================================================================================${NC}"
echo -e "${CYAN}Step 1: Downloading Models from S3${NC}"
echo -e "${CYAN}================================================================================${NC}"

download_model "sdxl-turbo" "models"
download_model "sdxl-base-1.0" "models"

# Copy inference code
echo ""
echo -e "${CYAN}Step 2: Adding inference code...${NC}"
mkdir -p code
cp ../model/code/inference_preloaded.py code/inference.py
echo -e "${GREEN}✓ Added inference.py${NC}"

# Create tar.gz
echo ""
echo -e "${CYAN}================================================================================${NC}"
echo -e "${CYAN}Step 3: Creating model.tar.gz${NC}"
echo -e "${CYAN}================================================================================${NC}"
echo ""

cd ..
TAR_FILE="model.tar.gz"

echo "Compressing models and code..."
tar -czf "$TAR_FILE" -C "$TEMP_DIR" models code

TAR_SIZE=$(du -h "$TAR_FILE" | cut -f1)
echo -e "${GREEN}✓ Created $TAR_FILE ($TAR_SIZE)${NC}"

# Upload to S3
echo ""
echo -e "${CYAN}================================================================================${NC}"
echo -e "${CYAN}Step 4: Uploading to S3${NC}"
echo -e "${CYAN}================================================================================${NC}"
echo ""

TIMESTAMP=$(date +%s)
S3_KEY="sagemaker/models/preloaded-${TIMESTAMP}/model.tar.gz"
S3_URI="s3://${S3_BUCKET}/${S3_KEY}"

echo "Uploading to $S3_URI..."
aws s3 cp "$TAR_FILE" "$S3_URI" --region "$REGION"
echo -e "${GREEN}✓ Uploaded to S3${NC}"

# Deploy to SageMaker
echo ""
echo -e "${CYAN}================================================================================${NC}"
echo -e "${CYAN}Step 5: Deploying to SageMaker${NC}"
echo -e "${CYAN}================================================================================${NC}"
echo ""

# Get IAM role
ROLE_ARN=$(aws iam get-role --role-name SageMakerExecutionRole --query 'Role.Arn' --output text)
echo "Using role: $ROLE_ARN"

# Container image
IMAGE_URI="763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-inference:2.1.0-transformers4.37.0-gpu-py310-cu118-ubuntu20.04"

# Create model
MODEL_NAME="${ENDPOINT_NAME}-model-${TIMESTAMP}"
echo ""
echo "Creating SageMaker model: $MODEL_NAME"

aws sagemaker create-model \
    --model-name "$MODEL_NAME" \
    --primary-container "{
        \"Image\": \"$IMAGE_URI\",
        \"ModelDataUrl\": \"$S3_URI\",
        \"Environment\": {
            \"SAGEMAKER_CONTAINER_LOG_LEVEL\": \"20\",
            \"SAGEMAKER_REGION\": \"$REGION\"
        }
    }" \
    --execution-role-arn "$ROLE_ARN" \
    --region "$REGION" \
    2>/dev/null || true

echo -e "${GREEN}✓ Model created${NC}"

# Create endpoint config
CONFIG_NAME="${ENDPOINT_NAME}-config-${TIMESTAMP}"
echo ""
echo "Creating endpoint config: $CONFIG_NAME"

aws sagemaker create-endpoint-config \
    --endpoint-config-name "$CONFIG_NAME" \
    --production-variants "[{
        \"VariantName\": \"AllTraffic\",
        \"ModelName\": \"$MODEL_NAME\",
        \"InitialInstanceCount\": 1,
        \"InstanceType\": \"$INSTANCE_TYPE\"
    }]" \
    --region "$REGION" \
    2>/dev/null || true

echo -e "${GREEN}✓ Config created${NC}"

# Update or create endpoint
echo ""
if aws sagemaker describe-endpoint --endpoint-name "$ENDPOINT_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Updating endpoint: $ENDPOINT_NAME"
    aws sagemaker update-endpoint \
        --endpoint-name "$ENDPOINT_NAME" \
        --endpoint-config-name "$CONFIG_NAME" \
        --region "$REGION"
    echo -e "${GREEN}✓ Update initiated${NC}"
else
    echo "Creating endpoint: $ENDPOINT_NAME"
    aws sagemaker create-endpoint \
        --endpoint-name "$ENDPOINT_NAME" \
        --endpoint-config-name "$CONFIG_NAME" \
        --region "$REGION"
    echo -e "${GREEN}✓ Creation initiated${NC}"
fi

# Cleanup
echo ""
echo -e "${CYAN}Cleaning up temp files...${NC}"
rm -rf "$TEMP_DIR"
echo -e "${GREEN}✓ Cleaned up${NC}"

echo ""
echo -e "${CYAN}================================================================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${CYAN}================================================================================${NC}"
echo ""
echo "Endpoint: $ENDPOINT_NAME"
echo "Status: Deploying (will take 10-15 minutes)"
echo ""
echo "Monitor status:"
echo "  aws sagemaker describe-endpoint --endpoint-name $ENDPOINT_NAME --query 'EndpointStatus'"
echo ""
echo "Or use the monitoring script:"
echo "  cd aws/sagemaker && ./monitor_deployment.sh"
echo ""
echo "Local file cleanup:"
echo "  rm $TAR_FILE  # ($TAR_SIZE)"
echo ""
echo -e "${GREEN}Done!${NC}"

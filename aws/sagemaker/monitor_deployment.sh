#!/bin/bash
# Monitor SageMaker endpoint deployment

ENDPOINT_NAME="photogenius-generation-dev"
REGION="us-east-1"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}Monitoring Endpoint Deployment${NC}"
echo -e "${CYAN}==========================================${NC}"
echo "Endpoint: $ENDPOINT_NAME"
echo "Started: $(date '+%H:%M:%S')"
echo -e "${CYAN}==========================================${NC}"
echo ""

START_TIME=$(date +%s)

while true; do
    STATUS=$(aws sagemaker describe-endpoint \
        --endpoint-name "$ENDPOINT_NAME" \
        --region "$REGION" \
        --query 'EndpointStatus' \
        --output text 2>/dev/null)

    ELAPSED=$(( ($(date +%s) - START_TIME) / 60 ))
    TIMESTAMP=$(date '+%H:%M:%S')

    if [ "$STATUS" = "InService" ]; then
        echo -e "${TIMESTAMP} Status: ${GREEN}${STATUS}${NC} (${ELAPSED}m elapsed) - ${GREEN}READY!${NC}"
        echo ""
        echo -e "${CYAN}==========================================${NC}"
        echo -e "${GREEN}Deployment Complete!${NC}"
        echo -e "${CYAN}==========================================${NC}"
        echo "Total time: ${ELAPSED} minutes"
        echo ""
        echo "Next step: Test the endpoint"
        echo "  cd aws/sagemaker"
        echo "  python3 test_endpoint.py"
        echo ""
        exit 0
    elif [ "$STATUS" = "Failed" ]; then
        echo -e "${TIMESTAMP} Status: ${RED}${STATUS}${NC} - FAILED!"
        echo ""
        echo "Getting failure reason..."
        aws sagemaker describe-endpoint \
            --endpoint-name "$ENDPOINT_NAME" \
            --region "$REGION" \
            --query 'FailureReason'
        exit 1
    else
        echo -e "${TIMESTAMP} Status: ${YELLOW}${STATUS}${NC} (${ELAPSED}m elapsed) - In progress..."
    fi

    sleep 15
done

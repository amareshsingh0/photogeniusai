#!/bin/bash

FUNCS=(
    "photogenius-orchestrator-dev"
    "photogenius-generation-dev"
    "photogenius-safety-dev"
    "photogenius-prompt-enhancer-dev"
)

echo "Fixing Lambda Function URL permissions..."
echo ""

for FUNC in "${FUNCS[@]}"; do
    echo "--- $FUNC ---"
    
    # Remove old permission if exists
    aws lambda remove-permission \
        --function-name "$FUNC" \
        --statement-id FunctionURLAllowPublicAccess \
        2>/dev/null || true
    
    # Add new permission
    aws lambda add-permission \
        --function-name "$FUNC" \
        --statement-id FunctionURLAllowPublicAccess \
        --action lambda:InvokeFunctionUrl \
        --principal "*" \
        --function-url-auth-type NONE \
        --output text >/dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "  Permission added successfully"
    else
        echo "  Permission already exists or failed"
    fi
    
    # Get the URL
    URL=$(aws lambda get-function-url-config \
        --function-name "$FUNC" \
        --query 'FunctionUrl' \
        --output text 2>/dev/null)
    
    echo "  URL: $URL"
    echo ""
done

echo "Waiting for IAM propagation (10 seconds)..."
sleep 10
echo "Ready!"

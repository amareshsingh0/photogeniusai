#!/bin/bash
# Create Lambda Function URLs

ENV="${1:-dev}"

echo "Creating Lambda Function URLs: $ENV"
echo ""

FUNCTIONS=(
    "photogenius-orchestrator-$ENV"
    "photogenius-generation-$ENV"
    "photogenius-safety-$ENV"
    "photogenius-prompt-enhancer-$ENV"
)

declare -A URLS

for FUNC in "${FUNCTIONS[@]}"; do
    echo "--- $FUNC ---"
    
    # Check if already exists
    if aws lambda get-function-url-config --function-name "$FUNC" &>/dev/null; then
        URL=$(aws lambda get-function-url-config --function-name "$FUNC" --query 'FunctionUrl' --output text)
        echo "  Already exists: $URL"
        URLS["$FUNC"]="$URL"
    else
        echo "  Creating Function URL..."
        
        # Create Function URL
        URL=$(aws lambda create-function-url-config \
            --function-name "$FUNC" \
            --auth-type NONE \
            --cors '{"AllowOrigins":["*"],"AllowMethods":["GET","POST","PUT","DELETE","OPTIONS"],"AllowHeaders":["*"],"ExposeHeaders":["*"],"MaxAge":86400,"AllowCredentials":false}' \
            --query 'FunctionUrl' \
            --output text 2>&1)
        
        if [ $? -eq 0 ]; then
            echo "  SUCCESS: $URL"
            URLS["$FUNC"]="$URL"
            
            # Add public permission
            aws lambda add-permission \
                --function-name "$FUNC" \
                --statement-id FunctionURLAllowPublicAccess \
                --action lambda:InvokeFunctionUrl \
                --principal "*" \
                --function-url-auth-type NONE &>/dev/null
            
            echo "  Permission added"
        else
            echo "  FAILED: $URL"
        fi
    fi
    
    echo ""
done

# Save URLs
echo "================================"
echo "FUNCTION URLS:"
echo "================================"

for FUNC in "${!URLS[@]}"; do
    echo "$FUNC"
    echo "  ${URLS[$FUNC]}"
    echo ""
done

# Create env file for Next.js
cat > lambda_urls.env << END
# Lambda Function URLs - Generated $(date)
NEXT_PUBLIC_API_ORCHESTRATOR_URL=${URLS["photogenius-orchestrator-$ENV"]}
NEXT_PUBLIC_API_GENERATION_URL=${URLS["photogenius-generation-$ENV"]}
NEXT_PUBLIC_API_SAFETY_URL=${URLS["photogenius-safety-$ENV"]}
NEXT_PUBLIC_API_PROMPT_ENHANCER_URL=${URLS["photogenius-prompt-enhancer-$ENV"]}
END

echo "URLs saved to: lambda_urls.env"
cat lambda_urls.env

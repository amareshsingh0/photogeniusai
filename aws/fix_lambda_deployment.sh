#!/bin/bash
# PhotoGenius AI - Fix Lambda Code Deployment (Linux/Mac)
# This script directly updates Lambda function code (bypassing SAM issues)

set -e

# Configuration
ENVIRONMENT="${1:-dev}"
DRY_RUN="${2:-false}"

echo "🚀 PhotoGenius Lambda Code Update Script"
echo "Environment: $ENVIRONMENT"
echo "Dry Run: $DRY_RUN"
echo ""

# Lambda functions configuration
declare -A FUNCTIONS=(
    ["photogenius-orchestrator-$ENVIRONMENT"]="lambda/orchestrator"
    ["photogenius-orchestrator-v2-$ENVIRONMENT"]="lambda/orchestrator_v2"
    ["photogenius-prompt-enhancer-$ENVIRONMENT"]="lambda/prompt_enhancer"
    ["photogenius-generation-$ENVIRONMENT"]="lambda/generation"
    ["photogenius-post-processor-$ENVIRONMENT"]="lambda/post_processor"
    ["photogenius-safety-$ENVIRONMENT"]="lambda/safety"
    ["photogenius-training-$ENVIRONMENT"]="lambda/training"
    ["photogenius-refinement-$ENVIRONMENT"]="lambda/refinement"
)

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Install it first:"
    echo "   https://aws.amazon.com/cli/"
    exit 1
fi

echo "✅ AWS CLI installed: $(aws --version)"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured"
    echo "   Run: aws configure"
    exit 1
fi

IDENTITY=$(aws sts get-caller-identity --output json)
ACCOUNT=$(echo $IDENTITY | jq -r '.Account')
USER=$(echo $IDENTITY | jq -r '.Arn')

echo "✅ AWS Credentials valid"
echo "   Account: $ACCOUNT"
echo "   User: $USER"
echo ""

# Create temp directory
TEMP_DIR="./temp_lambda_packages"
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

echo "📦 Packaging and updating Lambda functions..."
echo ""

SUCCESS_COUNT=0
FAIL_COUNT=0

for FUNCTION_NAME in "${!FUNCTIONS[@]}"; do
    CODE_DIR="${FUNCTIONS[$FUNCTION_NAME]}"
    ZIP_PATH="$TEMP_DIR/${FUNCTION_NAME}.zip"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📦 Processing: $FUNCTION_NAME"

    # Check if code directory exists
    if [ ! -d "$CODE_DIR" ]; then
        echo "   ⚠️  Code directory not found: $CODE_DIR"
        ((FAIL_COUNT++))
        continue
    fi

    # Check if Lambda function exists
    if ! aws lambda get-function --function-name "$FUNCTION_NAME" &> /dev/null; then
        echo "   ⚠️  Function does not exist: $FUNCTION_NAME"
        ((FAIL_COUNT++))
        continue
    fi

    echo "   📁 Code directory: $CODE_DIR"

    # Package Lambda function
    echo "   📦 Creating deployment package..."

    pushd "$CODE_DIR" > /dev/null

    # Create zip with all files
    zip -r -q "$ZIP_PATH" . -x "*.pyc" -x "__pycache__/*" -x "*.git/*"

    if [ $? -eq 0 ]; then
        ZIP_SIZE=$(du -h "$ZIP_PATH" | cut -f1)
        echo "   ✅ Package created: $ZIP_SIZE"
    else
        echo "   ❌ Failed to create package"
        popd > /dev/null
        ((FAIL_COUNT++))
        continue
    fi

    popd > /dev/null

    # Update Lambda function code
    if [ "$DRY_RUN" != "true" ]; then
        echo "   🚀 Updating Lambda function code..."

        UPDATE_RESULT=$(aws lambda update-function-code \
            --function-name "$FUNCTION_NAME" \
            --zip-file "fileb://$ZIP_PATH" \
            --output json 2>&1)

        if [ $? -eq 0 ]; then
            VERSION=$(echo $UPDATE_RESULT | jq -r '.Version')
            CODE_SIZE=$(echo $UPDATE_RESULT | jq -r '.CodeSize')
            LAST_MODIFIED=$(echo $UPDATE_RESULT | jq -r '.LastModified')

            echo "   ✅ Code updated successfully!"
            echo "      Version: $VERSION"
            echo "      Code Size: $CODE_SIZE bytes"
            echo "      Last Modified: $LAST_MODIFIED"

            ((SUCCESS_COUNT++))
        else
            echo "   ❌ Update failed: $UPDATE_RESULT"
            ((FAIL_COUNT++))
        fi
    else
        echo "   ⏭️  DRY RUN: Would update $FUNCTION_NAME"
    fi

    echo ""
done

# Cleanup
echo "🧹 Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 DEPLOYMENT SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$DRY_RUN" != "true" ]; then
    echo "✅ Success: $SUCCESS_COUNT"
    echo "❌ Failed: $FAIL_COUNT"
    echo "📦 Total: ${#FUNCTIONS[@]}"
else
    echo "⏭️  DRY RUN - No changes made"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $SUCCESS_COUNT -gt 0 ] && [ "$DRY_RUN" != "true" ]; then
    echo ""
    echo "✨ Lambda functions updated successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Test the orchestrator endpoint:"
    echo "   aws lambda invoke --function-name photogenius-orchestrator-$ENVIRONMENT --payload file://test_payload.json response.json"
    echo ""
    echo "2. Check CloudWatch Logs:"
    echo "   aws logs tail /aws/lambda/photogenius-orchestrator-$ENVIRONMENT --follow"
    echo ""
    echo "3. View API Gateway endpoints:"
    echo "   aws cloudformation describe-stacks --stack-name photogenius-stack --query 'Stacks[0].Outputs'"
elif [ "$DRY_RUN" == "true" ]; then
    echo ""
    echo "💡 Run without 'true' second argument to actually update the functions"
else
    echo ""
    echo "⚠️  Some updates failed. Check the errors above."
    exit 1
fi

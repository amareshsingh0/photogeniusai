# Lambda Code Deployment Fix

## Problem

SAM deployment (`sam deploy`) only updates environment variables, not the actual Lambda function code. This causes old Lambda code to call non-existent endpoints.

## Solution

Use direct Lambda code updates via AWS CLI instead of SAM.

---

## Quick Fix (Choose Your OS)

### Windows (PowerShell)

```powershell
cd aws
.\fix_lambda_deployment.ps1 -Environment dev
```

**Dry run first (recommended):**
```powershell
.\fix_lambda_deployment.ps1 -Environment dev -DryRun
```

### Linux/Mac (Bash)

```bash
cd aws
chmod +x fix_lambda_deployment.sh
./fix_lambda_deployment.sh dev
```

**Dry run first (recommended):**
```bash
./fix_lambda_deployment.sh dev true
```

---

## What This Does

The script will:

1. ✅ **Package** each Lambda function (creates .zip files)
2. ✅ **Validate** AWS credentials and function existence
3. ✅ **Update** Lambda code directly using `aws lambda update-function-code`
4. ✅ **Verify** successful deployment (shows version, size, timestamp)
5. ✅ **Clean up** temporary files

### Functions Updated

- `photogenius-orchestrator-dev` - Main quality tier router
- `photogenius-orchestrator-v2-dev` - Smart routing orchestrator
- `photogenius-prompt-enhancer-dev` - Rule-based prompt enhancement
- `photogenius-generation-dev` - Direct SageMaker generation
- `photogenius-post-processor-dev` - Post-processing & upscaling
- `photogenius-safety-dev` - NSFW & safety checks
- `photogenius-training-dev` - LoRA training trigger
- `photogenius-refinement-dev` - Image refinement & editing

---

## Testing After Deployment

### 1. Test Orchestrator Function

```bash
# Create test payload
cat > test_payload.json << EOF
{
  "body": "{\"prompt\": \"a beautiful sunset over the ocean\", \"quality_tier\": \"STANDARD\", \"mode\": \"REALISM\", \"user_id\": \"test-user\"}"
}
EOF

# Invoke Lambda
aws lambda invoke \
  --function-name photogenius-orchestrator-dev \
  --payload file://test_payload.json \
  response.json

# Check response
cat response.json | jq .
```

### 2. Check CloudWatch Logs

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/photogenius-orchestrator-dev --follow

# Get recent logs
aws logs tail /aws/lambda/photogenius-orchestrator-dev --since 1h
```

### 3. View API Gateway Endpoints

```bash
# Get CloudFormation stack outputs
aws cloudformation describe-stacks \
  --stack-name photogenius-stack \
  --query 'Stacks[0].Outputs' \
  --output table

# Get API Gateway URL
aws cloudformation describe-stacks \
  --stack-name photogenius-stack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text
```

### 4. Test Full Generation Pipeline

```bash
# Get API endpoint
API_URL=$(aws cloudformation describe-stacks \
  --stack-name photogenius-stack \
  --query 'Stacks[0].Outputs[?OutputKey==`GenerationUrl`].OutputValue' \
  --output text)

# Test generation
curl -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "cinematic portrait of a warrior",
    "quality_tier": "STANDARD",
    "mode": "CINEMATIC"
  }' | jq .
```

---

## Alternative: Update Individual Function

If you only want to update one specific function:

```bash
# Package function
cd lambda/orchestrator
zip -r function.zip .

# Update Lambda
aws lambda update-function-code \
  --function-name photogenius-orchestrator-dev \
  --zip-file fileb://function.zip

# Cleanup
rm function.zip
cd ../..
```

---

## Troubleshooting

### Error: "Function does not exist"

**Problem**: Lambda function not deployed yet

**Solution**: Deploy with SAM first to create the functions
```bash
sam build
sam deploy --guided
```

Then run the fix script.

### Error: "Access Denied"

**Problem**: AWS credentials don't have Lambda permissions

**Solution**: Check IAM permissions. You need:
- `lambda:UpdateFunctionCode`
- `lambda:GetFunction`

### Error: "Invalid zip file"

**Problem**: Package creation failed

**Solution**:
1. Ensure all dependencies are in the Lambda directory
2. Check for permission issues
3. Try manual packaging:
   ```bash
   cd lambda/orchestrator
   zip -r ../../function.zip .
   ```

### Code Updates But Still Calling Old Endpoints

**Problem**: Cold start hasn't happened yet

**Solution**: Wait 1-2 minutes for Lambda cold start, or force it:
```bash
# Invoke function to force cold start
aws lambda invoke \
  --function-name photogenius-orchestrator-dev \
  --payload '{"body":"{}"}' \
  /dev/null
```

---

## Why SAM Deploy Doesn't Update Code

SAM has a known issue where:

1. **First deploy**: Creates function + uploads code ✅
2. **Subsequent deploys**: Only updates environment variables ❌
3. **Code changes**: Ignored unless stack is deleted first ❌

### SAM Deploy Issues

```bash
# This ONLY updates env vars, NOT code
sam deploy

# Code is cached in .aws-sam/build/
# SAM thinks nothing changed even when code is different
```

### The Fix We Use

Direct `aws lambda update-function-code` bypasses SAM's caching entirely:

```bash
# This ALWAYS updates code
aws lambda update-function-code \
  --function-name my-function \
  --zip-file fileb://function.zip
```

---

## Complete Clean Redeploy (Nuclear Option)

If nothing else works, delete and recreate everything:

```bash
# 1. Delete CloudFormation stack
aws cloudformation delete-stack --stack-name photogenius-stack

# 2. Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name photogenius-stack

# 3. Clean SAM cache
rm -rf .aws-sam/

# 4. Rebuild and deploy
sam build
sam deploy --guided

# 5. Update code with our script
./fix_lambda_deployment.sh dev
```

**⚠️ WARNING**: This will:
- Delete all Lambda functions
- Delete DynamoDB tables (data loss!)
- Delete S3 buckets (if empty)
- Require full reconfiguration

Only use as last resort!

---

## Automation (CI/CD)

Add this to your GitHub Actions or deployment pipeline:

```yaml
# .github/workflows/deploy-lambda.yml
name: Deploy Lambda Functions

on:
  push:
    branches: [main]
    paths:
      - 'aws/lambda/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Update Lambda functions
        run: |
          cd aws
          chmod +x fix_lambda_deployment.sh
          ./fix_lambda_deployment.sh prod
```

---

## Success Indicators

After running the script, you should see:

```
✅ Success: 8
❌ Failed: 0
📦 Total: 8

✨ Lambda functions updated successfully!
```

Check CloudWatch logs to verify the new code is running:

```bash
aws logs tail /aws/lambda/photogenius-orchestrator-dev --follow
```

Look for initialization messages from the new code (e.g., "Service Registry Initialized").

---

## Next Steps After Fix

Once Lambda code is updated:

1. ✅ **Test generation** - Verify end-to-end image generation works
2. ✅ **Check SageMaker connectivity** - Ensure Lambda can invoke endpoints
3. ✅ **Monitor CloudWatch** - Watch for errors in first few generations
4. ✅ **Deploy two-pass generation** - Follow WORLD_CLASS_WEBSITE_GUIDE.md Week 1
5. ✅ **Fix API Gateway** - Create Function URLs or recreate API Gateway

---

## Support

If you encounter issues:

1. **Check CloudWatch Logs**:
   ```bash
   aws logs tail /aws/lambda/photogenius-orchestrator-dev --follow
   ```

2. **Verify function versions**:
   ```bash
   aws lambda get-function --function-name photogenius-orchestrator-dev | jq -r '.Configuration.LastModified'
   ```

3. **Test manually**:
   ```bash
   aws lambda invoke --function-name photogenius-orchestrator-dev --payload file://test_payload.json response.json
   cat response.json
   ```

4. **Open GitHub issue** with logs and error messages

---

**Created**: Feb 5, 2026
**Status**: Ready to use
**Tested**: Windows PowerShell + Linux Bash

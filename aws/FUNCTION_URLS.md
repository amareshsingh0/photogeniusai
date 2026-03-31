# Lambda Function URLs

**Generated**: February 5, 2026
**Environment**: dev
**Status**: ✅ URLs Created, Permissions Configured

---

## 📡 Function URLs

| Function | URL | Methods |
|----------|-----|---------|
| **Orchestrator** | https://3gp3xsvqkesxjtf56vdmuxx53a0xaeew.lambda-url.us-east-1.on.aws/ | POST, GET, PUT, DELETE |
| **Generation** | https://iq3w5ugxkejdthvjvxavdo7t6a0xhdrs.lambda-url.us-east-1.on.aws/ | POST, GET |
| **Safety** | https://53z6qgev6wahml3au2nfeobi6u0zjbrn.lambda-url.us-east-1.on.aws/ | POST |
| **Prompt Enhancer** | https://wvn2umatf4pdflcxj7dkyor7p40prgxv.lambda-url.us-east-1.on.aws/ | POST |

---

## 🔧 Frontend Configuration

### Update `apps/web/.env.local`

Add these environment variables:

```bash
# Lambda Function URLs
NEXT_PUBLIC_API_ORCHESTRATOR_URL=https://3gp3xsvqkesxjtf56vdmuxx53a0xaeew.lambda-url.us-east-1.on.aws/
NEXT_PUBLIC_API_GENERATION_URL=https://iq3w5ugxkejdthvjvxavdo7t6a0xhdrs.lambda-url.us-east-1.on.aws/
NEXT_PUBLIC_API_SAFETY_URL=https://53z6qgev6wahml3au2nfeobi6u0zjbrn.lambda-url.us-east-1.on.aws/
NEXT_PUBLIC_API_PROMPT_ENHANCER_URL=https://wvn2umatf4pdflcxj7dkyor7p40prgxv.lambda-url.us-east-1.on.aws/

# Legacy compatibility (if needed)
NEXT_PUBLIC_API_URL=https://3gp3xsvqkesxjtf56vdmuxx53a0xaeew.lambda-url.us-east-1.on.aws/
```

---

## 🧪 Testing

### Test Prompt Enhancer

```bash
curl -X POST https://wvn2umatf4pdflcxj7dkyor7p40prgxv.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"body":"{\"prompt\":\"sunset over ocean\",\"mode\":\"REALISM\"}"}'
```

**Expected Response**:
```json
{
  "statusCode": 200,
  "body": {
    "original": "sunset over ocean",
    "enhanced": "sunset over ocean, stunning sunset with long shadows...",
    "style": "REALISM"
  }
}
```

### Test Orchestrator (Generation)

```bash
curl -X POST https://3gp3xsvqkesxjtf56vdmuxx53a0xaeew.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"body":"{\"prompt\":\"mountain landscape\",\"quality_tier\":\"STANDARD\",\"mode\":\"CINEMATIC\"}"}'
```

### PowerShell Testing

```powershell
$url = "https://wvn2umatf4pdflcxj7dkyor7p40prgxv.lambda-url.us-east-1.on.aws/"
$body = @{body='{"prompt":"sunset","mode":"REALISM"}'} | ConvertTo-Json
Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
```

---

## 🔒 Security Configuration

### CORS Settings

All Function URLs have CORS configured:

```json
{
  "AllowOrigins": ["*"],
  "AllowMethods": ["POST", "GET", "PUT", "DELETE"],
  "AllowHeaders": ["*"],
  "ExposeHeaders": ["*"],
  "MaxAge": 86400
}
```

### Authentication

- **Auth Type**: NONE (public access)
- **IAM Permissions**: Configured for public invoke
- **Resource Policy**: Allows `lambda:InvokeFunctionUrl` from `*` principal

---

## 🚀 Usage in Frontend

### React/Next.js Example

```typescript
// apps/web/lib/api.ts

const API_URLS = {
  orchestrator: process.env.NEXT_PUBLIC_API_ORCHESTRATOR_URL!,
  generation: process.env.NEXT_PUBLIC_API_GENERATION_URL!,
  safety: process.env.NEXT_PUBLIC_API_SAFETY_URL!,
  promptEnhancer: process.env.NEXT_PUBLIC_API_PROMPT_ENHANCER_URL!,
}

// Generate image
export async function generateImage(prompt: string, quality: string, mode: string) {
  const response = await fetch(API_URLS.orchestrator, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      body: JSON.stringify({
        prompt,
        quality_tier: quality,
        mode,
        user_id: 'user-123'
      })
    })
  })

  if (!response.ok) {
    throw new Error(`Generation failed: ${response.statusText}`)
  }

  return response.json()
}

// Enhance prompt
export async function enhancePrompt(prompt: string, mode: string = 'REALISM') {
  const response = await fetch(API_URLS.promptEnhancer, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      body: JSON.stringify({ prompt, mode })
    })
  })

  if (!response.ok) {
    throw new Error(`Prompt enhancement failed: ${response.statusText}`)
  }

  const data = await response.json()
  return JSON.parse(data.body)
}
```

### Usage Component

```typescript
// apps/web/components/GenerateButton.tsx

import { generateImage } from '@/lib/api'

export function GenerateButton() {
  const [loading, setLoading] = useState(false)

  const handleGenerate = async () => {
    setLoading(true)
    try {
      const result = await generateImage(
        'cinematic portrait of a warrior',
        'STANDARD',
        'CINEMATIC'
      )
      console.log('Generated:', result)
    } catch (error) {
      console.error('Generation failed:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button onClick={handleGenerate} disabled={loading}>
      {loading ? 'Generating...' : 'Generate Image'}
    </button>
  )
}
```

---

## 📊 Request/Response Format

### Orchestrator Endpoint

**Request**:
```json
{
  "body": "{\"prompt\":\"your prompt here\",\"quality_tier\":\"STANDARD\",\"mode\":\"REALISM\",\"user_id\":\"user-123\"}"
}
```

**Response**:
```json
{
  "statusCode": 200,
  "body": {
    "images": {
      "preview": null,
      "final": "base64-encoded-image-string"
    },
    "metadata": {
      "quality_tier": "STANDARD",
      "generation_time": 15.2,
      "total_time": 15.2,
      "original_prompt": "your prompt here",
      "enhanced_prompt": "enhanced version...",
      "mode": "REALISM",
      "generation_id": "uuid"
    }
  }
}
```

### Prompt Enhancer Endpoint

**Request**:
```json
{
  "body": "{\"prompt\":\"sunset\",\"mode\":\"REALISM\"}"
}
```

**Response**:
```json
{
  "statusCode": 200,
  "body": {
    "original": "sunset",
    "enhanced": "sunset, stunning sunset with long shadows and rim lighting...",
    "style": "REALISM"
  }
}
```

---

## ⚠️ Troubleshooting

### 403 Forbidden Error

If you get "Forbidden" errors:

1. **Wait for IAM propagation** (up to 60 seconds)
2. **Check resource policy**:
   ```bash
   aws lambda get-policy --function-name photogenius-prompt-enhancer-dev
   ```
3. **Verify Function URL auth type**:
   ```bash
   aws lambda get-function-url-config --function-name photogenius-prompt-enhancer-dev
   ```
4. **Re-add permissions**:
   ```bash
   ./aws/fix_permissions.sh
   ```

### CORS Errors

If browser shows CORS errors:

1. Function URLs have CORS pre-configured
2. Ensure you're not using `OPTIONS` method (not supported by Lambda URLs)
3. Check browser console for specific CORS error
4. Verify AllowOrigins includes your domain

### Timeout Errors

If Lambda times out:

1. Check CloudWatch Logs:
   ```bash
   aws logs tail /aws/lambda/photogenius-orchestrator-dev --follow
   ```
2. Increase Lambda timeout (current: 600s for orchestrator)
3. Check SageMaker endpoint status

---

## 🔄 Migration from API Gateway

### Old URLs (Broken)
```
https://{api-id}.execute-api.us-east-1.amazonaws.com/Prod/generate
https://{api-id}.execute-api.us-east-1.amazonaws.com/Prod/safety
```

### New URLs (Working)
```
https://3gp3xsvqkesxjtf56vdmuxx53a0xaeew.lambda-url.us-east-1.on.aws/
https://53z6qgev6wahml3au2nfeobi6u0zjbrn.lambda-url.us-east-1.on.aws/
```

### Migration Steps

1. Update `.env.local` with new URLs
2. Replace API calls in frontend code
3. Test locally first
4. Deploy to production
5. Monitor CloudWatch for errors

---

## 📈 Monitoring

### CloudWatch Logs

```bash
# Orchestrator
aws logs tail /aws/lambda/photogenius-orchestrator-dev --follow

# Prompt Enhancer
aws logs tail /aws/lambda/photogenius-prompt-enhancer-dev --follow

# Generation
aws logs tail /aws/lambda/photogenius-generation-dev --follow
```

### Metrics to Track

- **Invocations**: How many requests per minute
- **Duration**: Average execution time
- **Errors**: 4xx/5xx response codes
- **Throttles**: Rate limiting hits

---

## 🎯 Next Steps

1. ✅ Function URLs created
2. ✅ Permissions configured
3. ⏭️ Update frontend `.env.local`
4. ⏭️ Test end-to-end generation
5. ⏭️ Deploy to production

---

**Status**: ✅ **Issue #2 RESOLVED - API Gateway replaced with Lambda Function URLs!**

**Created**: February 5, 2026
**Last Updated**: February 5, 2026

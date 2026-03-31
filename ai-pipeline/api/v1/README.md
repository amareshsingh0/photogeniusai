# PhotoGenius API v1 - Enterprise Developer Platform

**REST API for programmatic access to PhotoGenius AI services.**

This unlocks **ENTERPRISE revenue** - B2B customers pay 10x more than consumers.

## Features

- ✅ **API Key Authentication** - Secure access with API keys
- ✅ **Rate Limiting** - 100 req/hour (free), 1000 req/hour (pro), unlimited (enterprise)
- ✅ **Webhook Support** - Async job completion notifications
- ✅ **Job Status Tracking** - Real-time progress monitoring
- ✅ **Full Feature Access** - Generation, refinement, training, styles

## Quick Start

### Deploy API

```bash
cd ai-pipeline/api/v1
modal deploy main.py
```

### Get API Key

API keys are created through the admin dashboard or programmatically:

```python
from ai_pipeline.api.v1.auth import create_api_key

# Create API key for user
api_key = create_api_key(
    user_id="user_123",
    tier="pro",  # free, pro, enterprise
    name="My Company"
)

print(f"API Key: {api_key}")
# Save this securely - it won't be shown again!
```

### Make Your First Request

```bash
curl -X POST https://YOUR_USERNAME--photogenius-api-v1--api.modal.run/api/v1/generate \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "professional headshot",
    "mode": "REALISM",
    "quality_tier": "balanced",
    "num_images": 2
  }'
```

## API Endpoints

### POST `/api/v1/generate`

Generate images asynchronously.

**Request:**
```json
{
  "prompt": "beach sunset",
  "mode": "REALISM",
  "identity_id": "optional",
  "quality_tier": "balanced",
  "num_images": 2,
  "webhook_url": "https://your-app.com/webhook",
  "seed": 42
}
```

**Response:**
```json
{
  "job_id": "generation_abc123",
  "status": "pending",
  "estimated_time": 50,
  "status_url": "/api/v1/status/generation_abc123"
}
```

### POST `/api/v1/refine`

Refine an existing image.

**Request:**
```json
{
  "image_base64": "...",
  "refinement_request": "make it brighter",
  "generation_history": [
    {"prompt": "original prompt"}
  ],
  "mode": "REALISM",
  "webhook_url": "https://your-app.com/webhook"
}
```

### POST `/api/v1/train-identity`

Train a new identity (minimum 5 images).

**Request:**
```json
{
  "images": ["base64_img1", "base64_img2", ...],
  "identity_name": "John Doe",
  "webhook_url": "https://your-app.com/webhook"
}
```

### GET `/api/v1/status/{job_id}`

Check job status and get results.

**Response:**
```json
{
  "job_id": "generation_abc123",
  "status": "completed",
  "progress": 100,
  "results": [
    {
      "image_url": "https://cdn.photogenius.com/...",
      "rank": 1,
      "similarity": 0.98,
      "score": 92.5
    }
  ],
  "created_at": "2026-01-28T10:00:00Z",
  "completed_at": "2026-01-28T10:00:50Z"
}
```

### GET `/api/v1/styles`

List available styles.

**Response:**
```json
{
  "styles": [
    {
      "id": "cinematic_lighting",
      "name": "Cinematic Lighting",
      "description": "Film-style dramatic lighting",
      "preview_url": "..."
    }
  ]
}
```

## Authentication

All endpoints require API key authentication via Bearer token:

```
Authorization: Bearer YOUR_API_KEY
```

## Rate Limits

| Tier | Requests/Hour | Features |
|------|---------------|----------|
| **Free** | 100 | Standard quality only, no webhooks |
| **Pro** ($49/month) | 1,000 | All quality tiers, webhooks, priority queue |
| **Enterprise** (Custom) | Unlimited | Dedicated resources, SLA, white-label |

Rate limit exceeded returns `429 Too Many Requests`.

## Webhooks

Webhooks are called when jobs complete or fail.

**Generation Webhook:**
```json
{
  "job_id": "generation_abc123",
  "status": "completed",
  "results": [
    {
      "image_url": "https://cdn.photogenius.com/...",
      "rank": 1
    }
  ],
  "timestamp": "2026-01-28T10:00:50Z"
}
```

**Training Webhook:**
```json
{
  "training_job_id": "training_xyz789",
  "status": "completed",
  "identity_id": "identity_abc123",
  "timestamp": "2026-01-28T10:10:00Z"
}
```

## Quality Tiers

| Tier | Time | Use Case |
|------|------|----------|
| `standard` | ~30s | Quick previews |
| `balanced` | ~50s | General use (default) |
| `premium` | ~80s | High quality |
| `ultra` | ~120s | Maximum quality |

## Error Handling

All errors follow this format:

```json
{
  "error": "Error message",
  "detail": "Detailed information",
  "code": "ERROR_CODE"
}
```

Common status codes:
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid API key)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

## SDK Examples

### Python

```python
import requests

API_KEY = "your_api_key"
BASE_URL = "https://YOUR_USERNAME--photogenius-api-v1--api.modal.run"

headers = {"Authorization": f"Bearer {API_KEY}"}

# Generate
response = requests.post(
    f"{BASE_URL}/api/v1/generate",
    json={
        "prompt": "professional headshot",
        "mode": "REALISM",
        "quality_tier": "balanced"
    },
    headers=headers
)
job = response.json()

# Check status
status_response = requests.get(
    f"{BASE_URL}{job['status_url']}",
    headers=headers
)
status = status_response.json()

# Get results when completed
if status["status"] == "completed":
    for result in status["results"]:
        print(f"Image: {result['image_url']}")
```

### JavaScript/TypeScript

```typescript
const API_KEY = "your_api_key"
const BASE_URL = "https://YOUR_USERNAME--photogenius-api-v1--api.modal.run"

// Generate
const generateResponse = await fetch(`${BASE_URL}/api/v1/generate`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    prompt: "professional headshot",
    mode: "REALISM",
    quality_tier: "balanced",
  }),
})

const job = await generateResponse.json()

// Poll for completion
const checkStatus = async () => {
  const statusResponse = await fetch(
    `${BASE_URL}${job.status_url}`,
    { headers: { Authorization: `Bearer ${API_KEY}` } }
  )
  return await statusResponse.json()
}

// Poll every 5 seconds
const status = await pollUntilComplete(checkStatus, 5000)
```

## Pricing

### Free Tier
- 100 requests/hour
- Standard quality only
- No webhook support
- Community support

### Pro ($49/month)
- 1,000 requests/hour
- All quality tiers
- Webhook support
- Priority queue
- Email support

### Enterprise (Custom)
- Unlimited requests
- Dedicated GPU resources
- SLA guarantees (99.9% uptime)
- White-label option
- Dedicated support
- Custom integrations

## Documentation

Interactive API documentation available at:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Support

- Email: api@photogenius.ai
- Documentation: https://docs.photogenius.ai
- Status: https://status.photogenius.ai

## Security

- API keys are hashed (SHA-256) before storage
- Rate limiting prevents abuse
- HTTPS required for all requests
- Webhook URLs should use HTTPS
- API keys should be kept secret

## Best Practices

1. **Store API keys securely** - Never commit to git
2. **Use webhooks** - More efficient than polling
3. **Handle errors gracefully** - Check status codes
4. **Respect rate limits** - Implement exponential backoff
5. **Use appropriate quality tiers** - Balance speed vs quality
6. **Cache results** - Store image URLs, not regenerate

## Migration from v0

If you're using the internal API, migration is straightforward:

```python
# Old (internal)
result = orchestrator.orchestrate.remote(...)

# New (API v1)
response = requests.post("/api/v1/generate", ...)
job = response.json()
status = poll_status(job["status_url"])
```

## Roadmap

- [ ] GraphQL API
- [ ] Batch operations
- [ ] Image upload endpoints
- [ ] Custom model training
- [ ] Analytics dashboard
- [ ] Usage reports

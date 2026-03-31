# Smart Cache – Caching & CDN Optimization (Enhancement 8.2)

Intelligent caching for repeated generation requests. Reduces compute and latency.

## Strategy

| Level | Description | Storage |
|-------|-------------|---------|
| **1. Exact match** | Same `prompt` + `mode` + `identity_id` | Redis |
| **2. Semantic similarity** | Same identity, prompt similarity > 0.95 | Redis + SentenceTransformer |
| **3. Style/composition** | Future | — |

- **Storage**: Redis (metadata + payload). Optional S3/Volume for blobs later.
- **TTL**: **Tier-aware.** FAST/STANDARD → 1 hour; BALANCED/PREMIUM/ULTRA → 7 days. Cache key includes `quality_tier` so fast previews and full-quality results are stored separately.
- **Invalidation**: On model update → call `invalidate_cache()`.

## Expected Savings

- **Cache hit rate**: 15–25% of requests
- **Cost saved**: ~$0.015 per cached image
- **Latency**: <100 ms for cached results

## Setup

### 1. Redis

Use Upstash, ElastiCache, or any Redis reachable from Modal.

**Modal secret** `photogenius-redis`:

```bash
# Option A: REDIS_URL (recommended for Upstash)
modal secret create photogenius-redis REDIS_URL="rediss://:TOKEN@HOST:6379"

# Option B: REDIS_HOST + REDIS_PASSWORD
modal secret create photogenius-redis REDIS_HOST="..." REDIS_PASSWORD="..." REDIS_PORT="6379"
```

### 2. Deploy

```bash
modal deploy ai-pipeline/caching/smart_cache.py
modal deploy ai-pipeline/services/orchestrator.py
```

## Usage

### From Python (Orchestrator)

```python
import modal

OrchestratorCls = modal.Cls.from_name("photogenius-orchestrator", "Orchestrator")
orch = OrchestratorCls()

result = orch.orchestrate_with_cache.remote(
    user_prompt="beach sunset",
    mode="REALISM",
    identity_id="user_123",
)
# result["cached"] == True (exact/semantic) or False (miss)
# result["cache_type"] in ("exact", "semantic") when cached
```

### Web endpoint (orchestrate with cache)

The orchestrator exposes `orchestrate_with_cache_web` (separate from `orchestrate_web`):

```bash
curl -X POST "https://USER--photogenius-orchestrator--orchestrate-with-cache-web.modal.run" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "beach sunset", "mode": "REALISM", "identity_id": "user_123"}'
```

### Cache only (SmartCache)

```python
import modal

CacheCls = modal.Cls.from_name("photogenius-smart-cache", "SmartCache")
cache = CacheCls()

# Check
hit = cache.check_cache.remote("beach", "REALISM", "id_1")

# Store (usually done by orchestrator)
cache.store_result.remote(
    prompt="beach",
    mode="REALISM",
    identity_id="id_1",
    images=[...],
    parsed_prompt={...},
    execution_plan={...},
)

# Invalidate on model update
deleted = cache.invalidate_cache.remote()
```

## Response shapes

**Exact hit**

```json
{
  "images": [...],
  "parsed_prompt": {...},
  "execution_plan": {...},
  "rerank_used": false,
  "cached": true,
  "cache_type": "exact"
}
```

**Semantic hit**

```json
{
  "suggestion": {
    "message": "Similar to: '...'",
    "images": [...],
    "similarity": 0.97
  },
  "generate_anyway": true,
  "cached": true,
  "cache_type": "semantic"
}
```

**Cache miss**

Same as `orchestrate` response, plus `"cached": false`.

## Files

- `ai-pipeline/caching/smart_cache.py` – SmartCache implementation
- `ai-pipeline/caching/__init__.py` – Module exports
- `ai-pipeline/services/orchestrator.py` – `orchestrate_with_cache` + web endpoint

## Notes

- If Redis or SentenceTransformer is unavailable, caching is skipped; orchestration still runs.
- Semantic search runs only when `identity_id` is set.
- Exact-match payload is stored in Redis (images as base64 in JSON). For very large payloads, consider moving blobs to S3/Volume later.

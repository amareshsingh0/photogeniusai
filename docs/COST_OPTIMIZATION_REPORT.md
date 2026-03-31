# Cost Profiling & Smart Routing – Optimization Report

## Summary

This document describes the cost profiling, smart routing, and caching implementations added to achieve **~30% cost reduction** and **>15% cache hit rate** without degrading user satisfaction.

---

## 1. Cost Measurement (Task 1)

### Implemented

- **Cost tracking per generation**
  - **SageMaker**: USD per second by instance type (ml.g5.xlarge ~$1.10/hr, ml.g5.2xlarge ~$1.52/hr).
  - **Lambda**: Fixed ~$0.00002 per invocation (approximate).
  - **S3**: ~$0.023/GB; total bytes from uploaded images.
  - **Total** = SageMaker + Lambda + S3, rounded to 6 decimals.

- **Storage**
  - **Schema**: `generations.costUsd`, `generations.qualityTierUsed`, `generations.cacheHit` (see `packages/database/prisma/schema.prisma`).
  - **Lambda** returns `cost_usd`, `cost_breakdown`, `quality_tier_used`, `inference_seconds`; API and client can pass these into `POST /api/generations` so every saved generation has cost and tier.

- **Cost dashboard**
  - **Config**: `aws/monitoring/cost-dashboard.json`.
  - Widgets: average cost per generation, cost by tier (FAST/STANDARD/PREMIUM/PERFECT), cache hit rate, generations vs cache hits, cost trend.
  - Metrics namespace: `PhotoGenius`. Metrics must be emitted by your app (e.g. from `generations.cost_usd` aggregates or from Lambda/API using PutMetricData). See dashboard text widget for how to populate.

### Usage

- **Lambda**: Computes cost after each generation and returns it in the response body.
- **Next.js**: `apps/web/lib/cost.ts` exposes `computeGenerationCost()` for server-side estimates when the backend does not return cost (e.g. FastAPI path).
- **Client**: When saving a generation after a Lambda two-pass call, send `costUsd`, `qualityTierUsed`, and `cacheHit` in `POST /api/generations` so the DB stays accurate.

---

## 2. Smart Routing (Task 2)

### Implemented

- **Prompt complexity classifier** (`apps/web/lib/prompt-complexity.ts`)
  - **Inputs**: prompt, word count, hasIdentity, hasMultiPerson, style complexity, user-selected tier.
  - **Rules** (decision-tree style):
    - Very short + simple + no identity/multi-person → **FAST**.
    - Identity or multi-person → **PREMIUM** or **STANDARD**.
    - Long prompt or complex style keywords → **STANDARD** or **PREMIUM**.
    - Default → **STANDARD**.
  - **Output**: `recommended_tier`, `reason`, `savings_fraction`, `confidence`.

- **Routing behavior**
  - **Effective tier**: If classifier confidence ≥ 0.78 and recommended tier ≤ user tier, the effective tier is the recommended one (saves cost); otherwise the user’s choice is used.
  - **Env**: `SMART_ROUTING_ENABLED` (default true). Set to `"false"` to disable and always use user tier.
  - **API**: `POST /api/generate` uses `getEffectiveTier()` and sends `quality_tier_to_use` to Lambda. Response can include `tier_recommendation` (recommended_tier, reason, savings_fraction) for the UI.

- **Tier recommendation API**
  - **GET /api/generate/recommend?prompt=...&hasIdentity=false&userTier=STANDARD**
  - Returns recommended tier, reason, savings_fraction, confidence for the “We recommend STANDARD for this prompt (save 50%)” UX.

### UI integration (suggested)

- Before or after the user selects a tier, call `GET /api/generate/recommend` and show:
  - “We recommend **STANDARD** for this prompt (save ~50%).” with an option to accept or override.
- When the user accepts, the same tier is used by `POST /api/generate`; when they override, their tier is used and smart routing only downgrades when the classifier is confident.

---

## 3. Caching Strategy (Task 3)

### Implemented

- **Semantic prompt cache**
  - **Key**: SHA-256 of `prompt|seed|tier|identity_id` (normalized).
  - **Storage**: DynamoDB table `photogenius-prompt-cache-{Environment}` (see `aws/template.yaml` → `PromptCacheTable`) with `cache_key` (partition key) and `ttl` (DynamoDB TTL).
  - **Value**: List of S3 URLs for the generated images. Images themselves remain in the existing S3 bucket; the cache only stores the URLs.
  - **TTL**: 30 days (configurable via `CACHE_TTL_DAYS` in Lambda).

- **Flow**
  1. Lambda receives a request → computes `cache_key` → reads from DynamoDB.
  2. **Cache hit**: Returns stored URLs, `cost_usd: 0`, `cache_hit: true`, no SageMaker call.
  3. **Cache miss**: Invokes SageMaker, uploads to S3, writes `cache_key` → URLs + TTL to DynamoDB.

- **Analytics**
  - Each generation record can set `cacheHit: true/false` in the DB. You can:
    - Measure cache hit rate = (count where cacheHit=true) / (total generations) over a time window.
    - Expose this in the cost dashboard (e.g. custom metric `PhotoGenius.CacheHitRate` and `PhotoGenius.CacheHits` / `PhotoGenius.GenerationsTotal`).

### Env / infra

- Lambda env: `PROMPT_CACHE_TABLE` (set in template to `!Ref PromptCacheTable`). If unset, caching is skipped.
- IAM: Lambda role has DynamoDB access to `PromptCacheTable` (see template).

---

## 4. Resource Optimization (Task 4)

### Documented / config reference

- **Endpoint auto-scaling**
  - Current (from `deploy/endpoint_config.yaml`): min 1, max 10 instances per tier.
  - **Scale to 0**: Use **SageMaker Async Inference** or **Serverless Inference** for non–real-time workloads so endpoints can scale to 0 when idle. Sync real-time generation can stay on real-time endpoints with min 1.
  - **Async**: Invoke with `InvokeEndpointAsync`; poll or use SNS for completion. Fits batch or “generate and notify” flows.

- **Batch inference (style LoRA)**
  - Prefer **SageMaker Batch Transform** for offline style LoRA / batch jobs instead of many single InvokeEndpoint calls (cheaper and easier to size).

- **Model compression**
  - Use **FP16** (or BF16) for model artifacts where supported to cut memory and often cost (smaller instance or higher throughput). Set in SageMaker model / container config (e.g. `dtype=float16`).

---

## 5. Success Metrics

| Metric | Target | How to measure |
|--------|--------|----------------|
| Cost reduction | ~30% within 30 days | Compare average `cost_usd` per generation (and per tier) before vs after smart routing + cache. |
| Cache hit rate | >15% | (Generations with `cacheHit=true`) / (total generations) over rolling window; or from Lambda logs. |
| User satisfaction | No degradation | Track ratings, thumbs, or support tickets; A/B if needed. |

---

## 6. Files Touched

| Area | Files |
|------|--------|
| Schema / DB | `packages/database/prisma/schema.prisma`, `packages/database/prisma/migrations/20250204100000_add_cost_tier_cache/migration.sql` |
| Cost | `apps/web/lib/cost.ts` |
| Complexity & routing | `apps/web/lib/prompt-complexity.ts`, `apps/web/app/api/generate/recommend/route.ts` |
| Generate API | `apps/web/app/api/generate/route.ts` (cost, tier, cache_hit, smart routing, tier recommendation in response) |
| Generations API | `apps/web/app/api/generations/route.ts` (accept costUsd, qualityTierUsed, cacheHit) |
| Lambda | `aws/lambda/generation/handler.py` (cost calculation, cache get/put, cost_usd/cache_hit in response) |
| Infra | `aws/template.yaml` (PromptCacheTable, Lambda env PROMPT_CACHE_TABLE, DynamoDB policy) |
| Dashboards | `aws/monitoring/cost-dashboard.json` |
| Docs | `docs/COST_OPTIMIZATION_REPORT.md` (this file) |

---

## 7. Next Steps (optional)

1. **Emit CloudWatch metrics** from API or a cron: aggregate `generations.cost_usd` and `cacheHit` by day/tier and call `PutMetricData` so the cost dashboard fills automatically.
2. **Admin/analytics API**: Endpoint that returns “average cost per tier”, “top 10 most expensive prompts” (by cost_usd), “cache hit rate last 7 days” from the DB.
3. **Async + scale-to-zero**: Add an async inference path and use Serverless Inference or Async endpoints for non–real-time workloads.
4. **FP16**: Confirm SageMaker model and container use FP16 and update docs.

# PhotoGenius AI – API

## Overview

- **Next.js API routes**: `/api/*` (auth, generations, identities, upload, webhooks).
- **FastAPI**: `apps/api` (or `apps/ai-service`) – generation, safety, training.
- **AWS API Gateway** (SAM): generation, refinement, safety, training (see below).

## Next.js routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/auth/session` | GET | Session status `{ userId }` |
| `/api/generations` | GET, POST | List / create generations |
| `/api/generations/[id]` | PATCH, DELETE | Update or delete generation |
| `/api/dashboard/stats` | GET | Dashboard stats |
| `/api/identities` | GET, POST | List / create identities |
| `/api/upload` | POST | Upload file to storage |
| `/api/webhooks/clerk` | POST | Clerk webhook |
| `/api/webhooks/stripe` | POST | Stripe webhook (credits, subscription, tier). See [STRIPE_WEBHOOK_SETUP.md](STRIPE_WEBHOOK_SETUP.md) |
| `/api/preferences` | GET, POST | RLHF: get preference count/stats; record pairwise preference (prompt, imageAUrl, imageBUrl, preferred, source) |
| `/api/preferences/thumbs` | POST | RLHF: record thumbs up/down on one image (body: generationId, imageUrl, thumbs) |

## FastAPI

- **Base**: `http://localhost:8000` (or 8001 if 8000 in use).
- **Health**: `GET /health` → `{ "status": "ok" }`.
- **v1**: `GET/POST /api/v1/*` (auth, identities, generation, gallery, admin).

## AWS Lambda (SAM) – Refinement

- **Endpoint**: `POST /refine` (API Gateway; base URL from stack output `RefinementUrl`).
- **Purpose**: Edit an existing image from a natural-language instruction (e.g. “make it brighter”, “black and white”). Uses PIL-based global adjustments and simple style fallbacks; no SageMaker required. Cold start &lt; 3s, execution &lt; 30s.

### Request body (JSON)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image_url` | string | one of image_url / image_base64 | S3 URL (`s3://bucket/key`) or S3 key in `S3_BUCKET` (e.g. `generations/abc.png`) |
| `image_base64` | string | one of image_url / image_base64 | Base64-encoded image bytes |
| `instruction` | string | yes | Modification instruction, e.g. “make it brighter”, “more contrast”, “black and white”, “vintage” |
| `strength` | number | no | 0.1–1.0, default 0.7; how strong the modification is |
| `seed` | any | no | Reserved for future img2img; currently ignored |

Backward compatibility: `refinement_request` is accepted as an alias for `instruction`.

### Response (200)

```json
{
  "refined_url": "https://<bucket>.s3.<region>.amazonaws.com/refined/<uuid>.png",
  "modification_applied": "global: brightness=0.30",
  "metadata": { "mod_type": "global", "instruction": "make it brighter", "strength": 0.7, "seed": null }
}
```

### Supported instructions (PIL path)

- **Global**: brighter, darker, lighten, darken; more/less contrast; more/less saturated, vibrant, muted, grey; sharper, blur, soft.
- **Style fallback**: black and white, noir, monochrome, grayscale; vintage, sepia; blur/soft; sharp, crisp.

### Errors

- **400**: Missing `image_url`/`image_base64` or `instruction`; invalid or empty image; unclear instruction (no keyword match).
- **500**: S3 download/upload failure, or internal error.

## See also

- [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for env vars.
- [DEVELOPMENT.md](DEVELOPMENT.md) for local run.

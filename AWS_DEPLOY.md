# PhotoGenius AI — AWS Deployment Guide
**Last updated: March 23, 2026 | Strategy: App Runner via GitHub (now) → ECS Fargate (at scale)**
**Note: No Docker — GitHub source deploy only**

---

## Architecture

```
User
  │
  ▼
Route 53 (domain)
  │
  ├── photogenius.ai        → AWS Amplify (Next.js)
  └── api.photogenius.ai    → App Runner (FastAPI)
                                    │
                              Supabase PostgreSQL
                                    │
                            fal.ai + Gemini APIs
```

---

## Phase 1: Now (0–500 users/day)

### API — AWS App Runner
| Setting | Value |
|---------|-------|
| Source | GitHub |
| CPU | 2 vCPU |
| Memory | 4 GB |
| Min instances | 1 |
| Max instances | 20 |
| Scale out trigger | CPU > 60% |
| Scale in trigger | CPU < 30% |
| Port | 8080 |
| Cost | ~$50/mo (1 instance idle) |

### Web — AWS Amplify
| Setting | Value |
|---------|-------|
| Source | GitHub |
| Framework | Next.js 14 |
| Build command | `pnpm build` |
| Root directory | `apps/web` |
| Cost | ~$5-10/mo |

---

## Step 1: apprunner.yaml ✅ (already created)

`apps/api/apprunner.yaml` already hai — App Runner is file ko auto-detect karta hai:

```yaml
version: 1.0
runtime: python311
build:
  commands:
    build:
      - pip install -r requirements.txt
run:
  command: uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
  network:
    port: 8080
  env:
    - name: PORT
      value: "8080"
    - name: ENVIRONMENT
      value: "production"
```

---

## Step 2: Environment Variables (App Runner Dashboard)

App Runner → Service → Configuration → Environment variables mein ye sab add karo:

```
# API Keys
FAL_KEY=
GEMINI_API_KEY=
REPLICATE_API_TOKEN=

# Database
DATABASE_URL=postgresql://postgres:...@db.xxx.supabase.co:5432/postgres

# Feature Flags
USE_IDEOGRAM=false
USE_ANTHROPIC=false
USE_GEMINI_ENGINE=true
USE_BFL=true
USE_KIE=true
USE_PIXAZO=true
USE_TOGETHER=false

# AWS (for S3 image storage)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET=photogenius-images-dev

# App
ENVIRONMENT=production
NUDENET_ENABLED=false
```

---

## Step 3: Deploy API to App Runner

1. AWS Console → App Runner → **Create service**
2. Source: **GitHub repository**
3. Repository: `PhotoGenius-AI`
4. Branch: `main`
5. Root directory: `apps/api`
6. Runtime: **Python 3**
7. Build command: `pip install -r requirements.txt`
8. Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4`
9. Port: `8080`
10. CPU: `2 vCPU` | Memory: `4 GB`
11. Auto scaling: min=1, max=20
12. Add all env vars from Step 2
13. **Deploy ✓**

---

## Step 4: Deploy Web to Amplify

1. AWS Console → Amplify → **New app → GitHub**
2. Repository: `PhotoGenius-AI`
3. Branch: `main`
4. `amplify.yml` root mein already hai — auto detect hoga
5. Environment variables add karo:

```
NEXT_PUBLIC_API_URL=https://api.photogenius.ai
INTERNAL_API_URL=https://api.photogenius.ai
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXTAUTH_SECRET=
NEXTAUTH_URL=https://photogenius.ai
```

6. **Deploy ✓**

---

## Step 5: Domain Setup (Route 53)

```
Route 53 Hosted Zone: photogenius.ai
  │
  ├── A record:     photogenius.ai      → Amplify (auto-managed)
  ├── A record:     www.photogenius.ai  → Amplify
  └── CNAME:        api.photogenius.ai  → App Runner URL
```

**Amplify:** Amplify → Domain management → Add domain → `photogenius.ai`

**App Runner:** App Runner → Custom domains → Add → `api.photogenius.ai`

---

## Phase 2: Scale (500–50,000 users/day)

Migrate API: App Runner → **ECS Fargate** jab:
- Daily users > 500
- Cost > $100/mo on App Runner
- More networking control chahiye

### ECS Fargate Setup:
| Setting | Value |
|---------|-------|
| CPU | 2 vCPU |
| Memory | 4 GB |
| Min tasks | 3 |
| Max tasks | 20 |
| Load Balancer | ALB |
| Cost at 5k users/day | ~$200/mo |
| Cost at 20k users/day | ~$400/mo |
| Cost at 50k users/day | ~$900/mo |

---

## Cost Summary

| Phase | Users/day | Monthly Cost |
|-------|-----------|--------------|
| Phase 1 — App Runner (idle) | 0–100 | ~$60/mo |
| Phase 1 — App Runner (active) | 100–500 | ~$100/mo |
| Phase 2 — ECS Fargate | 5,000 | ~$200/mo |
| Phase 2 — ECS Fargate | 20,000 | ~$400/mo |
| Phase 2 — ECS Fargate | 50,000 | ~$900/mo |

---

## Health Check

App Runner `/health` ping → already returns `{"status":"ok"}` ✓

---

## Files Ready ✅

| File | Purpose |
|------|---------|
| `apps/api/apprunner.yaml` | App Runner build + run config |
| `amplify.yml` | Amplify build config (root level) |

---

## Checklist Before Deploy

- [ ] GitHub repo push kar do (main branch)
- [ ] `apps/api/apprunner.yaml` committed
- [ ] `amplify.yml` committed (root)
- [ ] All env vars ready (FAL_KEY, GEMINI_API_KEY, DATABASE_URL, etc.)
- [ ] AWS account with App Runner + Amplify access
- [ ] Domain Route 53 mein hai ya transfer karo
- [ ] Supabase DATABASE_URL confirm karo
- [ ] App Runner deploy karo → URL milega → Amplify mein `NEXT_PUBLIC_API_URL` set karo → Amplify deploy karo

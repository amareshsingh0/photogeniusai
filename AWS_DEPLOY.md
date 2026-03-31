# PhotoGenius AI — Deployment Guide
**Last updated: April 1, 2026 | Strategy: EC2 t2.medium (now) → ECS Fargate (at scale)**

---

## Current Setup (Live)

```
User
  │
  ▼
Route 53 (bimoraai.com)
  │
  ├── creatives.bimoraai.com     → EC2 t2.medium (Next.js :3002)
  └── api.creatives.bimoraai.com → EC2 t2.medium (FastAPI :8003)
                                          │
                                    Supabase PostgreSQL
                                          │
                                  fal.ai + Gemini APIs
```

**EC2 Instance:** `13.232.79.128` (ap-south-1, Ubuntu 22.04)
**SSL:** Let's Encrypt (auto-renew via certbot)
**Process Manager:** PM2

---

## EC2 Services

| Service | Command | Port | PM2 Name |
|---------|---------|------|----------|
| FastAPI | `uvicorn app.main:app` | 8003 | `photogenius-api` |
| Next.js | `pnpm start` | 3002 | `photogenius-web` |

---

## SSH Access

```bash
ssh -i "C:\desktop\PhotoGenius AI\bimoraAI.pem" ubuntu@13.232.79.128
```

---

## Deploy / Update

```bash
# SSH into EC2
ssh -i "C:\desktop\PhotoGenius AI\bimoraAI.pem" ubuntu@13.232.79.128

# Pull latest
cd ~/PhotoGenius-AI && git pull

# Rebuild web (required after any code change)
cd ~/PhotoGenius-AI/apps/web
pnpm build
pm2 restart photogenius-web

# Restart API (no rebuild needed, just restart)
pm2 restart photogenius-api
pm2 save
```

> **Note:** After EC2 reboot, API must be restarted with env vars (see PM2 section below).
> Web env changes require `pnpm build` + restart.

---

## First-Time Setup (already done)

1. Ubuntu 22.04, Node 20, Python 3.12, pnpm, pm2
2. `git clone https://github.com/amareshsingh0/photogenius.git ~/PhotoGenius-AI`
3. API: `python3 -m venv venv && pip install -r requirements.txt`
4. Prisma: `npx prisma@5 generate --schema=packages/database/prisma/schema.prisma`
5. Web: `pnpm install && pnpm build`
6. Nginx reverse proxy + Let's Encrypt SSL
7. PM2 startup: `pm2 startup systemd`

---

## Environment Files

- API: `~/PhotoGenius-AI/apps/api/.env`
- Web: `~/PhotoGenius-AI/apps/web/.env.local`

---

## Security Group (EC2)

| Port | Protocol | Source |
|------|----------|--------|
| 22 | TCP | 0.0.0.0/0 |
| 80 | TCP | 0.0.0.0/0 |
| 443 | TCP | 0.0.0.0/0 |
| 8003 | TCP | 0.0.0.0/0 |

---

## PM2 Commands

```bash
pm2 status              # check services
pm2 logs photogenius-api --lines 50 --nostream
pm2 logs photogenius-web --lines 50 --nostream
pm2 restart photogenius-web
pm2 save
```

### ⚠️ API Restart (env vars required every time)

PM2 does NOT persist env vars from `.env` file — must pass inline:

```bash
cd ~/PhotoGenius-AI/apps/api && source venv/bin/activate
pm2 delete photogenius-api

FAL_KEY=5e234793-a05c-4782-b35b-2506e8230be4:b7853b046543edc5c0e6c911aa479994 \
GEMINI_API_KEY=AIzaSyBBhnNoBahNoA5dm6vpZzuKmtVcTm1CVls \
FIREWORKS_API_KEY=fw_M8VDzojW3tBwgh4xUzNFjB \
PIXAZO_API_KEY=8a1d255420f3432696ea608dc59aa304 \
KIE_API_KEY=bb5dfd6f05f96508c9c2cf422507813d \
BFL_API_KEY=bfl_CJ8iHx7KVSneBF0jyrLYyQz2MiKBaxxE \
DATABASE_URL=postgresql://postgres:m9w9SBlS96oGwO8n@db.whefwzleeyimflfcunqt.supabase.co:5432/postgres \
CLERK_SECRET_KEY=sk_test_a4kjikWGmQjqybn8cykySbbjVP1yRUiXot4t7ru2p3 \
USE_FIREWORKS=true USE_PIXAZO=true USE_BFL=true USE_KIE=true \
USE_GEMINI_ENGINE=true GENERATION_BACKEND=fal API_PORT=8003 \
pm2 start "uvicorn app.main:app --host 0.0.0.0 --port 8003" --name photogenius-api
pm2 save
```

### Web env vars (EC2 `.env.local`)

```
NEXT_PUBLIC_API_URL=http://api.creatives.bimoraai.com
INTERNAL_API_URL=http://127.0.0.1:8003
FASTAPI_URL=http://127.0.0.1:8003
```

---

## Phase 2: Scale (500+ users/day)

Migrate to ECS Fargate when:
- Daily users > 500
- Cost > $100/mo on EC2

| Phase | Users/day | Monthly Cost |
|-------|-----------|--------------|
| EC2 t2.medium | 0–500 | ~$20/mo |
| ECS Fargate | 5,000 | ~$200/mo |
| ECS Fargate | 20,000 | ~$400/mo |

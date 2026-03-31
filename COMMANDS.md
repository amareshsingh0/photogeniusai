# PhotoGenius AI - Commands Reference

## Quick Start (Development)

```bash
# Install all dependencies (run once)
pnpm install

# Start frontend only
cd apps/web && pnpm dev

# Start everything (frontend + backend)
pnpm dev
```

---

## 📁 Folder-wise Commands

### 📂 Root (`/PhotoGenius AI`)

| Command | What it does |
|---------|--------------|
| `pnpm install` | Install all dependencies for entire monorepo |
| `pnpm dev` | Start all apps (web, api) in development mode |
| `pnpm build` | Build all apps for production |
| `pnpm lint` | Run linting on all apps |
| `pnpm clean` | Clean all node_modules and build artifacts |

---

### 📂 Frontend (`/apps/web`)

| Command | What it does |
|---------|--------------|
| `pnpm dev` | Start Next.js dev server at `http://localhost:3000` |
| `pnpm build` | Build production bundle |
| `pnpm start` | Start production server |
| `pnpm lint` | Run ESLint |
| `pnpm tsc --noEmit` | Type check without emitting |

**Port:** `3000`

---

### 📂 Backend API (`/apps/api`)

| Command | What it does |
|---------|--------------|
| `pnpm dev` | Start FastAPI server at `http://localhost:8000` |
| `pnpm start` | Start production server with uvicorn |
| `uvicorn app.main:app --reload --port 8000` | Manual start with reload |

**Port:** `8000`

---

### 📂 Database (`/packages/database`)

| Command | What it does |
|---------|--------------|
| `pnpm prisma generate` | Generate Prisma client |
| `pnpm prisma db push` | Push schema to database (dev) |
| `pnpm prisma migrate dev` | Create and apply migration |
| `pnpm prisma migrate deploy` | Apply migrations (production) |
| `pnpm prisma studio` | Open Prisma Studio GUI |
| `npx prisma db push` | Alternative: Push schema |

**Note:** Run from `packages/database` folder or use `pnpm --filter database prisma ...`

---

### 📂 AI Pipeline (`/ai-pipeline`)

#### Modal Deployment Commands

| Command | What it does |
|---------|--------------|
| `modal token new` | Authenticate with Modal (first time) |
| `modal secret create huggingface HUGGINGFACE_TOKEN=hf_xxx` | Create HuggingFace secret |
| `modal secret create anthropic ANTHROPIC_API_KEY=sk-ant-xxx` | Create Anthropic secret |
| `modal run models/download_models.py` | Download all models (one-time, ~10 min) |
| `modal deploy services/generation_service.py` | Deploy generation service |
| `modal deploy services/safety_service.py` | Deploy safety service |
| `modal deploy services/lora_trainer.py` | Deploy LoRA trainer |
| `modal deploy services/orchestrator.py` | Deploy orchestrator |
| `modal deploy services/refinement_engine.py` | Deploy refinement engine |
| `modal serve services/generation_service.py` | Run locally for testing |
| `modal app list` | List all deployed apps |
| `modal app stop <app-name>` | Stop an app |

#### Deploy All Services (PowerShell)

```powershell
# From project root
.\scripts\deploy-modal.ps1
```

---

### 📂 Scripts (`/scripts`)

| Command | What it does |
|---------|--------------|
| `.\scripts\deploy-modal.ps1` | Deploy all Modal services |
| `.\scripts\setup-modal-secrets.ps1` | Setup Modal secrets from .env |
| `.\scripts\verify-setup.ps1` | Verify project setup |
| `.\scripts\verify-env.ps1` | Verify environment variables |

---

## 🚀 Full Deployment Workflow

### 1. First Time Setup

```bash
# 1. Install dependencies
pnpm install

# 2. Setup database
cd packages/database
pnpm prisma generate
pnpm prisma db push
cd ../..

# 3. Setup Modal (AI services)
pip install modal
modal token new
modal secret create huggingface HUGGINGFACE_TOKEN=hf_xxx

# 4. Download AI models (one-time, ~10 min)
cd ai-pipeline
modal run models/download_models.py

# 5. Deploy AI services
.\scripts\deploy-modal.ps1
```

### 2. Daily Development

```bash
# Start frontend
cd apps/web && pnpm dev

# Or start full stack
pnpm dev
```

### 3. Production Deployment

```bash
# Build
pnpm build

# Deploy frontend (Vercel)
cd apps/web && vercel deploy --prod

# Deploy API (Railway/Render)
# See platform-specific docs

# AI services already deployed on Modal
```

---

## 🌐 Service URLs

### Development

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Prisma Studio | http://localhost:5555 |

### Production (Modal)

| Service | URL Pattern |
|---------|-------------|
| Safety | `https://cn149--photogenius-safety--check-prompt-safety-web.modal.run` |
| Generation | `https://cn149--photogenius-generation--generate-images-web.modal.run` |
| Refinement | `https://cn149--photogenius-refinement-engine--refine-web.modal.run` |
| Training | `https://cn149--photogenius-lora-trainer--train-lora-web.modal.run` |
| Orchestrator | `https://cn149--photogenius-orchestrator--orchestrate-web.modal.run` |

---

## 🔧 Troubleshooting Commands

```bash
# Check Modal auth
modal token show

# List Modal secrets
modal secret list

# Check deployed apps
modal app list

# View app logs
modal app logs <app-name>

# Prisma reset (⚠️ destroys data)
cd packages/database && npx prisma migrate reset

# Clear Next.js cache
cd apps/web && rm -rf .next

# Clear pnpm cache
pnpm store prune
```

---

## 📝 Environment Variables Required

### Must Fill (Empty in .env.local):

**Payment:**
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_HOBBY`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_STUDIO`

**AI (for Orchestrator):**
- `ANTHROPIC_API_KEY` - Claude for prompt parsing
- `OPENAI_API_KEY` - Alternative for Whisper

**Monitoring:**
- `SENTRY_DSN` - Error tracking
- `NEXT_PUBLIC_POSTHOG_KEY` - Analytics

**Admin:**
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `JWT_SECRET_KEY`

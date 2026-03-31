# Cloud Migration Guide - PhotoGenius AI

## 🎯 Problem
Laptop ki CPU, Memory, aur Disk overload ho rahi hai kyunki:
- **AI Service** (SDXL) - GPU + 10GB+ RAM chahiye
- **PostgreSQL** - Database storage
- **Redis** - Cache memory
- **Web + API** - Development servers

## 📊 Resource Usage Analysis

| Service | CPU | Memory | Disk | Priority to Move |
|---------|-----|--------|------|------------------|
| **AI Service** | 🔴 Very High | 🔴 8-16GB | 🔴 20GB+ | **#1 - MUST MOVE** |
| **PostgreSQL** | 🟡 Medium | 🟡 2-4GB | 🟡 5-10GB | **#2 - HIGH** |
| **Redis** | 🟢 Low | 🟢 500MB-2GB | 🟢 Minimal | **#3 - MEDIUM** |
| **Web/API** | 🟢 Low | 🟢 500MB-1GB | 🟢 Minimal | **#4 - OPTIONAL** |

---

## 🚀 Recommended Cloud Architecture

### Option 1: **Modal.com** (Best for AI Service) ⭐ RECOMMENDED

Modal.com is perfect for GPU-heavy AI workloads. They handle:
- GPU instances (A10, A100)
- Auto-scaling
- Pay-per-use
- Easy deployment

#### Setup Steps:

1. **Install Modal CLI:**
```bash
pip install modal
modal token new
```

2. **Create Modal App** (`apps/ai-service/modal_app.py`):
```python
import modal

app = modal.App("photogenius-ai")

# GPU image with all dependencies
image = (
    modal.Image.debian_slim()
    .pip_install(
        "fastapi",
        "uvicorn[standard]",
        "torch",
        "diffusers",
        "transformers",
        # ... all requirements
    )
    .apt_install("git")
)

# GPU function for SDXL generation
@app.function(
    image=image,
    gpu="A10G",  # or "A100" for faster
    timeout=600,
    secrets=[
        modal.Secret.from_name("aws-credentials"),  # For S3
    ],
)
@modal.web_endpoint(method="POST", label="generate")
def generate_image(prompt: str, identity_data: dict):
    from app.services.ai.generation_service import SDXLGenerationService
    
    service = SDXLGenerationService()
    result = await service.generate(
        prompt=prompt,
        identity_data=identity_data,
    )
    return {"images": result.images, "scores": result.quality_scores}

# Deploy
@app.local_entrypoint()
def main():
    app.deploy("photogenius-ai")
```

3. **Deploy:**
```bash
cd apps/ai-service
modal deploy modal_app.py
```

4. **Update API to use Modal:**
```python
# apps/api/app/services/ai/generation_service.py
import httpx

MODAL_URL = "https://your-username--photogenius-ai-generate.modal.run"

async def generate_via_modal(prompt: str, identity_data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            MODAL_URL,
            json={"prompt": prompt, "identity_data": identity_data},
            timeout=600.0
        )
        return response.json()
```

**Cost:** ~$0.50-2/hour for GPU (only when generating)

---

### Option 2: **AWS Setup** (Full Control)

#### 1. **AI Service → AWS ECS with GPU** or **SageMaker**

**ECS with GPU:**
```yaml
# infra/aws/ecs-ai-service.yml
services:
  ai-service:
    image: your-ecr-repo/ai-service:latest
    gpu: 1
    instance_type: g4dn.xlarge  # NVIDIA T4 GPU
    memory: 16GB
```

**Cost:** ~$0.50-1.50/hour

#### 2. **PostgreSQL → AWS RDS**

```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier photogenius-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username postgres \
  --master-user-password YOUR_PASSWORD \
  --allocated-storage 20
```

**Update connection string:**
```env
DATABASE_URL=postgresql://postgres:PASSWORD@photogenius-db.xxxxx.us-east-1.rds.amazonaws.com:5432/photogenius
```

**Cost:** ~$15-30/month (db.t3.micro)

#### 3. **Redis → AWS ElastiCache**

```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id photogenius-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1
```

**Cost:** ~$12-20/month

#### 4. **Storage → AWS S3** (Already configured)

LoRA weights, generated images → S3
**Cost:** ~$0.023/GB/month

---

### Option 3: **Google Cloud Platform**

#### 1. **AI Service → Cloud Run with GPU** or **Vertex AI**

```bash
# Deploy to Cloud Run with GPU
gcloud run deploy ai-service \
  --source apps/ai-service \
  --region us-central1 \
  --platform managed \
  --gpu-type nvidia-t4 \
  --gpu-count 1 \
  --memory 16Gi
```

**Cost:** Pay per request (~$0.50-2/hour when active)

#### 2. **PostgreSQL → Cloud SQL**

```bash
gcloud sql instances create photogenius-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=us-central1
```

**Cost:** ~$7-15/month

#### 3. **Redis → Memorystore**

```bash
gcloud redis instances create photogenius-redis \
  --size=1 \
  --region=us-central1 \
  --tier=basic
```

**Cost:** ~$30-50/month

---

## 🎯 **Quick Start: Minimum Viable Cloud Setup**

### Step 1: Move AI Service to Modal (30 minutes)

1. **Sign up:** https://modal.com
2. **Install:** `pip install modal`
3. **Create file:** `apps/ai-service/modal_app.py` (see above)
4. **Deploy:** `modal deploy modal_app.py`
5. **Update API:** Point to Modal URL

**Result:** Laptop se 8-16GB RAM free ho jayega! 🎉

### Step 2: Move Database to Supabase (Free tier available)

1. **Sign up:** https://supabase.com
2. **Create project**
3. **Get connection string:**
```env
DATABASE_URL=postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```
4. **Run migrations:**
```bash
cd apps/api
prisma migrate deploy
```

**Result:** 2-4GB RAM + 5-10GB disk free! 🎉

### Step 3: Move Redis to Upstash (Free tier)

1. **Sign up:** https://upstash.com
2. **Create Redis database**
3. **Get URL:**
```env
REDIS_URL=redis://default:xxxxx@xxxxx.upstash.io:6379
```

**Result:** 500MB-2GB RAM free! 🎉

---

## 📝 Environment Variables Update

After migration, update these files:

### `apps/api/.env.local`
```env
# Database (Supabase)
DATABASE_URL=postgresql://postgres.xxxxx@xxxxx.supabase.co:5432/postgres

# Redis (Upstash)
REDIS_URL=redis://default:xxxxx@xxxxx.upstash.io:6379

# AI Service (Modal)
AI_SERVICE_URL=https://your-username--photogenius-ai-generate.modal.run
```

### `apps/web/.env.local`
```env
# API URL (if API also on cloud)
NEXT_PUBLIC_API_URL=https://your-api.vercel.app
```

---

## 💰 Cost Comparison

| Service | Local (Laptop) | Modal | AWS | GCP | Supabase/Upstash |
|---------|---------------|-------|-----|-----|------------------|
| **AI Service** | Free (but kills laptop) | $0.50-2/hr | $0.50-1.50/hr | $0.50-2/hr | N/A |
| **PostgreSQL** | Free | N/A | $15-30/mo | $7-15/mo | **FREE** (up to 500MB) |
| **Redis** | Free | N/A | $12-20/mo | $30-50/mo | **FREE** (up to 10K requests/day) |
| **Storage (S3)** | Free | N/A | $0.023/GB/mo | $0.020/GB/mo | Included |

**Recommended:** Modal + Supabase + Upstash = **~$0-50/month** (depending on usage)

---

## 🚀 Deployment Scripts

### Quick Migration Script

```bash
# scripts/migrate-to-cloud.sh
#!/bin/bash

echo "🚀 Migrating PhotoGenius to Cloud..."

# 1. Deploy AI Service to Modal
echo "📦 Deploying AI Service to Modal..."
cd apps/ai-service
modal deploy modal_app.py

# 2. Update environment variables
echo "⚙️  Updating environment variables..."
# (Manual step - update .env files)

# 3. Test connections
echo "✅ Testing cloud connections..."
cd ../api
python -c "from app.core.db import get_db; get_db()"

echo "🎉 Migration complete!"
```

---

## 🔧 Local Development After Migration

After moving to cloud, you can still develop locally:

```bash
# Only run Web + API locally
pnpm dev --filter=web
pnpm dev --filter=api

# AI Service, DB, Redis → Cloud
# Update .env files to point to cloud services
```

**Result:** Laptop pe sirf 500MB-1GB RAM use hoga! 🎉

---

## 📚 Next Steps

1. ✅ **Start with Modal** (AI Service) - Biggest impact
2. ✅ **Move to Supabase** (Database) - Free tier
3. ✅ **Move to Upstash** (Redis) - Free tier
4. ✅ **Keep Web/API local** or deploy to Vercel/Railway

---

## 🆘 Troubleshooting

### AI Service not responding?
- Check Modal logs: `modal app logs photogenius-ai`
- Verify GPU quota: Modal dashboard

### Database connection failed?
- Check Supabase connection string
- Verify IP whitelist (if enabled)

### Redis timeout?
- Check Upstash dashboard
- Verify connection string format

---

## 📞 Support

For issues:
- Modal: https://modal.com/docs
- Supabase: https://supabase.com/docs
- Upstash: https://docs.upstash.com

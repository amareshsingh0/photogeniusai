# PhotoGenius AI - Development Guide

## Frontend-Backend Connection

### Quick Start

1. **Test Connection** (checks if everything is configured correctly):
   ```bash
   pnpm test:connection
   ```

2. **Start API Backend** (FastAPI on port 8000):
   ```bash
   pnpm dev:api
   ```

3. **Start Frontend** (Next.js on port 3002):
   ```bash
   pnpm dev:web
   ```

4. **Or start both together**:
   ```bash
   pnpm dev
   ```

### Configuration

#### Backend (FastAPI)
- **Location**: `apps/api/`
- **Port**: Auto-selected (8000-8010), written to `.api-port`
- **URL**: `http://127.0.0.1:8000`
- **Health Check**: `http://127.0.0.1:8000/health`
- **API Docs**: `http://127.0.0.1:8000/docs`

#### Frontend (Next.js)
- **Location**: `apps/web/`
- **Port**: 3002
- **URL**: `http://localhost:3002`
- **Environment**: `apps/web/.env.local`

Key environment variables:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_USE_LOCAL_API=true
FASTAPI_URL=http://127.0.0.1:8000
```

### API Endpoints

The frontend connects to the backend through Next.js API routes that proxy to FastAPI:

1. **Image Generation**:
   - Frontend: `POST /api/generate`
   - Backend: `POST /api/v3/orchestrator/generate`
   - SageMaker: PixArt-Sigma on `ml.g5.2xlarge`

2. **Health Check**:
   - Backend: `GET /health`

3. **Dashboard Stats**:
   - Frontend: `GET /api/user/stats`
   - Backend: Database queries via Prisma

### Connection Flow

```
User Browser
    ↓
Next.js Frontend (port 3002)
    ↓
Next.js API Routes (/api/*)
    ↓
FastAPI Backend (port 8000)
    ↓
AWS SageMaker (PixArt-Sigma)
```

### Troubleshooting

#### 1. API Not Running
```bash
# Check if API is running
curl http://localhost:8000/health

# If not, start it
pnpm dev:api
```

#### 2. Port Mismatch
```bash
# Check what port API is using
cat .api-port

# Should output: 8000
# If different, update apps/web/.env.local
```

#### 3. CORS Errors
The API is configured to allow CORS from localhost:
- Check `apps/api/app/core/config.py` - `ALLOWED_ORIGINS`
- Should include `http://localhost:3002`

#### 4. Connection Test Failed
```bash
# Run the diagnostic script
pnpm test:connection

# It will show:
# ✓ API port file found
# ✓ API is running
# ✓ Frontend API URL configured correctly
```

#### 5. Database Connection Errors (Prisma)
If you see errors like "Can't reach database server at db.tiobvzluqxbbupijajci.supabase.co":

**Option 1: Skip Database for Basic Testing**
The app will still work for image generation without the database. Stats and gallery will show errors but generation works.

**Option 2: Use Local PostgreSQL**
```bash
# Install PostgreSQL locally
# Update apps/web/.env.local:
DATABASE_URL=postgresql://postgres:password@localhost:5432/photogenius

# Run Prisma migrations
cd apps/web
pnpm prisma generate
pnpm prisma db push
```

**Option 3: Fix Supabase Connection**
Check if your Supabase instance is paused or has network restrictions. Visit your Supabase dashboard to verify the database is running.

### Development Workflow

1. **First time setup**:
   ```bash
   # Install dependencies
   pnpm install

   # Set up Python venv for API
   cd apps/api
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements-minimal.txt
   cd ../..
   ```

2. **Daily development**:
   ```bash
   # Terminal 1: Start API
   pnpm dev:api

   # Terminal 2: Start Frontend
   pnpm dev:web

   # Or use single command (parallel):
   pnpm dev
   ```

3. **Testing**:
   ```bash
   # Test connection
   pnpm test:connection

   # Test API directly
   curl http://localhost:8000/health

   # Test generation
   curl -X POST http://localhost:8000/api/v3/orchestrator/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "A beautiful sunset", "tier": "standard"}'
   ```

### Architecture Notes

- **No external API tokens** - 100% own infrastructure
- **AWS SageMaker** - PixArt-Sigma model on ml.g5.2xlarge
- **14 Models on S3** (~75GB total)
- **Quality Tiers**:
  - FAST: 4 steps (~3s)
  - STANDARD: 20 steps (~12s)
  - PREMIUM: 50 steps (~22s)

### Key Files

- `apps/web/.env.local` - Frontend environment variables
- `apps/api/.env.local` - Backend environment variables
- `.api-port` - Current API port (auto-generated)
- `test-connection.mjs` - Connection diagnostic script
- `apps/web/app/api/generate/route.ts` - Main generation endpoint
- `apps/api/app/api/v3/orchestrator.py` - Backend orchestrator
- `aws/sagemaker/model/code/inference.py` - PixArt-Sigma handler

### Support

If connection issues persist:
1. Check `.api-port` file exists and contains `8000`
2. Verify `apps/web/.env.local` has correct API URL
3. Ensure API backend is running (`pnpm dev:api`)
4. Check firewall/antivirus not blocking port 8000
5. Try `pnpm test:connection` for diagnostics

# 🚀 PhotoGenius AI - Development Setup

**Last Updated**: February 6, 2026
**Status**: ✅ Ready for Development

---

## ✅ What's Working

1. ✅ **Backend API** - FastAPI with AI services
2. ✅ **Frontend** - Next.js web app
3. ✅ **AI Services** - 20 integrated services
4. ✅ **Models** - All 4 downloaded to S3
5. ✅ **SageMaker** - Ready to deploy

---

## 🚀 Quick Start - Run Development Server

### Method 1: Use Batch File (Easiest)

```cmd
.\run-dev.bat
```

### Method 2: Use PowerShell Script

```powershell
.\run-dev.ps1
```

### Method 3: Use pnpm Directly

```powershell
pnpm run dev
```

**Note**: Scripts automatically clean up existing processes before starting!

---

## 🌐 URLs After Starting

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | `http://localhost:3002` | Next.js web app |
| **Backend API** | `http://localhost:8000` | FastAPI REST API |
| **API Docs** | `http://localhost:8000/docs` | Interactive API docs |
| **AI Service** | `http://localhost:8001` | AI-specific endpoints |

---

## 🔧 Configuration

### Environment Variables

**Frontend**: `apps/web/.env.local`
- ✅ Points to localhost (not AWS Lambda)
- ✅ `NEXT_PUBLIC_API_URL=http://localhost:8000`

**Backend**: `apps/api/.env`
- ✅ AWS credentials configured
- ✅ HuggingFace token set
- ✅ SageMaker endpoints ready

### Requirements

**Backend**: `apps/api/requirements-minimal.txt`
- ✅ No Modal dependency (AWS-only)
- ✅ Minimal packages for fast dev
- ✅ GPU work on AWS SageMaker

---

## 🛠️ Troubleshooting

### Port Already in Use

**Problem**: `[WinError 10013] An attempt was made to access a socket...`

**Solution**: Use the provided scripts - they automatically kill processes:
```cmd
.\run-dev.bat
```

Or manually:
```powershell
taskkill /F /IM python.exe
taskkill /F /IM node.exe
pnpm run dev
```

### Prisma Client Error

**Problem**: `Module not found: Can't resolve '.prisma/client/default'`

**Solution**: Generate Prisma client (scripts do this automatically):
```powershell
cd packages/database
pnpm run build
cd ../..
```

Or use the startup scripts which include this step:
```cmd
.\run-dev.bat
```

### Frontend Not Loading

**Check**:
1. Make sure API is running at `http://localhost:8000`
2. Check `.env.local` points to localhost
3. Clear browser cache and reload

**Test API**:
```bash
curl http://localhost:8000/health
```

Should return:
```json
{"status":"ok","services":{"s3":"connected"}}
```

### pnpm Not Found

**Solution**: PATH issue - use scripts:
```cmd
.\run-dev.bat
```

Or add to PATH manually:
```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Users\dell\AppData\Roaming\npm", "User")
```

Then restart PowerShell.

---

## 📊 Project Structure

```
PhotoGenius AI/
├── apps/
│   ├── web/              # Next.js frontend (port 3002)
│   ├── api/              # FastAPI backend (port 8000)
│   ├── ai-service/       # AI-specific services (port 8001)
│   └── database/         # Database schemas
├── scripts/
│   ├── run-web-dev.mjs   # Start Next.js
│   ├── run-api-dev.mjs   # Start FastAPI
│   └── run-ai-dev.mjs    # Start AI service
├── run-dev.bat           # ✅ Windows Batch (auto-cleanup)
├── run-dev.ps1           # ✅ PowerShell (auto-cleanup)
└── package.json          # Turborepo config
```

---

## 🎯 Development Workflow

### 1. Start Development Server

```cmd
.\run-dev.bat
```

Wait for:
- ✅ Frontend ready at `http://localhost:3002`
- ✅ API ready at `http://localhost:8000`
- ✅ AI Service ready at `http://localhost:8001`

### 2. Open in Browser

```
http://localhost:3002
```

### 3. Make Changes

All services auto-reload on file changes:
- Frontend: Hot reload (instant)
- Backend: Auto-restart (few seconds)

### 4. Test API

Visit: `http://localhost:8000/docs`

Try endpoints:
- `GET /health` - Health check
- `GET /api/v3/status` - AI system status
- `POST /api/v3/generate` - Generate image

---

## 🔥 Production Deployment

### Backend Deployment

**AWS SageMaker**:
```powershell
cd aws/sagemaker
python deploy_enhanced_endpoint.py
```

**Lambda Functions**: Already deployed ✅
- Orchestrator: `https://3gp3xsvqkesxjtf56vdmuxx53a0xaeew.lambda-url.us-east-1.on.aws/`
- Generation: `https://iq3w5ugxkejdthvjvxavdo7t6a0xhdrs.lambda-url.us-east-1.on.aws/`

### Frontend Deployment

**Vercel** (Recommended):
```bash
vercel --prod
```

**Environment Variables** (Production):
- Set `NEXT_PUBLIC_API_URL` to Lambda URL
- Remove `NEXT_PUBLIC_USE_LOCAL_API`

---

## 📚 Documentation

- **API Guide**: `V3_API_TESTING_GUIDE.md`
- **AI Setup**: `COMPLETE_AI_SETUP.md`
- **System Design**: `SMART_BALANCED_SYSTEM.md`
- **Backend Summary**: `AI_BACKEND_COMPLETE.md`

---

## ✅ System Status

### Models (S3)
- ✅ SDXL-Base-1.0
- ✅ SDXL-Refiner-1.0
- ✅ SDXL-Turbo
- ✅ CLIP-ViT-Large

### Services
- ✅ 20 AI services integrated
- ✅ Smart mode detection
- ✅ Auto category detection
- ✅ Prompt enhancement
- ✅ Quality scoring
- ✅ Two-pass generation

### Backends
- ✅ HuggingFace Inference API
- ⏳ Replicate API (ready to configure)
- ⏳ SageMaker (ready to deploy)

---

## 🎉 You're Ready!

Just run:
```cmd
.\run-dev.bat
```

Open browser:
```
http://localhost:3002
```

Happy coding! 🚀

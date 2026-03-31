# Services Start Guide - PhotoGenius AI

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

Start all services with Docker:

```powershell
.\scripts\start-services.ps1
```

This will start:
- ✅ **Postgres** (port 5432)
- ✅ **Redis** (port 6379)
- ✅ **Web** (port 3000)
- ✅ **API** (port 8000)
- ☁️ **AI Service** - Runs on Modal.com (cloud)

### Option 2: Local Development

Run services locally (requires Postgres & Redis running):

```powershell
.\scripts\run-all-services.ps1
```

Or manually:

```bash
# Terminal 1: Web
pnpm --filter @photogenius/web dev

# Terminal 2: API
pnpm --filter @photogenius/api dev
```

### Option 3: Turbo (All at once)

```bash
pnpm run dev
```

This starts Web + API + AI Service (if configured locally)

---

## 📍 Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| **Web** | http://localhost:3000 | Next.js Frontend |
| **API** | http://localhost:8000 | FastAPI Backend |
| **API Docs** | http://localhost:8000/docs | Swagger UI |
| **Postgres** | localhost:5432 | Database |
| **Redis** | localhost:6379 | Cache |
| **AI Service** | https://amareshsingh0--photogenius-ai-generate.modal.run | Modal.com (Cloud) |

---

## ✅ Verification

### 1. Check Docker Services

```powershell
docker compose -f infra/docker/docker-compose.dev.yml ps
```

### 2. Test API

```bash
curl http://localhost:8000/health
# or
curl http://localhost:8000/api/v1/health
```

### 3. Test Web

Open browser: http://localhost:3000

### 4. Test Modal AI Service

```bash
python scripts/test-modal-connection.py
```

### 5. Test Redis

```bash
python scripts/test-redis-connection.py
```

---

## 🔧 Troubleshooting

### Port Conflicts

If ports are already in use:

```powershell
# Check what's using the port
netstat -ano | findstr :3000
netstat -ano | findstr :8000

# Stop conflicting services or change ports in docker-compose.yml
```

### Docker Not Starting

```powershell
# Check Docker Desktop is running
docker info

# Restart Docker Desktop if needed
```

### Database Connection Issues

```powershell
# Check Postgres is healthy
docker inspect --format='{{.State.Health.Status}}' photogenius-postgres

# View logs
docker compose -f infra/docker/docker-compose.dev.yml logs postgres
```

### Redis Connection Issues

```powershell
# Check Redis is healthy
docker inspect --format='{{.State.Health.Status}}' photogenius-redis

# Test connection
python scripts/test-redis-connection.py
```

### Modal AI Service Not Working

1. Check deployment status:
   ```bash
   modal app list
   ```

2. Check if app is deployed:
   ```bash
   cd apps/ai-service
   modal deploy modal_app.py
   ```

3. Test endpoints:
   ```bash
   python scripts/test-modal-connection.py
   ```

---

## 📝 Environment Variables

Make sure these are set in `.env.local` files:

### `apps/api/.env.local`
- `DATABASE_URL` - Supabase PostgreSQL
- `REDIS_URL` - Upstash Redis
- `AI_SERVICE_URL` - Modal.com endpoint
- `CLERK_SECRET_KEY` - Authentication

### `apps/web/.env.local`
- `NEXT_PUBLIC_API_URL` - Backend API URL
- `AI_SERVICE_URL` - Modal.com endpoint
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` - Authentication

---

## 🎯 Current Architecture

```
┌─────────────┐
│   Browser   │
│  (Port 3000)│
└──────┬──────┘
       │
       ▼
┌─────────────┐      ┌──────────────┐
│  Next.js    │─────▶│  FastAPI     │
│   (Web)     │      │   (API)      │
└─────────────┘      └──────┬───────┘
                            │
                            ├──▶ Postgres (Supabase)
                            ├──▶ Redis (Upstash)
                            └──▶ AI Service (Modal.com)
```

---

## 🚀 Next Steps

1. ✅ All services started
2. ✅ Test endpoints
3. ✅ Verify Modal connection
4. ✅ Check logs for errors

---

## 📞 Support

- **Docker Issues**: Check `docker compose logs [service-name]`
- **API Issues**: Check `apps/api` logs or http://localhost:8000/docs
- **Web Issues**: Check browser console and Next.js logs
- **Modal Issues**: Check Modal dashboard at https://modal.com/apps

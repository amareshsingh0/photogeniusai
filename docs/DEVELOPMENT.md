# PhotoGenius AI – Development

## Setup

1. **Clone** and `pnpm install`.
2. **Env**: ensure `apps/web/.env.local` and `apps/api/.env.local` exist; fill `DATABASE_URL`, etc. See [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md). For SageMaker deploy use `aws/sagemaker/.env.local`.
3. **DB**: `pnpm run db:generate`, then `pnpm run db:push` or `pnpm run db:migrate`. Optionally `pnpm run db:seed`.
4. **Python** (API / AI): `cd apps/api` → `python -m venv .venv` → activate → `pip install -r requirements.txt`. Same for `apps/ai-service` if you use it.

## Run

- **All**: `pnpm run dev` (web + API + ai-service). API → `:8000`, ai-service → `:8001`.
- **Web only**: `pnpm run dev --filter=@photogenius/web`.
- **API only**: `pnpm run dev --filter=@photogenius/api` or `uvicorn app.main:app --reload` from `apps/api` (with venv activated).
- **API tests**: `pnpm run test --filter=@photogenius/api` or `cd apps/api` then `pnpm test`.

## Docker (Windows)

Use **PowerShell** (not CMD) for multi-line. Or use the scripts:

```powershell
.\scripts\docker-minio.ps1    # MinIO → :9000 (S3), :9001 (console). minioadmin / minioadmin
.\scripts\docker-redis.ps1    # Redis → :6379. REDIS_URL=redis://localhost:6379/0
```

**MinIO one-liner (CMD or PowerShell):**

```
docker run -d --name minio -p 9000:9000 -p 9001:9001 -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin minio/minio server /data --console-address ":9001"
```

**Redis one-liner:** `docker run -d --name photogenius-redis -p 6379:6379 redis:7-alpine`

## Scripts

- `pnpm run lint`, `pnpm run typecheck`, `pnpm run test`.
- `scripts/setup-dev.sh`, `scripts/setup-db.sh`, `scripts/run-tests.sh`.
- `scripts/docker-minio.ps1`, `scripts/docker-redis.ps1` (Windows).

## Layout

- Do not change frontend layout/structure; add or adjust functionality only when requested.

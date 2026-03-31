# PhotoGenius AI – Deployment

## Quick checks

- Node 18–20, pnpm 8+, Python 3.11+.
- `pnpm install`, `pnpm run db:generate`, then `pnpm run dev`.

## Docker

- **Postgres + Redis**: `docker compose -f infra/docker-compose.yml up -d`.
- **Apps**: use `infra/docker-compose.apps.yml` or `infra/docker/` compose files.
- Set `DATABASE_URL`, `REDIS_URL` (and other env) per [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md).

## Staging / production

1. Set `ENVIRONMENT=staging` or `production`.
2. Use staging/production DB and secrets.
3. Run `pnpm run build`, then deploy web (e.g. Vercel) and API (e.g. Railway, ECS, k8s).
4. Run migrations: `pnpm run db:migrate` (or your migration strategy).

## Scripts

- `scripts/deploy-staging.sh`, `scripts/deploy-prod.sh` – customize for your infra.

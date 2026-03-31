# Docker Compose Setup for PhotoGenius AI

## Services

This docker-compose configuration includes:

1. **postgres** - PostgreSQL 16 database (port 5432)
2. **redis** - Redis 7 cache (port 6379)
3. **web** - Next.js frontend (port 3000)
4. **api** - FastAPI backend (port 8000)
5. **ai-service** - AI service (port 8001 on host, 8000 in container)

## Quick Start

### Start all services:
```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d --build
```

### Start only infrastructure (postgres + redis):
```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d postgres redis
```

### Start application services:
```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d web api ai-service
```

### View logs:
```bash
docker compose -f infra/docker/docker-compose.dev.yml logs -f [service-name]
```

### Stop all services:
```bash
docker compose -f infra/docker/docker-compose.dev.yml down
```

### Stop and remove volumes:
```bash
docker compose -f infra/docker/docker-compose.dev.yml down -v
```

## Port Mappings

- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`
- **Web**: `localhost:3000`
- **API**: `localhost:8000`
- **AI Service**: `localhost:8001` (mapped from container port 8000)

## Environment Variables

Services use `.env.local` files from their respective directories:
- `apps/web/.env.local`
- `apps/api/.env.local`
- `apps/ai-service/.env.local`

## Network

All services are on the `photogenius-network` bridge network and can communicate using service names:
- `postgres:5432`
- `redis:6379`
- `api:8000`
- `ai-service:8000`
- `web:3000`

## Troubleshooting

### Port conflicts
If you see port conflicts, check what's using the ports:
```bash
# Windows
netstat -ano | findstr :3000
netstat -ano | findstr :8000
netstat -ano | findstr :8001

# Or check Docker containers
docker ps -a
```

### Container name conflicts
If containers with the same names exist, remove them:
```bash
docker stop photogenius-web photogenius-api photogenius-ai-service photogenius-postgres photogenius-redis
docker rm photogenius-web photogenius-api photogenius-ai-service photogenius-postgres photogenius-redis
```

### Build issues
If builds fail, try building individually:
```bash
docker compose -f infra/docker/docker-compose.dev.yml build [service-name]
```

### Database connection issues
Ensure postgres is healthy before starting other services:
```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d postgres
# Wait for health check
docker compose -f infra/docker/docker-compose.dev.yml ps postgres
```

## Observability stack (Jaeger, Prometheus, Grafana)

For tracing, metrics, and dashboards:

```bash
docker compose -f infra/docker/docker-compose.observability.yml up -d
```

- **Jaeger UI**: http://localhost:16686  
- **Prometheus**: http://localhost:9090  
- **Grafana**: http://localhost:3010 (admin / admin)

See `ai-pipeline/services/OBSERVABILITY_README.md` and `infra/docker/observability/` for config.

## Development vs Production

- **docker-compose.dev.yml**: Development setup with volume mounts for hot reload
- **docker-compose.prod.yml**: Production setup (minimal, build-based)
- **docker-compose.yml**: Basic infrastructure only (postgres + redis)
- **docker-compose.observability.yml**: Observability stack (Jaeger, Prometheus, Grafana)

# PhotoGenius AI – API

FastAPI backend for AI avatar generation with comprehensive safety features.

## Features

- ✅ **Dual Pipeline Safety System** - Pre and post-generation safety checks
- ✅ **Prompt Sanitization** - Comprehensive blocklists and context-aware filtering
- ✅ **NSFW Classification** - NudeNet-based content moderation with quarantine
- ✅ **Age Estimation** - DeepFace-based age verification
- ✅ **Rate Limiting** - Redis-based rate limiting
- ✅ **Audit Logging** - Comprehensive safety audit logs with 180-day retention
- ✅ **User Authentication** - Clerk integration
- ✅ **Image Generation** - AI-powered avatar generation

## Quick Start

### Setup

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Unix
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Environment Configuration

Ensure `.env.local` exists and configure (see docs/ENVIRONMENT_SETUP.md):

```bash
# Required
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379/0
CLERK_SECRET_KEY=sk_...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=...
HUGGINGFACE_TOKEN=...
MODAL_TOKEN_ID=...
MODAL_TOKEN_SECRET=...

# Optional
STRIPE_SECRET_KEY=sk_...
SENTRY_DSN=...
```

See [ENVIRONMENT_SETUP.md](../docs/ENVIRONMENT_SETUP.md) for detailed setup.

### Database Setup

```bash
# Run migrations
alembic upgrade head

# Check migration status
alembic current
```

### Run Development Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Or use the monorepo script:

```bash
pnpm --filter @photogenius/api dev
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest app/tests/test_safety.py -v
```

## API Documentation

Once server is running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
apps/api/
├── app/
│   ├── api/v1/endpoints/    # API endpoints
│   ├── core/                 # Config, database, security
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # Business logic
│   │   ├── safety/           # Safety features
│   │   ├── ai/               # AI generation
│   │   └── storage/          # S3/R2 storage
│   └── workers/              # Background workers
├── alembic/                  # Database migrations
└── tests/                    # Test suite
```

## Safety Features

### Pre-Generation Checks

- Prompt sanitization (explicit content, celebrities, politicians)
- User status verification (banned, strikes)
- Rate limiting
- Identity consent verification

### Post-Generation Checks

- NSFW classification (ALLOW, QUARANTINE, BLOCK)
- Age estimation (block if under 18)
- Audit logging

See [AUDIT_LOGGING_USAGE.md](app/services/safety/AUDIT_LOGGING_USAGE.md) for details.

## Development

### Adding New Endpoints

1. Create endpoint in `app/api/v1/endpoints/`
2. Add to router in `app/api/v1/router.py`
3. Create Pydantic schemas in `app/schemas/`
4. Add tests in `tests/`

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Review migration file
# Edit if needed

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Documentation

- [TODO Implementation Guide](TODO_IMPLEMENTATION.md) - Features needing implementation
- [Safety System Usage](app/services/safety/AUDIT_LOGGING_USAGE.md)
- [Environment Setup](../docs/ENVIRONMENT_SETUP.md)
- [Deployment Guide](../docs/DEPLOYMENT_PRODUCTION.md)

## Troubleshooting

### Database Connection Issues

- Verify `DATABASE_URL` format: `postgresql+asyncpg://user:pass@host:port/db`
- Check database is running and accessible
- Verify firewall rules

### Redis Connection Issues

- Verify `REDIS_URL` format: `redis://host:port/db`
- Check Redis is running: `redis-cli ping`
- For local: `docker run -d -p 6379:6379 redis:alpine`

### Migration Errors

- Check `alembic/env.py` is configured correctly
- Verify database connection
- See migration files for issues

## License

Proprietary

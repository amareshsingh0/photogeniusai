"""
Pixium AI – FastAPI application.
"""
import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# CRITICAL: configure root logger BEFORE any other imports so logger.info() calls
# from every module (multi_provider_client, simple_prompt_engine, generate_stream,
# etc.) actually reach stdout / pm2 logs. Without this, Python's default logger
# has level=WARNING and no handler — every [PAYLOAD], [FINAL-PROMPT], [SANITIZE]
# log was silently dropped, leaving us blind during debugging.
_log_level = getattr(logging, (os.getenv("LOG_LEVEL") or "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
    force=True,  # override any handlers Uvicorn / other libs already installed
)
# Loud one-shot heartbeat so we can confirm logging is wired:
logging.getLogger("photogenius.boot").info("[BOOT] root logger configured at level=%s", logging.getLevelName(_log_level))

# Add project root so config.tier_config is importable (main -> app -> api -> apps -> root)
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Load .env BEFORE any module reads os.getenv(...) so admin-panel feature-flag
# toggles (which write to apps/api/.env) take effect on the next pm2 restart.
# override=True ensures admin edits beat pm2's stale cached env.
try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore
    _env_file = Path(__file__).resolve().parents[1] / ".env"
    if _env_file.exists():
        _load_dotenv(_env_file, override=True)
except Exception:
    pass

# Suppress TensorFlow warnings if installed globally
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

from fastapi import FastAPI  # type: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # type: ignore[reportMissingImports]

from app.api.v1.router import api_router
from app.api.v2.router import router as api_v2_router
from app.api.v2.generate import router as api_v2_generate_router
from app.api.v3 import router as api_v3_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: connect DB, init services."""
    import asyncio
    from app.services.safety.audit_logger import audit_logger

    # Start background cleanup task for audit logs
    cleanup_task = None
    scheduler_started = False

    async def scheduled_cleanup():
        """Run cleanup every 24 hours"""
        from app.core.database import AsyncSessionLocal

        while True:
            try:
                await asyncio.sleep(86400)  # 24 hours
                async with AsyncSessionLocal() as db:
                    deleted = await audit_logger.cleanup_expired_logs(db_session=db)
                    if deleted > 0:
                        logger.info(f"Cleaned up {deleted} expired audit logs")
            except Exception as e:
                logger.error(f"Cleanup task error: {e}", exc_info=True)
                await asyncio.sleep(3600)  # Retry in 1 hour on error

    # Start cleanup task
    cleanup_task = asyncio.create_task(scheduled_cleanup())

    # Preload typography fonts DISABLED (compositor disabled, native AI text rendering now)
    # try:
    #     from app.services.smart.typography_engine import preload_all_fonts, validate_required_fonts
    #     validate_required_fonts()
    #     asyncio.create_task(preload_all_fonts())
    # except Exception as e:
    #     logger.warning("Typography font preload skipped: %s", e)

    # Start scheduled tasks only if apscheduler is available (optional for dev)
    try:
        from app.tasks.scheduled import start_scheduler, stop_scheduler
        logger.info("Starting scheduled task system...")
        start_scheduler()
        scheduler_started = True
        logger.info("Scheduled tasks started")
    except Exception as e:
        logger.warning("Scheduled tasks disabled (apscheduler not available): %s", e)

    yield

    # Teardown: close connections, cancel tasks
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

    if scheduler_started:
        try:
            from app.tasks.scheduled import stop_scheduler
            logger.info("Stopping scheduled task system...")
            stop_scheduler()
            logger.info("Scheduled tasks stopped")
        except Exception:
            pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(api_v2_router, prefix="/api/v2")
    app.include_router(api_v2_generate_router, prefix="/api/v2/smart")
    app.include_router(api_v3_router, prefix="/api/v3")
    return app


app = create_app()


@app.get("/")
async def root():
    """Root endpoint"""
    return {"service": "Pixium API", "status": "running", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check for load balancers and monitoring."""
    from app.services.storage import get_s3_service

    health_data = {"status": "ok", "services": {}}

    # Test S3/R2 connection if configured
    s3_service = get_s3_service()
    if s3_service.bucket and s3_service.access_key:
        try:
            s3_connected = s3_service.test_connection()
            health_data["services"]["s3"] = "connected" if s3_connected else "failed"
        except Exception as e:
            health_data["services"]["s3"] = f"error: {str(e)[:50]}"

    return health_data

"""
Production error handlers and logging for PhotoGenius AI

Features:
- Structured error responses
- Error classification and severity levels
- User-friendly error messages (hide internal details)
- Sentry integration for production monitoring
- Request context in error logs
"""

import logging
import traceback
from typing import Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# Error response schema
def error_response(
    error_code: str,
    message: str,
    details: Union[str, dict, None] = None,
    status_code: int = 500
) -> JSONResponse:
    """
    Standardized error response format

    Args:
        error_code: Machine-readable error code (e.g., "VALIDATION_ERROR")
        message: Human-readable error message
        details: Additional error details (only in development)
        status_code: HTTP status code
    """
    response_data = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
        }
    }

    # Include details only in development (not production)
    if details is not None:
        from app.core.config import settings
        if settings.ENVIRONMENT != "production":
            response_data["error"]["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


# Exception handlers

async def validation_exception_handler(request: Request, exc: Union[RequestValidationError, ValidationError]):
    """
    Handle Pydantic validation errors

    Returns user-friendly message without exposing internal validation logic
    """
    logger.warning(
        f"Validation error on {request.method} {request.url.path}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": exc.errors() if hasattr(exc, 'errors') else str(exc)
        }
    )

    # Extract first error for user message
    errors = exc.errors() if hasattr(exc, 'errors') else [{"msg": str(exc)}]
    first_error = errors[0]

    # User-friendly message based on error type
    field = first_error.get("loc", ["unknown"])[-1]
    error_type = first_error.get("type", "")

    if "missing" in error_type:
        message = f"Required field '{field}' is missing"
    elif "type_error" in error_type:
        message = f"Invalid value for '{field}'"
    elif "value_error" in error_type:
        message = f"Invalid value for '{field}': {first_error.get('msg', 'validation failed')}"
    else:
        message = "Invalid request data"

    return error_response(
        error_code="VALIDATION_ERROR",
        message=message,
        details=errors,  # Only shown in development
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    """
    Handle rate limit exceeded errors

    Returns clear message with retry information
    """
    from app.core.rate_limiter import get_user_tier

    tier = get_user_tier(request)

    logger.warning(
        f"Rate limit exceeded for {tier} tier",
        extra={
            "path": request.url.path,
            "tier": tier,
            "ip": request.client.host if request.client else "unknown"
        }
    )

    upgrade_message = ""
    if tier == "free":
        upgrade_message = " Upgrade to Pro for 6x more requests!"
    elif tier == "pro":
        upgrade_message = " Upgrade to Enterprise for 5x more requests!"

    return error_response(
        error_code="RATE_LIMIT_EXCEEDED",
        message=f"Rate limit exceeded for {tier} tier.{upgrade_message}",
        details={
            "tier": tier,
            "retry_after": str(exc.detail) if hasattr(exc, 'detail') else "60"
        },
        status_code=status.HTTP_429_TOO_MANY_REQUESTS
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """
    Handle all uncaught exceptions

    Logs full traceback but returns sanitized error to user
    """
    # Log full error with traceback
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
            "error_message": str(exc)
        }
    )

    # Check if this is a known error type
    error_type = type(exc).__name__

    if "Connection" in error_type or "Timeout" in error_type:
        return error_response(
            error_code="SERVICE_UNAVAILABLE",
            message="Service temporarily unavailable. Please try again in a moment.",
            details=str(exc),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    if "Permission" in error_type or "Forbidden" in error_type:
        return error_response(
            error_code="FORBIDDEN",
            message="You don't have permission to perform this action.",
            details=str(exc),
            status_code=status.HTTP_403_FORBIDDEN
        )

    # Generic 500 error (don't expose internal details to user)
    return error_response(
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred. Our team has been notified.",
        details=str(exc),  # Only in development
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


# Sentry integration (optional - only if configured)

def init_sentry():
    """
    Initialize Sentry error tracking (production only)

    Only activates if SENTRY_DSN is configured in environment
    """
    from app.core.config import settings

    if settings.ENVIRONMENT == "production":
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.starlette import StarletteIntegration

            # Check if SENTRY_DSN is configured
            sentry_dsn = getattr(settings, "SENTRY_DSN", None)

            if sentry_dsn:
                sentry_sdk.init(
                    dsn=sentry_dsn,
                    environment=settings.ENVIRONMENT,
                    traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
                    profiles_sample_rate=0.1,  # 10% for profiling
                    integrations=[
                        FastApiIntegration(),
                        StarletteIntegration(),
                    ],
                    before_send=before_send_sentry,
                )
                logger.info("Sentry error tracking enabled")
            else:
                logger.info("Sentry DSN not configured, error tracking disabled")

        except ImportError:
            logger.warning("Sentry SDK not installed, error tracking disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}")


def before_send_sentry(event, hint):
    """
    Filter Sentry events before sending

    - Remove sensitive data (API keys, tokens)
    - Skip low-priority errors
    """
    # Skip validation errors (logged but not critical)
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        if isinstance(exc_value, (RequestValidationError, ValidationError)):
            return None

    # Remove sensitive headers
    if 'request' in event:
        headers = event['request'].get('headers', {})
        for sensitive_key in ['Authorization', 'X-API-Key', 'Cookie']:
            headers.pop(sensitive_key, None)

    return event


# Structured logging setup

def setup_logging():
    """
    Configure structured logging for production

    - JSON format for production (easy parsing)
    - Human-readable format for development
    - Request ID tracking
    - Performance metrics
    """
    from app.core.config import settings

    # Root logger configuration
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if settings.ENVIRONMENT != "production"
        else '{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("s3transfer").setLevel(logging.WARNING)

    logger.info(f"Logging configured: {settings.LOG_LEVEL} ({settings.ENVIRONMENT})")


# Request logging middleware (add to main.py if needed)

async def log_requests_middleware(request: Request, call_next):
    """
    Log all incoming requests with timing

    Useful for debugging and performance monitoring
    """
    import time

    start_time = time.time()
    path = request.url.path

    # Skip health check spam
    if path in ["/health", "/", "/docs", "/openapi.json"]:
        return await call_next(request)

    logger.info(
        f"→ {request.method} {path}",
        extra={
            "method": request.method,
            "path": path,
            "client": request.client.host if request.client else "unknown"
        }
    )

    response = await call_next(request)

    duration = round((time.time() - start_time) * 1000, 2)  # ms

    logger.info(
        f"← {request.method} {path} - {response.status_code} ({duration}ms)",
        extra={
            "method": request.method,
            "path": path,
            "status": response.status_code,
            "duration_ms": duration
        }
    )

    return response

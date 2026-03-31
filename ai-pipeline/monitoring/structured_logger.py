"""
Structured JSON logging for CloudWatch Logs Insights.
Format: { timestamp, level, service, correlation_id?, message, ...metadata }

Uses structlog; binds correlation_id from observability.request_id_ctx when set.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

try:
    import structlog
    _STRUCTLOG_AVAILABLE = True
except ImportError:
    _STRUCTLOG_AVAILABLE = False

try:
    from ..services import observability
except ImportError:
    observability = None  # type: ignore[assignment]

SERVICE_NAME = "ai-pipeline"


def _add_correlation_id(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add correlation_id to every log event from context."""
    if observability is not None:
        cid = observability.get_request_id()
        if cid:
            event_dict["correlation_id"] = cid
    return event_dict


_configured = False


def _configure_structlog() -> None:
    global _configured
    if not _STRUCTLOG_AVAILABLE or _configured:
        return
    _configured = True
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _add_correlation_id,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> Any:
    """
    Return a structlog logger that includes correlation_id in every message.
    If structlog is not installed, returns stdlib logger (no JSON).
    """
    if _STRUCTLOG_AVAILABLE:
        _configure_structlog()
        return structlog.get_logger(name or SERVICE_NAME)
    return logging.getLogger(name or SERVICE_NAME)


def bind_correlation_id(correlation_id: Optional[str]) -> None:
    """Set correlation ID for the current context (e.g. from X-Request-ID)."""
    if observability is not None:
        observability.set_request_id(correlation_id)

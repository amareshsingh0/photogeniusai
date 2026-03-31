"""
Observability system for PhotoGenius AI pipeline.

Provides:
- Request ID generation and propagation (contextvars)
- Distributed tracing (OpenTelemetry, optional)
- Structured logging with context
- Prometheus metrics for critical paths
- Circuit breaker for external dependencies
- Retry with exponential backoff
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections import deque
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Context variable for request ID (thread-safe, async-safe)
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    return request_id_ctx.get()


def set_request_id(value: Optional[str]) -> None:
    request_id_ctx.set(value)

# Optional OpenTelemetry
try:
    from opentelemetry import trace  # type: ignore[reportMissingImports]
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore[reportMissingImports]
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter  # type: ignore[reportMissingImports]
    from opentelemetry.trace import Status, StatusCode  # type: ignore[reportMissingImports]

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    Status = None  # type: ignore[assignment]
    StatusCode = None  # type: ignore[assignment]

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore[reportMissingImports]
    from opentelemetry.sdk.resources import Resource  # type: ignore[reportMissingImports]

    _OTLP_AVAILABLE = True
except ImportError:
    _OTLP_AVAILABLE = False
    OTLPSpanExporter = None  # type: ignore[assignment, misc]
    Resource = None  # type: ignore[assignment, misc]

# Prometheus
try:
    from prometheus_client import Counter, Gauge, Histogram, Summary  # type: ignore[reportMissingImports]

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    Counter = None  # type: ignore[assignment, misc]
    Gauge = None  # type: ignore[assignment, misc]
    Histogram = None  # type: ignore[assignment, misc]
    Summary = None  # type: ignore[assignment, misc]


# ==================== TRACING CONFIG ====================


class TracingConfig:
    """OpenTelemetry configuration (env-driven)."""

    SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "photogenius-orchestrator")
    OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    ENABLE_CONSOLE_EXPORT = os.environ.get("OTEL_CONSOLE_EXPORT", "").lower() in ("1", "true", "yes")
    SAMPLE_RATE = float(os.environ.get("OTEL_SAMPLE_RATE", "1.0"))


def _noop_span():
    """Context manager that does nothing (when tracing disabled)."""
    from contextlib import contextmanager

    @contextmanager
    def _inner():
        yield None

    return _inner()


# ==================== METRICS ====================


class _NoopMetric:
    def labels(self, **kwargs):
        return self

    def inc(self, amount=1):
        pass

    def dec(self, amount=1):
        pass

    def observe(self, value):
        pass


def _counter(name: str, desc: str, labels: list):
    if _PROMETHEUS_AVAILABLE and Counter is not None:
        return Counter(name, desc, labels)
    return _NoopMetric()


def _histogram(name: str, desc: str, labels: list, buckets=None):
    if _PROMETHEUS_AVAILABLE and Histogram is not None:
        return Histogram(name, desc, labels, buckets=buckets or [1, 5, 10, 30, 60, 120, 300])
    return _NoopMetric()


def _summary(name: str, desc: str, labels: list):
    if _PROMETHEUS_AVAILABLE and Summary is not None:
        return Summary(name, desc, labels)
    return _NoopMetric()


def _gauge(name: str, desc: str, labels: list):
    if _PROMETHEUS_AVAILABLE and Gauge is not None:
        return Gauge(name, desc, labels)
    return _NoopMetric()


class Metrics:
    """Centralized Prometheus metrics (no-op when prometheus_client not installed)."""

    if _PROMETHEUS_AVAILABLE and Counter is not None and Histogram is not None and Gauge is not None and Summary is not None:
        requests_total = Counter(
            "photogenius_requests_total",
            "Total requests",
            ["mode", "quality_tier", "status"],
        )
        request_duration = Histogram(
            "photogenius_request_duration_seconds",
            "Request duration",
            ["mode", "quality_tier"],
            buckets=[1, 5, 10, 30, 60, 120, 300],
        )
        engine_calls_total = Counter(
            "photogenius_engine_calls_total",
            "Engine invocations",
            ["engine", "status"],
        )
        engine_duration = Histogram(
            "photogenius_engine_duration_seconds",
            "Engine call duration",
            ["engine"],
            buckets=[0.5, 1, 5, 10, 30, 60, 120],
        )
        quality_scores = Summary(
            "photogenius_quality_scores",
            "Image quality scores",
            ["component"],
        )
        face_similarity = Histogram(
            "photogenius_face_similarity",
            "Face similarity scores",
            buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0],
        )
        llm_calls_total = Counter(
            "photogenius_llm_calls_total",
            "LLM API calls",
            ["purpose", "status"],
        )
        llm_tokens_used = Counter(
            "photogenius_llm_tokens_used",
            "LLM tokens consumed",
            ["purpose"],
        )
        errors_total = Counter(
            "photogenius_errors_total",
            "Total errors",
            ["error_type", "component"],
        )
        active_requests = Gauge(
            "photogenius_active_requests",
            "Currently active requests",
            ["mode"],
        )
        cache_hits = Counter(
            "photogenius_cache_hits_total",
            "Cache hits",
            ["cache_type"],
        )
        cache_misses = Counter(
            "photogenius_cache_misses_total",
            "Cache misses",
            ["cache_type"],
        )
        # Task 5.1: Phase metrics for production readiness
        aesthetic_guidance_time_ms = Histogram(
            "photogenius_aesthetic_guidance_time_ms",
            "Aesthetic guidance phase duration in milliseconds",
            [],
            buckets=[10, 25, 50, 100, 200, 500, 1000, 2000],
        )
        validation_first_try_success_total = Counter(
            "photogenius_validation_first_try_success_total",
            "Validation first-try successes",
            ["category"],
        )
        validation_first_try_total = Counter(
            "photogenius_validation_first_try_total",
            "Validation first-try attempts",
            ["category"],
        )
        refinement_loops = Summary(
            "photogenius_refinement_loops",
            "Refinement loops per request",
            ["category"],
        )
        constraint_solver_execution_time_ms = Histogram(
            "photogenius_constraint_solver_execution_time_ms",
            "Constraint solver execution time in milliseconds",
            [],
            buckets=[1, 5, 10, 25, 50, 100, 250, 500],
        )
        typography_ocr_success_total = Counter(
            "photogenius_typography_ocr_success_total",
            "Typography OCR verifications passed",
            [],
        )
        typography_ocr_total = Counter(
            "photogenius_typography_ocr_total",
            "Typography OCR verification attempts",
            [],
        )
        math_validation_success_total = Counter(
            "photogenius_math_validation_success_total",
            "Math formula validations passed",
            [],
        )
        math_validation_total = Counter(
            "photogenius_math_validation_total",
            "Math formula validation attempts",
            [],
        )
    else:
        requests_total = _NoopMetric()
        request_duration = _NoopMetric()
        engine_calls_total = _NoopMetric()
        engine_duration = _NoopMetric()
        quality_scores = _NoopMetric()
        face_similarity = _NoopMetric()
        llm_calls_total = _NoopMetric()
        llm_tokens_used = _NoopMetric()
        errors_total = _NoopMetric()
        active_requests = _NoopMetric()
        cache_hits = _NoopMetric()
        cache_misses = _NoopMetric()
        aesthetic_guidance_time_ms = _NoopMetric()
        validation_first_try_success_total = _NoopMetric()
        validation_first_try_total = _NoopMetric()
        refinement_loops = _NoopMetric()
        constraint_solver_execution_time_ms = _NoopMetric()
        typography_ocr_success_total = _NoopMetric()
        typography_ocr_total = _NoopMetric()
        math_validation_success_total = _NoopMetric()
        math_validation_total = _NoopMetric()


# ==================== STRUCTURED LOGGING ====================


@dataclass
class LogContext:
    """Structured log context."""

    request_id: str
    user_id: Optional[str] = None
    mode: Optional[str] = None
    quality_tier: Optional[str] = None
    identity_id: Optional[str] = None
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class StructuredLogger:
    """Logger with structured JSON context and request ID propagation."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _build_message(self, msg: str, context: Optional[Dict[str, Any]] = None) -> str:
        log_context = LogContext(
            request_id=get_request_id() or "no-request-id",
            timestamp=time.time(),
        )
        extra: Dict[str, Any] = {}
        if context:
            for key, value in context.items():
                if hasattr(log_context, key):
                    setattr(log_context, key, value)
                else:
                    extra[key] = value
        structured: Dict[str, Any] = {"message": msg, "context": log_context.to_dict()}
        if extra:
            structured["extra"] = extra
        return json.dumps(structured, default=str)

    def info(self, msg: str, **context: Any) -> None:
        self.logger.info(self._build_message(msg, context if context else None))

    def warning(self, msg: str, **context: Any) -> None:
        self.logger.warning(self._build_message(msg, context if context else None))

    def error(self, msg: str, **context: Any) -> None:
        self.logger.error(self._build_message(msg, context if context else None))

    def debug(self, msg: str, **context: Any) -> None:
        self.logger.debug(self._build_message(msg, context if context else None))


# ==================== REQUEST TRACKING ====================


class RequestTracker:
    """Track request lifecycle and propagate request ID."""

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or self._generate_request_id()
        self.start_time = time.time()
        self.metadata: Dict[str, Any] = {}

    @staticmethod
    def _generate_request_id() -> str:
        return f"req_{uuid.uuid4().hex[:16]}"

    def __enter__(self) -> "RequestTracker":
        request_id_ctx.set(self.request_id)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        request_id_ctx.set(None)

    def set_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value

    def get_duration(self) -> float:
        return time.time() - self.start_time


# ==================== TRACING SETUP ====================


def setup_tracing() -> bool:
    """
    Initialize OpenTelemetry tracing when OTLP endpoint is configured.
    Returns True if tracing is active, False otherwise.
    """
    if not _OTEL_AVAILABLE or not _OTLP_AVAILABLE:
        logger.debug("OpenTelemetry not available; tracing disabled")
        return False
    endpoint = TracingConfig.OTLP_ENDPOINT
    if not endpoint or endpoint == "http://localhost:4317":
        use_otlp = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT"
        )
        if not use_otlp and not TracingConfig.ENABLE_CONSOLE_EXPORT:
            logger.debug("OTLP endpoint not configured; tracing disabled")
            return False
        endpoint = use_otlp or "http://localhost:4317"
    try:
        if Resource is None or trace is None:
            return False
        resource = Resource.create(
            {"service.name": TracingConfig.SERVICE_NAME, "service.version": "2.0"}
        )
        provider = TracerProvider(resource=resource)
        if endpoint and OTLPSpanExporter is not None:
            insecure = "localhost" in endpoint or "127.0.0.1" in endpoint
            otlp = OTLPSpanExporter(endpoint=endpoint.replace("http://", "").replace("https://", "").rstrip("/"), insecure=insecure)
            provider.add_span_processor(BatchSpanProcessor(otlp))
        if TracingConfig.ENABLE_CONSOLE_EXPORT and ConsoleSpanExporter is not None:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        if trace is not None:
            trace.set_tracer_provider(provider)
        logger.info("Tracing initialized: %s", TracingConfig.SERVICE_NAME)
        return True
    except Exception as e:
        logger.warning("Tracing setup failed: %s", e)
        return False


def get_tracer():
    """Return tracer (no-op when tracing disabled)."""
    if _OTEL_AVAILABLE and trace is not None:
        return trace.get_tracer("photogenius.observability", "2.0")
    return None


def setup_metrics() -> bool:
    """No-op; metrics use default registry. Kept for API compatibility."""
    return True


# Initialize tracer (used by decorators)
_tracer = get_tracer() if _OTEL_AVAILABLE else None


def tracked_engine_call(engine_name: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run fn with engine metrics and optional tracing. Use when @track_engine_call cannot be used."""
    start_time = time.time()
    status = "success"

    def _run() -> Any:
        return fn(*args, **kwargs)

    try:
        if _tracer is not None:
            with _tracer.start_as_current_span(f"engine.{engine_name}") as span:
                span.set_attribute("engine", engine_name)
                req_id = get_request_id()
                if req_id:
                    span.set_attribute("request_id", req_id)
                try:
                    result = _run()
                    span.set_attribute("duration_seconds", time.time() - start_time)
                    if Status is not None and StatusCode is not None:
                        span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    status = "error"
                    if Status is not None and StatusCode is not None:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    try:
                        Metrics.errors_total.labels(
                            error_type=type(e).__name__, component=engine_name
                        ).inc()
                    except Exception:
                        pass
                    raise
        else:
            return _run()
    except Exception as e:
        status = "error"
        if _tracer is None:
            try:
                Metrics.errors_total.labels(
                    error_type=type(e).__name__, component=engine_name
                ).inc()
            except Exception:
                pass
        raise
    finally:
        duration = time.time() - start_time
        try:
            Metrics.engine_calls_total.labels(engine=engine_name, status=status).inc()
            Metrics.engine_duration.labels(engine=engine_name).observe(duration)
        except Exception:
            pass


# ==================== DECORATORS ====================


def trace_function(name: Optional[str] = None) -> Callable:
    """Decorator to trace function execution with OpenTelemetry."""

    def decorator(func: Callable):
        span_name = name or f"{getattr(func, '__module__', '')}.{func.__name__}"

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if _tracer is None:
                return func(*args, **kwargs)
            with _tracer.start_as_current_span(span_name) as span:
                req_id = request_id_ctx.get()
                if req_id:
                    span.set_attribute("request_id", req_id)
                span.set_attribute("function", func.__name__)
                t0 = time.time()
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("duration_seconds", time.time() - t0)
                    if Status is not None and StatusCode is not None:
                        span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    if Status is not None and StatusCode is not None:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        return wrapper

    return decorator


def track_engine_call(engine_name: str) -> Callable:
    """Decorator to track engine calls with metrics and optional tracing."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            status = "success"
            try:
                if _tracer is not None:
                    with _tracer.start_as_current_span(f"engine.{engine_name}") as span:
                        span.set_attribute("engine", engine_name)
                        req_id = get_request_id()
                        if req_id:
                            span.set_attribute("request_id", req_id)
                        try:
                            result = func(*args, **kwargs)
                            span.set_attribute("duration_seconds", time.time() - start_time)
                            if Status is not None and StatusCode is not None:
                                span.set_status(Status(StatusCode.OK))
                            return result
                        except Exception as e:
                            status = "error"
                            if Status is not None and StatusCode is not None:
                                span.set_status(Status(StatusCode.ERROR, str(e)))
                            span.record_exception(e)
                            try:
                                Metrics.errors_total.labels(
                                    error_type=type(e).__name__, component=engine_name
                                ).inc()
                            except Exception:
                                pass
                            raise
                else:
                    return func(*args, **kwargs)
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                try:
                    Metrics.engine_calls_total.labels(
                        engine=engine_name,
                        status=status,
                    ).inc()
                    Metrics.engine_duration.labels(engine=engine_name).observe(duration)
                except Exception:
                    pass

        return wrapper

    return decorator


def track_llm_call(purpose: str) -> Callable:
    """Decorator to track LLM API calls (tokens, success/error)."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from contextlib import nullcontext

            created_span = None
            span_ctx = None
            if _tracer is not None:
                created_span = _tracer.start_span(f"llm.{purpose}")
                created_span.set_attribute("llm_purpose", purpose)
                span_ctx = trace.use_context(trace.set_span_in_context(created_span)) if trace is not None else nullcontext()
            else:
                span_ctx = nullcontext()

            status = "success"
            tokens_used = 0
            try:
                with span_ctx:
                    result = func(*args, **kwargs)
                    if isinstance(result, dict) and "usage" in result:
                        u = result["usage"]
                        tokens_used = u.get("total_tokens") or (
                            (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
                        )
                    else:
                        usage_obj = getattr(result, "usage", None)
                        if usage_obj is not None:
                            tokens_used = getattr(usage_obj, "input_tokens", 0) + getattr(
                                usage_obj, "output_tokens", 0
                            )
                    if created_span is not None and created_span.is_recording() and tokens_used:
                        created_span.set_attribute("tokens_used", int(tokens_used))
                    return result
            except Exception as e:
                status = "error"
                if created_span is not None and created_span.is_recording():
                    created_span.record_exception(e)
                    if Status is not None and StatusCode is not None:
                        created_span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
            finally:
                try:
                    Metrics.llm_calls_total.labels(purpose=purpose, status=status).inc()
                    if tokens_used > 0:
                        Metrics.llm_tokens_used.labels(purpose=purpose).inc(int(tokens_used))
                except Exception:
                    pass
                if created_span is not None:
                    created_span.end()

        return wrapper

    return decorator


# ==================== CIRCUIT BREAKER ====================


class CircuitBreakerState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 2


class CircuitBreaker:
    """Circuit breaker for external dependencies (e.g. Claude, engines)."""

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.logger = StructuredLogger(f"circuit_breaker.{name}")

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time is not None and (
                time.time() - self.last_failure_time >= self.config.recovery_timeout
            ):
                self.logger.info("Circuit entering half-open state", name=self.name)
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
            else:
                raise RuntimeError(f"Circuit breaker {self.name} is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self) -> None:
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.logger.info("Circuit closing (recovered)", name=self.name)
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def _on_failure(self, error: Exception) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.logger.warning("Circuit reopening (still failing)", name=self.name)
            self.state = CircuitBreakerState.OPEN
        elif self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.logger.error("Circuit opening (threshold reached)", name=self.name)
                self.state = CircuitBreakerState.OPEN
        try:
            Metrics.errors_total.labels(
                error_type=type(error).__name__,
                component=self.name,
            ).inc()
        except Exception:
            pass


# ==================== RETRY WITH BACKOFF ====================


def retry_with_backoff(
    max_retries: int = 3,
    backoff_base: float = 0.5,
    jitter: bool = True,
) -> Callable:
    """Decorator for exponential backoff retry."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import random

            last_exc: Optional[Exception] = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt == max_retries:
                        logger.error(
                            "Max retries (%d) exceeded for %s",
                            max_retries,
                            func.__name__,
                            exc_info=True,
                        )
                        raise
                    wait_time = backoff_base * (2**attempt)
                    if jitter:
                        wait_time *= 0.5 + random.random()
                    logger.warning(
                        "Retry %d/%d for %s after %.2fs: %s",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        wait_time,
                        e,
                    )
                    time.sleep(wait_time)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# ==================== PHASE METRICS HELPERS (Task 5.1) ====================


def record_aesthetic_guidance_time_ms(ms: float) -> None:
    """Record aesthetic guidance phase duration in milliseconds."""
    try:
        Metrics.aesthetic_guidance_time_ms.observe(ms)
    except Exception:
        pass


def record_validation_first_try(category: str, success: bool) -> None:
    """Record validation first-try result (by category for success rate)."""
    try:
        cat = category or "unknown"
        Metrics.validation_first_try_total.labels(category=cat).inc()
        if success:
            Metrics.validation_first_try_success_total.labels(category=cat).inc()
    except Exception:
        pass


def record_refinement_loops(category: str, count: float) -> None:
    """Record refinement loops per request (for avg)."""
    try:
        Metrics.refinement_loops.labels(category=category or "unknown").observe(count)
    except Exception:
        pass


def record_constraint_solver_time_ms(ms: float) -> None:
    """Record constraint solver execution time in milliseconds."""
    try:
        Metrics.constraint_solver_execution_time_ms.observe(ms)
    except Exception:
        pass


def record_typography_ocr(success: bool) -> None:
    """Record typography OCR verification result."""
    try:
        Metrics.typography_ocr_total.inc()
        if success:
            Metrics.typography_ocr_success_total.inc()
    except Exception:
        pass


def record_math_validation(success: bool) -> None:
    """Record math formula validation result."""
    try:
        Metrics.math_validation_total.inc()
        if success:
            Metrics.math_validation_success_total.inc()
    except Exception:
        pass


def get_validation_first_try_success_rate_by_category() -> Dict[str, float]:
    """Return current success rate by category (from Prometheus registry if available)."""
    try:
        if not _PROMETHEUS_AVAILABLE:
            return {}
        from prometheus_client import REGISTRY  # type: ignore[reportMissingImports]
        acc: Dict[str, List[float]] = {}
        for metric in REGISTRY.collect():
            if metric.name == "photogenius_validation_first_try_success_total":
                for s in metric.samples:
                    cat = s.labels.get("category", "unknown")
                    if cat not in acc:
                        acc[cat] = [0.0, 0.0]
                    acc[cat][0] += s.value
            elif metric.name == "photogenius_validation_first_try_total":
                for s in metric.samples:
                    cat = s.labels.get("category", "unknown")
                    if cat not in acc:
                        acc[cat] = [0.0, 0.0]
                    acc[cat][1] += s.value
        return {cat: (a / b if b else 0.0) for cat, (a, b) in acc.items()}
    except Exception:
        return {}


# ==================== PRODUCTION CIRCUIT BREAKERS (Task 5.1) ====================

# Sliding window: (timestamp, success)
_VALIDATION_WINDOW: deque = deque(maxlen=5000)
_TYPOGRAPHY_WINDOW: deque = deque(maxlen=5000)
_CIRCUIT_LOCK = Lock()

# Config (env)
CIRCUIT_VALIDATION_FAILURE_RATE_THRESHOLD = float(os.environ.get("CIRCUIT_VALIDATION_FAILURE_RATE_THRESHOLD", "0.20"))
CIRCUIT_VALIDATION_WINDOW_SECONDS = float(os.environ.get("CIRCUIT_VALIDATION_WINDOW_SECONDS", "300"))  # 5 min
CIRCUIT_TYPOGRAPHY_FAILURE_RATE_THRESHOLD = float(os.environ.get("CIRCUIT_TYPOGRAPHY_FAILURE_RATE_THRESHOLD", "0.30"))
CIRCUIT_TYPOGRAPHY_WINDOW_SECONDS = float(os.environ.get("CIRCUIT_TYPOGRAPHY_WINDOW_SECONDS", "300"))
CIRCUIT_SNS_ALERT_TOPIC_ARN = os.environ.get("CIRCUIT_SNS_ALERT_TOPIC_ARN", "")

# State: when True, auto-validation is disabled / typography fallback to no-text
_auto_validation_disabled_until: Optional[float] = None
_typography_no_text_fallback_until: Optional[float] = None
_RECOVERY_COOLDOWN_SECONDS = 600  # 10 min before re-enabling


def _trim_window(window: deque, window_seconds: float) -> None:
    now = time.time()
    while window and (now - window[0][0]) > window_seconds:
        window.popleft()


def record_validation_result(success: bool) -> None:
    """Record a validation attempt for circuit breaker (sliding 5-min window)."""
    with _CIRCUIT_LOCK:
        _VALIDATION_WINDOW.append((time.time(), success))
        _trim_window(_VALIDATION_WINDOW, CIRCUIT_VALIDATION_WINDOW_SECONDS)


def record_typography_ocr_result(success: bool) -> None:
    """Record typography OCR attempt for circuit breaker."""
    with _CIRCUIT_LOCK:
        _TYPOGRAPHY_WINDOW.append((time.time(), success))
        _trim_window(_TYPOGRAPHY_WINDOW, CIRCUIT_TYPOGRAPHY_WINDOW_SECONDS)


def _failure_rate(window: deque) -> float:
    if not window:
        return 0.0
    failures = sum(1 for _, s in window if not s)
    return failures / len(window)


def _check_validation_circuit() -> bool:
    """Return True if auto-validation should be disabled (circuit open)."""
    global _auto_validation_disabled_until
    with _CIRCUIT_LOCK:
        _trim_window(_VALIDATION_WINDOW, CIRCUIT_VALIDATION_WINDOW_SECONDS)
        if len(_VALIDATION_WINDOW) < 10:
            return False
        rate = _failure_rate(_VALIDATION_WINDOW)
        if rate > CIRCUIT_VALIDATION_FAILURE_RATE_THRESHOLD:
            _auto_validation_disabled_until = time.time() + _RECOVERY_COOLDOWN_SECONDS
            _send_sns_alert(
                "PhotoGenius Auto-Validation Circuit Open",
                f"Validation first-try failure rate {rate:.1%} exceeded threshold {CIRCUIT_VALIDATION_FAILURE_RATE_THRESHOLD:.0%} over last {CIRCUIT_VALIDATION_WINDOW_SECONDS/60:.0f} min. Auto-validation disabled for {_RECOVERY_COOLDOWN_SECONDS/60:.0f} min.",
            )
            return True
        return False


def _check_typography_circuit() -> bool:
    """Return True if typography should fall back to no-text mode."""
    global _typography_no_text_fallback_until
    with _CIRCUIT_LOCK:
        _trim_window(_TYPOGRAPHY_WINDOW, CIRCUIT_TYPOGRAPHY_WINDOW_SECONDS)
        if len(_TYPOGRAPHY_WINDOW) < 10:
            return False
        rate = _failure_rate(_TYPOGRAPHY_WINDOW)
        if rate > CIRCUIT_TYPOGRAPHY_FAILURE_RATE_THRESHOLD:
            _typography_no_text_fallback_until = time.time() + _RECOVERY_COOLDOWN_SECONDS
            _send_sns_alert(
                "PhotoGenius Typography OCR Circuit Open",
                f"Typography OCR failure rate {rate:.1%} exceeded threshold {CIRCUIT_TYPOGRAPHY_FAILURE_RATE_THRESHOLD:.0%}. Falling back to no-text mode for {_RECOVERY_COOLDOWN_SECONDS/60:.0f} min.",
            )
            return True
        return False


def _send_sns_alert(subject: str, message: str) -> None:
    """Send alert to SNS topic when CIRCUIT_SNS_ALERT_TOPIC_ARN is set."""
    if not CIRCUIT_SNS_ALERT_TOPIC_ARN:
        logger.warning("SNS alert skipped (no CIRCUIT_SNS_ALERT_TOPIC_ARN): %s", subject)
        return
    try:
        import boto3
        client = boto3.client("sns")
        client.publish(
            TopicArn=CIRCUIT_SNS_ALERT_TOPIC_ARN,
            Subject=subject[:100],
            Message=message,
        )
    except Exception as e:
        logger.warning("SNS alert failed: %s", e)


def is_auto_validation_disabled() -> bool:
    """True if circuit breaker has disabled auto-validation (call this before running validation)."""
    global _auto_validation_disabled_until
    if _auto_validation_disabled_until is not None and time.time() < _auto_validation_disabled_until:
        return True
    if _check_validation_circuit():
        return True
    return False


def is_typography_no_text_fallback() -> bool:
    """True if typography should skip overlay and use no-text mode (call before typography)."""
    global _typography_no_text_fallback_until
    if _typography_no_text_fallback_until is not None and time.time() < _typography_no_text_fallback_until:
        return True
    if _check_typography_circuit():
        return True
    return False


# ==================== PUSH GATEWAY (OPTIONAL) ====================


def push_metrics_to_gateway(job: str = "photogenius-orchestrator") -> None:
    """Push Prometheus metrics to Pushgateway when PUSHGATEWAY_URL is set (e.g. Modal)."""
    url = os.environ.get("PUSHGATEWAY_URL")
    if not url or not _PROMETHEUS_AVAILABLE:
        return
    try:
        from prometheus_client import REGISTRY, push_to_gateway  # type: ignore[reportMissingImports]

        push_to_gateway(url, job=job, registry=REGISTRY)
    except Exception as e:
        logger.debug("Pushgateway push failed: %s", e)


# ==================== WEEKLY AUTOMATED REPORTS (Task 5.1) ====================

def build_weekly_metrics_report(
    metrics_by_category: Optional[Dict[str, Dict[str, Any]]] = None,
    metrics_by_tier: Optional[Dict[str, Dict[str, Any]]] = None,
    metrics_by_segment: Optional[Dict[str, Dict[str, Any]]] = None,
    validation_first_try_rate: Optional[float] = None,
    refinement_loops_avg: Optional[float] = None,
    typography_ocr_accuracy: Optional[float] = None,
    math_validation_pass_rate: Optional[float] = None,
    aesthetic_guidance_time_p50_ms: Optional[float] = None,
    constraint_solver_time_p50_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Build a weekly summary of key metrics for email report.
    Caller should pass aggregated metrics (e.g. from CloudWatch or Prometheus query).
    Returns dict suitable for JSON or HTML email body.
    """
    report: Dict[str, Any] = {
        "period": "weekly",
        "summary": {},
        "by_category": metrics_by_category or {},
        "by_tier": metrics_by_tier or {},
        "by_user_segment": metrics_by_segment or {},
    }
    if validation_first_try_rate is not None:
        report["summary"]["validation_first_try_success_rate"] = round(validation_first_try_rate, 4)
    if refinement_loops_avg is not None:
        report["summary"]["refinement_loops_avg"] = round(refinement_loops_avg, 2)
    if typography_ocr_accuracy is not None:
        report["summary"]["typography_ocr_accuracy"] = round(typography_ocr_accuracy, 4)
    if math_validation_pass_rate is not None:
        report["summary"]["math_validation_pass_rate"] = round(math_validation_pass_rate, 4)
    if aesthetic_guidance_time_p50_ms is not None:
        report["summary"]["aesthetic_guidance_time_p50_ms"] = round(aesthetic_guidance_time_p50_ms, 0)
    if constraint_solver_time_p50_ms is not None:
        report["summary"]["constraint_solver_time_p50_ms"] = round(constraint_solver_time_p50_ms, 0)
    return report


def send_weekly_report_email(
    report: Dict[str, Any],
    to_emails: Optional[List[str]] = None,
    from_email: Optional[str] = None,
) -> bool:
    """
    Send weekly report via AWS SES. Requires WEEKLY_REPORT_TO_EMAILS (comma-separated)
    and optionally WEEKLY_REPORT_FROM_EMAIL. Returns True if sent.
    """
    to_list = to_emails or (os.environ.get("WEEKLY_REPORT_TO_EMAILS") or "").strip().split(",")
    to_list = [e.strip() for e in to_list if e.strip()]
    if not to_list:
        logger.info("Weekly report not sent: no WEEKLY_REPORT_TO_EMAILS")
        return False
    from_addr = from_email or os.environ.get("WEEKLY_REPORT_FROM_EMAIL", "noreply@photogenius.local")
    try:
        import boto3
        client = boto3.client("ses")
        body = json.dumps(report, indent=2)
        html = f"<pre>{body}</pre>"
        client.send_email(
            Source=from_addr,
            Destination={"ToAddresses": to_list},
            Message={
                "Subject": {"Data": "PhotoGenius Weekly Metrics Report", "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body, "Charset": "UTF-8"},
                    "Html": {"Data": html, "Charset": "UTF-8"},
                },
            },
        )
        logger.info("Weekly report sent to %s", to_list)
        return True
    except Exception as e:
        logger.warning("Weekly report email failed: %s", e)
        return False

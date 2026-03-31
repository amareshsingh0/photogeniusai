# Observability (Reliability & Request Tracing)

Request tracing, correlation IDs, metrics, and structured logging for the PhotoGenius AI pipeline.

## Features

- **Request ID** – `request_id_ctx`, `get_request_id()`, `set_request_id()`, `RequestTracker`
- **Structured logging** – `StructuredLogger` with JSON context and request ID
- **Prometheus metrics** – `Metrics` (requests, engines, LLM, errors, cache, etc.)
- **OpenTelemetry** – Optional distributed tracing; `setup_tracing()`, `trace_function`, `track_engine_call`, `track_llm_call`
- **Helpers** – `tracked_engine_call(engine_name, fn)` for one-off engine calls, `CircuitBreaker`, `retry_with_backoff`

## Usage

```python
from services.observability import (
    RequestTracker,
    StructuredLogger,
    Metrics,
    get_request_id,
    setup_tracing,
    setup_metrics,
    trace_function,
    track_engine_call,
    track_llm_call,
    tracked_engine_call,
    retry_with_backoff,
)

setup_tracing()
setup_metrics()
log = StructuredLogger(__name__)

with RequestTracker() as t:
    log.info("started", mode="REALISM", quality_tier="BALANCED")
    # ... do work ...
    Metrics.requests_total.labels(mode="REALISM", quality_tier="BALANCED", status="success").inc()
```

## Orchestrator Integration

- `orchestrate` uses `RequestTracker`, `Metrics` (active_requests, requests_total, request_duration), and `StructuredLogger`.
- All successful returns include `request_id` when observability is available.
- Realtime/ultra engine calls are wrapped with `tracked_engine_call`; `_parse_prompt` and `_llm_rerank` use `@track_llm_call`.

## Docker Observability Stack

Run Jaeger, Prometheus, and Grafana:

```bash
docker compose -f infra/docker/docker-compose.observability.yml up -d
```

- **Jaeger UI**: http://localhost:16686  
- **Prometheus**: http://localhost:9090  
- **Grafana**: http://localhost:3010 (admin / admin)

Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` (and `OTEL_ENABLED=1` if required) to export traces to Jaeger.

## Env

- `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_CONSOLE_EXPORT`, `OTEL_SAMPLE_RATE`
- `PUSHGATEWAY_URL` – optional; `push_metrics_to_gateway()` pushes to Prometheus Pushgateway.

## Dependencies

- `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc` (optional)
- `prometheus_client`

If Otel or Prometheus are missing, tracing/metrics degrade gracefully (no-op).

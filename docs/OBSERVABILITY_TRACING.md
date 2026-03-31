# Observability & Distributed Tracing

PhotoGenius uses **correlation IDs** (X-Request-ID) and **structured logging** for full-stack tracing. Optional: **OpenTelemetry** and **AWS X-Ray** for distributed traces.

## Correlation ID flow

1. **Frontend / Next.js**  
   Middleware generates or forwards `X-Request-ID` (UUID). All API routes attach it to responses and pass it to backends.

2. **Next.js API routes**  
   `getCorrelationId(req)` reads the header; `correlationId` is stored on `Generation` and sent to Lambda/FastAPI in headers and body.

3. **API Gateway → Lambda**  
   Configure the API to forward the header (e.g. request mapping: `X-Request-ID` → Lambda event). Lambda reads it from `event.headers["x-request-id"]` or `body.correlation_id`, logs with it, and passes `correlation_id` to SageMaker in the payload. Response includes `X-Request-ID`.

4. **SageMaker**  
   Endpoint code can read `correlation_id` from the request and log it with predictions for trace continuity.

5. **Database**  
   `Generation.correlationId` stores the ID so you can look up a generation by correlation ID and then search logs.

## Structured logging

- **Format:** JSON with `timestamp`, `level`, `service`, `correlation_id` (when present), `message`, and optional metadata.
- **Web (Node):** `apps/web/lib/logger.ts` — use `logger.info(message, correlationId, meta)` in API routes.
- **Lambda (Python):** `aws/lambda/generation/handler.py` — `_log(level, message, correlation_id, **meta)` prints JSON.
- **ai-pipeline (Python):** `ai-pipeline/monitoring/structured_logger.py` — structlog with `bind_correlation_id()`; logs include `correlation_id` from context.

## OpenTelemetry (optional)

The ai-pipeline already has optional OpenTelemetry in `services/observability.py`:

- Set `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`, and optionally `OTEL_CONSOLE_EXPORT`, `OTEL_SAMPLE_RATE`.
- Use `observability.get_tracer()` and create spans; correlation ID can be set as a span attribute for linking logs and traces.

## AWS X-Ray (optional)

To get a single trace for **API Gateway → Lambda → SageMaker**:

1. **Enable X-Ray on API Gateway**  
   In the API stage, enable "AWS X-Ray tracing".

2. **Enable X-Ray on Lambda**  
   Add the Lambda layer `AWSXRaySDKForPython` (or Node equivalent) and enable "Active tracing" on the function. In the handler, use the X-Ray SDK to record subsegments for the SageMaker call and S3 upload.

3. **SageMaker**  
   SageMaker can propagate the trace header if the endpoint forwards it; otherwise the trace will show Lambda → SageMaker as a single segment.

4. **View traces**  
   In **AWS X-Ray → Traces**, filter by response time or by annotation (e.g. correlation_id if you add it as an annotation in Lambda).

## Runbooks

- **Debug a failed generation:** `docs/runbooks/OBSERVABILITY_RUNBOOKS.md` (§ 1)  
- **Find slow requests:** `docs/runbooks/OBSERVABILITY_RUNBOOKS.md` (§ 2)  
- **Trace S3 upload failures:** `docs/runbooks/OBSERVABILITY_RUNBOOKS.md` (§ 3)

## CloudWatch

- **Observability dashboard:** `aws/monitoring/observability-dashboard.json` — Lambda metrics and Logs Insights query snippets for correlation_id.
- **Pipeline dashboard:** `aws/monitoring/dashboard.json` — validation, refinement, and request/error metrics.

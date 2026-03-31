/**
 * Correlation ID for full-stack tracing.
 * Use X-Request-ID header: generate if missing, propagate in responses.
 */

const HEADER = "x-request-id";

export function getCorrelationId(request: Request): string {
  const id = request.headers.get(HEADER) ?? request.headers.get("X-Request-ID") ?? crypto.randomUUID();
  return String(id).slice(0, 64);
}

export function correlationIdResponseHeaders(correlationId: string): Record<string, string> {
  return { [HEADER]: correlationId };
}

export { HEADER as CORRELATION_ID_HEADER };

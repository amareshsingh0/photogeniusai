/**
 * Structured JSON logging for CloudWatch Logs Insights.
 * Format: { timestamp, level, service, correlation_id?, message, ...metadata }
 */

type LogLevel = "info" | "warn" | "error" | "debug";

const SERVICE = "web";

function format(level: LogLevel, message: string, correlationId?: string, meta?: Record<string, unknown>): string {
  const entry: Record<string, unknown> = {
    timestamp: new Date().toISOString(),
    level,
    service: SERVICE,
    message,
    ...(correlationId && { correlation_id: correlationId }),
    ...meta,
  };
  return JSON.stringify(entry);
}

export const logger = {
  info(message: string, correlationId?: string, meta?: Record<string, unknown>): void {
    console.log(format("info", message, correlationId, meta));
  },
  warn(message: string, correlationId?: string, meta?: Record<string, unknown>): void {
    console.warn(format("warn", message, correlationId, meta));
  },
  error(message: string, correlationId?: string, meta?: Record<string, unknown>): void {
    console.error(format("error", message, correlationId, meta));
  },
  debug(message: string, correlationId?: string, meta?: Record<string, unknown>): void {
    if (process.env.NODE_ENV === "development") {
      console.debug(format("debug", message, correlationId, meta));
    }
  },
};

// Re-export prisma client from the database package
// This ensures we use the same generated Prisma client across the monorepo
export { prisma } from "@photogenius/database";
export { prisma as default } from "@photogenius/database";

/**
 * True when the Prisma/DB error is transient — safe to return [] / no-op instead of 500.
 * Covers:
 *   P1001               — DB unreachable (connection refused)
 *   PrismaClientInitializationError — init failure
 *   PostgreSQL 57014    — statement_timeout (index missing / cold connection)
 *   "canceling statement" — same timeout in different Prisma wrapping
 */
export function isPrismaDbUnavailable(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const e = error as { name?: string; code?: string; message?: string };
  if (e.code === "P1001") return true;
  const msg = String(e.message ?? "").toLowerCase();
  // PostgreSQL statement_timeout (57014) — treat as temporary, return empty not 500
  if (msg.includes("57014") || msg.includes("statement timeout") || msg.includes("canceling statement")) return true;
  return e.name === "PrismaClientInitializationError" && msg.includes("can't reach");
}

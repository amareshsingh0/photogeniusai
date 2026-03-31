/**
 * Biometric compliance: log access to identity (face embeddings / LoRA) for audit trail.
 */

import { prisma } from "@/lib/db";

export type IdentityAccessAction = "VIEW" | "EXPORT" | "DELETE" | "TRAIN";

export async function logIdentityAccess(params: {
  identityId: string;
  userId: string;
  action: IdentityAccessAction;
  req?: Request;
}): Promise<void> {
  try {
    const ip = params.req?.headers?.get("x-forwarded-for")?.split(",")[0]?.trim()
      ?? params.req?.headers?.get("x-real-ip") ?? null;
    const userAgent = params.req?.headers?.get("user-agent") ?? null;
    await prisma.identityAccessAuditLog.create({
      data: {
        identityId: params.identityId,
        userId: params.userId,
        action: params.action,
        ipAddress: ip,
        userAgent: userAgent,
      },
    });
  } catch {
    // Do not fail the request if audit log fails
  }
}

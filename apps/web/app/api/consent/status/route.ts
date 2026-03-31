import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/consent/status
 * Returns whether user has a consent record and granular flags (for "first generation" modal).
 */
export async function GET() {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({
        hasRecord: false,
        allowTraining: false,
        allowShowcase: false,
        showModal: false,
      });
    }

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });
    if (!dbUser) {
      return NextResponse.json({
        hasRecord: false,
        allowTraining: false,
        allowShowcase: false,
        showModal: false,
      });
    }

    const latest = await prisma.consentRecord.findFirst({
      where: { userId: dbUser.id, withdrawnAt: null },
      orderBy: { timestamp: "desc" },
      select: { allowTraining: true, allowShowcase: true },
    });

    const hasRecord = !!latest;
    const allowTraining = latest?.allowTraining ?? false;
    const allowShowcase = latest?.allowShowcase ?? false;

    return NextResponse.json({
      hasRecord,
      allowTraining,
      allowShowcase,
      showModal: !hasRecord,
    });
  } catch (e) {
    console.error("[consent/status]", e);
    return NextResponse.json(
      { hasRecord: false, allowTraining: false, allowShowcase: false, showModal: false },
      { status: 500 }
    );
  }
}

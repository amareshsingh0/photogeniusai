import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * POST /api/consent/withdraw
 * GDPR: User withdraws consent. We mark latest consent as withdrawn and stop using data for training.
 */
export async function POST() {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });
    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const updated = await prisma.consentRecord.updateMany({
      where: { userId: dbUser.id, withdrawnAt: null },
      data: { withdrawnAt: new Date() },
    });

    return NextResponse.json({
      success: true,
      withdrawn: updated.count,
      message: "Consent withdrawn. Your data will not be used for training.",
    });
  } catch (e) {
    console.error("[consent/withdraw]", e);
    return NextResponse.json(
      { success: false, error: "Failed to withdraw consent" },
      { status: 500 }
    );
  }
}

import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

const CONSENT_VERSION = "1.0.0";
const OPT_IN_CREDITS = 100;

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const { userId: clerkId } = await auth();

    if (!clerkId) {
      return NextResponse.json({ success: true, anonymous: true });
    }

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });

    if (!dbUser) {
      return NextResponse.json({ success: true, pending: true });
    }

    const ipAddress =
      req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
      req.headers.get("x-real-ip") ??
      "unknown";
    const userAgent = req.headers.get("user-agent") ?? "unknown";

    const allowTraining = Boolean(body?.allowTraining);
    const allowShowcase = Boolean(body?.allowShowcase);

    const previousWithCredits = await prisma.consentRecord.findFirst({
      where: { userId: dbUser.id, creditsGranted: true },
    });
    const grantCredits = allowTraining && !previousWithCredits;

    await prisma.$transaction(async (tx) => {
      await tx.consentRecord.create({
        data: {
          userId: dbUser.id,
          consentVersion: (body?.version as string) ?? CONSENT_VERSION,
          checkboxesChecked: Array.isArray(body?.checkboxes) ? body.checkboxes : [],
          consentText: (body?.text as string) ?? undefined,
          allowTraining,
          allowShowcase,
          creditsGranted: grantCredits,
          ipAddress,
          userAgent,
        },
      });
      if (grantCredits) {
        await tx.user.update({
          where: { id: dbUser.id },
          data: { creditsBalance: { increment: OPT_IN_CREDITS } },
        });
      }
    });

    return NextResponse.json({
      success: true,
      creditsGranted: grantCredits ? OPT_IN_CREDITS : 0,
      allowTraining,
      allowShowcase,
    });
  } catch (e) {
    console.error("[consent/record]", e);
    return NextResponse.json(
      { success: false, error: "Failed to record consent" },
      { status: 500 }
    );
  }
}

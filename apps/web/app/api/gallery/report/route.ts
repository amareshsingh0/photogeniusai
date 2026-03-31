import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

const ALLOWED_REASONS = [
  "NSFW",
  "HATE",
  "VIOLENCE",
  "CELEBRITY",
  "COPYRIGHT",
  "OTHER",
] as const;

/**
 * POST /api/gallery/report – report a gallery item (generation).
 * Body: { generationId, reason, description? }
 */
export async function POST(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    const dbUser = await prisma.user.findUnique({
      where: { clerkId: clerkId ?? "" },
      select: { id: true },
    });

    const body = (await req.json().catch(() => ({}))) as {
      generationId?: string;
      reason?: string;
      description?: string;
    };

    const generationId = body.generationId;
    if (!generationId || typeof generationId !== "string") {
      return NextResponse.json(
        { error: "generationId required" },
        { status: 400 }
      );
    }

    const reason: (typeof ALLOWED_REASONS)[number] =
      (body.reason && ALLOWED_REASONS.includes(body.reason as (typeof ALLOWED_REASONS)[number]))
        ? (body.reason as (typeof ALLOWED_REASONS)[number])
        : "OTHER";
    const description =
      typeof body.description === "string"
        ? body.description.trim().slice(0, 500)
        : null;

    const gen = await prisma.generation.findFirst({
      where: {
        id: generationId,
        isPublic: true,
        isDeleted: false,
      },
      select: { id: true },
    });

    if (!gen) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    await prisma.abuseReport.create({
      data: {
        generationId,
        reporterUserId: dbUser?.id ?? undefined,
        reason,
        description,
        status: "PENDING",
      },
    });

    return NextResponse.json({ ok: true, reported: true });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: "Failed to submit report" },
      { status: 500 }
    );
  }
}

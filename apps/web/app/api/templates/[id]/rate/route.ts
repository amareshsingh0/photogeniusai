import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * POST /api/templates/[id]/rate – rate a template 1–5 (auth required).
 */
export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
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

    const { id: templateId } = await params;
    const body = (await req.json().catch(() => ({}))) as { rating?: number };
    const rating = Math.min(5, Math.max(1, Math.round(Number(body.rating) || 0)));

    const template = await prisma.promptTemplate.findFirst({
      where: { id: templateId, isPublic: true },
      select: { id: true, ratingSum: true, ratingCount: true },
    });

    if (!template) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const existing = await prisma.templateRating.findUnique({
      where: { userId_templateId: { userId: dbUser.id, templateId } },
      select: { id: true, rating: true },
    });

    const delta = existing ? rating - existing.rating : rating;
    const countDelta = existing ? 0 : 1;

    if (existing) {
      await prisma.templateRating.update({
        where: { id: existing.id },
        data: { rating },
      });
    } else {
      await prisma.templateRating.create({
        data: { userId: dbUser.id, templateId, rating },
      });
    }

    await prisma.promptTemplate.update({
      where: { id: templateId },
      data: {
        ratingSum: { increment: delta },
        ratingCount: { increment: countDelta },
      },
    });

    return NextResponse.json({ ok: true, rating });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json({ error: "Database unavailable" }, { status: 503 });
    }
    return NextResponse.json({ error: "Failed to rate" }, { status: 500 });
  }
}

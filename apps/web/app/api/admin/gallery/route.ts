import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    const dbUser = await prisma.user.findUnique({ where: { clerkId }, select: { id: true } });
    if (!dbUser) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

    const { searchParams } = new URL(req.url);
    const status = searchParams.get("status") ?? "PENDING";
    const limit = Math.min(Number(searchParams.get("limit")) || 20, 50);
    const cursor = searchParams.get("cursor") ?? undefined;
    const validStatus = ["PENDING", "APPROVED", "REJECTED", "FLAGGED"].includes(status) ? status : "PENDING";

    const rows = await prisma.generation.findMany({
      where: { isPublic: true, galleryModeration: validStatus as any, isDeleted: false },
      take: limit + 1,
      ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
      orderBy: { publishedAt: "desc" },
      select: {
        id: true,
        originalPrompt: true,
        selectedOutputUrl: true,
        outputUrls: true,
        publishedAt: true,
        galleryModeration: true,
        userId: true,
        user: { select: { name: true, displayName: true } },
      },
    });

    const nextCursor = rows.length > limit ? rows[limit - 1]?.id : null;
    const list = rows.slice(0, limit);
    return NextResponse.json({
      items: list.map((g) => ({
        id: g.id,
        prompt: g.originalPrompt,
        url: g.selectedOutputUrl ?? (Array.isArray(g.outputUrls) ? g.outputUrls[0] : null),
        publishedAt: g.publishedAt?.toISOString() ?? null,
        status: g.galleryModeration,
        userId: g.userId,
        userName: g.user?.displayName ?? g.user?.name ?? null,
      })),
      nextCursor,
    });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ error: "Database unavailable" }, { status: 503 });
    return NextResponse.json({ error: "Failed to list" }, { status: 500 });
  }
}

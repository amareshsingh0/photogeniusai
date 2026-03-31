import { NextResponse } from "next/server";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id: userId } = await params;
    const limit = Math.min(Number(new URL(req.url).searchParams.get("limit")) || 20, 50);
    const cursor = new URL(req.url).searchParams.get("cursor");
    const rows = await prisma.activity.findMany({
      where: { userId },
      take: limit + 1,
      ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
      orderBy: { createdAt: "desc" },
      select: { id: true, type: true, targetType: true, targetId: true, metadata: true, createdAt: true },
    });
    const nextCursor = rows.length > limit ? rows[limit - 1]?.id : null;
    return NextResponse.json({
      activities: rows.slice(0, limit).map((a) => ({ id: a.id, type: a.type, targetType: a.targetType, targetId: a.targetId, metadata: a.metadata, createdAt: a.createdAt.toISOString() })),
      nextCursor,
    });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ activities: [], nextCursor: null });
    return NextResponse.json({ error: "Failed to load activity" }, { status: 500 });
  }
}

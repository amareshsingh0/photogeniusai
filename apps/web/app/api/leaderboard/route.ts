import { NextResponse } from "next/server";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const type = new URL(req.url).searchParams.get("type") ?? "templates";
    const limit = Math.min(Number(new URL(req.url).searchParams.get("limit")) || 10, 50);

    if (type === "templates") {
      const templates = await prisma.promptTemplate.findMany({
        where: { isPublic: true },
        orderBy: { usesCount: "desc" },
        take: limit,
        select: { id: true, name: true, usesCount: true, successCount: true, ratingSum: true, ratingCount: true, user: { select: { displayName: true, name: true } } },
      });
      return NextResponse.json({
        leaderboard: templates.map((t) => ({
          id: t.id,
          name: t.name,
          usesCount: t.usesCount,
          successRate: t.usesCount > 0 ? t.successCount / t.usesCount : 0,
          rating: t.ratingCount > 0 ? t.ratingSum / t.ratingCount : null,
          creatorName: t.user?.displayName ?? t.user?.name ?? "Anonymous",
        })),
      });
    }

    if (type === "creators") {
      const gens = await prisma.generation.findMany({
        where: { isPublic: true, galleryModeration: "APPROVED", isDeleted: false },
        select: { userId: true, galleryLikesCount: true, user: { select: { id: true, name: true, displayName: true, profileImageUrl: true } } },
      });
      const byUser = new Map<string, { id: string; name: string; profileImageUrl: string | null; totalLikes: number; count: number }>();
      for (const g of gens) {
        const u = g.user;
        if (!u) continue;
        const cur = byUser.get(u.id);
        const likes = g.galleryLikesCount ?? 0;
        if (!cur) byUser.set(u.id, { id: u.id, name: u.displayName ?? u.name ?? "Anonymous", profileImageUrl: u.profileImageUrl ?? null, totalLikes: likes, count: 1 });
        else { cur.totalLikes += likes; cur.count += 1; }
      }
      const sorted = [...byUser.values()].sort((a, b) => b.totalLikes - a.totalLikes).slice(0, limit);
      return NextResponse.json({ leaderboard: sorted });
    }

    return NextResponse.json({ leaderboard: [] });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ leaderboard: [] });
    return NextResponse.json({ error: "Failed to load leaderboard" }, { status: 500 });
  }
}

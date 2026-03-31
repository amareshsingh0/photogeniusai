import { NextResponse } from "next/server";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

const SORTS = ["recent", "trending", "top_rated"] as const;
type Sort = (typeof SORTS)[number];

/**
 * GET /api/gallery – public gallery (no auth).
 * Query: category, style, sort=recent|trending|top_rated, limit, cursor
 */
export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const category = searchParams.get("category") ?? undefined;
    const style = searchParams.get("style") ?? undefined;
    const sort = (searchParams.get("sort") as Sort) || "recent";
    const limit = Math.min(Number(searchParams.get("limit")) || 24, 48);
    const cursor = searchParams.get("cursor") ?? undefined;

    const orderBy: Record<string, "asc" | "desc"> =
      sort === "top_rated"
        ? { galleryLikesCount: "desc" }
        : sort === "trending"
          ? { galleryLikesCount: "desc", publishedAt: "desc" }
          : { publishedAt: "desc" };

    const where = {
      isPublic: true,
      isDeleted: false,
      isQuarantined: false,
      galleryModeration: "APPROVED" as const,
      ...(category ? { galleryCategory: category } : {}),
      ...(style ? { galleryStyle: style } : {}),
    };

    const items = await prisma.generation.findMany({
      where,
      take: limit + 1,
      ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
      orderBy,
      select: {
        id: true,
        originalPrompt: true,
        mode: true,
        selectedOutputUrl: true,
        thumbnailUrl: true,
        outputUrls: true,
        galleryCategory: true,
        galleryStyle: true,
        galleryLikesCount: true,
        galleryCommentsCount: true,
        publishedAt: true,
        user: {
          select: {
            id: true,
            name: true,
            profileImageUrl: true,
            displayName: true,
          },
        },
      },
    });

    const nextCursor =
      items.length > limit ? items[limit - 1]?.id : undefined;
    const list = items.slice(0, limit);

    const payload = list.map((g) => ({
      id: g.id,
      prompt: g.originalPrompt,
      mode: g.mode,
      url: g.selectedOutputUrl ?? (Array.isArray(g.outputUrls) ? g.outputUrls[0] : null),
      thumbnailUrl: g.thumbnailUrl ?? undefined,
      category: g.galleryCategory ?? undefined,
      style: g.galleryStyle ?? undefined,
      likesCount: g.galleryLikesCount ?? 0,
      commentsCount: g.galleryCommentsCount ?? 0,
      publishedAt: g.publishedAt?.toISOString() ?? null,
      user: g.user
        ? {
            id: g.user.id,
            name: g.user.displayName ?? g.user.name ?? "Anonymous",
            profileImageUrl: g.user.profileImageUrl ?? undefined,
          }
        : null,
    }));

    return NextResponse.json({
      items: payload,
      nextCursor: nextCursor ?? null,
    });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json({ items: [], nextCursor: null });
    }
    return NextResponse.json(
      { error: "Failed to load gallery" },
      { status: 500 }
    );
  }
}

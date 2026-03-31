import { prisma } from "@/lib/db";
import ExploreClient from "@/app/explore/ExploreClient";
import { FEATURED_SEED } from "@/app/explore/featured-seed";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Explore | PhotoGenius AI",
  description: "Discover AI-generated images from the PhotoGenius community.",
};

const LIMIT = 24;
const wherePublic = {
  isPublic: true,
  isDeleted: false,
  isQuarantined: false,
  galleryModeration: "APPROVED" as const,
};

export default async function ExplorePage() {
  type GalleryItem = {
    id: string;
    prompt: string;
    mode: string;
    url: string | null;
    thumbnailUrl?: string | null;
    category?: string | null;
    style?: string | null;
    likesCount: number;
    commentsCount: number;
    publishedAt: string | null;
    user: { id: string; name: string; profileImageUrl?: string | null } | null;
  };

  let items: GalleryItem[] = [];
  let nextCursor: string | null = null;
  let activityToday = 0;

  try {
    const startOfToday = new Date();
    startOfToday.setHours(0, 0, 0, 0);

    const [rows, todayCount] = await Promise.all([
      prisma.generation.findMany({
        where: wherePublic,
        take: LIMIT + 1,
        orderBy: { publishedAt: "desc" } as object,
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
      }) as unknown as Array<{
        id: string;
        originalPrompt: string;
        mode: string;
        selectedOutputUrl: string | null;
        thumbnailUrl: string | null;
        outputUrls: unknown;
        galleryCategory: string | null;
        galleryStyle: string | null;
        galleryLikesCount: number;
        galleryCommentsCount: number;
        publishedAt: Date | null;
        user: { id: string; name: string | null; profileImageUrl: string | null; displayName: string | null } | null;
      }>,
      prisma.generation.count({
        where: { ...wherePublic, publishedAt: { gte: startOfToday } },
      }),
    ]);

    activityToday = todayCount;
    nextCursor = rows.length > LIMIT ? rows[LIMIT - 1]?.id ?? null : null;
    items = rows.slice(0, LIMIT).map((g) => ({
      id: g.id,
      prompt: g.originalPrompt,
      mode: g.mode,
      url: g.selectedOutputUrl ?? (Array.isArray(g.outputUrls) ? (g.outputUrls[0] as string) : null),
      thumbnailUrl: g.thumbnailUrl ?? null,
      category: g.galleryCategory ?? null,
      style: g.galleryStyle ?? null,
      likesCount: g.galleryLikesCount ?? 0,
      commentsCount: g.galleryCommentsCount ?? 0,
      publishedAt: g.publishedAt?.toISOString() ?? null,
      user: g.user
        ? { id: g.user.id, name: (g.user.displayName ?? g.user.name ?? "Anonymous") as string, profileImageUrl: g.user.profileImageUrl ?? null }
        : null,
    }));
  } catch {
    // leave items empty, show featured seed
  }

  const displayItems =
    items.length > 0
      ? items
      : FEATURED_SEED.map((s) => ({
          id: s.id,
          prompt: s.prompt,
          mode: s.mode,
          url: s.url,
          thumbnailUrl: s.thumbnailUrl ?? null,
          category: s.category ?? null,
          style: s.style ?? null,
          likesCount: s.likesCount,
          commentsCount: s.commentsCount,
          publishedAt: s.publishedAt,
          user: s.user,
        }));

  const showFeaturedLabel = items.length === 0;

  return (
    <div className="max-w-7xl mx-auto">
      <ExploreClient
        initialItems={displayItems}
        initialNextCursor={items.length > 0 ? nextCursor : null}
        activityToday={activityToday}
        showFeaturedLabel={showFeaturedLabel}
      />
    </div>
  );
}

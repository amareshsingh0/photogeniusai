import { NextResponse } from "next/server";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

const wherePublic = {
  isPublic: true,
  isDeleted: false,
  isQuarantined: false,
  galleryModeration: "APPROVED" as const,
};

/**
 * GET /api/gallery/explore-activity
 * Returns counts for Explore header: today and last hour (approximate).
 */
export async function GET() {
  try {
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const startOfLastHour = new Date(now.getTime() - 60 * 60 * 1000);

    const [todayCount, lastHourCount] = await Promise.all([
      prisma.generation.count({
        where: {
          ...wherePublic,
          publishedAt: { gte: startOfToday },
        },
      }),
      prisma.generation.count({
        where: {
          ...wherePublic,
          publishedAt: { gte: startOfLastHour },
        },
      }),
    ]);

    return NextResponse.json({
      todayCount,
      lastHourCount,
    });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json({ todayCount: 0, lastHourCount: 0 });
    }
    return NextResponse.json(
      { error: "Failed to load activity" },
      { status: 500 }
    );
  }
}

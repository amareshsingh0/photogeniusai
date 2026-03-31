import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

const DELETE_AFTER_DAYS = 15;

/**
 * GET /api/gallery/stats
 * Returns gallery storage stats for current user (matches Python backend GET /api/v1/gallery/stats).
 * - total: total generations (non-deleted)
 * - favoritesCount: generations marked favorite (protected from auto-cleanup)
 * - eligibleForDeletion: count of non-favorite generations older than DELETE_AFTER_DAYS
 * - cutoffDate: ISO date string for eligibility cutoff
 */
export async function GET() {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({
        total: 0,
        favoritesCount: 0,
        eligibleForDeletion: 0,
        cutoffDate: null,
      });
    }

    const dbUser = await prisma.user.findUnique({
      where: { clerkId: userId },
      select: { id: true },
    });

    if (!dbUser) {
      return NextResponse.json({
        total: 0,
        favoritesCount: 0,
        eligibleForDeletion: 0,
        cutoffDate: null,
      });
    }

    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - DELETE_AFTER_DAYS);

    const [total, favoritesCount, eligibleForDeletion] = await Promise.all([
      prisma.generation.count({
        where: { userId: dbUser.id, isDeleted: false },
      }),
      prisma.generation.count({
        where: { userId: dbUser.id, isDeleted: false, isFavorite: true },
      }),
      prisma.generation.count({
        where: {
          userId: dbUser.id,
          isDeleted: false,
          isFavorite: false,
          createdAt: { lt: cutoffDate },
        },
      }),
    ]);

    return NextResponse.json({
      total,
      favoritesCount,
      eligibleForDeletion,
      cutoffDate: cutoffDate.toISOString(),
    });
  } catch (e) {
    if (!isPrismaDbUnavailable(e)) {
      console.error("[api/gallery/stats]", e);
    }
    // Return empty stats (not 500) so the gallery page still loads
    return NextResponse.json({
      total: 0,
      favoritesCount: 0,
      eligibleForDeletion: 0,
      cutoffDate: null,
    });
  }
}

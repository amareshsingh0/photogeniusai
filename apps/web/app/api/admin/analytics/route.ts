import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/admin-auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/admin/analytics - Get system analytics
 */
export async function GET() {
  try {
    await requireAdmin();

    // Get date ranges
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const thisWeek = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const thisMonth = new Date(now.getFullYear(), now.getMonth(), 1);

    // Parallel queries for better performance
    const [
      totalUsers,
      totalGenerations,
      todayGenerations,
      weekGenerations,
      monthGenerations,
      activeUsers,
      totalCreditsUsed,
      generationsByTier,
      generationsByBucket,
      recentGenerations,
      userGrowth,
    ] = await Promise.all([
      // Total users
      prisma.user.count(),

      // Total generations
      prisma.generation.count(),

      // Today's generations
      prisma.generation.count({
        where: { createdAt: { gte: today } },
      }),

      // This week's generations
      prisma.generation.count({
        where: { createdAt: { gte: thisWeek } },
      }),

      // This month's generations
      prisma.generation.count({
        where: { createdAt: { gte: thisMonth } },
      }),

      // Active users (generated in last 7 days)
      prisma.user.count({
        where: {
          generations: {
            some: {
              createdAt: { gte: thisWeek },
            },
          },
        },
      }),

      // Total credits used (approximate from generations)
      prisma.generation.aggregate({
        _sum: { creditsUsed: true },
      }),

      // Generations by tier
      prisma.generation.groupBy({
        by: ["qualityTierUsed"],
        where: { qualityTierUsed: { not: null } },
        _count: true,
      }),

      // Generations by bucket
      prisma.generation.groupBy({
        by: ["bucket"],
        where: { bucket: { not: null } },
        _count: true,
      }),

      // Recent generations
      prisma.generation.findMany({
        take: 10,
        orderBy: { createdAt: "desc" },
        select: {
          id: true,
          originalPrompt: true,
          qualityTierUsed: true,
          bucket: true,
          createdAt: true,
          user: {
            select: {
              email: true,
              name: true,
            },
          },
        },
      }),

      // User growth (last 30 days) - simplified to avoid raw SQL table name issues
      Promise.resolve([]),
    ]);

    // Calculate average generations per user
    const avgGenerationsPerUser =
      totalUsers > 0 ? (totalGenerations / totalUsers).toFixed(2) : 0;

    // Calculate daily average (last 7 days)
    const dailyAverage = (weekGenerations / 7).toFixed(2);

    return NextResponse.json({
      overview: {
        totalUsers,
        totalGenerations,
        activeUsers,
        totalCreditsUsed: totalCreditsUsed._sum.creditsUsed || 0,
        avgGenerationsPerUser,
        dailyAverage,
      },
      generations: {
        today: todayGenerations,
        week: weekGenerations,
        month: monthGenerations,
      },
      breakdown: {
        byTier: generationsByTier.map((item) => ({
          tier: item.qualityTierUsed || "unknown",
          count: item._count,
        })),
        byBucket: generationsByBucket.map((item) => ({
          bucket: item.bucket || "unknown",
          count: item._count,
        })),
      },
      recent: recentGenerations,
      userGrowth,
    });
  } catch (error: any) {
    console.error("[admin/analytics] Error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to fetch analytics" },
      { status: error.message?.includes("Admin") ? 403 : 500 }
    );
  }
}

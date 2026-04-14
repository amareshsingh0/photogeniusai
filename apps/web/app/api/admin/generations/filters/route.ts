import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/admin-auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/admin/generations/filters - Get filter options
 */
export async function GET() {
  try {
    await requireAdmin();

    // Get unique values for filters
    const [users, models, buckets, qualities] = await Promise.all([
      // All users who have generated images
      prisma.user.findMany({
        where: {
          generations: {
            some: { isDeleted: false },
          },
        },
        select: {
          id: true,
          email: true,
          name: true,
        },
        orderBy: { email: "asc" },
      }),

      // Unique models used
      prisma.generation.groupBy({
        by: ["modelUsed"],
        where: {
          isDeleted: false,
          modelUsed: { not: null },
        },
        _count: { modelUsed: true },
      }),

      // Unique buckets
      prisma.generation.groupBy({
        by: ["bucket"],
        where: {
          isDeleted: false,
          bucket: { not: null },
        },
        _count: { bucket: true },
      }),

      // Unique quality tiers
      prisma.generation.groupBy({
        by: ["qualityTierUsed"],
        where: {
          isDeleted: false,
          qualityTierUsed: { not: null },
        },
        _count: { qualityTierUsed: true },
      }),
    ]);

    return NextResponse.json({
      users,
      models: models.map((m) => ({
        value: m.modelUsed,
        count: m._count.modelUsed,
      })),
      buckets: buckets.map((b) => ({
        value: b.bucket,
        count: b._count.bucket,
      })),
      qualities: qualities.map((q) => ({
        value: q.qualityTierUsed,
        count: q._count.qualityTierUsed,
      })),
    });
  } catch (error: any) {
    console.error("[admin/generations/filters] Error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to fetch filter options" },
      { status: error.message?.includes("Admin") ? 403 : 500 }
    );
  }
}

import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = 'force-dynamic';

/**
 * GET /api/dashboard/stats – credits, images generated, identities count.
 * Returns zeros when not authenticated.
 */
export async function GET() {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({
        credits: 0,
        imagesGenerated: 0,
        identitiesCount: 0,
      });
    }

    // First get the database user by Clerk ID
    const dbUser = await prisma.user.findUnique({
      where: { clerkId: userId },
      select: { id: true, creditsBalance: true },
    });

    if (!dbUser) {
      return NextResponse.json({
        credits: 0,
        imagesGenerated: 0,
        identitiesCount: 0,
      });
    }

    const [genCount, identityCount, costAgg, cacheHits] = await Promise.all([
      prisma.generation.count({ where: { userId: dbUser.id } }),
      prisma.identity.count({ where: { userId: dbUser.id } }),
      prisma.generation.aggregate({
        where: { userId: dbUser.id, costUsd: { not: null } },
        _sum: { costUsd: true },
      }),
      prisma.generation.count({ where: { userId: dbUser.id, cacheHit: true } }),
    ]);

    const totalCostUsd = costAgg._sum.costUsd ?? 0;
    const cacheHitRate = genCount > 0 ? cacheHits / genCount : 0;

    return NextResponse.json({
      credits: dbUser.creditsBalance ?? 0,
      imagesGenerated: genCount,
      identitiesCount: identityCount,
      totalCostUsd: Math.round(totalCostUsd * 1e6) / 1e6,
      cacheHits,
      cacheHitRate: Math.round(cacheHitRate * 100) / 100,
    });
  } catch (e) {
    console.error("[api/dashboard/stats]", e);
    return NextResponse.json(
      { error: "Failed to fetch stats" },
      { status: 500 }
    );
  }
}

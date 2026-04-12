import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/user/stats
 * Alias for /api/dashboard/stats — returns credits, generationsCount, identitiesCount.
 */
export async function GET() {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ credits: 0, generationsCount: 0, identitiesCount: 0 });
    }

    const dbUser = await prisma.user.findUnique({
      where: { id: userId },
      select: { id: true, creditsBalance: true },
    });

    if (!dbUser) {
      return NextResponse.json({ credits: 0, generationsCount: 0, identitiesCount: 0 });
    }

    const [generationsCount, identitiesCount] = await Promise.all([
      prisma.generation.count({ where: { userId: dbUser.id } }),
      prisma.identity.count({ where: { userId: dbUser.id } }),
    ]);

    return NextResponse.json({
      credits: dbUser.creditsBalance ?? 0,
      generationsCount,
      identitiesCount,
    });
  } catch (e) {
    console.error("[api/user/stats]", e);
    return NextResponse.json({ credits: 0, generationsCount: 0, identitiesCount: 0 });
  }
}

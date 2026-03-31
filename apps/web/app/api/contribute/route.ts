import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

const CREDITS_PER_CONTRIBUTION = 5;
const QUALITY_THRESHOLD = 0.8;
const QUALITY_MULTIPLIER = 2;
const TIER_BONUSES = [
  { at: 100, credits: 500 },
  { at: 1000, credits: 10000 },
];

export async function GET(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) return NextResponse.json({ optedIn: false, totalContributions: 0, totalCreditsEarned: 0, tier: 0 });
    const dbUser = await prisma.user.findUnique({ where: { clerkId }, select: { id: true, allowTrainingExport: true } });
    if (!dbUser) return NextResponse.json({ optedIn: false, totalContributions: 0, totalCreditsEarned: 0, tier: 0 });
    const contributions = await prisma.dataContribution.findMany({
      where: { userId: dbUser.id },
      select: { creditsEarned: true },
    });
    const totalContributions = contributions.length;
    const totalCreditsEarned = contributions.reduce((s, c) => s + c.creditsEarned, 0);
    let tier = 0;
    for (let i = TIER_BONUSES.length - 1; i >= 0; i--) {
      if (totalContributions >= TIER_BONUSES[i].at) {
        tier = i + 1;
        break;
      }
    }
    return NextResponse.json({
      optedIn: !!dbUser.allowTrainingExport,
      totalContributions,
      totalCreditsEarned,
      tier,
      nextTierAt: tier < TIER_BONUSES.length ? TIER_BONUSES[tier].at : null,
      nextTierCredits: tier < TIER_BONUSES.length ? TIER_BONUSES[tier].credits : null,
    });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ optedIn: false, totalContributions: 0, totalCreditsEarned: 0, tier: 0 });
    return NextResponse.json({ error: "Failed to load" }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    const dbUser = await prisma.user.findUnique({ where: { clerkId }, select: { id: true, allowTrainingExport: true, creditsBalance: true } });
    if (!dbUser) return NextResponse.json({ error: "User not found" }, { status: 404 });
    const body = (await req.json().catch(() => ({}))) as { optIn?: boolean };
    if (typeof body.optIn !== "boolean") return NextResponse.json({ error: "optIn boolean required" }, { status: 400 });
    await prisma.user.update({
      where: { id: dbUser.id },
      data: { allowTrainingExport: body.optIn },
    });
    return NextResponse.json({ ok: true, optedIn: body.optIn });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ error: "Database unavailable" }, { status: 503 });
    return NextResponse.json({ error: "Failed to update" }, { status: 500 });
  }
}

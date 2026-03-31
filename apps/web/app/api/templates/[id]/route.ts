import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const t = await prisma.promptTemplate.findFirst({
      where: { id, isPublic: true },
      select: { id: true, name: true, prompt: true, negativePrompt: true, suggestedSettings: true, priceType: true, priceCredits: true, usesCount: true, successCount: true, ratingSum: true, ratingCount: true, createdAt: true, user: { select: { id: true, name: true, displayName: true } } },
    });
    if (!t) return NextResponse.json({ error: "Not found" }, { status: 404 });
    return NextResponse.json({
      id: t.id,
      name: t.name,
      prompt: t.prompt,
      negativePrompt: t.negativePrompt ?? undefined,
      suggestedSettings: t.suggestedSettings ?? undefined,
      priceType: t.priceType,
      priceCredits: t.priceCredits,
      usesCount: t.usesCount,
      successRate: t.usesCount > 0 ? t.successCount / t.usesCount : 0,
      rating: t.ratingCount > 0 ? t.ratingSum / t.ratingCount : null,
      ratingCount: t.ratingCount,
      createdAt: t.createdAt.toISOString(),
      creator: t.user ? { id: t.user.id, name: t.user.displayName ?? t.user.name ?? "Anonymous" } : null,
    });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ error: "Database unavailable" }, { status: 503 });
    return NextResponse.json({ error: "Failed to load template" }, { status: 500 });
  }
}

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const template = await prisma.promptTemplate.findFirst({
      where: { id, isPublic: true },
      select: { id: true, userId: true, priceType: true, priceCredits: true, usesCount: true, successCount: true },
    });
    if (!template) return NextResponse.json({ error: "Not found" }, { status: 404 });
    const body = (await req.json().catch(() => ({}))) as { success?: boolean };
    const success = body.success === true;

    if (template.priceType === "PREMIUM" && template.priceCredits > 0) {
      const { userId: clerkId } = await auth();
      if (!clerkId) return NextResponse.json({ error: "Sign in to use premium template" }, { status: 401 });
      const dbUser = await prisma.user.findUnique({ where: { clerkId }, select: { id: true, creditsBalance: true } });
      if (!dbUser || (dbUser.creditsBalance ?? 0) < template.priceCredits) return NextResponse.json({ error: "Insufficient credits" }, { status: 400 });
      const creatorShare = Math.floor(template.priceCredits * 0.7);
      const platformShare = template.priceCredits - creatorShare;
      await prisma.$transaction([
        prisma.user.update({ where: { id: dbUser.id }, data: { creditsBalance: { decrement: template.priceCredits } } }),
        prisma.user.update({ where: { id: template.userId }, data: { creditsBalance: { increment: creatorShare } } }),
        prisma.promptTemplate.update({ where: { id }, data: { usesCount: { increment: 1 }, ...(success ? { successCount: { increment: 1 } } : {}) } }),
        prisma.templatePurchase.create({ data: { userId: dbUser.id, templateId: id, creditsPaid: template.priceCredits, creatorEarned: creatorShare, platformEarned: platformShare } }),
      ]);
    } else {
      await prisma.promptTemplate.update({
        where: { id },
        data: { usesCount: { increment: 1 }, ...(success ? { successCount: { increment: 1 } } : {}) },
      });
    }
    return NextResponse.json({ ok: true, used: true });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ error: "Database unavailable" }, { status: 503 });
    return NextResponse.json({ error: "Failed to use template" }, { status: 500 });
  }
}

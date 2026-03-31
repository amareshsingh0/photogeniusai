import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const u = new URL(req.url);
    const search = u.searchParams.get("search") ?? "";
    const priceType = u.searchParams.get("priceType");
    const sort = u.searchParams.get("sort") ?? "recent";
    const limit = Math.min(Number(u.searchParams.get("limit")) || 20, 50);
    const cursor = u.searchParams.get("cursor");
    const where: { isPublic: boolean; priceType?: "FREE" | "PREMIUM" } = { isPublic: true };
    if (priceType === "FREE" || priceType === "PREMIUM") where.priceType = priceType;
    if (search.trim()) {
      const term = search.trim().slice(0, 100);
      Object.assign(where, { OR: [{ name: { contains: term, mode: "insensitive" } }, { prompt: { contains: term, mode: "insensitive" } }] });
    }
    const orderBy = sort === "popular" ? [{ usesCount: "desc" }, { createdAt: "desc" }] : sort === "rating" ? [{ ratingCount: "desc" }, { ratingSum: "desc" }] : { createdAt: "desc" };
    const rows = await prisma.promptTemplate.findMany({
      where,
      take: limit + 1,
      ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
      orderBy: orderBy as object,
      select: { id: true, name: true, prompt: true, negativePrompt: true, suggestedSettings: true, priceType: true, priceCredits: true, usesCount: true, successCount: true, ratingSum: true, ratingCount: true, createdAt: true, user: { select: { id: true, name: true, displayName: true } } },
    });
    const nextCursor = rows.length > limit ? rows[limit - 1]?.id : null;
    const items = rows.slice(0, limit).map((t) => ({
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
    }));
    return NextResponse.json({ items, nextCursor });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ items: [], nextCursor: null });
    return NextResponse.json({ error: "Failed to list templates" }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    const dbUser = await prisma.user.findUnique({ where: { clerkId }, select: { id: true } });
    if (!dbUser) return NextResponse.json({ error: "User not found" }, { status: 404 });
    const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
    const name = typeof body.name === "string" ? body.name.trim().slice(0, 200) : "";
    const prompt = typeof body.prompt === "string" ? body.prompt.trim().slice(0, 5000) : "";
    if (!name || !prompt) return NextResponse.json({ error: "name and prompt required" }, { status: 400 });
    const priceType = body.priceType === "PREMIUM" ? "PREMIUM" : "FREE";
    const priceCredits = priceType === "PREMIUM" && typeof body.priceCredits === "number" && body.priceCredits >= 0 ? Math.min(body.priceCredits, 10000) : 0;
    const template = await prisma.promptTemplate.create({
      data: {
        userId: dbUser.id,
        name,
        prompt,
        negativePrompt: typeof body.negativePrompt === "string" ? body.negativePrompt.slice(0, 2000) : undefined,
        suggestedSettings: body.suggestedSettings && typeof body.suggestedSettings === "object" ? (body.suggestedSettings as object) : undefined,
        priceType,
        priceCredits,
      },
    });
    return NextResponse.json({ id: template.id, name: template.name, prompt: template.prompt, priceType: template.priceType, priceCredits: template.priceCredits, createdAt: template.createdAt.toISOString() });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ error: "Database unavailable" }, { status: 503 });
    return NextResponse.json({ error: "Failed to create template" }, { status: 500 });
  }
}

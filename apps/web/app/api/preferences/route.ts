import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

const PREFERRED_VALUES = ["A", "B", "EQUAL"] as const;
const SOURCE_VALUES = [
  "EXPLICIT_THUMBS",
  "SAVE_GALLERY",
  "DELETE",
  "DOWNLOAD",
  "REQUEST_VARIANTS",
] as const;

type Preferred = (typeof PREFERRED_VALUES)[number];
type Source = (typeof SOURCE_VALUES)[number];

/**
 * POST /api/preferences – record a pairwise preference (RLHF data collection).
 * Body: { prompt, imageAUrl, imageBUrl, preferred: "A"|"B"|"EQUAL", source, strength?, generationIdA?, generationIdB? }
 */
export async function POST(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });
    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const body = (await req.json()) as {
      prompt: string;
      imageAUrl: string;
      imageBUrl: string;
      preferred: string;
      source: string;
      strength?: number;
      generationIdA?: string;
      generationIdB?: string;
    };

    const prompt = typeof body.prompt === "string" ? body.prompt.trim() : "";
    const imageAUrl = typeof body.imageAUrl === "string" ? body.imageAUrl.trim() : "";
    const imageBUrl = typeof body.imageBUrl === "string" ? body.imageBUrl.trim() : "";
    if (!prompt || !imageAUrl || !imageBUrl) {
      return NextResponse.json(
        { error: "prompt, imageAUrl, imageBUrl required" },
        { status: 400 }
      );
    }

    const preferred = PREFERRED_VALUES.includes(body.preferred as Preferred)
      ? (body.preferred as Preferred)
      : "A";
    const source = SOURCE_VALUES.includes(body.source as Source)
      ? (body.source as Source)
      : "EXPLICIT_THUMBS";

    const strength =
      typeof body.strength === "number" && body.strength >= 0 && body.strength <= 1
        ? body.strength
        : null;
    const generationIdA =
      typeof body.generationIdA === "string" && body.generationIdA ? body.generationIdA : null;
    const generationIdB =
      typeof body.generationIdB === "string" && body.generationIdB ? body.generationIdB : null;

    await prisma.preferencePair.create({
      data: {
        userId: dbUser.id,
        prompt,
        imageAUrl,
        imageBUrl,
        preferred,
        source,
        strength: strength ?? undefined,
        generationIdA: generationIdA ?? undefined,
        generationIdB: generationIdB ?? undefined,
      },
    });

    return NextResponse.json({ success: true });
  } catch (e) {
    console.error("[api/preferences]", e);
    return NextResponse.json(
      { error: "Failed to record preference" },
      { status: 500 }
    );
  }
}

/**
 * GET /api/preferences – return count (for dashboard); optional ?stats=1
 */
export async function GET(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ count: 0, bySource: {} });
    }

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });
    if (!dbUser) {
      return NextResponse.json({ count: 0, bySource: {} });
    }

    const count = await prisma.preferencePair.count({
      where: { userId: dbUser.id },
    });

    const url = new URL(req.url);
    if (url.searchParams.get("stats") === "1") {
      const bySource = await prisma.preferencePair.groupBy({
        by: ["source"],
        where: { userId: dbUser.id },
        _count: true,
      });
      const bySourceMap: Record<string, number> = {};
      for (const row of bySource) {
        bySourceMap[row.source] = row._count;
      }
      return NextResponse.json({ count, bySource: bySourceMap });
    }

    return NextResponse.json({ count });
  } catch (e) {
    console.error("[api/preferences GET]", e);
    return NextResponse.json({ count: 0, bySource: {} }, { status: 500 });
  }
}

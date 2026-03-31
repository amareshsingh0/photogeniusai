import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * POST /api/preferences/thumbs
 * Body: { generationId, imageUrl, thumbs: "up"|"down", style?, bucket?, tier? }
 *
 * Always:
 *   1. Updates Generation.userRating (5=up, 1=down)
 *   2. Updates User.preferences.style_dna (style/bucket/tier weights)
 * Optionally (if a second image exists):
 *   3. Creates a PreferencePair for RLHF
 */
export async function POST(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true, preferences: true },
    });
    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const body = (await req.json()) as {
      generationId?: string;
      imageUrl?: string;
      thumbs: "up" | "down";
      style?: string;
      bucket?: string;
      tier?: string;
    };

    const generationId = (body.generationId ?? "").trim();
    const imageUrl = (body.imageUrl ?? "").trim();
    const thumbs = body.thumbs === "down" ? "down" : "up";
    const style = body.style ?? "Auto";
    const bucket = body.bucket ?? "photorealism";
    const tier = body.tier ?? "balanced";
    const liked = thumbs === "up";
    const rating = liked ? 5 : 1;

    // ── 1. Update Generation.userRating ──────────────────────────────────────
    if (generationId) {
      await prisma.generation
        .updateMany({
          where: { id: generationId, userId: dbUser.id },
          data: { userRating: rating },
        })
        .catch(() => {});
    }

    // ── 2. Update Style DNA ───────────────────────────────────────────────────
    const prefs = (dbUser.preferences as Record<string, unknown>) ?? {};
    const dna = (prefs.style_dna as Record<string, unknown> | undefined) ?? {
      styles: {}, buckets: {}, tiers: {}, liked: 0, disliked: 0,
    };

    const styles = (dna.styles as Record<string, number>) ?? {};
    const buckets = (dna.buckets as Record<string, number>) ?? {};
    const tiers = (dna.tiers as Record<string, number>) ?? {};

    const w = liked ? 1 : -1;
    styles[style] = (styles[style] ?? 0) + w;
    buckets[bucket] = (buckets[bucket] ?? 0) + w;
    tiers[tier] = (tiers[tier] ?? 0) + (liked ? 1 : 0);

    const updatedDna = {
      ...dna,
      styles,
      buckets,
      tiers,
      liked: ((dna.liked as number) ?? 0) + (liked ? 1 : 0),
      disliked: ((dna.disliked as number) ?? 0) + (liked ? 0 : 1),
      last_updated: new Date().toISOString(),
    };

    await prisma.user
      .update({
        where: { id: dbUser.id },
        data: { preferences: { ...prefs, style_dna: updatedDna } },
      })
      .catch(() => {});

    // ── 3. PreferencePair (RLHF — optional, skip if no second image) ──────────
    if (generationId && imageUrl) {
      try {
        const gen = await prisma.generation.findFirst({
          where: { id: generationId, userId: dbUser.id },
          select: { id: true, originalPrompt: true, outputUrls: true },
        });

        if (gen) {
          const prompt = gen.originalPrompt ?? "";
          const urls = Array.isArray(gen.outputUrls) ? (gen.outputUrls as string[]) : [];

          let otherUrl: string | null = null;
          let otherGenerationId: string | null = null;

          for (const u of urls) {
            if (u && u !== imageUrl) { otherUrl = u; break; }
          }
          if (!otherUrl) {
            const otherGen = await prisma.generation.findFirst({
              where: { userId: dbUser.id, originalPrompt: prompt, id: { not: generationId }, isDeleted: false },
              select: { id: true, selectedOutputUrl: true, outputUrls: true },
            });
            if (otherGen) {
              otherUrl = otherGen.selectedOutputUrl ??
                (Array.isArray(otherGen.outputUrls) ? (otherGen.outputUrls[0] as string) : null);
              otherGenerationId = otherGen.id;
            }
          }

          if (otherUrl) {
            const imageAUrl = liked ? imageUrl : otherUrl;
            const imageBUrl = liked ? otherUrl : imageUrl;
            await prisma.preferencePair.create({
              data: {
                userId: dbUser.id,
                prompt,
                imageAUrl,
                imageBUrl,
                preferred: "A",
                source: "EXPLICIT_THUMBS",
                strength: liked ? 0.9 : 0.7,
                generationIdA: liked ? gen.id : otherGenerationId ?? undefined,
                generationIdB: liked ? otherGenerationId ?? undefined : gen.id,
              },
            }).catch(() => {});
          }
        }
      } catch (e) {
        if (!isPrismaDbUnavailable(e)) console.warn("[thumbs] PreferencePair skipped:", e);
      }
    }

    return NextResponse.json({ success: true, style_dna: updatedDna });
  } catch (e) {
    console.error("[api/preferences/thumbs]", e);
    return NextResponse.json({ error: "Failed to record preference" }, { status: 500 });
  }
}

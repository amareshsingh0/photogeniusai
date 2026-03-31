import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";
import { getCorrelationId, correlationIdResponseHeaders } from "@/lib/correlation-id";
import { logger } from "@/lib/logger";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = 'force-dynamic';

/**
 * GET /api/generations – list generations for the current user.
 * Query: mode (REALISM|CREATIVE|ROMANTIC), isFavorite (true|false).
 * Returns [] when not authenticated.
 */
export async function GET(req: Request) {
  const correlationId = getCorrelationId(req);
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json([]);
    }

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });

    if (!dbUser) {
      return NextResponse.json([], { headers: correlationIdResponseHeaders(correlationId) });
    }

    const { searchParams } = new URL(req.url);
    const mode = searchParams.get("mode")?.toUpperCase();
    const isFavoriteParam = searchParams.get("isFavorite");
    const limitParam = parseInt(searchParams.get("limit") ?? "100", 10);
    const limit = Math.min(Math.max(limitParam, 1), 200); // clamp 1-200
    const cursorParam = searchParams.get("cursor"); // createdAt ISO string for cursor pagination

    const validModes = ["REALISM", "CREATIVE", "ROMANTIC", "CINEMATIC", "FASHION", "COOL_EDGY", "ARTISTIC", "MAX_SURPRISE"] as const;
    type ModeValue = typeof validModes[number];

    // Build where using spread — lets Prisma infer the correct enum type for `mode`
    const where = {
      userId: dbUser.id,
      isDeleted: false,
      ...(mode && (validModes as ReadonlyArray<string>).includes(mode) && { mode: mode as ModeValue }),
      ...(isFavoriteParam === "true" && { isFavorite: true }),
      ...(isFavoriteParam === "false" && { isFavorite: false }),
      ...(cursorParam && { createdAt: { lt: new Date(cursorParam) } }),
    };

    const rows = await prisma.generation.findMany({
      where,
      orderBy: { createdAt: "desc" },
      take: limit,
      select: {
        id: true,
        originalPrompt: true,
        mode: true,
        outputUrls: true,
        selectedOutputUrl: true,
        thumbnailUrl: true,
        createdAt: true,
        faceMatchScore: true,
        aestheticScore: true,
        technicalScore: true,
        overallScore: true,
        isPublic: true,
        publishedAt: true,
        galleryModeration: true,
        isFavorite: true,
        identity: {
          select: {
            id: true,
            name: true,
          },
        },
      },
    });

    const generations = rows.map((g: typeof rows[number]) => ({
      id: g.id,
      prompt: g.originalPrompt,
      mode: g.mode,
      outputUrls: g.outputUrls,
      selectedUrl: g.selectedOutputUrl ?? undefined,
      previewUrl: g.thumbnailUrl ?? undefined,
      createdAt: g.createdAt.toISOString(),
      isPublic: g.isPublic ?? false,
      publishedAt: g.publishedAt?.toISOString() ?? null,
      galleryModeration: g.galleryModeration ?? null,
      isFavorite: g.isFavorite ?? false,
      scores: {
        face_match: g.faceMatchScore ?? 0,
        aesthetic: g.aestheticScore ?? 0,
        technical: g.technicalScore ?? 0,
        total: g.overallScore ?? 0,
      },
      identity: g.identity
        ? {
            id: g.identity.id,
            name: g.identity.name ?? "Unnamed Identity",
          }
        : null,
    }));

    return NextResponse.json(generations, { headers: correlationIdResponseHeaders(correlationId) });
  } catch (e: unknown) {
    logger.error("Generations GET failed", correlationId, { error: String(e) });
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json([], { headers: correlationIdResponseHeaders(correlationId) });
    }
    return NextResponse.json(
      { error: "Failed to list generations" },
      { status: 500, headers: correlationIdResponseHeaders(correlationId) }
    );
  }
}

/**
 * POST /api/generations – create a generation (persist after generate complete).
 * No-op when not authenticated; returns 200 without creating.
 */
export async function POST(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ ok: true, skipped: "no auth" });
    }

    // Get database user by Clerk ID
    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true, allowTrainingExport: true },
    });

    if (!dbUser) {
      return NextResponse.json({ ok: true, skipped: "user not found" });
    }

    const body = (await req.json()) as {
      prompt: string;
      mode: "REALISM" | "CREATIVE" | "ROMANTIC";
      outputUrls: string[];
      selectedUrl?: string;
      faceMatchScore?: number;
      aestheticScore?: number;
      identityId?: string | null;
      creditsUsed?: number;
      costUsd?: number | null;
      qualityTierUsed?: string | null;
      cacheHit?: boolean;
    };

    if (!body.prompt || !Array.isArray(body.outputUrls)) {
      return NextResponse.json(
        { error: "prompt and outputUrls required" },
        { status: 400 }
      );
    }

    const correlationId = getCorrelationId(req);
    const primaryUrl = body.selectedUrl ?? body.outputUrls[0] ?? null;

    const latestConsent = await prisma.consentRecord.findFirst({
      where: { userId: dbUser.id, allowTraining: true, withdrawnAt: null },
      orderBy: { timestamp: "desc" },
      select: { id: true },
    });
    const allowTrainingDataExport = !!latestConsent;

    const gen = await prisma.generation.create({
      data: {
        userId: dbUser.id,
        identityId: body.identityId || null,
        originalPrompt: body.prompt,
        mode: body.mode ?? "REALISM",
        outputUrls: body.outputUrls,
        selectedOutputUrl: primaryUrl,
        faceMatchScore: body.faceMatchScore ?? null,
        aestheticScore: body.aestheticScore ?? null,
        creditsUsed: body.creditsUsed ?? 1,
        allowTrainingDataExport,
        correlationId: correlationId || undefined,
        costUsd: body.costUsd ?? undefined,
        qualityTierUsed: body.qualityTierUsed ?? undefined,
        cacheHit: body.cacheHit ?? false,
      },
    });

    // Data flywheel: award credits for contributed generations (opt-in)
    if (allowTrainingDataExport && dbUser.allowTrainingExport) {
      const baseCredits = 5;
      const score = (body.aestheticScore ?? body.faceMatchScore ?? 0) / 100;
      const qualityBonus = score >= 0.8;
      const creditsEarned = qualityBonus ? baseCredits * 2 : baseCredits;
      try {
        await prisma.dataContribution.create({
          data: { userId: dbUser.id, generationId: gen.id, creditsEarned, qualityBonus },
        });
        await prisma.user.update({
          where: { id: dbUser.id },
          data: { creditsBalance: { increment: creditsEarned } },
        });
      } catch (err) {
        logger.error("Contribution credit failed", correlationId, { error: String(err) });
      }
    }

    logger.info("Generation saved", correlationId, { prompt: body.prompt?.slice(0, 50) });
    return NextResponse.json({ ok: true }, { headers: correlationIdResponseHeaders(correlationId) });
  } catch (e: unknown) {
    logger.error("Generations POST failed", undefined, { error: String(e) });
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json({ ok: true, skipped: "database unavailable" });
    }
    return NextResponse.json(
      { error: "Failed to save generation" },
      { status: 500 }
    );
  }
}

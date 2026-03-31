import { NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import type { Prisma } from "@photogenius/database";
import { prisma } from "@/lib/db";
import { UserRepository } from "@photogenius/database";
import { AIService } from "@/lib/ai-service";
import { getCorrelationId, correlationIdResponseHeaders } from "@/lib/correlation-id";
import { logger } from "@/lib/logger";
import { computeGenerationCost, roundCost, type QualityTier } from "@/lib/cost";
import { getEffectiveTier, classifyPromptComplexity } from "@/lib/prompt-complexity";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = "force-dynamic";

/**
 * POST /api/generate - Generate images via AI Service
 *
 * Supports AWS (default), FastAPI backend, or optional GCP/Lightning.
 * Provider is auto-detected from environment variables.
 *
 * Flow:
 * 1. Authenticate user
 * 2. Sync user to DB if missing (e.g. webhook missed or local dev)
 * 3. Load identity (LoRA + face embedding) if specified
 * 4. Safety check
 * 5. Generate images
 * 6. Save to database with scores
 */
export async function POST(req: Request) {
  const correlationId = getCorrelationId(req);
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401, headers: correlationIdResponseHeaders(correlationId) }
      );
    }

    // Get database user; if missing, sync from Clerk (webhook may not have run)
    let dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });

    if (!dbUser) {
      const clerkUser = await currentUser();
      if (!clerkUser) {
        return NextResponse.json(
          { error: "User not found" },
          { status: 404, headers: correlationIdResponseHeaders(correlationId) }
        );
      }
      const email = clerkUser.emailAddresses?.[0]?.emailAddress;
      if (!email) {
        return NextResponse.json(
          { error: "Email required. Please complete your profile." },
          { status: 400, headers: correlationIdResponseHeaders(correlationId) }
        );
      }
      const newUser = await UserRepository.create({
        clerkId,
        email,
        name: clerkUser.firstName && clerkUser.lastName
          ? `${clerkUser.firstName} ${clerkUser.lastName}`
          : clerkUser.firstName ?? undefined,
        profileImageUrl: clerkUser.imageUrl,
      });
      dbUser = { id: newUser.id };
    }

    const body = await req.json();
    const { prompt, mode, identityId, numImages, quality_tier, style_lora } = body;

    // Validate input
    if (!prompt || prompt.trim().length < 10) {
      return NextResponse.json(
        { error: "Prompt must be at least 10 characters" },
        { status: 400, headers: correlationIdResponseHeaders(correlationId) }
      );
    }

    const trimmedPrompt = prompt.trim();
    const genMode = mode || "REALISM";

    // Smart routing: recommend tier from prompt complexity (can override user choice to save cost)
    const smartRoutingEnabled = process.env.SMART_ROUTING_ENABLED !== "false";
    const userRequestedTier = quality_tier as QualityTier | undefined;
    const { tier: effectiveTier, fromRecommendation, result: complexityResult } = getEffectiveTier(
      {
        prompt: trimmedPrompt,
        hasIdentity: !!(identityId && identityId !== "default"),
        userTier: userRequestedTier ?? "STANDARD",
      },
      { minConfidenceForOverride: 0.78 }
    );
    const quality_tier_to_use = smartRoutingEnabled ? effectiveTier : (userRequestedTier ?? "STANDARD");

    // Two-pass: call AWS Lambda /generate when quality_tier is set and AWS_API_GATEWAY_URL is configured
    const awsApiGatewayUrl = process.env.AWS_API_GATEWAY_URL || process.env.NEXT_PUBLIC_AWS_API_GATEWAY_URL;
    const generatePath = "/generate";
    if (quality_tier_to_use && ["FAST", "STANDARD", "PREMIUM", "PERFECT"].includes(quality_tier_to_use) && awsApiGatewayUrl) {
      const baseUrl = awsApiGatewayUrl.replace(/\/$/, "");
      const url = baseUrl.endsWith(generatePath) ? baseUrl : `${baseUrl}${generatePath}`;
      const tierMap: Record<string, string> = {
        FAST: "standard",
        STANDARD: "standard",
        PREMIUM: "premium",
        PERFECT: "perfect",
      };
      const tier = tierMap[quality_tier_to_use] ?? "standard";
      logger.info("Two-pass generation", correlationId, { tier: quality_tier_to_use, fromRecommendation: smartRoutingEnabled && fromRecommendation, url });
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Request-ID": correlationId,
          },
          body: JSON.stringify({
            prompt: trimmedPrompt,
            tier,
            quality_tier, // Lambda also accepts this and maps to tier
            environment: body.physics === "rainy" ? "rainy" : body.physics === "fantasy" ? "fantasy" : "normal",
            seed: body.seed ?? undefined,
            correlation_id: correlationId,
          }),
        });
        const result = await response.json().catch(() => ({}));
        // API Gateway may wrap: { statusCode, body: "..." }; Lambda returns 200 with image_url, images[]
        let bodyPayload: Record<string, unknown> = result;
        if (typeof result?.body === "string") {
          try {
            bodyPayload = JSON.parse(result.body) as Record<string, unknown>;
          } catch {
            bodyPayload = result;
          }
        }
        if (!response.ok) {
          const errMsg = bodyPayload?.error || bodyPayload?.message || "Generation failed";
          logger.error("Orchestrator error", correlationId, { error: errMsg });
          return NextResponse.json(
            { error: "Generation failed", details: errMsg },
            { status: response.status, headers: correlationIdResponseHeaders(correlationId) }
          );
        }
        // Return shape expected by frontend: images + cost profiling (for POST /api/generations)
        const images = bodyPayload?.images ?? (bodyPayload?.image_url ? [{ url: bodyPayload.image_url, base64: bodyPayload.image_base64 }] : []);
        return NextResponse.json(
          {
            job_id: bodyPayload?.job_id,
            status: bodyPayload?.status ?? "completed",
            image_url: bodyPayload?.image_url,
            image_base64: bodyPayload?.image_base64,
            metadata: bodyPayload?.metadata,
            images,
            cost_usd: bodyPayload?.cost_usd,
            cost_breakdown: bodyPayload?.cost_breakdown,
            quality_tier_used: bodyPayload?.quality_tier_used ?? quality_tier_to_use,
            inference_seconds: bodyPayload?.inference_seconds,
            cache_hit: !!bodyPayload?.cache_hit,
            tier_recommendation: smartRoutingEnabled && fromRecommendation ? {
              recommended_tier: complexityResult.recommendedTier,
              reason: complexityResult.reason,
              savings_fraction: complexityResult.savingsFraction,
            } : undefined,
          },
          { headers: correlationIdResponseHeaders(correlationId) }
        );
      } catch (err) {
        logger.error("Orchestrator request failed", correlationId, { error: String(err) });
        return NextResponse.json(
          { error: err instanceof Error ? err.message : "Orchestrator request failed" },
          { status: 502, headers: correlationIdResponseHeaders(correlationId) }
        );
      }
    }

    const useFastApiBackend =
      process.env.USE_FASTAPI_BACKEND === "true" ||
      process.env.NEXT_PUBLIC_USE_FASTAPI_BACKEND === "true";

    // When using FastAPI backend: single call to /api/v1/generation/sync (safety + generation)
    if (useFastApiBackend) {
      const fastApiUrl = process.env.FASTAPI_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";
      const { getToken } = await auth();
      const token = await getToken();

      const syncRes = await fetch(`${fastApiUrl}/api/v1/generation/sync`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": correlationId,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          prompt: trimmedPrompt,
          mode: genMode,
          identity_id: identityId || null,
          num_images: numImages || 2,
          guidance_scale: 7.5,
          num_inference_steps: 40,
          seed: null,
          correlation_id: correlationId,
        }),
      });

      const syncData = await syncRes.json();

      if (!syncRes.ok) {
        if (syncRes.status === 403) {
          return NextResponse.json(
            {
              error: "Content blocked",
              message: syncData.detail?.error || "Your prompt was blocked by safety filters",
              violations: syncData.detail?.violations || [],
            },
            { status: 403, headers: correlationIdResponseHeaders(correlationId) }
          );
        }
        return NextResponse.json(
          { error: syncData.detail?.error || syncData.detail || "Generation failed" },
          { status: syncRes.status, headers: correlationIdResponseHeaders(correlationId) }
        );
      }

      const images = (syncData.images || []).map((img: { url?: string; seed?: number; scores?: Record<string, number> }) => ({
        url: img.url || "",
        seed: img.seed,
        scores: img.scores,
      }));
      const jobId = syncData.job_id || `gen_${Date.now().toString(36)}`;

      let identity = null;
      if (identityId && identityId !== "default") {
        identity = await prisma.identity.findFirst({
          where: { id: identityId, userId: dbUser.id, trainingStatus: "COMPLETED" },
          select: { id: true },
        });
      }

      if (images.length > 0) {
        try {
          const consentTraining = await prisma.consentRecord.findFirst({
            where: { userId: dbUser.id, allowTraining: true, withdrawnAt: null },
            orderBy: { timestamp: "desc" },
            select: { id: true },
          });
          type GenImage = { url?: string; seed?: number; scores?: Record<string, number> };
          const base = {
              userId: dbUser.id,
              identityId: identity?.id ?? null,
              originalPrompt: trimmedPrompt,
              mode: genMode,
              outputUrls: images.map((img: GenImage) => img.url ?? ""),
              selectedOutputUrl: images[0].url,
              creditsUsed: 1,
              preGenSafetyPassed: true,
              postGenSafetyPassed: true,
              faceMatchScore: images[0].scores?.face_match ?? null,
              aestheticScore: images[0].scores?.aesthetic ?? null,
              technicalScore: images[0].scores?.technical ?? null,
              overallScore: images[0].scores?.total ?? null,
              allowTrainingDataExport: !!consentTraining,
              correlationId: correlationId || undefined,
              metadata: {
                job_id: jobId,
                mode: genMode,
                num_generated: images.length,
                seed: images[0].seed,
                provider: "backend",
                hasIdentity: !!identity?.id,
              },
            };
          await prisma.generation.create({
            data: base as unknown as Prisma.GenerationUncheckedCreateInput,
          });
        } catch (dbError) {
          logger.error("DB save failed", correlationId, { error: String(dbError) });
        }
      }

      return NextResponse.json(
        {
          success: true,
          job_id: jobId,
          status: "completed",
          message: `Generated ${images.length} images`,
          images,
          provider: "backend",
        },
        { headers: correlationIdResponseHeaders(correlationId) }
      );
    }

    // Load identity if specified (for face-consistent generation / identity lock)
    let identity = null;
    let faceEmbedding: number[] | undefined;
    let loraFilePath: string | null = null;

    if (identityId && identityId !== "default") {
      identity = await prisma.identity.findFirst({
        where: {
          id: identityId,
          userId: dbUser.id,
          trainingStatus: "COMPLETED",
        },
        select: {
          id: true,
          faceEmbedding: true,
          loraFilePath: true,
        },
      });

      if (identity) {
        if (identity.faceEmbedding) faceEmbedding = identity.faceEmbedding as number[];
        loraFilePath = identity.loraFilePath;
      }
    }

    // Step 1: Safety check (via AI Service)
    logger.info("Safety check", correlationId, { prompt_preview: trimmedPrompt.slice(0, 50), provider: AIService.getProvider() });

    const safetyResult = await AIService.checkSafety({
      prompt: trimmedPrompt,
      mode: genMode,
    });

    if (!safetyResult.allowed) {
      return NextResponse.json(
        {
          error: "Content blocked",
          message: "Your prompt was blocked by safety filters",
          violations: safetyResult.violations,
        },
        { status: 403, headers: correlationIdResponseHeaders(correlationId) }
      );
    }

    // Step 2: Generate images (via AI Service)
    logger.info("Starting generation", correlationId, { mode: genMode, identity: identityId || "default" });

    const generationResult = await AIService.generate({
      prompt: trimmedPrompt,
      mode: genMode,
      identityId: identityId || undefined,
      userId: dbUser.id,
      numCandidates: Math.min((numImages || 2) + 2, 4),
      faceEmbedding: faceEmbedding ?? undefined,
      loraPath: loraFilePath ?? undefined,
      correlationId,
    });

    if (!generationResult.success) {
      logger.error("Generation failed", correlationId, { error: generationResult.error });
      return NextResponse.json(
        { error: generationResult.error || "Generation failed" },
        { status: 502, headers: correlationIdResponseHeaders(correlationId) }
      );
    }

    const images = generationResult.images;
    const jobId = generationResult.jobId || `gen_${Date.now().toString(36)}`;

    // Step 3: Save generation to database (all generations, with or without identity)
    if (images.length > 0) {
      try {
        const consentTraining = await prisma.consentRecord.findFirst({
          where: { userId: dbUser.id, allowTraining: true, withdrawnAt: null },
          orderBy: { timestamp: "desc" },
          select: { id: true },
        });
        const firstImage = images[0];
        type GenImage = { url?: string; seed?: number; scores?: Record<string, number> };
        const tierUsed: QualityTier | string = (body.quality_tier as QualityTier) || "STANDARD";
        const costEst = computeGenerationCost({ tier: tierUsed, inferenceSeconds: 12, imageCount: images.length });
        const base = {
          userId: dbUser.id,
          identityId: identity?.id ?? null,
          originalPrompt: trimmedPrompt,
          mode: genMode,
          outputUrls: images.map((img: GenImage) => img.url ?? ""),
          selectedOutputUrl: firstImage.url,
          creditsUsed: 1,
          preGenSafetyPassed: safetyResult.allowed,
          postGenSafetyPassed: true,
          faceMatchScore: firstImage.scores?.face_match || null,
          aestheticScore: firstImage.scores?.aesthetic || null,
          technicalScore: firstImage.scores?.technical || null,
          overallScore: firstImage.scores?.total || null,
          allowTrainingDataExport: !!consentTraining,
          correlationId: correlationId || undefined,
          costUsd: roundCost(costEst.totalUsd),
          qualityTierUsed: tierUsed,
          cacheHit: false,
          metadata: {
            job_id: jobId,
            mode: genMode,
            num_generated: images.length,
            seed: firstImage.seed,
            provider: AIService.getProvider(),
            hasIdentity: !!identity?.id,
          },
        };
        await prisma.generation.create({
          data: base as unknown as Prisma.GenerationUncheckedCreateInput,
        });
        logger.info("Saved to DB", correlationId, { job_id: jobId, identity: identity?.id || "none" });
      } catch (dbError) {
        logger.error("DB save failed", correlationId, { error: String(dbError) });
        // Don't fail the request, just log
      }
    }

    logger.info("Generation success", correlationId, { image_count: images.length });

    return NextResponse.json(
      {
        success: true,
        job_id: jobId,
        status: "completed",
        message: `Generated ${images.length} images`,
        images,
        provider: AIService.getProvider(),
      },
      { headers: correlationIdResponseHeaders(correlationId) }
    );
  } catch (error) {
    logger.error("Generate failed", correlationId, { error: String(error) });

    if (error instanceof Error && error.name === "TimeoutError") {
      return NextResponse.json(
        { error: "Generation timed out. Please try again." },
        { status: 504, headers: correlationIdResponseHeaders(correlationId) }
      );
    }

    const message = error instanceof Error ? error.message : "Failed to generate images";
    const isDev = process.env.NODE_ENV === "development";

    return NextResponse.json(
      {
        error: isDev ? message : "Failed to generate images",
        ...(isDev && error instanceof Error && { details: String((error as Error).stack) }),
      },
      { status: 500, headers: correlationIdResponseHeaders(correlationId) }
    );
  }
}

import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { AIService } from "@/lib/ai-service";
import { logIdentityAccess } from "@/lib/identity-audit";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = "force-dynamic";

/**
 * POST /api/identities/[id]/train – start training for an identity.
 *
 * Supports multiple cloud providers (AWS primary; GCP, Lightning optional)
 * Provider is auto-detected from environment variables.
 *
 * Returns: { success: boolean, message: string }.
 */
export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { id } = await params;

    // Get database user by Clerk ID
    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });

    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    // Get identity
    const identity = await prisma.identity.findFirst({
      where: {
        id,
        userId: dbUser.id,
      },
      select: {
        id: true,
        trainingStatus: true,
        referencePhotoUrls: true,
        referencePhotoCount: true,
      },
    });

    if (!identity) {
      return NextResponse.json({ error: "Identity not found" }, { status: 404 });
    }

    // Check if already training or completed
    if (identity.trainingStatus === "TRAINING") {
      return NextResponse.json({
        success: false,
        message: "Training already in progress",
      });
    }

    if (identity.trainingStatus === "COMPLETED") {
      return NextResponse.json({
        success: false,
        message: "Training already completed",
      });
    }

    // Validate photo count - minimum 8 photos for quality training
    const MIN_PHOTOS = 8;
    if (identity.referencePhotoCount < MIN_PHOTOS) {
      return NextResponse.json({
        success: false,
        message: `At least ${MIN_PHOTOS} photos required for training. You have ${identity.referencePhotoCount}.`,
      });
    }

    await logIdentityAccess({ identityId: id, userId: dbUser.id, action: "TRAIN", req: _req });

    // Update status to TRAINING
    await prisma.identity.update({
      where: { id },
      data: {
        trainingStatus: "TRAINING",
        trainingProgress: 0,
        trainingStartedAt: new Date(),
        trainingError: null,
      },
    });

    const photoUrls = Array.isArray(identity.referencePhotoUrls)
      ? (identity.referencePhotoUrls as string[])
      : [];

    // Start training via AI Service (runs async in background)
    console.log(`[Training] Starting for identity ${id} [Provider: ${AIService.getProvider()}]`);

    // Fire and forget - don't await the full training
    AIService.startTraining({
      userId: dbUser.id,
      identityId: id,
      imageUrls: photoUrls,
      triggerWord: "sks",
      trainingSteps: 1000,
    })
      .then(async (result) => {
        if (result.success) {
          // Update identity with LoRA path and face embedding
          await prisma.identity.update({
            where: { id },
            data: {
              trainingStatus: "COMPLETED",
              trainingProgress: 100,
              trainingCompletedAt: new Date(),
              loraFilePath: result.loraPath,
              faceEmbedding: result.faceEmbedding,
              qualityScore: result.faceQuality,
            },
          });
          console.log(`[Training Complete] Identity ${id} trained successfully`);
        } else {
          await prisma.identity.update({
            where: { id },
            data: {
              trainingStatus: "FAILED",
              trainingError: result.error || "Training failed",
            },
          });
          console.error(`[Training Failed] Identity ${id}: ${result.error}`);
        }
      })
      .catch(async (err) => {
        await prisma.identity.update({
          where: { id },
          data: {
            trainingStatus: "FAILED",
            trainingError: `Training error: ${err.message}`,
          },
        });
        console.error(`[Training Error] Identity ${id}:`, err);
      });

    return NextResponse.json({
      success: true,
      message: "Training started successfully",
      identityId: id,
      provider: AIService.getProvider(),
    });
  } catch (e) {
    console.error("[api/identities/[id]/train]", e);
    return NextResponse.json(
      { success: false, message: "Failed to start training" },
      { status: 500 }
    );
  }
}

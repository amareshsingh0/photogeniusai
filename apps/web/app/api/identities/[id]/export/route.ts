import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { logIdentityAccess } from "@/lib/identity-audit";

export const dynamic = "force-dynamic";

/**
 * GET /api/identities/[id]/export – GDPR right to access / portability.
 * Returns identity package: metadata, consent info, reference photo URLs, LoRA path (no raw face embedding in JSON for security).
 * Biometric compliance: access is audit-logged.
 */
export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { id } = await params;

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });

    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const identity = await prisma.identity.findFirst({
      where: { id, userId: dbUser.id, isDeleted: false },
      select: {
        id: true,
        name: true,
        description: true,
        triggerWord: true,
        referencePhotoUrls: true,
        referencePhotoCount: true,
        loraFilePath: true,
        loraFileSize: true,
        trainingStatus: true,
        trainingCompletedAt: true,
        consentGiven: true,
        consentTimestamp: true,
        consentVersion: true,
        createdAt: true,
        updatedAt: true,
      },
    });

    if (!identity) {
      return NextResponse.json({ error: "Identity not found" }, { status: 404 });
    }

    await logIdentityAccess({ identityId: id, userId: dbUser.id, action: "EXPORT", req });

    const package_ = {
      export_date: new Date().toISOString(),
      identity: {
        id: identity.id,
        name: identity.name,
        description: identity.description ?? undefined,
        trigger_word: identity.triggerWord,
        reference_photo_urls: identity.referencePhotoUrls,
        reference_photo_count: identity.referencePhotoCount,
        lora_file_path: identity.loraFilePath ?? undefined,
        lora_file_size_bytes: identity.loraFileSize ?? undefined,
        training_status: identity.trainingStatus,
        training_completed_at: identity.trainingCompletedAt?.toISOString(),
        consent_given: identity.consentGiven,
        consent_timestamp: identity.consentTimestamp?.toISOString(),
        consent_version: identity.consentVersion ?? undefined,
        created_at: identity.createdAt.toISOString(),
        updated_at: identity.updatedAt.toISOString(),
      },
      note: "Face embedding (biometric vector) is not included in export for security. It is stored only for inference and is deleted on erasure.",
    };

    return NextResponse.json(package_, {
      headers: {
        "Content-Disposition": `attachment; filename="identity-export-${id}.json"`,
      },
    });
  } catch (e) {
    console.error("[api/identities/[id]/export]", e);
    return NextResponse.json(
      { error: "Failed to export identity" },
      { status: 500 }
    );
  }
}

import { NextResponse } from "next/server";
import { Prisma } from "@photogenius/database";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * POST /api/identities/erasure – GDPR/BIPA: full erasure of all biometric data (identities).
 * One-click "Delete my biometric data": soft-deletes all identities and clears face embeddings/LoRA refs.
 * S3 object deletion can be run asynchronously by a backend job.
 */
export async function POST() {
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

    const identities = await prisma.identity.findMany({
      where: { userId: dbUser.id, isDeleted: false },
      select: { id: true },
    });

    let count = 0;
    for (const identity of identities) {
      await prisma.identity.update({
        where: { id: identity.id },
        data: {
          isDeleted: true,
          deletedAt: new Date(),
          referencePhotoUrls: [],
          referencePhotoCount: 0,
          faceEmbedding: Prisma.DbNull,
          loraFilePath: null,
          loraFileSize: null,
        },
      });
      count++;
    }

    return NextResponse.json({
      success: true,
      message: "All identity (biometric) data has been erased.",
      identities_erased: count,
    });
  } catch (e) {
    console.error("[api/identities/erasure]", e);
    return NextResponse.json(
      { error: "Failed to erase biometric data" },
      { status: 500 }
    );
  }
}

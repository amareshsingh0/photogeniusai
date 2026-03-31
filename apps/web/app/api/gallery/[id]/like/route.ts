import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/gallery/[id]/like – check if current user liked this generation.
 */
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ liked: false });
    }

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });
    if (!dbUser) {
      return NextResponse.json({ liked: false });
    }

    const { id: generationId } = await params;
    const like = await prisma.galleryLike.findUnique({
      where: {
        userId_generationId: { userId: dbUser.id, generationId },
      },
    });

    return NextResponse.json({ liked: !!like });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json({ liked: false });
    }
    return NextResponse.json(
      { error: "Failed to check like" },
      { status: 500 }
    );
  }
}

/**
 * POST /api/gallery/[id]/like – toggle like.
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

    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });
    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const { id: generationId } = await params;

    const gen = await prisma.generation.findFirst({
      where: {
        id: generationId,
        isPublic: true,
        galleryModeration: "APPROVED",
        isDeleted: false,
      },
      select: { id: true, galleryLikesCount: true },
    });

    if (!gen) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const existing = await prisma.galleryLike.findUnique({
      where: {
        userId_generationId: { userId: dbUser.id, generationId },
      },
    });

    if (existing) {
      await prisma.galleryLike.delete({
        where: { id: existing.id },
      });
      await prisma.generation.update({
        where: { id: generationId },
        data: { galleryLikesCount: Math.max(0, (gen.galleryLikesCount ?? 0) - 1) },
      });
      return NextResponse.json({ liked: false });
    }

    await prisma.galleryLike.create({
      data: {
        userId: dbUser.id,
        generationId,
      },
    });
    await prisma.generation.update({
      where: { id: generationId },
      data: { galleryLikesCount: (gen.galleryLikesCount ?? 0) + 1 },
    });

    return NextResponse.json({ liked: true });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: "Failed to toggle like" },
      { status: 500 }
    );
  }
}

import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/gallery/[id]/comments – list comments for a public gallery item (no auth required to read).
 */
export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: generationId } = await params;
    const { searchParams } = new URL(req.url);
    const limit = Math.min(Number(searchParams.get("limit")) || 50, 100);
    const cursor = searchParams.get("cursor") ?? undefined;

    const gen = await prisma.generation.findFirst({
      where: {
        id: generationId,
        isPublic: true,
        galleryModeration: "APPROVED",
        isDeleted: false,
      },
      select: { id: true },
    });

    if (!gen) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const comments = await prisma.galleryComment.findMany({
      where: { generationId },
      take: limit + 1,
      ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
      orderBy: { createdAt: "asc" },
      select: {
        id: true,
        body: true,
        createdAt: true,
        user: {
          select: {
            id: true,
            name: true,
            profileImageUrl: true,
            displayName: true,
          },
        },
      },
    });

    const nextCursor = comments.length > limit ? comments[limit - 1]?.id : undefined;
    const list = comments.slice(0, limit);

    const payload = list.map((c) => ({
      id: c.id,
      body: c.body,
      createdAt: c.createdAt.toISOString(),
      user: c.user
        ? {
            id: c.user.id,
            name: c.user.displayName ?? c.user.name ?? "Anonymous",
            profileImageUrl: c.user.profileImageUrl ?? undefined,
          }
        : null,
    }));

    return NextResponse.json({
      comments: payload,
      nextCursor: nextCursor ?? null,
    });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json({ comments: [], nextCursor: null });
    }
    return NextResponse.json(
      { error: "Failed to load comments" },
      { status: 500 }
    );
  }
}

/**
 * POST /api/gallery/[id]/comments – add a comment (auth required).
 */
export async function POST(
  req: Request,
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
    const body = (await req.json().catch(() => ({}))) as { body?: string };

    const bodyText =
      typeof body.body === "string"
        ? body.body.trim().slice(0, 2000)
        : "";
    if (!bodyText) {
      return NextResponse.json(
        { error: "Comment body required" },
        { status: 400 }
      );
    }

    const gen = await prisma.generation.findFirst({
      where: {
        id: generationId,
        isPublic: true,
        galleryModeration: "APPROVED",
        isDeleted: false,
      },
      select: { id: true, galleryCommentsCount: true },
    });

    if (!gen) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const comment = await prisma.galleryComment.create({
      data: {
        userId: dbUser.id,
        generationId,
        body: bodyText,
      },
      select: {
        id: true,
        body: true,
        createdAt: true,
        user: {
          select: {
            id: true,
            name: true,
            profileImageUrl: true,
            displayName: true,
          },
        },
      },
    });

    await prisma.generation.update({
      where: { id: generationId },
      data: {
        galleryCommentsCount: (gen.galleryCommentsCount ?? 0) + 1,
      },
    });

    return NextResponse.json({
      comment: {
        id: comment.id,
        body: comment.body,
        createdAt: comment.createdAt.toISOString(),
        user: comment.user
          ? {
              id: comment.user.id,
              name: comment.user.displayName ?? comment.user.name ?? "Anonymous",
              profileImageUrl: comment.user.profileImageUrl ?? undefined,
            }
          : null,
      },
    });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: "Failed to add comment" },
      { status: 500 }
    );
  }
}

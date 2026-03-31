import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * POST /api/generations/[id]/publish – publish generation to public gallery (opt-in).
 * Body: { category?, style? }. Sets isPublic=true, publishedAt=now(), galleryModeration=PENDING.
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

    const { id } = await params;
    const body = (await req.json().catch(() => ({}))) as {
      category?: string;
      style?: string;
    };

    const gen = await prisma.generation.findFirst({
      where: { id, userId: dbUser.id, isDeleted: false },
      select: {
        id: true,
        postGenSafetyPassed: true,
        isQuarantined: true,
      },
    });

    if (!gen) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }
    if (gen.isQuarantined || !gen.postGenSafetyPassed) {
      return NextResponse.json(
        { error: "Generation cannot be published (safety)" },
        { status: 400 }
      );
    }

    const category =
      typeof body.category === "string" && body.category.length <= 50
        ? body.category
        : null;
    const style =
      typeof body.style === "string" && body.style.length <= 50
        ? body.style
        : null;

    await prisma.generation.update({
      where: { id },
      data: {
        isPublic: true,
        publishedAt: new Date(),
        galleryCategory: category,
        galleryStyle: style,
        galleryModeration: "PENDING",
      },
    });

    await prisma.activity.create({
      data: {
        userId: dbUser.id,
        type: "PUBLISHED_GALLERY",
        targetType: "generation",
        targetId: id,
        metadata: { category, style },
      },
    }).catch(() => {});

    return NextResponse.json({ ok: true, published: true });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: "Failed to publish" },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/generations/[id]/publish – unpublish from public gallery.
 */
export async function DELETE(
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

    const { id } = await params;
    const gen = await prisma.generation.findFirst({
      where: { id, userId: dbUser.id },
      select: { id: true },
    });

    if (!gen) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    await prisma.generation.update({
      where: { id },
      data: {
        isPublic: false,
        publishedAt: null,
        galleryModeration: null,
      },
    });

    return NextResponse.json({ ok: true, published: false });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: "Failed to unpublish" },
      { status: 500 }
    );
  }
}

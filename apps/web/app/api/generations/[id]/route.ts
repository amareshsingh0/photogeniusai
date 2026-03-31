import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = 'force-dynamic';

/**
 * PATCH /api/generations/[id] – update generation (e.g. selectedOutputUrl for "star").
 */
export async function PATCH(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    // Get database user by Clerk ID
    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });

    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const { id } = await params;
    const body = (await _req.json()) as { selectedUrl?: string; userRating?: number; isFavorite?: boolean };

    const gen = await prisma.generation.findFirst({
      where: { id, userId: dbUser.id },
      select: { id: true, originalPrompt: true, outputUrls: true },
    });

    if (!gen) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const updates: { selectedOutputUrl?: string; userRating?: number; isFavorite?: boolean } = {};
    if (typeof body.selectedUrl === "string") updates.selectedOutputUrl = body.selectedUrl;
    if (typeof body.userRating === "number" && body.userRating >= 1 && body.userRating <= 5) {
      updates.userRating = Math.round(body.userRating);
    }
    if (typeof body.isFavorite === "boolean") updates.isFavorite = body.isFavorite;

    if (Object.keys(updates).length === 0) {
      return NextResponse.json(await prisma.generation.findUnique({ where: { id } }));
    }

    const updated = await prisma.generation.update({
      where: { id },
      data: updates,
    });

    // RLHF: record preference pairs when user selects one output (save to gallery / star)
    const selectedUrl = updates.selectedOutputUrl ?? updated.selectedOutputUrl;
    const prompt = gen.originalPrompt || "";
    const urls = Array.isArray(gen.outputUrls) ? (gen.outputUrls as string[]) : [];
    if (selectedUrl && prompt && urls.length > 1) {
      const source = updates.isFavorite === true ? "SAVE_GALLERY" : "EXPLICIT_THUMBS";
      for (const other of urls) {
        if (other && other !== selectedUrl) {
          prisma.preferencePair
            .create({
              data: {
                userId: dbUser.id,
                prompt,
                imageAUrl: selectedUrl,
                imageBUrl: other,
                preferred: "A",
                source,
                generationIdA: gen.id,
                generationIdB: undefined,
              },
            })
            .catch((err) => console.error("[preferences] create failed:", err));
        }
      }
    }

    return NextResponse.json(updated);
  } catch (e) {
    console.error("[api/generations PATCH]", e);
    return NextResponse.json(
      { error: "Failed to update generation" },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/generations/[id] – delete a generation.
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

    // Get database user by Clerk ID
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
      select: { id: true, originalPrompt: true, selectedOutputUrl: true, outputUrls: true },
    });

    if (!gen) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const deletedUrl = gen.selectedOutputUrl ?? (Array.isArray(gen.outputUrls) ? gen.outputUrls[0] : null);
    const prompt = gen.originalPrompt || "";
    if (deletedUrl && prompt) {
      const other = await prisma.generation.findFirst({
        where: {
          userId: dbUser.id,
          originalPrompt: prompt,
          id: { not: id },
          isDeleted: false,
        },
        select: { id: true, selectedOutputUrl: true, outputUrls: true },
      });
      if (other) {
        const otherUrl = other.selectedOutputUrl ?? (Array.isArray(other.outputUrls) ? (other.outputUrls[0] as string) : null);
        if (otherUrl) {
          prisma.preferencePair
            .create({
              data: {
                userId: dbUser.id,
                prompt,
                imageAUrl: otherUrl as string,
                imageBUrl: deletedUrl as string,
                preferred: "A",
                source: "DELETE",
                strength: 0.8,
                generationIdA: other.id,
                generationIdB: gen.id,
              },
            })
            .catch((err) => console.error("[preferences] delete pair failed:", err));
        }
      }
    }

    await prisma.generation.delete({ where: { id } });
    return NextResponse.json({ ok: true });
  } catch (e) {
    console.error("[api/generations DELETE]", e);
    return NextResponse.json(
      { error: "Failed to delete generation" },
      { status: 500 }
    );
  }
}

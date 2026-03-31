import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * POST /api/generations/[id]/download – mark one output as downloaded (increment count + RLHF strong positive).
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

    const { id } = await params;
    const body = (await _req.json().catch(() => ({}))) as { imageUrl?: string };

    const gen = await prisma.generation.findFirst({
      where: { id, userId: dbUser.id },
      select: { id: true, originalPrompt: true, outputUrls: true, selectedOutputUrl: true },
    });

    if (!gen) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const imageUrl: string | null =
      typeof body.imageUrl === "string"
        ? body.imageUrl.trim()
        : gen.selectedOutputUrl ?? (Array.isArray(gen.outputUrls) ? (gen.outputUrls[0] as string) : null);

    await prisma.generation.update({
      where: { id },
      data: { downloadCount: { increment: 1 } },
    });

    const prompt = gen.originalPrompt || "";
    const urls = Array.isArray(gen.outputUrls) ? (gen.outputUrls as string[]) : [];
    if (imageUrl && prompt && urls.length > 1) {
      for (const other of urls) {
        if (other && other !== imageUrl) {
          prisma.preferencePair
            .create({
              data: {
                userId: dbUser.id,
                prompt,
                imageAUrl: imageUrl,
                imageBUrl: other,
                preferred: "A",
                source: "DOWNLOAD",
                strength: 1.0,
                generationIdA: gen.id,
              },
            })
            .catch((err) => console.error("[preferences] download pair failed:", err));
        }
      }
    }

    return NextResponse.json({ ok: true });
  } catch (e) {
    console.error("[api/generations download]", e);
    return NextResponse.json({ error: "Failed to record download" }, { status: 500 });
  }
}

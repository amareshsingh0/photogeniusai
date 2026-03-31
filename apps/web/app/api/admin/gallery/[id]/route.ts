import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

const ALLOWED = ["APPROVED", "REJECTED", "FLAGGED"] as const;

/**
 * PATCH /api/admin/gallery/[id] – set moderation status (admin only).
 * Body: { status: "APPROVED" | "REJECTED" | "FLAGGED" }
 */
export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    // TODO: check admin role
    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });
    if (!dbUser) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }

    const { id } = await params;
    const body = (await req.json().catch(() => ({}))) as { status?: string };
    const status = ALLOWED.includes(body.status as any) ? body.status : "REJECTED";

    await prisma.generation.update({
      where: { id },
      data: { galleryModeration: status as "APPROVED" | "REJECTED" | "FLAGGED" },
    });

    return NextResponse.json({ ok: true, status });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json({ error: "Database unavailable" }, { status: 503 });
    }
    return NextResponse.json({ error: "Failed to update" }, { status: 500 });
  }
}

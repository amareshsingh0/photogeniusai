import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = 'force-dynamic';

/**
 * GET /api/identities – list identities for the current user.
 */
export async function GET() {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json([]);
    }

    // Get database user by Clerk ID
    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    });

    if (!dbUser) {
      return NextResponse.json([]);
    }

    const rows = await prisma.identity.findMany({
      where: { userId: dbUser.id, isDeleted: false },
      orderBy: { createdAt: "desc" },
      select: {
        id: true,
        name: true,
        referencePhotoUrls: true,
        trainingStatus: true,
        createdAt: true,
      },
    });

    return NextResponse.json(
      rows.map((r: typeof rows[number]) => ({
        id: r.id,
        name: r.name ?? undefined,
        imageUrls: r.referencePhotoUrls,
        status: r.trainingStatus === "COMPLETED" ? "READY" : r.trainingStatus,
        createdAt: r.createdAt.toISOString(),
      }))
    );
  } catch (e: unknown) {
    console.error("[api/identities GET]", e);
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json([]);
    }
    return NextResponse.json(
      { error: "Failed to list identities" },
      { status: 500 }
    );
  }
}

/**
 * POST /api/identities – create an identity (after uploads).
 * Body: { name: string, imageUrls: string[] }.
 */
export async function POST(req: Request) {
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

    const body = (await req.json()) as { name?: string; imageUrls: string[] };
    if (!Array.isArray(body.imageUrls) || body.imageUrls.length === 0) {
      return NextResponse.json(
        { error: "imageUrls array required" },
        { status: 400 }
      );
    }

    const identity = await prisma.identity.create({
      data: {
        userId: dbUser.id,
        name: body.name?.trim() || "Untitled",
        referencePhotoUrls: body.imageUrls,
        referencePhotoCount: body.imageUrls.length,
        trainingStatus: "PENDING",
      },
    });

    return NextResponse.json({
      id: identity.id,
      name: identity.name ?? undefined,
      imageUrls: identity.referencePhotoUrls,
      status: identity.trainingStatus,
    });
  } catch (e: unknown) {
    console.error("[api/identities POST]", e);
    if (isPrismaDbUnavailable(e)) {
      return NextResponse.json(
        { error: "Database unavailable. Please try again later." },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: "Failed to create identity" },
      { status: 500 }
    );
  }
}

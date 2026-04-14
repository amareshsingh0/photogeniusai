import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/admin-auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/admin/generations - Get all generations with pagination
 */
export async function GET(req: Request) {
  try {
    await requireAdmin();

    const { searchParams } = new URL(req.url);
    const page = parseInt(searchParams.get("page") || "1");
    const limit = parseInt(searchParams.get("limit") || "50");
    const skip = (page - 1) * limit;

    // Fetch generations with user info
    const [generations, total] = await Promise.all([
      prisma.generation.findMany({
        where: { isDeleted: false },
        skip,
        take: limit,
        orderBy: { createdAt: "desc" },
        select: {
          id: true,
          originalPrompt: true,
          mode: true,
          creditsUsed: true,
          qualityTierUsed: true,
          modelUsed: true,
          bucket: true,
          createdAt: true,
          user: {
            select: {
              id: true,
              email: true,
              name: true,
            },
          },
        },
      }),
      prisma.generation.count({ where: { isDeleted: false } }),
    ]);

    return NextResponse.json({
      generations,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    });
  } catch (error: any) {
    console.error("[admin/generations] Error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to fetch generations" },
      { status: error.message?.includes("Admin") ? 403 : 500 }
    );
  }
}

/**
 * DELETE /api/admin/generations - Delete generation
 */
export async function DELETE(req: Request) {
  try {
    await requireAdmin();

    const { searchParams } = new URL(req.url);
    const generationId = searchParams.get("generationId");

    if (!generationId) {
      return NextResponse.json(
        { error: "generationId is required" },
        { status: 400 }
      );
    }

    // Delete generation and all variants
    await prisma.generation.delete({
      where: { id: generationId },
    });

    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error("[admin/generations] DELETE error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to delete generation" },
      { status: error.message?.includes("Admin") ? 403 : 500 }
    );
  }
}

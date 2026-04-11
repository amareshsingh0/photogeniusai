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
    const userId = searchParams.get("userId") || "";
    const quality = searchParams.get("quality") || "";
    const bucket = searchParams.get("bucket") || "";

    const skip = (page - 1) * limit;

    // Build where clause
    const where: any = {};
    if (userId) {
      where.userId = userId;
    }
    if (quality) {
      where.quality = quality;
    }
    if (bucket) {
      where.bucket = bucket;
    }

    // Get generations with pagination
    const [generations, total] = await Promise.all([
      prisma.generation.findMany({
        where,
        skip,
        take: limit,
        orderBy: { createdAt: "desc" },
        select: {
          id: true,
          prompt: true,
          enhancedPrompt: true,
          quality: true,
          bucket: true,
          modelUsed: true,
          credits: true,
          overallScore: true,
          createdAt: true,
          user: {
            select: {
              id: true,
              email: true,
              name: true,
            },
          },
          variants: {
            select: {
              id: true,
              imageUrl: true,
              juryScore: true,
              selected: true,
            },
            take: 1,
          },
        },
      }),
      prisma.generation.count({ where }),
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

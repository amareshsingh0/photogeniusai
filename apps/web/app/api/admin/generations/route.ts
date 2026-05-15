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

    // Filters
    const search = searchParams.get("search") || "";
    const qualityFilter = searchParams.get("quality");
    const modelFilter = searchParams.get("model");
    const userFilter = searchParams.get("userId");
    const bucketFilter = searchParams.get("bucket");
    const sortBy = searchParams.get("sortBy") || "createdAt";
    const sortOrder = searchParams.get("sortOrder") || "desc";

    // Build where clause
    const where: any = { isDeleted: false };

    if (search) {
      where.originalPrompt = { contains: search, mode: "insensitive" };
    }

    if (qualityFilter) {
      where.qualityTierUsed = qualityFilter;
    }

    if (modelFilter) {
      where.modelUsed = modelFilter;
    }

    if (userFilter) {
      where.userId = userFilter;
    }

    if (bucketFilter) {
      where.bucket = bucketFilter;
    }

    // Build orderBy
    const orderBy: any = {};
    orderBy[sortBy] = sortOrder;

    // Fetch generations with user info and all data
    const [generations, total] = await Promise.all([
      prisma.generation.findMany({
        where,
        skip,
        take: limit,
        orderBy,
        select: {
          id: true,
          originalPrompt: true,
          mode: true,
          creditsUsed: true,
          qualityTierUsed: true,
          modelUsed: true,
          bucket: true,
          selectedOutputUrl: true,
          thumbnailUrl: true,
          outputUrls: true,
          userRating: true,
          generationTimeSeconds: true,
          overallScore: true,
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

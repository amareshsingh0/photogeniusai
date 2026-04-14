import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/admin-auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * GET /api/admin/users - Get all users with pagination
 */
export async function GET(req: Request) {
  try {
    await requireAdmin();

    const { searchParams } = new URL(req.url);
    const page = parseInt(searchParams.get("page") || "1");
    const limit = parseInt(searchParams.get("limit") || "50");
    const search = searchParams.get("search") || "";
    const skip = (page - 1) * limit;

    // Build where clause for search
    const where = search
      ? {
          OR: [
            { email: { contains: search, mode: "insensitive" as const } },
            { name: { contains: search, mode: "insensitive" as const } },
          ],
        }
      : {};

    // Fetch users with pagination
    const [users, total] = await Promise.all([
      prisma.user.findMany({
        where,
        skip,
        take: limit,
        orderBy: { createdAt: "desc" },
        select: {
          id: true,
          email: true,
          name: true,
          role: true,
          creditsBalance: true,
          createdAt: true,
          _count: {
            select: { generations: true },
          },
        },
      }),
      prisma.user.count({ where }),
    ]);

    // Map creditsBalance to credits for frontend compatibility
    const formattedUsers = users.map((user) => ({
      ...user,
      credits: user.creditsBalance,
      creditsBalance: undefined,
    }));

    return NextResponse.json({
      users: formattedUsers,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    });
  } catch (error: any) {
    console.error("[admin/users] GET error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to fetch users" },
      { status: error.message?.includes("Admin") ? 403 : 500 }
    );
  }
}

/**
 * PATCH /api/admin/users - Update user
 */
export async function PATCH(req: Request) {
  try {
    await requireAdmin();

    const body = await req.json();
    const { userId, updates } = body;

    if (!userId) {
      return NextResponse.json(
        { error: "userId is required" },
        { status: 400 }
      );
    }

    // Allowed update fields (map credits to creditsBalance)
    const allowedFields = ["name", "email", "role", "credits"];
    const updateData: any = {};

    for (const field of allowedFields) {
      if (updates[field] !== undefined) {
        // Map credits to creditsBalance for database
        const dbField = field === "credits" ? "creditsBalance" : field;
        updateData[dbField] = updates[field];
      }
    }

    if (Object.keys(updateData).length === 0) {
      return NextResponse.json(
        { error: "No valid update fields provided" },
        { status: 400 }
      );
    }

    const updatedUser = await prisma.user.update({
      where: { id: userId },
      data: updateData,
      select: {
        id: true,
        email: true,
        name: true,
        role: true,
        creditsBalance: true,
        updatedAt: true,
      },
    });

    // Map creditsBalance to credits for frontend
    return NextResponse.json({
      user: {
        ...updatedUser,
        credits: updatedUser.creditsBalance,
        creditsBalance: undefined,
      },
    });
  } catch (error: any) {
    console.error("[admin/users] PATCH error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to update user" },
      { status: error.message?.includes("Admin") ? 403 : 500 }
    );
  }
}

/**
 * DELETE /api/admin/users - Delete user
 */
export async function DELETE(req: Request) {
  try {
    await requireAdmin();

    const { searchParams } = new URL(req.url);
    const userId = searchParams.get("userId");

    if (!userId) {
      return NextResponse.json(
        { error: "userId is required" },
        { status: 400 }
      );
    }

    // Delete user and all related data
    await prisma.user.delete({
      where: { id: userId },
    });

    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error("[admin/users] DELETE error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to delete user" },
      { status: error.message?.includes("Admin") ? 403 : 500 }
    );
  }
}

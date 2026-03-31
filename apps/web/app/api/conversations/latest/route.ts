import { NextResponse } from "next/server"
import { auth } from "@clerk/nextjs/server"
import { prisma } from "@/lib/db"

// Force dynamic rendering
export const dynamic = "force-dynamic"

/**
 * GET /api/conversations/latest - Get user's latest conversation
 */
export async function GET() {
  try {
    const { userId: clerkId } = await auth()
    if (!clerkId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 }
      )
    }

    // Get database user
    const dbUser = await prisma.user.findUnique({
      where: { clerkId },
      select: { id: true },
    })

    if (!dbUser) {
      return NextResponse.json(
        { error: "User not found" },
        { status: 404 }
      )
    }

    // Get latest active conversation
    const conversation = await prisma.conversation.findFirst({
      where: {
        userId: dbUser.id,
        active: true,
      },
      orderBy: {
        updatedAt: "desc",
      },
      include: {
        messages: {
          orderBy: {
            createdAt: "asc",
          },
        },
      },
    })

    if (!conversation) {
      return NextResponse.json({
        messages: [],
        context: {},
      })
    }

    // Format messages
    const messages = conversation.messages.map((msg) => ({
      id: msg.id,
      role: msg.role,
      content: msg.content,
      images: msg.images as string[] | undefined,
      timestamp: msg.createdAt.toISOString(),
      metadata: msg.metadata as Record<string, any> | undefined,
    }))

    return NextResponse.json({
      messages,
      context: (conversation.context as Record<string, any>) || {},
    })
  } catch (error) {
    console.error("[conversations/latest]", error)
    return NextResponse.json(
      { error: "Failed to load conversation" },
      { status: 500 }
    )
  }
}

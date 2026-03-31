import { NextResponse } from "next/server"
import { auth } from "@clerk/nextjs/server"
import { prisma } from "@/lib/db"

// Force dynamic rendering
export const dynamic = "force-dynamic"

/**
 * POST /api/conversations - Save conversation history
 */
export async function POST(req: Request) {
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

    const body = await req.json()
    const { messages, context } = body

    if (!messages || !Array.isArray(messages)) {
      return NextResponse.json(
        { error: "Messages array required" },
        { status: 400 }
      )
    }

    // Get or create conversation
    let conversation = await prisma.conversation.findFirst({
      where: {
        userId: dbUser.id,
        active: true,
      },
      orderBy: {
        updatedAt: "desc",
      },
    })

    if (!conversation) {
      conversation = await prisma.conversation.create({
        data: {
          userId: dbUser.id,
          context: context || {},
          active: true,
        },
      })
    } else {
      // Update context
      await prisma.conversation.update({
        where: { id: conversation.id },
        data: {
          context: context || {},
          updatedAt: new Date(),
        },
      })
    }

    // Delete existing messages and create new ones
    await prisma.conversationMessage.deleteMany({
      where: { conversationId: conversation.id },
    })

    // Create messages
    await prisma.conversationMessage.createMany({
      data: messages.map((msg: any) => ({
        conversationId: conversation.id,
        role: msg.role,
        content: msg.content,
        images: msg.images || null,
        metadata: msg.metadata || null,
        createdAt: msg.timestamp ? new Date(msg.timestamp) : new Date(),
      })),
    })

    return NextResponse.json({ status: "saved" })
  } catch (error) {
    console.error("[conversations]", error)
    return NextResponse.json(
      { error: "Failed to save conversation" },
      { status: 500 }
    )
  }
}

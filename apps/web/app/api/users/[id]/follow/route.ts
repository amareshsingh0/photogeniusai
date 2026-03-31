import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    const dbUser = await prisma.user.findUnique({ where: { clerkId }, select: { id: true } });
    if (!dbUser) return NextResponse.json({ error: "User not found" }, { status: 404 });
    const { id: followingId } = await params;
    if (followingId === dbUser.id) return NextResponse.json({ error: "Cannot follow self" }, { status: 400 });
    const target = await prisma.user.findUnique({ where: { id: followingId }, select: { id: true } });
    if (!target) return NextResponse.json({ error: "User not found" }, { status: 404 });
    const existing = await prisma.follow.findUnique({ where: { followerId_followingId: { followerId: dbUser.id, followingId } } });
    if (existing) {
      await prisma.follow.delete({ where: { id: existing.id } });
      return NextResponse.json({ ok: true, following: false });
    }
    await prisma.follow.create({ data: { followerId: dbUser.id, followingId } });
    await prisma.activity.create({ data: { userId: followingId, type: "NEW_FOLLOWER", targetType: "user", targetId: dbUser.id, metadata: {} } }).catch(() => {});
    return NextResponse.json({ ok: true, following: true });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ error: "Database unavailable" }, { status: 503 });
    return NextResponse.json({ error: "Failed to update follow" }, { status: 500 });
  }
}

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) return NextResponse.json({ following: false });
    const dbUser = await prisma.user.findUnique({ where: { clerkId }, select: { id: true } });
    if (!dbUser) return NextResponse.json({ following: false });
    const { id: followingId } = await params;
    const f = await prisma.follow.findUnique({ where: { followerId_followingId: { followerId: dbUser.id, followingId } } });
    return NextResponse.json({ following: !!f });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ following: false });
    return NextResponse.json({ error: "Failed to check" }, { status: 500 });
  }
}

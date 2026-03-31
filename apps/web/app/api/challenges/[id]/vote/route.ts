import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    const dbUser = await prisma.user.findUnique({ where: { clerkId }, select: { id: true } });
    if (!dbUser) return NextResponse.json({ error: "User not found" }, { status: 404 });
    const { id: challengeId } = await params;
    const body = (await req.json().catch(() => ({}))) as { submissionId: string };
    const submissionId = body.submissionId;
    if (!submissionId) return NextResponse.json({ error: "submissionId required" }, { status: 400 });
    const challenge = await prisma.challenge.findFirst({ where: { id: challengeId, status: "VOTING" }, select: { id: true } });
    if (!challenge) return NextResponse.json({ error: "Challenge not open for voting" }, { status: 400 });
    const sub = await prisma.challengeSubmission.findFirst({ where: { id: submissionId, challengeId }, select: { id: true, voteCount: true } });
    if (!sub) return NextResponse.json({ error: "Submission not found" }, { status: 404 });
    const existing = await prisma.challengeVote.findUnique({ where: { challengeId_userId: { challengeId, userId: dbUser.id } }, select: { id: true, submissionId: true } });
    if (existing) {
      if (existing.submissionId === submissionId) return NextResponse.json({ ok: true, voted: true });
      await prisma.$transaction([
        prisma.challengeSubmission.update({ where: { id: existing.submissionId }, data: { voteCount: { decrement: 1 } } }),
        prisma.challengeVote.delete({ where: { id: existing.id } }),
        prisma.challengeVote.create({ data: { challengeId, submissionId, userId: dbUser.id } }),
        prisma.challengeSubmission.update({ where: { id: submissionId }, data: { voteCount: { increment: 1 } } }),
      ]);
    } else {
      await prisma.$transaction([
        prisma.challengeVote.create({ data: { challengeId, submissionId, userId: dbUser.id } }),
        prisma.challengeSubmission.update({ where: { id: submissionId }, data: { voteCount: { increment: 1 } } }),
      ]);
    }
    return NextResponse.json({ ok: true, voted: true });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ error: "Database unavailable" }, { status: 503 });
    return NextResponse.json({ error: "Failed to vote" }, { status: 500 });
  }
}

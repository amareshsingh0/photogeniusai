import { NextResponse } from "next/server";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const status = new URL(req.url).searchParams.get("status") ?? "ACTIVE";
    const limit = Math.min(Number(new URL(req.url).searchParams.get("limit")) || 10, 20);
    const valid = ["DRAFT", "ACTIVE", "VOTING", "ENDED"].includes(status) ? status : "ACTIVE";
    const rows = await prisma.challenge.findMany({
      where: { status: valid as "ACTIVE" | "DRAFT" | "VOTING" | "ENDED" },
      take: limit,
      orderBy: { startAt: "desc" },
      select: { id: true, title: true, description: true, theme: true, startAt: true, endAt: true, status: true, prizeCredits: true },
    });
    return NextResponse.json({ challenges: rows.map((c) => ({ id: c.id, title: c.title, description: c.description, theme: c.theme, startAt: c.startAt.toISOString(), endAt: c.endAt.toISOString(), status: c.status, prizeCredits: c.prizeCredits })) });
  } catch (e) {
    if (isPrismaDbUnavailable(e)) return NextResponse.json({ challenges: [] });
    return NextResponse.json({ error: "Failed to list" }, { status: 500 });
  }
}

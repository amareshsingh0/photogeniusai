import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = 'force-dynamic';

/**
 * GET /api/auth/session – { userId: string | null }.
 * Used by client to check auth (e.g. identity vault "Sign in to save").
 */
export async function GET() {
  try {
    const { userId } = await auth();
    return NextResponse.json({ userId });
  } catch (e) {
    console.error("[api/auth/session]", e);
    return NextResponse.json({ userId: null });
  }
}

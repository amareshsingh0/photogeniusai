import { NextResponse } from "next/server";

/**
 * Clerk auth catch-all. Handles /api/auth/* (sign-in, sign-up, OAuth callbacks).
 * Wire to Clerk per https://clerk.com/docs/references/nextjs/route-handlers.
 * Ensure CLERK_SECRET_KEY and NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY are set.
 */
export async function GET() {
  return NextResponse.json({ message: "Clerk auth" });
}

export async function POST() {
  return NextResponse.json({ message: "Clerk auth" });
}

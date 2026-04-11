import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * POST /api/auth/logout
 * Clear authentication token
 */
export async function POST() {
  const response = NextResponse.json({ success: true });

  // Clear auth cookie
  response.cookies.delete("auth_token");

  return response;
}

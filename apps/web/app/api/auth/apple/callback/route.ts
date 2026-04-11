import { NextResponse } from "next/server";
import { SignJWT } from "jose";
import { prisma } from "@/lib/db";

const JWT_SECRET = new TextEncoder().encode(
  process.env.JWT_SECRET || "photogenius-dev-secret-change-in-production"
);

export const dynamic = "force-dynamic";

/**
 * POST /api/auth/apple/callback
 * Handle Apple OAuth callback (form_post)
 */
export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const code = formData.get("code") as string;
    const error = formData.get("error");

    if (error || !code) {
      return NextResponse.redirect(
        `${process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3002"}/login?error=oauth_failed`
      );
    }

    // Apple OAuth token exchange would go here
    // For now, return error as Apple requires additional setup (team ID, key ID, private key)
    console.log("[auth/apple/callback] Apple OAuth not fully implemented yet");

    return NextResponse.redirect(
      `${process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3002"}/login?error=apple_not_configured`
    );
  } catch (error) {
    console.error("[auth/apple/callback] Error:", error);
    return NextResponse.redirect(
      `${process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3002"}/login?error=oauth_failed`
    );
  }
}

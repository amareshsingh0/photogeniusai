/**
 * Custom JWT-based authentication utilities
 * Supports: Email/Password, Google OAuth, Apple OAuth
 * Replaces Clerk integration for PhotoGenius AI
 */

import { jwtVerify } from "jose";
import { cookies } from "next/headers";
import { prisma } from "@/lib/db";

const JWT_SECRET = new TextEncoder().encode(
  process.env.JWT_SECRET || "photogenius-dev-secret-change-in-production"
);

// Dev mode user type
export interface DevUser {
  id: string;
  email: string;
  name: string;
  credits: number;
}

const DEV_USER: DevUser = {
  id: "dev_user_123",
  email: "dev@photogenius.local",
  name: "Dev User",
  credits: 1000,
};

/**
 * Get JWT token from cookies
 */
async function getToken(): Promise<string | null> {
  try {
    const cookieStore = await cookies();
    return cookieStore.get("auth_token")?.value || null;
  } catch {
    // In development, might not have cookies available
    return null;
  }
}

/**
 * Verify JWT token and return payload
 */
async function verifyToken(token: string) {
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET);
    return payload;
  } catch {
    return null;
  }
}

/**
 * Get authentication state
 * Returns userId and token getter function
 */
export async function auth() {
  // Development mode bypass
  if (process.env.NODE_ENV === "development" && !process.env.REQUIRE_AUTH) {
    return {
      userId: DEV_USER.id,
      getToken: async () => "dev_token_123",
    };
  }

  const token = await getToken();
  if (!token) {
    return { userId: null, getToken: async () => null };
  }

  const payload = await verifyToken(token);
  if (!payload) {
    return { userId: null, getToken: async () => null };
  }

  return {
    userId: payload.userId as string,
    getToken: async () => token,
  };
}

/**
 * Get current authenticated user from database
 */
export async function getCurrentUser(): Promise<DevUser | null> {
  // Development mode bypass
  if (process.env.NODE_ENV === "development" && !process.env.REQUIRE_AUTH) {
    return DEV_USER;
  }

  const { userId } = await auth();
  if (!userId) {
    return null;
  }

  try {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        name: true,
        credits: true,
      },
    });

    return user as DevUser | null;
  } catch (error) {
    console.error("[auth] Error fetching user:", error);
    return null;
  }
}

/**
 * Require authentication (throw if not authenticated)
 */
export async function requireAuth(): Promise<DevUser> {
  const user = await getCurrentUser();

  if (!user) {
    throw new Error("Authentication required");
  }

  return user;
}

/**
 * Check if user has sufficient credits
 */
export async function checkCredits(requiredCredits: number): Promise<DevUser> {
  const user = await requireAuth();

  // Development mode bypass
  if (process.env.NODE_ENV === "development" && !process.env.REQUIRE_AUTH) {
    console.log(`[DEV] Credit check skipped - required: ${requiredCredits}`);
    return user;
  }

  if (user.credits < requiredCredits) {
    throw new Error(`Insufficient credits. Required: ${requiredCredits}, Available: ${user.credits}`);
  }

  return user;
}

/**
 * Get user ID from session
 */
export async function getUserId(): Promise<string | null> {
  const { userId } = await auth();
  return userId;
}

/**
 * Legacy function for backwards compatibility
 * @deprecated Use getCurrentUser() instead
 */
export async function getClerkUser() {
  return getCurrentUser();
}

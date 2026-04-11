/**
 * Admin authentication utilities
 * Checks if user has admin privileges
 */

import { auth, getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/db";

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: string;
  credits: number;
}

/**
 * Check if current user is admin
 */
export async function isAdmin(): Promise<boolean> {
  const user = await getCurrentUser();
  if (!user) return false;

  // Development mode - allow dev user as admin
  if (process.env.NODE_ENV === "development" && user.email === "dev@photogenius.local") {
    return true;
  }

  // Check if user has admin role in database
  try {
    const dbUser = await prisma.user.findUnique({
      where: { id: user.id },
      select: { role: true },
    });

    return dbUser?.role === "ADMIN" || dbUser?.role === "SUPER_ADMIN";
  } catch (error) {
    console.error("[admin-auth] Error checking admin status:", error);
    return false;
  }
}

/**
 * Require admin privileges (throw if not admin)
 */
export async function requireAdmin(): Promise<AdminUser> {
  const user = await getCurrentUser();

  if (!user) {
    throw new Error("Authentication required");
  }

  const isAdminUser = await isAdmin();
  if (!isAdminUser) {
    throw new Error("Admin privileges required");
  }

  // Get full admin user data
  const adminUser = await prisma.user.findUnique({
    where: { id: user.id },
    select: {
      id: true,
      email: true,
      name: true,
      role: true,
      credits: true,
    },
  });

  if (!adminUser) {
    throw new Error("User not found");
  }

  return adminUser as AdminUser;
}

/**
 * Get admin user data if authenticated as admin
 */
export async function getAdminUser(): Promise<AdminUser | null> {
  try {
    const user = await getCurrentUser();
    if (!user) return null;

    const isAdminUser = await isAdmin();
    if (!isAdminUser) return null;

    const adminUser = await prisma.user.findUnique({
      where: { id: user.id },
      select: {
        id: true,
        email: true,
        name: true,
        role: true,
        credits: true,
      },
    });

    return adminUser as AdminUser | null;
  } catch (error) {
    console.error("[admin-auth] Error getting admin user:", error);
    return null;
  }
}

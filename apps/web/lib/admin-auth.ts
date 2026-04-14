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

  // Allow dev user as admin (bypass database check due to pgbouncer issues)
  if (user.email === "dev@photogenius.local") {
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

  // Return dev user directly (bypass database due to pgbouncer issues)
  if (user.email === "dev@photogenius.local") {
    return {
      id: user.id,
      email: user.email,
      name: user.name,
      role: "SUPER_ADMIN",
      credits: user.creditsBalance || 1000,
    };
  }

  // Get full admin user data from database
  const adminUser = await prisma.user.findUnique({
    where: { id: user.id },
    select: {
      id: true,
      email: true,
      name: true,
      role: true,
      creditsBalance: true,
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

    // Return dev user directly (bypass database due to pgbouncer issues)
    if (user.email === "dev@photogenius.local") {
      return {
        id: user.id,
        email: user.email,
        name: user.name,
        role: "SUPER_ADMIN",
        credits: user.creditsBalance || 1000,
      };
    }

    const adminUser = await prisma.user.findUnique({
      where: { id: user.id },
      select: {
        id: true,
        email: true,
        name: true,
        role: true,
        creditsBalance: true,
      },
    });

    return adminUser as AdminUser | null;
  } catch (error) {
    console.error("[admin-auth] Error getting admin user:", error);
    return null;
  }
}

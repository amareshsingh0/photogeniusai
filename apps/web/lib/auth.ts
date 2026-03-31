/**
 * Simplified authentication utilities for development
 * Clerk integration disabled for faster development
 */

// Dev mode user type
export interface DevUser {
  id: string
  email: string
  name: string
  credits: number
}

const DEV_USER: DevUser = {
  id: "dev_user_123",
  email: "dev@photogenius.local",
  name: "Dev User",
  credits: 1000,
}

/**
 * Get authentication state - returns dev user in development
 */
export async function auth() {
  return {
    userId: DEV_USER.id,
    getToken: async () => "dev_token_123"
  }
}

/**
 * Get current authenticated user from database
 */
export async function getCurrentUser(): Promise<DevUser | null> {
  return DEV_USER
}

/**
 * Require authentication (throw if not authenticated)
 * In dev mode, always returns the dev user
 */
export async function requireAuth(): Promise<DevUser> {
  return DEV_USER
}

/**
 * Check if user has sufficient credits
 * NOTE: Credit checks are DISABLED during development/testing phase
 */
export async function checkCredits(requiredCredits: number): Promise<DevUser> {
  console.log(`[DEV] Credit check skipped - required: ${requiredCredits}`)
  return DEV_USER
}

/**
 * Get Clerk user data - returns dev user in dev mode
 */
export async function getClerkUser() {
  return DEV_USER
}

/**
 * Get user ID from session
 */
export async function getUserId(): Promise<string | null> {
  return DEV_USER.id
}

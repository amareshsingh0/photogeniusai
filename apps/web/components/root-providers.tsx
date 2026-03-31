"use client";

// Clerk disabled in dev - auth handled by lib/auth.ts (DEV_USER)
// Re-enable when deploying to production with real Clerk keys
// import { ClerkProvider } from "@clerk/nextjs";

export function RootProviders({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

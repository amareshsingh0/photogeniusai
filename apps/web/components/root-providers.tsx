"use client";

// Custom JWT authentication system
// Auth handled by lib/auth.ts (JWT tokens + OAuth)

export function RootProviders({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

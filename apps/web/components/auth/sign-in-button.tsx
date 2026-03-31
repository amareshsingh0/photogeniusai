"use client";

import Link from "next/link";

/**
 * Sign-in button. Link to /login or use Clerk SignInButton when wired.
 */
export function SignInButton() {
  return (
    <Link
      href="/login"
      className="rounded-md bg-primary px-4 py-2 text-primary-foreground hover:opacity-90"
    >
      Sign in
    </Link>
  );
}

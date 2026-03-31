import Link from "next/link";

// Force dynamic rendering to prevent Clerk errors during CI builds
export const dynamic = 'force-dynamic';

/**
 * 404 page. Rendered when a route is not found.
 */
export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-bold">404</h1>
      <p className="text-muted-foreground">This page could not be found.</p>
      <Link href="/" className="text-primary underline hover:no-underline">
        Return home
      </Link>
    </div>
  );
}

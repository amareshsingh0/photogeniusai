// Force dynamic rendering for auth routes
// This prevents static generation errors with Clerk during CI builds
export const dynamic = 'force-dynamic';

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-primary/5">
      {children}
    </div>
  );
}

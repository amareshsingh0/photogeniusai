/**
 * Loading spinner. Reusable across app.
 */
export function LoadingSpinner({ className = "" }: { className?: string }) {
  return (
    <div
      className={`h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}

/**
 * Error message. Display API or validation errors.
 */
export function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-2 text-sm text-destructive">
      {message}
    </div>
  );
}

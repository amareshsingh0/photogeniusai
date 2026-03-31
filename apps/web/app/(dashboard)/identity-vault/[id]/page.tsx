import { notFound } from "next/navigation";

type Props = { params: Promise<{ id: string }> };

/**
 * Single identity detail page. Fetch by id and show training status, photos, etc.
 */
export default async function IdentityDetailPage({ params }: Props) {
  const { id } = await params;
  if (!id) notFound();
  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Identity</h1>
      <p className="text-muted-foreground">Identity detail for {id} (implement fetch by id).</p>
    </div>
  );
}

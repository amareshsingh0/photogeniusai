import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

type Props = { params: Promise<{ id: string }> };

/**
 * Single identity detail page. Fetch by id and show training status, photos, etc.
 * (Detail data wiring is implemented in a follow-up; this is the Lumen-styled shell.)
 */
export default async function IdentityDetailPage({ params }: Props) {
  const { id } = await params;
  if (!id) notFound();
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-24 space-y-6">
      <Link href="/identity-vault" className="inline-flex items-center gap-1.5 text-sm text-white/50 hover:text-white/80 transition">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to vault
      </Link>
      <div className="flex items-center gap-3">
        <div>
          <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Identity</h1>
          <p className="mt-1 font-mono text-[11px] text-white/60">{id}</p>
        </div>
      </div>
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <p className="kerned text-white/40 mb-2">DETAIL</p>
        <p className="text-sm text-white/50">Training status, consistency score, training photos and actions for this identity will appear here.</p>
      </div>
    </div>
  );
}

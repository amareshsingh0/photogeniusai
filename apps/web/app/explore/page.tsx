"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { samples, styles } from "@/lib/pixium/samples";
import { brandedImageUrl } from "@/lib/image-url";

interface GalleryItem {
  id: string;
  prompt: string;
  url: string | null;
  thumbnailUrl?: string;
  style?: string;
  likesCount?: number;
  user?: { id: string; name: string } | null;
}

export default function Explore() {
  const [q, setQ] = useState("");
  const [active, setActive] = useState<string | null>(null);
  const [remote, setRemote] = useState<GalleryItem[] | null>(null);
  const [loading, setLoading] = useState(true);

  // Pull the public community gallery; fall back to curated samples if empty/unavailable.
  useEffect(() => {
    (async () => {
      try {
        const params = new URLSearchParams({ sort: "recent", limit: "48" });
        if (active) params.set("style", active);
        const res = await fetch(`/api/gallery?${params}`);
        if (res.ok) {
          const data = await res.json();
          setRemote(Array.isArray(data.items) ? data.items : []);
        } else {
          setRemote([]);
        }
      } catch {
        setRemote([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [active]);

  // Normalize to a common shape; use samples as fallback when there's no real data.
  const items = useMemo(() => {
    const haveRemote = remote && remote.length > 0;
    if (haveRemote) {
      return remote!
        .filter((r) => r.url || r.thumbnailUrl)
        .filter((r) => !q || (r.prompt || "").toLowerCase().includes(q.toLowerCase()))
        .map((r) => ({
          id: r.id,
          src: (r.url || r.thumbnailUrl) as string,
          prompt: r.prompt || "",
          author: r.user?.name ? `@${r.user.name.replace(/\s+/g, "").toLowerCase()}` : "@anon",
          model: "",
          style: r.style || "",
        }));
    }
    // Fallback: curated samples, client-filtered
    return samples
      .filter((s) => (!active || s.style === active) && (!q || s.prompt.toLowerCase().includes(q.toLowerCase())))
      .map((s) => ({ id: s.id, src: s.src, prompt: s.prompt, author: s.author, model: s.model, style: s.style }));
  }, [remote, q, active]);

  return (
    <div className="mx-auto max-w-7xl px-4 pb-24">
      {/* Compact header — matches editor / video / generate */}
      <div className="flex items-center gap-2 py-3 text-sm">
        <span className="kerned text-white/40">Gallery</span>
        <span className="text-white/20">/</span>
        <span className="font-display">Explore</span>
        <span className="text-white/20">·</span>
        <span className="text-white/50">{items.length} images</span>
      </div>
      <div className="glass-panel sticky top-20 z-20 flex flex-col gap-3 rounded-2xl p-3 sm:flex-row sm:items-center">
        <div className="flex flex-1 items-center gap-2 rounded-xl bg-white/5 px-3 py-2">
          <Search className="h-4 w-4 text-white/40" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search prompts, models, creators…"
            className="w-full bg-transparent text-sm outline-none placeholder:text-white/30"
          />
        </div>
        <div className="flex flex-wrap gap-1.5 overflow-x-auto">
          <button onClick={() => setActive(null)} className={`shrink-0 rounded-full px-3 py-1 text-xs ${!active ? "bg-white text-black" : "bg-white/5 text-white/70"}`}>All</button>
          {styles.map((s) => (
            <button key={s} onClick={() => setActive(s)} className={`shrink-0 rounded-full px-3 py-1 text-xs ${active === s ? "bg-white text-black" : "bg-white/5 text-white/70 hover:bg-white/10"}`}>{s}</button>
          ))}
        </div>
      </div>
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-7 w-7 animate-spin text-white/30" />
        </div>
      ) : items.length === 0 ? (
        <div className="glass-panel mx-auto mt-10 max-w-md rounded-2xl p-8 text-center">
          <p className="font-display text-xl">Nothing here yet</p>
          <p className="mt-2 text-sm text-white/55">No public images match this filter — try another style, or be the first to publish one.</p>
          <Link href="/generate" className="mt-5 inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-black" style={{ background: "var(--gradient-aurora)" }}>Start creating</Link>
        </div>
      ) : (
        <div className="mt-6 columns-2 gap-3 sm:columns-3 sm:gap-4 lg:columns-4">
          {items.map((s) => (
            <Link href={`/showcase/${s.id}`} key={s.id} className="group mb-3 block break-inside-avoid overflow-hidden rounded-2xl hairline sm:mb-4">
              <div className="relative">
                <img src={brandedImageUrl(s.src)} alt={s.prompt} loading="lazy" className="w-full transition duration-700 group-hover:scale-[1.03]" />
                <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/85 via-transparent p-3 opacity-0 transition group-hover:opacity-100">
                  <p className="line-clamp-2 font-mono text-[10px] text-white/90">{s.prompt}</p>
                  <p className="kerned mt-1 text-white/50">{s.author}{s.model ? ` · ${s.model}` : ""}</p>
                </div>
                {s.style && <span className="absolute left-2 top-2 rounded-full bg-black/50 px-2 py-0.5 text-[10px] text-white/80 backdrop-blur">{s.style}</span>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

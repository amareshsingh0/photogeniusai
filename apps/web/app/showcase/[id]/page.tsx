"use client";

import Link from "next/link";
import { useParams, notFound } from "next/navigation";
import { samples } from "@/lib/pixium/samples";
import { ArrowLeft, Download, Heart, Share2, Wand2, Copy, Check } from "lucide-react";
import { useState } from "react";

export default function Showcase() {
  const params = useParams<{ id: string }>();
  const s = samples.find((x) => x.id === params.id);
  if (!s) {
    notFound();
  }
  const sample = s!;
  const related = samples.filter((x) => x.id !== sample.id).slice(0, 8);
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState(false);

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(sample.prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch { /* ignore */ }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 pb-16">
      {/* Compact breadcrumb header — matches /editor and /generate */}
      <div className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="flex items-center gap-2 text-sm">
          <Link href="/explore" className="inline-flex items-center gap-1 text-white/50 hover:text-white">
            <ArrowLeft className="h-3.5 w-3.5" /> Explore
          </Link>
          <span className="text-white/20">/</span>
          <span className="kerned text-white/40">Showcase</span>
          <span className="text-white/20">·</span>
          <span className="font-mono text-[11px] text-white/55">{sample.id}</span>
        </div>
        <Link
          href={`/generate?prompt=${encodeURIComponent(sample.prompt)}`}
          className="inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium text-black"
          style={{ background: "var(--gradient-aurora)" }}
        >
          <Wand2 className="h-3.5 w-3.5" /> Remix this
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.5fr_1fr]">
        {/* Image — viewport-bounded, contained (no huge overflow) */}
        <div
          className="relative flex items-center justify-center overflow-hidden rounded-2xl hairline"
          style={{
            background: "repeating-conic-gradient(oklch(0.16 0 0) 0% 25%, oklch(0.12 0 0) 0% 50%) 50% / 18px 18px",
            maxHeight: "calc(100vh - 160px)",
          }}
        >
          <img
            src={sample.src}
            alt={sample.prompt}
            className="block max-h-[calc(100vh-160px)] max-w-full object-contain"
          />
          {/* Floating badge */}
          <div className="glass-panel absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px]">
            <span className="kerned text-white/55">{sample.style}</span>
          </div>
        </div>

        {/* Inspector */}
        <aside className="space-y-3">
          <div className="glass-panel space-y-2 rounded-2xl p-4">
            <p className="font-display text-lg leading-snug">{sample.prompt}</p>
            <p className="text-xs text-white/55">by <span className="text-white/80">{sample.author}</span></p>
          </div>

          {/* Action row */}
          <div className="flex flex-wrap gap-1.5">
            <Link
              href={`/generate?prompt=${encodeURIComponent(sample.prompt)}`}
              className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium text-black"
              style={{ background: "var(--gradient-aurora)" }}
            >
              <Wand2 className="h-3.5 w-3.5" /> Remix
            </Link>
            <a
              href={sample.src}
              download
              className="glass-panel inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs hover:bg-white/10"
            >
              <Download className="h-3.5 w-3.5" /> Download
            </a>
            <button
              onClick={() => setLiked((v) => !v)}
              className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs transition ${liked ? "border border-rose-400/40 bg-rose-400/15 text-rose-200" : "glass-panel hover:bg-white/10"}`}
            >
              <Heart className={`h-3.5 w-3.5 ${liked ? "fill-current" : ""}`} /> {liked ? "Saved" : "Save"}
            </button>
            <button className="glass-panel inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs hover:bg-white/10">
              <Share2 className="h-3.5 w-3.5" /> Share
            </button>
          </div>

          {/* Prompt block (copyable) */}
          <div className="glass-panel rounded-2xl p-3">
            <div className="mb-1.5 flex items-center justify-between">
              <p className="kerned text-white/40">Prompt</p>
              <button
                onClick={copyPrompt}
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-white/55 hover:bg-white/10 hover:text-white"
              >
                {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <p className="font-mono text-[11px] leading-relaxed text-white/75">{sample.prompt}</p>
          </div>

          {/* Generation params */}
          <div className="glass-panel rounded-2xl p-4">
            <p className="kerned mb-2 text-white/40">Generation params</p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 font-mono text-[11px]">
              <dt className="text-white/40">style</dt><dd className="text-white/85">{sample.style}</dd>
              <dt className="text-white/40">steps</dt><dd className="text-white/85">40</dd>
              <dt className="text-white/40">cfg</dt><dd className="text-white/85">7.5</dd>
              <dt className="text-white/40">seed</dt><dd className="text-white/85">742193</dd>
              <dt className="text-white/40">size</dt><dd className="text-white/85">2048×2048</dd>
            </dl>
          </div>
        </aside>
      </div>

      {/* Related */}
      <div className="mt-10">
        <div className="mb-3 flex items-end justify-between">
          <div>
            <p className="kerned text-white/40">More like this</p>
            <h2 className="mt-0.5 font-display text-xl">Related work</h2>
          </div>
          <Link href="/explore" className="text-xs text-white/55 hover:text-white">
            Browse explore →
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
          {related.map((r) => (
            <Link
              href={`/showcase/${r.id}`}
              key={r.id}
              className="group relative aspect-square overflow-hidden rounded-xl hairline"
              title={r.prompt}
            >
              <img
                src={r.src}
                alt={r.prompt}
                loading="lazy"
                className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-linear-to-t from-black/70 via-transparent opacity-0 transition group-hover:opacity-100" />
              <p className="kerned absolute bottom-1 left-1.5 right-1.5 truncate text-[9px] text-white/85 opacity-0 transition group-hover:opacity-100">
                {r.style} · {r.author}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

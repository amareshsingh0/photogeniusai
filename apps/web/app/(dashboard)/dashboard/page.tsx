"use client";

import Link from "next/link";
import { samples } from "@/lib/pixium/samples";
import { Sparkles, ArrowUpToLine, Film, TrendingUp } from "lucide-react";

function Ring({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div className="glass-panel flex items-center gap-4 rounded-2xl p-4">
      <div className="relative h-16 w-16">
        <svg viewBox="0 0 36 36" className="h-16 w-16 -rotate-90">
          <circle cx="18" cy="18" r="14" fill="none" stroke="oklch(1 0 0 / 0.1)" strokeWidth="3" />
          <circle cx="18" cy="18" r="14" fill="none" stroke={color} strokeWidth="3" strokeDasharray={`${value * 0.88} 100`} strokeLinecap="round" />
        </svg>
        <span className="absolute inset-0 grid place-items-center font-mono text-xs">{value}%</span>
      </div>
      <div>
        <p className="kerned text-white/40">{label}</p>
        <p className="font-display text-xl">{Math.round(value * 30)}</p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  return (
    <div className="mx-auto max-w-7xl px-4 pb-24">
      <div className="flex items-end justify-between py-8">
        <div>
          <p className="kerned text-white/40">Welcome back</p>
          <h1 className="mt-2 font-display text-4xl sm:text-5xl">Kira's studio</h1>
        </div>
        <Link href="/generate" className="inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-medium text-black" style={{ background: "var(--gradient-aurora)" }}>
          <Sparkles className="h-4 w-4" /> New generation
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Ring value={62} label="Generations" color="oklch(0.68 0.27 305)" />
        <Ring value={34} label="Upscales" color="oklch(0.78 0.18 200)" />
        <Ring value={18} label="Videos" color="oklch(0.72 0.25 350)" />
        <Ring value={84} label="Credits used" color="oklch(0.82 0.16 80)" />
      </div>

      <section className="mt-10">
        <div className="mb-4 flex items-end justify-between">
          <h2 className="font-display text-2xl">Recent generations</h2>
          <Link href="/explore" className="text-sm text-white/60">View all</Link>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          {samples.slice(0, 12).map((s) => (
            <Link href={`/showcase/${s.id}`} key={s.id} className="group aspect-square overflow-hidden rounded-2xl hairline">
              <img src={s.src} alt={s.prompt} loading="lazy" className="h-full w-full object-cover transition group-hover:scale-105" />
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-12 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {[
          { icon: TrendingUp, t: "This week", v: "+126", d: "Generations vs last week" },
          { icon: ArrowUpToLine, t: "Best quality", v: "12K", d: "Highest upscale this month" },
          { icon: Film, t: "Collections", v: "8", d: "Saved boards & sets" },
        ].map((c) => (
          <div key={c.t} className="glass-panel rounded-3xl p-6">
            <c.icon className="h-5 w-5 text-white/60" />
            <p className="mt-4 font-display text-4xl">{c.v}</p>
            <p className="kerned mt-1 text-white/40">{c.t}</p>
            <p className="mt-2 text-sm text-white/60">{c.d}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

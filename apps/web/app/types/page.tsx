"use client";

import Link from "next/link";
import { types } from "@/lib/pixium/samples";
import { ArrowRight } from "lucide-react";

export default function Types() {
  return (
    <div className="mx-auto max-w-7xl px-4 pb-24">
      {/* Compact header (matches editor / video) */}
      <div className="flex items-center gap-2 py-3 text-sm">
        <span className="kerned text-white/40">Studio</span>
        <span className="text-white/20">/</span>
        <span className="font-display">Types</span>
        <span className="text-white/20">·</span>
        <span className="text-white/50">{types.length} capabilities</span>
      </div>

      {/* Cards */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {types.map((t) => (
          <Link
            key={t.id}
            href={`/generate?type=${t.id}`}
            className="glass-panel group flex flex-col overflow-hidden rounded-2xl transition hover:-translate-y-0.5"
          >
            {/* Sample strip — bigger, 4-up row */}
            <div className="grid grid-cols-4 gap-px overflow-hidden">
              {t.samples.slice(0, 4).map((s, i) => (
                <div key={i} className="aspect-[3/4] overflow-hidden bg-white/[0.02]">
                  <img
                    src={s}
                    alt=""
                    loading="lazy"
                    className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                  />
                </div>
              ))}
            </div>
            {/* Meta */}
            <div className="flex flex-1 flex-col gap-1.5 p-5">
              <div className="flex items-start justify-between gap-2">
                <p className="font-display text-2xl tracking-tight">{t.name}</p>
                <span className="kerned mt-1.5 shrink-0 rounded-full bg-white/5 px-2 py-0.5 text-white/45">{t.tag}</span>
              </div>
              <p className="text-sm leading-relaxed text-white/55">{t.description}</p>
              <span className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-white/70 transition group-hover:text-white">
                Try this <ArrowRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

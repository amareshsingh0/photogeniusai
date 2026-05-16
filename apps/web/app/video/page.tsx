"use client";

import { Film, Play, Camera } from "lucide-react";
import { samples } from "@/lib/pixium/samples";

export default function Video() {
  const presets = ["Slow zoom in", "Push", "Orbit", "Parallax", "Dolly", "Aerial"];
  return (
    <div className="mx-auto flex h-[calc(100vh-5rem)] max-w-7xl flex-col px-4 pb-4">
      {/* Header hidden on desktop for max content space; visible on mobile/tablet */}
      <div className="flex shrink-0 items-center gap-2 py-2 text-sm lg:hidden">
        <span className="kerned text-white/40">Studio</span>
        <span className="text-white/20">/</span>
        <span className="font-display">Image to Video</span>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        {/* Preview + timeline */}
        <section className="flex min-h-0 min-w-0 flex-col gap-3">
          <div className="glass-panel relative flex flex-1 items-center justify-center overflow-hidden rounded-3xl bg-black" style={{ minHeight: 160 }}>
            <img src={samples[6].src} alt="preview" className="max-h-full max-w-full object-contain" />
            <button className="absolute grid h-16 w-16 place-items-center rounded-full bg-white/90 text-black" style={{ boxShadow: "var(--shadow-glow)" }}>
              <Play className="h-6 w-6 fill-black" />
            </button>
            <span className="kerned absolute left-3 top-3 rounded-md bg-black/65 px-2 py-1 backdrop-blur">Coming soon</span>
          </div>
          <div className="glass-panel shrink-0 rounded-2xl p-3">
            <p className="kerned mb-2 text-white/50">Timeline · 5s</p>
            <div className="relative h-12 overflow-hidden rounded-lg bg-white/5">
              <div className="absolute inset-y-0 flex">
                {samples.slice(0, 10).map((s, i) => (
                  <div key={i} className="h-full w-12 overflow-hidden border-r border-white/10">
                    <img src={s.src} alt="" className="h-full w-full object-cover" />
                  </div>
                ))}
              </div>
              <div className="absolute inset-y-0 left-1/3 w-0.5 bg-white" />
            </div>
          </div>
        </section>

        {/* Controls */}
        <aside className="glass-panel no-scrollbar min-h-0 space-y-4 overflow-y-auto rounded-3xl p-4">
          <div>
            <p className="kerned mb-2 text-white/50"><Camera className="mr-1 inline h-3 w-3" /> Camera move</p>
            <div className="grid grid-cols-2 gap-1.5">
              {presets.map((p, i) => (
                <button key={p} className={`rounded-xl border border-white/10 bg-white/5 p-2 text-left text-xs ${i === 0 ? "ring-1 ring-white/30" : ""}`}>
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="kerned mb-2 text-white/50">Motion intensity</p>
            <input type="range" defaultValue={45} className="w-full accent-white" />
          </div>
          <div>
            <p className="kerned mb-2 text-white/50">Duration</p>
            <div className="flex gap-1.5">
              {["3s", "5s", "10s"].map((d, i) => (
                <button key={d} className={`flex-1 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-xs ${i === 1 ? "ring-1 ring-white/30" : ""}`}>{d}</button>
              ))}
            </div>
          </div>
          <button className="inline-flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium text-black" style={{ background: "var(--gradient-aurora)" }}>
            <Film className="h-4 w-4" /> Render · 24 credits
          </button>
        </aside>
      </div>
    </div>
  );
}

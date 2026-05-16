"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowRight, Sparkles, Wand2, Layers, ArrowUpToLine, Film, Boxes,
  Compass, Command, CornerDownLeft,
} from "lucide-react";
import { samples, models } from "@/lib/pixium/samples";

export default function Index() {
  return (
    <>
      <Hero />
      <ToolStrip />
      <LiveFeed />
      <ModelStrip />
      <ShowcaseGrid />
      <FinalCTA />
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Hero — full-bleed image showcase + centered floating prompt bar
// ─────────────────────────────────────────────────────────────────────────────
function Hero() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [activeChip, setActiveChip] = useState("Cinematic");
  const chips = ["Cinematic", "Anime", "Photoreal", "3D", "Editorial", "Surreal", "Vector"];

  const go = () => {
    const q = new URLSearchParams();
    if (prompt.trim()) q.set("prompt", prompt.trim());
    if (activeChip && activeChip !== "Cinematic") q.set("style", activeChip);
    router.push(`/generate${q.toString() ? `?${q}` : ""}`);
  };

  return (
    <section className="relative -mt-20 min-h-[72vh] overflow-hidden sm:min-h-[88vh]">
      {/* Living image wall — cinematic marquee + blur-up shuffle + parallax */}
      <LivingWall />

      {/* Dark legibility scrim */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/55 via-black/75 to-[var(--ink)]" />
      <div className="pointer-events-none absolute inset-0" style={{ background: "radial-gradient(60% 50% at 50% 45%, rgba(0,0,0,0.4), transparent)" }} />

      {/* Foreground */}
      <div className="relative z-10 mx-auto flex min-h-[72vh] max-w-3xl flex-col items-center justify-center px-4 pt-24 pb-10 text-center sm:min-h-[88vh] sm:pt-28 sm:pb-16">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="glass-panel mb-6 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          <span className="kerned text-white/75">Real-time AI studio · live</span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05 }}
          className="font-display text-[44px] font-light leading-[0.95] tracking-tight sm:text-7xl lg:text-[88px]"
        >
          Image making,<br />
          <span className="text-aurora italic">reimagined.</span>
        </motion.h1>

        {/* Prompt bar — real input, routes to /generate */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mt-10 w-full max-w-2xl"
        >
          <div className="glass-panel rounded-3xl p-2.5" style={{ boxShadow: "var(--shadow-float)" }}>
            <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-black/40 px-3 py-2.5">
              <Wand2 className="h-4 w-4 shrink-0 text-white/50" aria-hidden />
              <input
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") go(); }}
                placeholder="Describe an image — a portrait bathed in northern lights, 85mm…"
                className="min-w-0 flex-1 bg-transparent text-sm text-white/90 outline-none placeholder:text-white/35"
              />
              <span className="kerned hidden items-center gap-1 rounded-md bg-white/10 px-2 py-1 text-white/60 sm:inline-flex">
                <Command className="h-3 w-3" aria-hidden /> <CornerDownLeft className="h-3 w-3" aria-hidden />
              </span>
              <button onClick={go} className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl px-3.5 text-xs font-medium text-black" style={{ background: "var(--gradient-aurora)" }}>
                <Sparkles className="h-3.5 w-3.5" aria-hidden /> Generate
              </button>
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-center gap-1.5 px-1">
              {chips.map((c) => (
                <button
                  key={c}
                  onClick={() => setActiveChip(c)}
                  className={`rounded-full px-2.5 py-1 text-[11px] transition ${activeChip === c ? "bg-white text-black" : "bg-white/[0.06] text-white/65 hover:bg-white/10"}`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.35 }}
          className="mt-5 flex flex-wrap items-center justify-center gap-3"
        >
          <Link href="/generate" className="text-sm text-white/55 underline-offset-4 hover:text-white hover:underline">Open the full studio</Link>
          <span className="text-white/20">·</span>
          <Link href="/explore" className="text-sm text-white/55 underline-offset-4 hover:text-white hover:underline">Browse the gallery</Link>
        </motion.div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// LivingWall — cinematic marquee of images, alternating direction + speed,
// blur-up shuffle on a random tile every ~5s, subtle mouse parallax.
// Tries to fetch real public gallery images; falls back to sample assets.
// ─────────────────────────────────────────────────────────────────────────────
type WallImg = { src: string; key: string };
const NUM_COLS = 6;
const COL_SPEEDS = [55, 38, 62, 44, 70, 50]; // seconds per loop, varied
const COL_DIRS = [1, -1, 1, -1, 1, -1];      // 1 = up, -1 = down

function LivingWall() {
  const [pool, setPool] = useState<WallImg[]>(() =>
    samples.map((s, i) => ({ src: s.src, key: `sample-${i}` }))
  );
  const [tick, setTick] = useState(0); // forces re-shuffle of a random tile
  // Mouse parallax removed — see comment in the useEffect below.

  // Try to enrich pool with real public gallery generations (non-blocking)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/gallery?sort=recent&limit=48");
        if (!res.ok) return;
        const data = await res.json();
        const items = (data.items || data.generations || []) as Array<{
          id: string;
          selectedOutputUrl?: string;
          thumbnailUrl?: string;
          outputUrls?: string[];
        }>;
        const real = items
          .map((g) => ({
            src: g.thumbnailUrl || g.selectedOutputUrl || (g.outputUrls && g.outputUrls[0]) || "",
            key: g.id,
          }))
          .filter((g) => g.src);
        if (!cancelled && real.length >= 12) setPool(real);
      } catch {
        /* keep samples */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Per-column image lists (doubled for seamless scroll loop). Re-derived when pool/tick changes.
  const cols = useMemo(() => {
    const out: WallImg[][] = Array.from({ length: NUM_COLS }, () => []);
    pool.forEach((img, i) => out[i % NUM_COLS].push(img));
    // Ensure each column has at least 6 images by repeating from pool
    out.forEach((col, ci) => {
      while (col.length < 6 && pool.length) col.push(pool[(col.length + ci) % pool.length]);
    });
    // Double each column so the keyframes can translate -50% for seamless loop
    return out.map((col) => [...col, ...col]);
  }, [pool, tick]);

  // Periodic blur-up shuffle: every ~5s, rotate the pool order by one,
  // which makes one random-looking tile swap to a fresh image with the
  // CSS blur-in animation re-triggered via key change.
  useEffect(() => {
    const id = setInterval(() => {
      setPool((prev) => {
        if (prev.length < 2) return prev;
        const idx = Math.floor(Math.random() * prev.length);
        // Move a random element to a different random position
        const next = [...prev];
        const [item] = next.splice(idx, 1);
        const insertAt = Math.floor(Math.random() * next.length);
        next.splice(insertAt, 0, { ...item, key: `${item.key}-${Date.now()}` });
        return next;
      });
      setTick((t) => t + 1);
    }, 4800);
    return () => clearInterval(id);
  }, []);

  // Mouse parallax disabled — was repainting on every mousemove and causing
  // scroll lag. The constant-speed marquee scroll already gives plenty of motion.
  // To re-enable selectively: only attach the listener on hover of the wall,
  // throttle to 16ms or coarser, and only transform a single will-change layer.

  return (
    <>
      <style jsx>{`
        @keyframes wallUp {
          from { transform: translateY(0); }
          to { transform: translateY(-50%); }
        }
        @keyframes wallDown {
          from { transform: translateY(-50%); }
          to { transform: translateY(0); }
        }
        @keyframes blurIn {
          0% { filter: blur(18px); opacity: 0; transform: scale(1.04); }
          100% { filter: blur(0); opacity: 1; transform: scale(1); }
        }
        .wall-col {
          will-change: transform;
          animation-timing-function: linear;
          animation-iteration-count: infinite;
        }
        .wall-col:hover { animation-play-state: paused; }
        .wall-tile {
          animation: blurIn 1.2s ease-out both;
        }
        @media (prefers-reduced-motion: reduce) {
          .wall-col { animation: none !important; }
          .wall-tile { animation: none !important; }
        }
      `}</style>

      <div
        className="pointer-events-none absolute inset-0 grid grid-cols-2 gap-2 overflow-hidden p-2 sm:grid-cols-4 sm:gap-3 sm:p-3 lg:grid-cols-6"
        style={{ transform: "scale(1.04)" }}
      >
        {cols.map((col, ci) => {
          const speed = COL_SPEEDS[ci] || 50;
          const dir = COL_DIRS[ci] || 1;
          const animName = dir > 0 ? "wallUp" : "wallDown";
          return (
            <div
              key={ci}
              className={`relative ${ci > 2 ? "hidden lg:block" : ""} ${ci === 2 ? "hidden sm:block" : ""}`}
            >
              <div
                className="wall-col flex flex-col gap-2 sm:gap-3"
                style={{
                  animationName: animName,
                  animationDuration: `${speed}s`,
                  animationDelay: `${ci * -3}s`,
                }}
              >
                {col.map((img, i) => (
                  <div
                    key={`${img.key}-${i}`}
                    className="wall-tile overflow-hidden rounded-2xl hairline"
                    style={{ animationDelay: `${(i % 3) * 0.15}s` }}
                  >
                    <img
                      src={img.src}
                      alt=""
                      loading="lazy"
                      className={`w-full object-cover ${i % 3 === 0 ? "aspect-[3/4]" : i % 3 === 1 ? "aspect-square" : "aspect-[4/5]"}`}
                    />
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool strip — compact icon row (replaces the old text-heavy feature cards)
// ─────────────────────────────────────────────────────────────────────────────
function ToolStrip() {
  const tools = [
    { href: "/generate", icon: Wand2, label: "Create", sub: "Text → image" },
    { href: "/editor", icon: Layers, label: "Edit", sub: "Inpaint · remix · objects" },
    { href: "/editor?tool=upscale", icon: ArrowUpToLine, label: "Upscale", sub: "Up to 16K" },
    { href: "/video", icon: Film, label: "Video", sub: "Animate stills" },
    { href: "/types", icon: Boxes, label: "Types", sub: "6 tuned engines" },
    { href: "/explore", icon: Compass, label: "Explore", sub: "Community feed" },
  ];
  return (
    <section className="relative mx-auto -mt-8 max-w-6xl px-4">
      <div className="glass-panel grid grid-cols-2 gap-1 rounded-3xl p-2 sm:grid-cols-3 lg:grid-cols-6" style={{ boxShadow: "var(--shadow-float)" }}>
        {tools.map((t) => {
          const Icon = t.icon;
          return (
            <Link
              key={t.href}
              href={t.href}
              className="group flex flex-col items-start gap-1 rounded-2xl px-3 py-3 transition hover:bg-white/[0.06]"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/[0.06] text-white/75 transition group-hover:bg-white/10">
                <Icon className="h-4 w-4" />
              </div>
              <p className="font-display text-sm">{t.label}</p>
              <p className="kerned text-white/35">{t.sub}</p>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Live feed marquee
// ─────────────────────────────────────────────────────────────────────────────
function LiveFeed() {
  const row = [...samples, ...samples];
  return (
    <section className="relative mt-20 overflow-hidden py-8">
      <div className="mb-5 flex items-end justify-between px-4 sm:px-8">
        <div>
          <p className="kerned text-white/40">Fresh from the community</p>
          <h2 className="font-display text-2xl tracking-tight sm:text-3xl">Generated, just now.</h2>
        </div>
        <Link href="/explore" className="hidden text-sm text-white/55 hover:text-white sm:inline-flex sm:items-center sm:gap-1">View all <ArrowRight className="h-4 w-4" /></Link>
      </div>
      <div className="flex gap-3 animate-marquee">
        {row.map((s, i) => (
          <figure key={`${s.id}-${i}`} className="relative h-48 w-36 shrink-0 overflow-hidden rounded-2xl hairline sm:h-64 sm:w-48">
            <img src={s.src} alt={s.prompt} loading="lazy" className="h-full w-full object-cover" />
            <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-2.5">
              <p className="line-clamp-2 font-mono text-[10px] text-white/80">{s.prompt}</p>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Types / model strip — each card's 4-tile filmstrip slowly Ken-Burns-pans +
// cross-fades to a fresh sample every ~3s. Hover pauses everything.
// ─────────────────────────────────────────────────────────────────────────────
function ModelStrip() {
  return (
    <section className="relative mx-auto mt-20 max-w-7xl px-4">
      <style jsx>{`
        @keyframes kenBurns {
          0%   { transform: scale(1.08) translate(0, 0); }
          50%  { transform: scale(1.14) translate(-1.5%, 1.5%); }
          100% { transform: scale(1.08) translate(1.5%, -1%); }
        }
        @keyframes tileFade {
          0%, 90%, 100% { opacity: 1; }
          45%, 55%      { opacity: 0; }
        }
        .ks-strip:hover .ks-tile,
        .ks-strip:hover .ks-tile-img { animation-play-state: paused; }
        .ks-tile-img {
          animation: kenBurns 32s ease-in-out infinite alternate;
          will-change: transform;
        }
        @media (prefers-reduced-motion: reduce) {
          .ks-tile-img, .ks-tile-swap { animation: none !important; }
        }
      `}</style>
      <div className="mb-8 flex items-end justify-between">
        <div>
          <p className="kerned text-white/40">Tuned for every medium</p>
          <h2 className="mt-1.5 font-display text-3xl tracking-tight sm:text-4xl">Pick your type.</h2>
        </div>
        <Link href="/types" className="text-sm text-white/55 hover:text-white">All types →</Link>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {models.map((m, mi) => (
          <Link href={`/generate?type=${m.id}`} key={m.id} className="glass-panel group block overflow-hidden rounded-2xl p-2 transition hover:-translate-y-0.5">
            <div className="ks-strip grid grid-cols-4 gap-px overflow-hidden rounded-xl">
              {m.samples.map((s, i) => (
                <ModelTileSwap
                  key={i}
                  initialSrc={s}
                  delay={(mi * 4 + i) * 700}
                />
              ))}
            </div>
            <div className="flex items-center justify-between px-2 py-2.5">
              <div>
                <p className="font-display text-lg">{m.name}</p>
                <p className="kerned text-white/40">{m.tag}</p>
              </div>
              <ArrowRight className="h-4 w-4 text-white/35 transition group-hover:translate-x-0.5 group-hover:text-white" />
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

function ModelTileSwap({ initialSrc, delay }: { initialSrc: string; delay: number }) {
  const pool = useMemo(() => samples.map((s) => s.src), []);
  const [src, setSrc] = useState(initialSrc);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    if (pool.length < 2) return;
    let intervalId: ReturnType<typeof setInterval> | null = null;
    let fadeTimeout: ReturnType<typeof setTimeout> | null = null;
    const startTimeout = setTimeout(() => {
      intervalId = setInterval(() => {
        setFading(true);
        fadeTimeout = setTimeout(() => {
          setSrc((cur) => {
            let next = pool[Math.floor(Math.random() * pool.length)];
            if (next === cur && pool.length > 1) {
              next = pool[(pool.indexOf(cur) + 1) % pool.length];
            }
            return next;
          });
          setFading(false);
        }, 600);
      }, 6500 + Math.random() * 1500);
    }, delay);
    return () => {
      clearTimeout(startTimeout);
      if (intervalId) clearInterval(intervalId);
      if (fadeTimeout) clearTimeout(fadeTimeout);
    };
  }, [pool, delay]);

  return (
    <div className="ks-tile aspect-[3/4] overflow-hidden bg-white/[0.02]">
      <img
        src={src}
        alt=""
        loading="lazy"
        className="ks-tile-img h-full w-full object-cover transition-opacity duration-700"
        style={{
          opacity: fading ? 0 : 1,
          animationDelay: `${(delay % 8000) * -0.004}s`,
        }}
      />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Community showcase masonry — stagger blur-in on viewport intersection,
// subtle idle drift on hover-out, sharp aurora glow on hover.
// ─────────────────────────────────────────────────────────────────────────────
function ShowcaseGrid() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const tiles = containerRef.current.querySelectorAll<HTMLElement>(".sg-tile");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            (entry.target as HTMLElement).classList.add("sg-in");
            io.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.05 }
    );
    tiles.forEach((t) => io.observe(t));
    return () => io.disconnect();
  }, []);

  return (
    <section className="relative mx-auto mt-20 max-w-7xl px-4">
      <style jsx>{`
        @keyframes sgIn {
          from { opacity: 0; filter: blur(14px); transform: translateY(18px) scale(0.98); }
          to   { opacity: 1; filter: blur(0);    transform: translateY(0)    scale(1);    }
        }
        .sg-tile {
          opacity: 0;
        }
        .sg-tile.sg-in {
          animation: sgIn 1s cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
          will-change: auto; /* drop will-change once entrance is done so the
                                browser can stop reserving a GPU layer per tile */
        }
        /* Per-tile drift animation removed — 32 simultaneous infinite transforms
           caused noticeable scroll jank on lower-end machines. The entrance
           blur-up still gives a sense of motion. */
        .sg-glow {
          position: absolute; inset: -1px; border-radius: 1rem; pointer-events: none;
          background: var(--gradient-aurora);
          opacity: 0; filter: blur(20px);
          transition: opacity 600ms ease;
        }
        .sg-tile:hover .sg-glow { opacity: 0.45; }
        @media (prefers-reduced-motion: reduce) {
          .sg-tile, .sg-tile .sg-inner { animation: none !important; opacity: 1 !important; filter: none !important; transform: none !important; }
        }
      `}</style>
      <div className="mb-8 flex items-end justify-between">
        <div>
          <p className="kerned text-white/40">Community</p>
          <h2 className="mt-1.5 font-display text-3xl tracking-tight sm:text-4xl">Made with Pixium.</h2>
        </div>
        <Link href="/explore" className="text-sm text-white/55 hover:text-white">See more →</Link>
      </div>
      <div ref={containerRef} className="columns-2 gap-3 sm:columns-3 sm:gap-4 lg:columns-4">
        {/* Show each sample only once — doubling was producing visible duplicate
            pairs in the "Made with Pixium" grid. With 24 distinct samples the
            masonry already fills the viewport on most screens. */}
        {samples.map((s, i) => (
          <Link
            href={`/showcase/${s.id}`}
            key={`${s.id}-${i}`}
            className="sg-tile group relative mb-3 block break-inside-avoid sm:mb-4"
            style={{
              animationDelay: `${(i % 8) * 80}ms`,
              // stagger the drift cycle so tiles don't move in lockstep
              ["--drift-delay" as string]: `${(i % 5) * -1.8}s`,
            }}
          >
            <span className="sg-glow" />
            <div className="sg-inner relative overflow-hidden rounded-2xl hairline" style={{ animationDelay: `var(--drift-delay)` }}>
              <img src={s.src} alt={s.prompt} loading="lazy" className="w-full transition duration-700 group-hover:scale-[1.03]" />
              <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/85 via-transparent p-3 opacity-0 transition group-hover:opacity-100">
                <p className="line-clamp-2 font-mono text-[10px] text-white/90">{s.prompt}</p>
                <p className="kerned mt-1 text-white/50">{s.author} · {s.model}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Final CTA — horizontal infinite scrolling image strip behind the panel,
// breathing aurora blobs, glowing CTA button.
// ─────────────────────────────────────────────────────────────────────────────
function FinalCTA() {
  // Long strip so the marquee never looks empty
  const strip = useMemo(() => {
    const ids = [0, 5, 2, 6, 8, 3, 11, 10, 1, 7, 4, 9];
    const picked = ids.map((i) => samples[i]).filter(Boolean);
    return [...picked, ...picked, ...picked]; // triple for seamless loop
  }, []);

  return (
    <section className="relative mx-auto mt-12 w-full px-2 pb-2 sm:px-3 sm:pb-3">
      <style jsx>{`
        @keyframes ctaMarquee {
          from { transform: translateX(0); }
          to   { transform: translateX(-33.333%); }
        }
        @keyframes ctaBreathe1 {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1);   opacity: 0.45; }
          50%      { transform: translate3d(20px, -15px, 0) scale(1.15); opacity: 0.6;  }
        }
        @keyframes ctaBreathe2 {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1);   opacity: 0.35; }
          50%      { transform: translate3d(-25px, 20px, 0) scale(1.2); opacity: 0.55; }
        }
        @keyframes ctaPulseGlow {
          0%, 100% { box-shadow: 0 0 0 0 rgba(255,255,255,0.0), var(--shadow-glow); }
          50%      { box-shadow: 0 0 0 8px rgba(255,255,255,0.06), var(--shadow-glow); }
        }
        .cta-marquee {
          display: flex;
          gap: 12px;
          width: max-content;
          animation: ctaMarquee 38s linear infinite;
          will-change: transform;
        }
        .cta-marquee:hover { animation-play-state: paused; }
        .cta-blob-1 { animation: ctaBreathe1 11s ease-in-out infinite; }
        .cta-blob-2 { animation: ctaBreathe2 13s ease-in-out infinite; }
        .cta-go     { animation: ctaPulseGlow 2.6s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .cta-marquee, .cta-blob-1, .cta-blob-2, .cta-go { animation: none !important; }
        }
      `}</style>
      <div className="relative overflow-hidden rounded-3xl border border-white/10">
        {/* Horizontal infinite scrolling collage backdrop */}
        <div className="pointer-events-none absolute inset-0 flex items-center">
          <div className="cta-marquee">
            {strip.map((s, i) => (
              <div
                key={i}
                className={`shrink-0 overflow-hidden rounded-xl ${i % 2 ? "translate-y-3" : "-translate-y-2"}`}
                style={{ width: "140px" }}
              >
                <img src={s.src} alt="" loading="lazy" className="aspect-[3/4] w-full object-cover" />
              </div>
            ))}
          </div>
        </div>
        {/* Vivid gradient + scrim */}
        <div className="pointer-events-none absolute inset-0" style={{ background: "linear-gradient(135deg, rgba(79,140,255,0.35), rgba(168,85,247,0.3) 45%, rgba(236,72,153,0.3))", mixBlendMode: "color" }} />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/55 via-black/80 to-black/90 backdrop-blur-[2px]" />
        <div className="cta-blob-1 pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full blur-3xl" style={{ background: "var(--gradient-aurora)" }} />
        <div className="cta-blob-2 pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full blur-3xl" style={{ background: "linear-gradient(135deg,#a855f7,#ec4899)" }} />

        {/* Content */}
        <div className="relative z-10 flex flex-col items-center px-6 py-14 text-center sm:px-12 sm:py-16">
          <span className="kerned mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-white/75 backdrop-blur">
            <Sparkles className="h-3 w-3" /> Start free — no card
          </span>
          <h2 className="font-display text-3xl font-light leading-[0.95] tracking-tight sm:text-6xl">
            Your next great image<br />
            <span className="text-aurora italic">is one prompt away.</span>
          </h2>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href="/generate" className="cta-go inline-flex items-center gap-2 rounded-2xl px-6 py-3 text-sm font-medium text-black" style={{ background: "var(--gradient-aurora)", boxShadow: "var(--shadow-glow)" }}>
              Open the studio <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/explore" className="glass-panel inline-flex items-center gap-2 rounded-2xl px-6 py-3 text-sm">
              Browse the gallery
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  Sparkles, Compass, Wand2, Layers, ArrowUpToLine, Film, Boxes, CreditCard,
  LayoutDashboard, User, LogOut, ChevronDown, Settings,
} from "lucide-react";

const links = [
  { to: "/explore", label: "Explore", icon: Compass },
  { to: "/generate", label: "Create", icon: Wand2 },
  { to: "/editor", label: "Edit", icon: Layers },
  { to: "/editor?tool=upscale", label: "Upscale", icon: ArrowUpToLine },
  { to: "/video", label: "Video", icon: Film },
  { to: "/types", label: "Types", icon: Boxes },
  { to: "/pricing", label: "Pricing", icon: CreditCard },
] as const;

export function SiteNav() {
  const path = usePathname() ?? "/";
  return (
    <header className="fixed left-1/2 top-3 z-50 w-[min(1200px,calc(100vw-1rem))] -translate-x-1/2">
      <nav
        aria-label="Primary"
        className="glass-panel flex items-center justify-between rounded-2xl px-3 py-2"
        style={{ boxShadow: "var(--shadow-float)" }}
      >
        <Link href="/" className="flex items-center gap-2 px-2" aria-label="Pixium home">
          <span aria-hidden className="relative grid h-7 w-7 place-items-center rounded-lg" style={{ background: "var(--gradient-aurora)" }}>
            <Sparkles className="h-4 w-4 text-black/80" strokeWidth={2.5} />
          </span>
          <span className="font-display text-lg font-semibold tracking-tight">Pixium</span>
        </Link>
        <ul className="hidden items-center gap-1 lg:flex">
          {links.map((l) => {
            const active = path === l.to || path.startsWith(l.to + "/");
            return (
              <li key={l.to}>
                <Link
                  href={l.to}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-xl px-3 py-1.5 text-sm transition ${active ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"}`}
                >
                  {l.label}
                </Link>
              </li>
            );
          })}
        </ul>
        <div className="flex items-center gap-2">
          <CreditOrb credits={847} />
          <Link
            href="/generate"
            className="relative inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-medium text-black"
            style={{ background: "var(--gradient-aurora)" }}
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden /> Generate
          </Link>
          <AccountMenu />
        </div>
      </nav>
    </header>
  );
}

function AccountMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") setOpen(false); }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 p-1 pr-2 hover:bg-white/10"
      >
        <span aria-hidden className="grid h-6 w-6 place-items-center rounded-lg font-display text-[11px] text-black" style={{ background: "var(--gradient-aurora)" }}>P</span>
        <ChevronDown className="h-3 w-3 text-white/60" aria-hidden />
      </button>
      {open && (
        <div role="menu" className="glass-panel absolute right-0 mt-2 w-64 overflow-hidden rounded-2xl p-2" style={{ boxShadow: "var(--shadow-float)" }}>
          <div className="px-3 py-2">
            <p className="text-sm font-medium">Pixium User</p>
            <p className="truncate text-xs text-white/50">dev@photogenius.local</p>
          </div>
          <div className="my-1 h-px bg-white/10" />
          {[
            { to: "/dashboard", label: "Studio", icon: LayoutDashboard },
            { to: "/account", label: "Account", icon: User },
            { to: "/settings", label: "Settings", icon: Settings },
          ].map((i) => (
            <Link key={i.label} href={i.to} role="menuitem" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-white/80 hover:bg-white/10">
              <i.icon className="h-4 w-4 text-white/50" aria-hidden /> {i.label}
            </Link>
          ))}
          <div className="my-1 h-px bg-white/10" />
          <button
            role="menuitem"
            onClick={async () => {
              try { await fetch("/api/auth/logout", { method: "POST" }); } catch {}
              window.location.href = "/login";
            }}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-white/70 hover:bg-white/10"
          >
            <LogOut className="h-4 w-4 text-white/50" aria-hidden /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function CreditOrb({ credits }: { credits: number }) {
  const pct = Math.min(100, (credits / 1000) * 100);
  return (
    <Link
      href="/usage"
      aria-label={`${credits} credits remaining`}
      className="hidden items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-2.5 py-1 hover:bg-white/10 sm:flex"
    >
      <div className="relative h-4 w-4" aria-hidden>
        <svg viewBox="0 0 36 36" className="h-4 w-4 -rotate-90">
          <circle cx="18" cy="18" r="14" fill="none" stroke="oklch(1 0 0 / 0.15)" strokeWidth="4" />
          <circle cx="18" cy="18" r="14" fill="none" stroke="url(#og)" strokeWidth="4" strokeDasharray={`${pct * 0.88} 100`} strokeLinecap="round" />
          <defs>
            <linearGradient id="og" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="oklch(0.78 0.18 200)" />
              <stop offset="100%" stopColor="oklch(0.68 0.27 305)" />
            </linearGradient>
          </defs>
        </svg>
      </div>
      <span className="font-mono text-xs text-white/80">{credits}</span>
    </Link>
  );
}

export function MobileDock() {
  const path = usePathname() ?? "/";
  const items = [
    { to: "/", label: "Home", icon: Sparkles },
    { to: "/explore", label: "Explore", icon: Compass },
    { to: "/generate", label: "Create", icon: Wand2 },
    { to: "/editor", label: "Edit", icon: Layers },
    { to: "/account", label: "Me", icon: User },
  ] as const;
  return (
    <nav aria-label="Mobile" className="fixed bottom-3 left-1/2 z-50 -translate-x-1/2 lg:hidden">
      <ul className="glass-panel flex items-center gap-1 rounded-2xl p-1.5" style={{ boxShadow: "var(--shadow-float)" }}>
        {items.map((i) => {
          const active = path === i.to;
          const Icon = i.icon;
          return (
            <li key={i.to}>
              <Link
                href={i.to}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center gap-0.5 rounded-xl px-3 py-1.5 text-[10px] transition ${active ? "bg-white/10 text-white" : "text-white/60"}`}
              >
                <Icon className="h-4 w-4" aria-hidden />
                {i.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function SiteFooter() {
  return (
    <footer className="relative z-10 mt-16 border-t border-white/10 px-6 py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-2">
            <span aria-hidden className="grid h-7 w-7 place-items-center rounded-lg" style={{ background: "var(--gradient-aurora)" }}>
              <Sparkles className="h-4 w-4 text-black/80" />
            </span>
            <span className="font-display text-lg">Pixium</span>
          </div>
          <p className="mt-2 max-w-sm text-sm text-white/50">A new visual language for image generation.</p>
        </div>
        <div className="grid grid-cols-3 gap-8 text-sm">
          <div>
            <p className="kerned mb-2 text-white/40">Product</p>
            <ul className="space-y-1.5 text-white/70">
              <li><Link href="/generate">Create</Link></li>
              <li><Link href="/types">Types</Link></li>
              <li><Link href="/pricing">Pricing</Link></li>
            </ul>
          </div>
          <div>
            <p className="kerned mb-2 text-white/40">Tools</p>
            <ul className="space-y-1.5 text-white/70">
              <li><Link href="/editor">Edit</Link></li>
              <li><Link href="/editor?tool=upscale">Upscale</Link></li>
              <li><Link href="/video">Video</Link></li>
            </ul>
          </div>
          <div>
            <p className="kerned mb-2 text-white/40">Account</p>
            <ul className="space-y-1.5 text-white/70">
              <li><Link href="/account">Account</Link></li>
              <li><Link href="/dashboard">Studio</Link></li>
              <li><Link href="/settings">Settings</Link></li>
            </ul>
          </div>
        </div>
      </div>
      <p className="mx-auto mt-10 max-w-6xl text-xs text-white/30">© 2026 Pixium AI · Crafted with care.</p>
    </footer>
  );
}

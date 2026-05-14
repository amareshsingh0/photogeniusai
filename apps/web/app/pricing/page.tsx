"use client";

import Link from "next/link";
import { Check } from "lucide-react";

const tiers = [
  { name: "Spark", price: "$0", desc: "Get started with daily credits", features: ["50 generations / month", "Standard quality", "Public gallery"], cta: "Start free" },
  { name: "Studio", price: "$24", per: "/mo", desc: "For creators who ship", features: ["3,000 generations", "All quality tiers (1K–4K)", "Inpaint, upscale, video", "Private workspace", "Commercial license"], cta: "Go Studio", featured: true },
  { name: "Atelier", price: "$96", per: "/mo", desc: "For agencies and teams", features: ["Unlimited generations", "Early access models", "Team workspaces", "Public API", "Priority rendering"], cta: "Talk to us" },
];

const matrix = [
  { row: "Monthly generations", values: ["50", "3,000", "Unlimited"] },
  { row: "Image resolution", values: ["1024px", "4K", "16K"] },
  { row: "Inpaint & outpaint", values: ["—", "✓", "✓"] },
  { row: "Image to video", values: ["—", "✓", "✓"] },
  { row: "Commercial license", values: ["—", "✓", "✓"] },
  { row: "API access", values: ["—", "—", "✓"] },
  { row: "Priority queue", values: ["—", "—", "✓"] },
];

export default function Pricing() {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-24">
      <div className="py-12 text-center">
        <p className="kerned text-white/40">Pricing</p>
        <h1 className="mt-2 font-display text-5xl leading-tight sm:text-7xl">Honest plans,<br /><span className="italic text-white/60">infinite ideas.</span></h1>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {tiers.map((t) => (
          <div key={t.name} className={`glass-panel relative overflow-hidden rounded-3xl p-7 ${t.featured ? "ring-1 ring-white/25" : ""}`}>
            {t.featured && <div className="absolute -right-20 -top-20 h-56 w-56 rounded-full opacity-40 blur-3xl" style={{ background: "var(--gradient-aurora)" }} />}
            <p className="kerned text-white/40">{t.name}</p>
            <p className="mt-4 font-display text-5xl">{t.price}<span className="text-base text-white/40">{t.per}</span></p>
            <p className="mt-2 text-sm text-white/60">{t.desc}</p>
            <ul className="mt-6 space-y-2 text-sm">
              {t.features.map((f) => <li key={f} className="flex items-start gap-2"><Check className="mt-0.5 h-4 w-4 text-white/60" />{f}</li>)}
            </ul>
            <Link href="/generate" className={`mt-8 inline-flex w-full items-center justify-center rounded-xl px-4 py-2.5 text-sm font-medium ${t.featured ? "text-black" : "border border-white/15 bg-white/5"}`} style={t.featured ? { background: "var(--gradient-aurora)" } : undefined}>
              {t.cta}
            </Link>
          </div>
        ))}
      </div>

      <div className="glass-panel mt-12 overflow-hidden rounded-3xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10 text-left">
              <th className="kerned p-4 text-white/40">Compare</th>
              {tiers.map((t) => <th key={t.name} className="p-4 font-display text-base">{t.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {matrix.map((m) => (
              <tr key={m.row} className="border-b border-white/5">
                <td className="p-4 text-white/70">{m.row}</td>
                {m.values.map((v, i) => <td key={i} className="p-4 font-mono text-xs text-white/85">{v}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

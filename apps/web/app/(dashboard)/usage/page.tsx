"use client"

import { useState, Suspense } from "react"
import dynamic from "next/dynamic"
import { TrendingUp, Download, FileText } from "lucide-react"

// Lazy load charts component
const UsageCharts = dynamic(() => import("@/components/usage/usage-charts"), {
  ssr: false,
  loading: () => (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="h-80 animate-pulse rounded-2xl bg-white/[0.02]" />
      <div className="h-80 animate-pulse rounded-2xl bg-white/[0.02]" />
    </div>
  )
})

const transactions = [
  {
    id: "1",
    date: "2025-01-26",
    type: "Generation",
    mode: "REALISM",
    credits: -3,
    balance: 147,
  },
  {
    id: "2",
    date: "2025-01-25",
    type: "Purchase",
    description: "Pro Pack",
    credits: +150,
    balance: 150,
    invoice: "INV-001",
  },
  {
    id: "3",
    date: "2025-01-24",
    type: "Generation",
    mode: "CREATIVE",
    credits: -5,
    balance: 0,
  },
]

const TIME_RANGES = [
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
  { key: "90d", label: "90 days" },
  { key: "1y", label: "1 year" },
]

export default function UsagePage() {
  const [timeRange, setTimeRange] = useState("30d")

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-24 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Usage & Billing</h1>
          <p className="mt-1 text-sm text-white/50">Track your credit usage and billing history.</p>
        </div>
        <div className="flex items-center gap-1.5">
          {TIME_RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setTimeRange(r.key)}
              className={`rounded-full px-2.5 py-1 text-[11px] transition ${timeRange === r.key ? "bg-white text-black" : "bg-white/5 text-white/70 hover:bg-white/10"}`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="glass-panel rounded-2xl p-4">
          <p className="kerned text-white/40 mb-2">CREDITS USED</p>
          <p className="font-mono text-3xl text-aurora">108</p>
          <p className="mt-1 text-xs text-emerald-400"><TrendingUp className="inline h-3 w-3" /> +12% vs last month</p>
        </div>
        <div className="glass-panel rounded-2xl p-4">
          <p className="kerned text-white/40 mb-2">TOTAL GENERATIONS</p>
          <p className="font-mono text-3xl text-aurora">36</p>
          <p className="mt-1 text-xs text-white/50">This month</p>
        </div>
        <div className="glass-panel rounded-2xl p-4">
          <p className="kerned text-white/40 mb-2">AVG QUALITY SCORE</p>
          <p className="font-mono text-3xl text-aurora">8.6</p>
          <p className="mt-1 text-xs text-white/50">Last 30 days</p>
        </div>
      </div>

      {/* Charts */}
      <div className="glass-panel rounded-2xl p-5">
        <p className="kerned text-white/40 mb-4">ACTIVITY</p>
        <Suspense fallback={
          <div className="grid gap-6 md:grid-cols-2">
            <div className="h-80 animate-pulse rounded-2xl bg-white/[0.02]" />
            <div className="h-80 animate-pulse rounded-2xl bg-white/[0.02]" />
          </div>
        }>
          <UsageCharts />
        </Suspense>
      </div>

      {/* Transaction History */}
      <div className="glass-panel rounded-2xl p-5">
        <div className="mb-4 flex items-center justify-between">
          <p className="kerned text-white/40">TRANSACTION HISTORY</p>
          <button className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition">
            <Download className="h-3.5 w-3.5" /> Export
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="kerned text-white/40 text-left py-2 px-4">Date</th>
                <th className="kerned text-white/40 text-left py-2 px-4">Type</th>
                <th className="kerned text-white/40 text-left py-2 px-4">Credits</th>
                <th className="kerned text-white/40 text-left py-2 px-4">Balance</th>
                <th className="kerned text-white/40 text-left py-2 px-4">Invoice</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.id} className="border-b border-white/5">
                  <td className="py-3 px-4 text-sm font-mono text-[11px] text-white/60">
                    {new Date(t.date).toLocaleDateString()}
                  </td>
                  <td className="py-3 px-4 text-sm text-white/70">
                    {t.type}
                    {t.mode && <span className="ml-2 rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-white/60">{t.mode}</span>}
                    {t.description && <span className="ml-2 text-white/40">{t.description}</span>}
                  </td>
                  <td className={`py-3 px-4 text-sm font-mono text-[11px] ${t.credits > 0 ? "text-emerald-400" : "text-white/70"}`}>
                    {t.credits > 0 ? "+" : ""}{t.credits}
                  </td>
                  <td className="py-3 px-4 text-sm font-mono text-[11px] text-white/60">{t.balance}</td>
                  <td className="py-3 px-4 text-sm">
                    {t.invoice ? (
                      <span className="inline-flex items-center gap-1 text-white/50"><FileText className="h-3 w-3" />{t.invoice}</span>
                    ) : <span className="text-white/30">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

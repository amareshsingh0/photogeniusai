'use client'

import React, { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  CalendarDays, Sparkles, Loader2, ChevronLeft, ChevronRight,
  Instagram, Linkedin, Twitter, Globe, Download, Settings2, X,
} from 'lucide-react'

interface CalendarEntry {
  date:          string
  day_of_week:   string
  platform:      string
  content_type:  string
  prompt:        string
  caption:       string
  hashtags:      string[]
  cta:           string
  is_festival:   boolean
  festival_name: string | null
}

const MONTH_NAMES = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
]

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  instagram: <Instagram className="h-3 w-3" />,
  linkedin:  <Linkedin  className="h-3 w-3" />,
  twitter:   <Twitter   className="h-3 w-3" />,
  general:   <Globe     className="h-3 w-3" />,
}

const PLATFORMS = ['instagram', 'linkedin', 'twitter', 'general']
const TONES     = ['professional', 'casual', 'luxury', 'energetic', 'playful', 'trustworthy']

function getDaysInMonth(year: number, month: number) { return new Date(year, month + 1, 0).getDate() }
function getFirstDayOfWeek(year: number, month: number) { return new Date(year, month, 1).getDay() }
function formatTypeLabel(s: string) { return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) }

export default function CalendarPage() {
  const router = useRouter()
  const today  = new Date()

  const [viewYear,  setViewYear]  = useState(today.getFullYear())
  const [viewMonth, setViewMonth] = useState(today.getMonth())
  const [calendar,  setCalendar]  = useState<CalendarEntry[]>([])
  const [loading,   setLoading]   = useState(false)
  const [selected,  setSelected]  = useState<CalendarEntry | null>(null)
  const [showCfg,   setShowCfg]   = useState(false)

  const [brandName, setBrandName] = useState('')
  const [brandTone, setBrandTone] = useState('professional')
  const [industry,  setIndustry]  = useState('Technology / SaaS')
  const [platform,  setPlatform]  = useState('instagram')
  const [notes,     setNotes]     = useState('')

  const entryMap = React.useMemo(() => {
    const m: Record<string, CalendarEntry> = {}
    calendar.forEach(e => { m[e.date] = e })
    return m
  }, [calendar])

  const generatePlan = useCallback(async () => {
    setLoading(true)
    setCalendar([])
    try {
      const res = await fetch('/api/content/plan', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          brand_name:   brandName || 'My Brand',
          brand_tone:   brandTone,
          industry,
          platform,
          month:        viewMonth + 1,
          year:         viewYear,
          custom_notes: notes || undefined,
        }),
      })
      const data = await res.json()
      if (data.calendar) setCalendar(data.calendar)
    } catch { /* silent */ }
    finally { setLoading(false) }
  }, [brandName, brandTone, industry, platform, viewMonth, viewYear, notes])

  const openInGenerate = (entry: CalendarEntry) => {
    const params = new URLSearchParams({ prefill_prompt: entry.prompt, prefill_caption: entry.caption })
    router.push(`/generate?${params.toString()}`)
  }

  const exportCSV = () => {
    if (!calendar.length) return
    const headers = ['Date','Day','Platform','Content Type','Prompt','Caption','Hashtags','CTA','Festival']
    const rows = calendar.map(e => [
      e.date, e.day_of_week, e.platform, e.content_type,
      `"${e.prompt.replace(/"/g,'""')}"`,
      `"${e.caption.replace(/"/g,'""')}"`,
      e.hashtags.join(' '), e.cta, e.festival_name || '',
    ])
    const csv  = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url
    a.download = `content-calendar-${viewYear}-${String(viewMonth+1).padStart(2,'0')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const daysInMonth  = getDaysInMonth(viewYear, viewMonth)
  const firstWeekday = getFirstDayOfWeek(viewYear, viewMonth)

  const prevMonth = () => viewMonth === 0  ? (setViewYear(y => y-1), setViewMonth(11))  : setViewMonth(m => m-1)
  const nextMonth = () => viewMonth === 11 ? (setViewYear(y => y+1), setViewMonth(0))   : setViewMonth(m => m+1)

  const Pill = ({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) => (
    <button type="button" onClick={onClick} className={`rounded-full px-2.5 py-1 text-[11px] transition ${active ? 'bg-white text-black' : 'bg-white/5 text-white/70 hover:bg-white/10'}`}>{children}</button>
  )

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-24 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <CalendarDays className="h-5 w-5 text-white/60" />
          <div>
            <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Content Calendar</h1>
            <p className="mt-1 text-sm text-white/50">AI-planned content schedule — click any day to generate.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {calendar.length > 0 && (
            <button onClick={exportCSV} className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition">
              <Download className="h-3.5 w-3.5" /> CSV
            </button>
          )}
          <button onClick={() => setShowCfg(c => !c)} className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm transition ${showCfg ? 'border-white/30 bg-white/10' : 'border-white/10 bg-white/5 hover:bg-white/10'}`}>
            <Settings2 className="h-3.5 w-3.5" /> Settings
          </button>
          <button onClick={generatePlan} disabled={loading} className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-black transition disabled:opacity-50" style={{ background: 'var(--gradient-aurora)' }}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {loading ? 'Planning…' : calendar.length ? 'Regenerate' : 'New plan'}
          </button>
        </div>
      </div>

      {/* Config panel */}
      {showCfg && (
        <div className="glass-panel grid grid-cols-1 gap-3 rounded-2xl p-4 sm:grid-cols-3">
          <div>
            <p className="kerned text-white/40 mb-2">BRAND NAME</p>
            <input value={brandName} onChange={e => setBrandName(e.target.value)} placeholder="e.g. Pixium AI" className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30" />
          </div>
          <div>
            <p className="kerned text-white/40 mb-2">PLATFORM</p>
            <div className="flex flex-wrap gap-1.5">{PLATFORMS.map(p => <Pill key={p} active={platform === p} onClick={() => setPlatform(p)}>{p.charAt(0).toUpperCase()+p.slice(1)}</Pill>)}</div>
          </div>
          <div>
            <p className="kerned text-white/40 mb-2">BRAND TONE</p>
            <div className="flex flex-wrap gap-1.5">{TONES.map(t => <Pill key={t} active={brandTone === t} onClick={() => setBrandTone(t)}>{t.charAt(0).toUpperCase()+t.slice(1)}</Pill>)}</div>
          </div>
          <div>
            <p className="kerned text-white/40 mb-2">INDUSTRY</p>
            <input value={industry} onChange={e => setIndustry(e.target.value)} placeholder="Technology / SaaS" className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30" />
          </div>
          <div className="sm:col-span-2">
            <p className="kerned text-white/40 mb-2">NOTES</p>
            <input value={notes} onChange={e => setNotes(e.target.value)} placeholder="Include product launch on 15th, avoid weekends…" className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30" />
          </div>
        </div>
      )}

      {/* Month toolbar */}
      <div className="flex items-center justify-between">
        <button onClick={prevMonth} className="rounded-xl border border-white/10 bg-white/5 p-2 hover:bg-white/10 transition"><ChevronLeft className="h-4 w-4" /></button>
        <div className="text-center">
          <h2 className="font-display text-2xl tracking-tight">{MONTH_NAMES[viewMonth]} {viewYear}</h2>
          {calendar.length > 0 && <p className="mt-0.5 font-mono text-[11px] text-white/60">{calendar.length} posts planned</p>}
        </div>
        <button onClick={nextMonth} className="rounded-xl border border-white/10 bg-white/5 p-2 hover:bg-white/10 transition"><ChevronRight className="h-4 w-4" /></button>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-1 text-center">
        {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => (
          <div key={d} className="kerned py-1 text-white/40">{d}</div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: firstWeekday }).map((_, i) => (
          <div key={`e${i}`} className="min-h-24 rounded-xl" />
        ))}
        {Array.from({ length: daysInMonth }).map((_, i) => {
          const dayNum  = i + 1
          const dateStr = `${viewYear}-${String(viewMonth+1).padStart(2,'0')}-${String(dayNum).padStart(2,'0')}`
          const entry   = entryMap[dateStr]
          const isToday = dateStr === today.toISOString().split('T')[0]
          return (
            <button
              key={dateStr}
              onClick={() => entry ? setSelected(entry) : undefined}
              className={`hairline min-h-24 rounded-xl p-2 text-left transition ${entry ? 'cursor-pointer hover:-translate-y-0.5 bg-white/[0.02]' : ''} ${isToday ? 'ring-1 ring-white/30' : ''}`}
            >
              <span className={`font-mono text-[11px] ${isToday ? 'text-white/85' : 'text-white/40'}`}>{dayNum}</span>
              {entry && (
                <div className="mt-1 space-y-1">
                  <div className="inline-flex items-center gap-1 rounded-full bg-white/5 px-1.5 py-0.5 text-[9px] text-white/60">
                    {PLATFORM_ICONS[entry.platform] ?? <Globe className="h-3 w-3" />}
                  </div>
                  <div className="truncate rounded-full bg-white/5 px-1.5 py-0.5 text-[9px] text-white/70">{formatTypeLabel(entry.content_type)}</div>
                  {entry.is_festival && entry.festival_name && (
                    <div className="truncate text-[9px] text-amber-400">★ {entry.festival_name}</div>
                  )}
                </div>
              )}
            </button>
          )
        })}
      </div>

      {/* Empty state */}
      {!loading && calendar.length === 0 && (
        <div className="glass-panel rounded-2xl p-12 text-center">
          <h3 className="font-display text-2xl tracking-tight">No content plan yet</h3>
          <p className="mx-auto mt-2 max-w-sm text-sm text-white/50">Generate a plan to fill this month with AI-crafted content ideas.</p>
          <button onClick={generatePlan} className="mt-5 inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-black transition" style={{ background: 'var(--gradient-aurora)' }}>
            <Sparkles className="h-4 w-4" /> Generate my content plan
          </button>
        </div>
      )}

      {/* Detail drawer */}
      {selected && (
        <>
          <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={() => setSelected(null)} />
          <div
            className="glass-panel fixed bottom-0 left-0 right-0 z-50 space-y-4 rounded-t-3xl p-6 md:bottom-auto md:left-auto md:right-6 md:top-1/2 md:w-96 md:-translate-y-1/2 md:rounded-2xl"
            style={{ boxShadow: 'var(--shadow-float)' }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-mono text-[11px] text-white/60">{selected.day_of_week}, {selected.date}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-white/70">{formatTypeLabel(selected.content_type)}</span>
                  <span className="inline-flex items-center gap-1 rounded-full bg-white/5 px-1.5 py-0.5 text-[10px] text-white/60">
                    {PLATFORM_ICONS[selected.platform] ?? <Globe className="h-3 w-3" />}{selected.platform}
                  </span>
                  {selected.is_festival && <span className="text-[10px] text-amber-400">★ {selected.festival_name}</span>}
                </div>
              </div>
              <button onClick={() => setSelected(null)} className="rounded-xl border border-white/10 bg-white/5 p-1.5 hover:bg-white/10 transition"><X className="h-4 w-4" /></button>
            </div>

            <div>
              <p className="kerned text-white/40 mb-2">GENERATION PROMPT</p>
              <p className="hairline rounded-xl p-3 text-xs leading-relaxed text-white/70">{selected.prompt}</p>
            </div>

            <div>
              <p className="kerned text-white/40 mb-2">CAPTION</p>
              <p className="text-xs leading-relaxed text-white/70">{selected.caption}</p>
            </div>

            {selected.hashtags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {selected.hashtags.map(h => <span key={h} className="rounded-full bg-white/5 px-1.5 py-0.5 text-[10px] text-white/60">{h}</span>)}
              </div>
            )}

            {selected.cta && <p className="text-xs text-white/50">CTA: <span className="text-white/70">{selected.cta}</span></p>}

            <button
              onClick={() => { const e = selected; setSelected(null); openInGenerate(e) }}
              className="flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-medium text-black transition"
              style={{ background: 'var(--gradient-aurora)' }}
            >
              <Sparkles className="h-4 w-4" /> Generate this post
            </button>
          </div>
        </>
      )}
    </div>
  )
}

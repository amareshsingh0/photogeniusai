'use client'

/**
 * Content Calendar — /calendar
 * AI-powered 30-day content planner.
 * "Generate Plan" → calls Gemini agent → fills month grid.
 * Click any day → opens generate page pre-filled with that day's prompt.
 */

import React, { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  CalendarDays, Sparkles, Loader2, ChevronLeft, ChevronRight,
  Instagram, Linkedin, Twitter, Globe, RefreshCw, Download,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface CalendarEntry {
  date:         string
  day_of_week:  string
  platform:     string
  content_type: string
  prompt:       string
  caption:      string
  hashtags:     string[]
  cta:          string
  is_festival:  boolean
  festival_name: string | null
}

// ── Constants ─────────────────────────────────────────────────────────────────

const MONTH_NAMES = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
]

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  instagram: <Instagram className="w-3 h-3" />,
  linkedin:  <Linkedin  className="w-3 h-3" />,
  twitter:   <Twitter   className="w-3 h-3" />,
  general:   <Globe     className="w-3 h-3" />,
}

const PLATFORM_COLORS: Record<string, string> = {
  instagram: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
  linkedin:  'text-blue-400 bg-blue-500/10 border-blue-500/20',
  twitter:   'text-sky-400  bg-sky-500/10  border-sky-500/20',
  general:   'text-white/50 bg-white/5     border-white/10',
}

const TYPE_COLORS: Record<string, string> = {
  product_showcase:   'bg-purple-500/20 text-purple-300',
  behind_the_scenes:  'bg-amber-500/20  text-amber-300',
  tip_or_tutorial:    'bg-emerald-500/20 text-emerald-300',
  testimonial:        'bg-blue-500/20   text-blue-300',
  promotion_sale:     'bg-red-500/20    text-red-300',
  announcement:       'bg-indigo-500/20 text-indigo-300',
  poll_question:      'bg-teal-500/20   text-teal-300',
  quote_card:         'bg-orange-500/20 text-orange-300',
  carousel:           'bg-fuchsia-500/20 text-fuchsia-300',
  reel_idea:          'bg-rose-500/20   text-rose-300',
  event_promo:        'bg-yellow-500/20 text-yellow-300',
  ugc_repost:         'bg-cyan-500/20   text-cyan-300',
}

const PLATFORMS = ['instagram','linkedin','twitter','general']
const TONES     = ['professional','casual','luxury','energetic','playful','trustworthy']

// ── Helpers ───────────────────────────────────────────────────────────────────

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}
function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay() // 0=Sun
}
function formatTypeLabel(s: string) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const router = useRouter()

  const today = new Date()
  const [viewYear, setViewYear]   = useState(today.getFullYear())
  const [viewMonth, setViewMonth] = useState(today.getMonth())  // 0-indexed

  const [calendar, setCalendar]   = useState<CalendarEntry[]>([])
  const [loading, setLoading]     = useState(false)
  const [selected, setSelected]   = useState<CalendarEntry | null>(null)

  // Plan settings
  const [brandName,  setBrandName]  = useState('')
  const [brandTone,  setBrandTone]  = useState('professional')
  const [industry,   setIndustry]   = useState('Technology / SaaS')
  const [platform,   setPlatform]   = useState('instagram')
  const [notes,      setNotes]      = useState('')
  const [showConfig, setShowConfig] = useState(false)

  // Build a lookup map: date string → entry
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
    const params = new URLSearchParams({
      prefill_prompt: entry.prompt,
      prefill_caption: entry.caption,
    })
    router.push(`/generate?${params.toString()}`)
  }

  const exportCSV = () => {
    if (!calendar.length) return
    const headers = ['Date','Day','Platform','Content Type','Prompt','Caption','Hashtags','CTA','Festival']
    const rows = calendar.map(e => [
      e.date, e.day_of_week, e.platform, e.content_type,
      `"${e.prompt.replace(/"/g,'""')}"`,
      `"${e.caption.replace(/"/g,'""')}"`,
      e.hashtags.join(' '),
      e.cta,
      e.festival_name || '',
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `content-calendar-${viewYear}-${String(viewMonth+1).padStart(2,'0')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Calendar grid
  const daysInMonth  = getDaysInMonth(viewYear, viewMonth)
  const firstWeekday = getFirstDayOfWeek(viewYear, viewMonth)

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11) }
    else setViewMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0) }
    else setViewMonth(m => m + 1)
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <CalendarDays className="w-5 h-5 text-purple-400" />
            Content Calendar
          </h1>
          <p className="text-sm text-white/40 mt-0.5">
            AI-planned 30-day content schedule — click any day to generate that post
          </p>
        </div>
        <div className="flex items-center gap-2">
          {calendar.length > 0 && (
            <button
              onClick={exportCSV}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white/50 hover:text-white hover:border-white/20 transition-colors"
            >
              <Download className="w-3.5 h-3.5" /> Export CSV
            </button>
          )}
          <button
            onClick={() => setShowConfig(c => !c)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white/50 hover:text-white hover:border-white/20 transition-colors"
          >
            Settings
          </button>
          <button
            onClick={generatePlan}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-60 text-white text-sm font-semibold transition-colors"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {loading ? 'Planning…' : calendar.length ? 'Regenerate' : 'Generate Plan'}
          </button>
        </div>
      </div>

      {/* Config panel */}
      {showConfig && (
        <div className="bg-white/3 border border-white/8 rounded-2xl p-5 grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div>
            <label className="text-xs text-white/40 mb-1 block">Brand Name</label>
            <input value={brandName} onChange={e => setBrandName(e.target.value)}
              placeholder="e.g. PhotoGenius AI"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/50" />
          </div>
          <div>
            <label className="text-xs text-white/40 mb-1 block">Platform</label>
            <select value={platform} onChange={e => setPlatform(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/50 appearance-none">
              {PLATFORMS.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase()+p.slice(1)}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-white/40 mb-1 block">Brand Tone</label>
            <select value={brandTone} onChange={e => setBrandTone(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/50 appearance-none">
              {TONES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase()+t.slice(1)}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-white/40 mb-1 block">Industry</label>
            <input value={industry} onChange={e => setIndustry(e.target.value)}
              placeholder="Technology / SaaS"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/50" />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-white/40 mb-1 block">Additional Notes</label>
            <input value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="Include product launch on 15th, avoid weekends..."
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/50" />
          </div>
        </div>
      )}

      {/* Month navigator */}
      <div className="flex items-center justify-between">
        <button onClick={prevMonth} className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white transition-colors">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <h2 className="text-sm font-semibold text-white">
          {MONTH_NAMES[viewMonth]} {viewYear}
          {calendar.length > 0 && (
            <span className="ml-2 text-xs text-purple-400 font-normal">{calendar.length} posts planned</span>
          )}
        </h2>
        <button onClick={nextMonth} className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white transition-colors">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Day-of-week headers */}
      <div className="grid grid-cols-7 gap-1 text-center">
        {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => (
          <div key={d} className="text-[10px] font-semibold text-white/30 py-1">{d}</div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {/* Leading empty cells */}
        {Array.from({ length: firstWeekday }).map((_, i) => (
          <div key={`empty-${i}`} className="h-24 rounded-xl" />
        ))}

        {/* Day cells */}
        {Array.from({ length: daysInMonth }).map((_, i) => {
          const dayNum  = i + 1
          const dateStr = `${viewYear}-${String(viewMonth+1).padStart(2,'0')}-${String(dayNum).padStart(2,'0')}`
          const entry   = entryMap[dateStr]
          const isToday = dateStr === today.toISOString().split('T')[0]

          return (
            <DayCell
              key={dateStr}
              dayNum={dayNum}
              dateStr={dateStr}
              isToday={isToday}
              entry={entry}
              onClick={() => entry ? setSelected(entry) : null}
            />
          )
        })}
      </div>

      {/* Empty state */}
      {!loading && calendar.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
          <div className="w-16 h-16 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
            <Sparkles className="w-8 h-8 text-purple-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white/80">No content plan yet</p>
            <p className="text-xs text-white/30 mt-1">Click "Generate Plan" to fill this month with AI-crafted content ideas</p>
          </div>
          <button
            onClick={generatePlan}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold transition-colors"
          >
            <Sparkles className="w-4 h-4" /> Generate My Content Plan
          </button>
        </div>
      )}

      {/* Day detail drawer */}
      {selected && (
        <DayDetailDrawer
          entry={selected}
          onClose={() => setSelected(null)}
          onGenerate={() => { setSelected(null); openInGenerate(selected) }}
        />
      )}
    </div>
  )
}

// ── Day Cell ──────────────────────────────────────────────────────────────────

function DayCell({
  dayNum, dateStr, isToday, entry, onClick,
}: {
  dayNum:  number
  dateStr: string
  isToday: boolean
  entry?:  CalendarEntry
  onClick: () => void
}) {
  const typeColor = entry ? (TYPE_COLORS[entry.content_type] ?? 'bg-white/10 text-white/50') : ''
  const platColor = entry ? (PLATFORM_COLORS[entry.platform] ?? PLATFORM_COLORS.general) : ''

  return (
    <div
      onClick={onClick}
      className={[
        'relative h-24 rounded-xl p-1.5 border transition-all text-left',
        entry
          ? 'bg-white/[0.03] border-white/8 hover:bg-white/6 hover:border-purple-500/30 cursor-pointer'
          : 'bg-white/[0.015] border-white/4',
        isToday ? 'ring-1 ring-purple-500/50' : '',
      ].join(' ')}
    >
      {/* Day number */}
      <span className={[
        'text-[11px] font-semibold leading-none',
        isToday ? 'text-purple-400' : 'text-white/40',
      ].join(' ')}>
        {dayNum}
      </span>

      {entry && (
        <div className="mt-1 space-y-1">
          {/* Platform badge */}
          <div className={`inline-flex items-center gap-0.5 text-[9px] px-1 py-0.5 rounded border ${platColor}`}>
            {PLATFORM_ICONS[entry.platform] ?? <Globe className="w-3 h-3" />}
          </div>
          {/* Content type chip */}
          <div className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium leading-none truncate ${typeColor}`}>
            {formatTypeLabel(entry.content_type)}
          </div>
          {/* Festival indicator */}
          {entry.is_festival && entry.festival_name && (
            <div className="text-[9px] text-amber-400 truncate">🎉 {entry.festival_name}</div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Day Detail Drawer ─────────────────────────────────────────────────────────

function DayDetailDrawer({
  entry, onClose, onGenerate,
}: {
  entry:      CalendarEntry
  onClose:    () => void
  onGenerate: () => void
}) {
  const typeColor = TYPE_COLORS[entry.content_type] ?? 'bg-white/10 text-white/50'
  const platColor = PLATFORM_COLORS[entry.platform] ?? PLATFORM_COLORS.general

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed bottom-0 left-0 right-0 z-50 md:left-auto md:right-6 md:top-1/2 md:-translate-y-1/2 md:w-96 md:bottom-auto bg-[#0E0E18] border border-white/10 rounded-t-3xl md:rounded-2xl shadow-2xl p-6 space-y-4">

        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs text-white/40">{entry.day_of_week}, {entry.date}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${typeColor}`}>
                {formatTypeLabel(entry.content_type)}
              </span>
              <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border ${platColor}`}>
                {PLATFORM_ICONS[entry.platform] ?? <Globe className="w-3 h-3" />}
                {entry.platform}
              </span>
              {entry.is_festival && (
                <span className="text-[10px] text-amber-400">🎉 {entry.festival_name}</span>
              )}
            </div>
          </div>
          <button onClick={onClose} className="text-white/30 hover:text-white text-lg leading-none mt-1">✕</button>
        </div>

        {/* Image Prompt */}
        <div>
          <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1">Generation Prompt</p>
          <p className="text-xs text-white/80 leading-relaxed bg-white/3 border border-white/8 rounded-xl p-3">
            {entry.prompt}
          </p>
        </div>

        {/* Caption */}
        <div>
          <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1">Caption</p>
          <p className="text-xs text-white/70 leading-relaxed">{entry.caption}</p>
        </div>

        {/* Hashtags */}
        {entry.hashtags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {entry.hashtags.map(h => (
              <span key={h} className="text-[10px] text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded-full">
                {h}
              </span>
            ))}
          </div>
        )}

        {/* CTA */}
        {entry.cta && (
          <p className="text-xs text-white/40">CTA: <span className="text-white/70">{entry.cta}</span></p>
        )}

        {/* Action */}
        <button
          onClick={onGenerate}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold transition-colors"
        >
          <Sparkles className="w-4 h-4" /> Generate This Post
        </button>
      </div>
    </>
  )
}

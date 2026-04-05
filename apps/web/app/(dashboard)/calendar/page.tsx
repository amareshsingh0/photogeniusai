'use client'

import React, { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  CalendarDays, Sparkles, Loader2, ChevronLeft, ChevronRight,
  Instagram, Linkedin, Twitter, Globe, Download, Settings2,
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
  instagram: <Instagram className="w-3 h-3" />,
  linkedin:  <Linkedin  className="w-3 h-3" />,
  twitter:   <Twitter   className="w-3 h-3" />,
  general:   <Globe     className="w-3 h-3" />,
}

const PLATFORM_COLORS: Record<string, string> = {
  instagram: 'text-pink-400  bg-pink-500/10  border-pink-500/20',
  linkedin:  'text-blue-400  bg-blue-500/10  border-blue-500/20',
  twitter:   'text-sky-400   bg-sky-500/10   border-sky-500/20',
  general:   'text-white/40  bg-white/5      border-white/8',
}

const TYPE_COLORS: Record<string, string> = {
  product_showcase:  'bg-purple-500/20 text-purple-300',
  behind_the_scenes: 'bg-amber-500/20  text-amber-300',
  tip_or_tutorial:   'bg-emerald-500/20 text-emerald-300',
  testimonial:       'bg-blue-500/20   text-blue-300',
  promotion_sale:    'bg-red-500/20    text-red-300',
  announcement:      'bg-indigo-500/20 text-indigo-300',
  poll_question:     'bg-teal-500/20   text-teal-300',
  quote_card:        'bg-orange-500/20 text-orange-300',
  carousel:          'bg-fuchsia-500/20 text-fuchsia-300',
  reel_idea:         'bg-rose-500/20   text-rose-300',
  event_promo:       'bg-yellow-500/20 text-yellow-300',
  ugc_repost:        'bg-cyan-500/20   text-cyan-300',
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

  return (
    <div className="max-w-5xl mx-auto space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-white flex items-center gap-2">
            <CalendarDays className="w-4.5 h-4.5 text-purple-400" />
            Content Calendar
          </h1>
          <p className="text-xs text-white/30 mt-0.5">AI-planned content schedule — click any day to generate</p>
        </div>
        <div className="flex items-center gap-2">
          {calendar.length > 0 && (
            <button onClick={exportCSV}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-white/40 hover:text-white transition-colors"
              style={{ border: '1px solid rgba(255,255,255,0.08)' }}>
              <Download className="w-3.5 h-3.5" /> CSV
            </button>
          )}
          <button onClick={() => setShowCfg(c => !c)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors ${showCfg ? 'text-purple-400' : 'text-white/40 hover:text-white'}`}
            style={{ border: `1px solid ${showCfg ? 'rgba(124,58,237,0.4)' : 'rgba(255,255,255,0.08)'}` }}>
            <Settings2 className="w-3.5 h-3.5" /> Settings
          </button>
          <button onClick={generatePlan} disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-semibold transition-all disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', boxShadow: '0 0 16px rgba(124,58,237,0.3)' }}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {loading ? 'Planning…' : calendar.length ? 'Regenerate' : 'Generate Plan'}
          </button>
        </div>
      </div>

      {/* Config panel */}
      {showCfg && (
        <div className="rounded-2xl p-4 grid grid-cols-2 sm:grid-cols-3 gap-3"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)' }}>
          <div>
            <label className="text-[10px] text-white/30 mb-1 block uppercase tracking-wider">Brand Name</label>
            <input value={brandName} onChange={e => setBrandName(e.target.value)}
              placeholder="e.g. PhotoGenius AI"
              className="w-full bg-white/5 border border-white/8 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/40" />
          </div>
          <div>
            <label className="text-[10px] text-white/30 mb-1 block uppercase tracking-wider">Platform</label>
            <select value={platform} onChange={e => setPlatform(e.target.value)}
              style={{ colorScheme: 'dark' }}
              className="w-full bg-[#1a1a2e] border border-white/8 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/40 appearance-none cursor-pointer">
              {PLATFORMS.map(p => <option key={p} value={p} style={{ background: '#1a1a2e', color: '#fff' }}>{p.charAt(0).toUpperCase()+p.slice(1)}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-white/30 mb-1 block uppercase tracking-wider">Brand Tone</label>
            <select value={brandTone} onChange={e => setBrandTone(e.target.value)}
              style={{ colorScheme: 'dark' }}
              className="w-full bg-[#1a1a2e] border border-white/8 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/40 appearance-none cursor-pointer">
              {TONES.map(t => <option key={t} value={t} style={{ background: '#1a1a2e', color: '#fff' }}>{t.charAt(0).toUpperCase()+t.slice(1)}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-white/30 mb-1 block uppercase tracking-wider">Industry</label>
            <input value={industry} onChange={e => setIndustry(e.target.value)}
              placeholder="Technology / SaaS"
              className="w-full bg-white/5 border border-white/8 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/40" />
          </div>
          <div className="col-span-2">
            <label className="text-[10px] text-white/30 mb-1 block uppercase tracking-wider">Notes</label>
            <input value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="Include product launch on 15th, avoid weekends…"
              className="w-full bg-white/5 border border-white/8 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/40" />
          </div>
        </div>
      )}

      {/* Month nav */}
      <div className="flex items-center justify-between">
        <button onClick={prevMonth} className="p-2 rounded-lg text-white/30 hover:text-white hover:bg-white/5 transition-colors">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <div className="text-center">
          <h2 className="text-sm font-semibold text-white">{MONTH_NAMES[viewMonth]} {viewYear}</h2>
          {calendar.length > 0 && (
            <p className="text-[10px] text-purple-400 mt-0.5">{calendar.length} posts planned</p>
          )}
        </div>
        <button onClick={nextMonth} className="p-2 rounded-lg text-white/30 hover:text-white hover:bg-white/5 transition-colors">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-1 text-center">
        {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => (
          <div key={d} className="text-[10px] font-medium text-white/20 py-1">{d}</div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: firstWeekday }).map((_, i) => (
          <div key={`e${i}`} className="h-20 rounded-xl" />
        ))}
        {Array.from({ length: daysInMonth }).map((_, i) => {
          const dayNum  = i + 1
          const dateStr = `${viewYear}-${String(viewMonth+1).padStart(2,'0')}-${String(dayNum).padStart(2,'0')}`
          const entry   = entryMap[dateStr]
          const isToday = dateStr === today.toISOString().split('T')[0]
          return (
            <DayCell key={dateStr} dayNum={dayNum} isToday={isToday} entry={entry}
              onClick={() => entry ? setSelected(entry) : undefined} />
          )
        })}
      </div>

      {/* Empty state */}
      {!loading && calendar.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
            style={{ background: 'rgba(124,58,237,0.12)', border: '1px solid rgba(124,58,237,0.2)' }}>
            <Sparkles className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white/70">No content plan yet</p>
            <p className="text-xs text-white/25 mt-1">Click "Generate Plan" to fill this month with AI-crafted content ideas</p>
          </div>
          <button onClick={generatePlan}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-white text-sm font-semibold transition-all"
            style={{ background: 'linear-gradient(135deg, #7c3aed, #4f46e5)' }}>
            <Sparkles className="w-4 h-4" /> Generate My Content Plan
          </button>
        </div>
      )}

      {/* Detail drawer */}
      {selected && (
        <DayDetailDrawer entry={selected} onClose={() => setSelected(null)}
          onGenerate={() => { setSelected(null); openInGenerate(selected) }} />
      )}
    </div>
  )
}

// ── Day Cell ──────────────────────────────────────────────────────────────────

function DayCell({ dayNum, isToday, entry, onClick }: {
  dayNum:  number
  isToday: boolean
  entry?:  CalendarEntry
  onClick: () => void
}) {
  const typeColor = entry ? (TYPE_COLORS[entry.content_type] ?? 'bg-white/10 text-white/40') : ''
  const platColor = entry ? (PLATFORM_COLORS[entry.platform] ?? PLATFORM_COLORS.general) : ''

  return (
    <div
      onClick={onClick}
      className={[
        'relative h-20 rounded-xl p-1.5 transition-all text-left',
        entry ? 'cursor-pointer hover:scale-[1.02]' : '',
        isToday ? 'ring-1 ring-purple-500/40' : '',
      ].join(' ')}
      style={{
        background: entry ? 'rgba(255,255,255,0.025)' : 'rgba(255,255,255,0.012)',
        border: `1px solid ${entry ? 'rgba(255,255,255,0.07)' : 'rgba(255,255,255,0.04)'}`,
      }}
    >
      <span className={`text-[11px] font-semibold ${isToday ? 'text-purple-400' : 'text-white/30'}`}>
        {dayNum}
      </span>
      {entry && (
        <div className="mt-1 space-y-1">
          <div className={`inline-flex items-center gap-0.5 text-[9px] px-1 py-0.5 rounded border ${platColor}`}>
            {PLATFORM_ICONS[entry.platform] ?? <Globe className="w-3 h-3" />}
          </div>
          <div className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium leading-none truncate ${typeColor}`}>
            {formatTypeLabel(entry.content_type)}
          </div>
          {entry.is_festival && entry.festival_name && (
            <div className="text-[9px] text-amber-400 truncate">🎉 {entry.festival_name}</div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Day Detail Drawer ─────────────────────────────────────────────────────────

function DayDetailDrawer({ entry, onClose, onGenerate }: {
  entry:      CalendarEntry
  onClose:    () => void
  onGenerate: () => void
}) {
  const typeColor = TYPE_COLORS[entry.content_type] ?? 'bg-white/10 text-white/40'
  const platColor = PLATFORM_COLORS[entry.platform] ?? PLATFORM_COLORS.general

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed bottom-0 left-0 right-0 z-50 md:left-auto md:right-6 md:top-1/2 md:-translate-y-1/2 md:w-96 md:bottom-auto rounded-t-3xl md:rounded-2xl shadow-2xl p-6 space-y-4"
        style={{ background: '#0e0e1a', border: '1px solid rgba(255,255,255,0.08)' }}>

        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs text-white/30">{entry.day_of_week}, {entry.date}</p>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
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
          <button onClick={onClose} className="text-white/20 hover:text-white text-lg leading-none">✕</button>
        </div>

        <div>
          <p className="text-[10px] text-white/25 uppercase tracking-wider mb-1.5">Generation Prompt</p>
          <p className="text-xs text-white/70 leading-relaxed rounded-xl p-3"
            style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
            {entry.prompt}
          </p>
        </div>

        <div>
          <p className="text-[10px] text-white/25 uppercase tracking-wider mb-1.5">Caption</p>
          <p className="text-xs text-white/60 leading-relaxed">{entry.caption}</p>
        </div>

        {entry.hashtags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {entry.hashtags.map(h => (
              <span key={h} className="text-[10px] text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded-full">{h}</span>
            ))}
          </div>
        )}

        {entry.cta && (
          <p className="text-xs text-white/30">CTA: <span className="text-white/60">{entry.cta}</span></p>
        )}

        <button onClick={onGenerate}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-white text-sm font-semibold transition-all"
          style={{ background: 'linear-gradient(135deg, #7c3aed, #4f46e5)' }}>
          <Sparkles className="w-4 h-4" /> Generate This Post
        </button>
      </div>
    </>
  )
}

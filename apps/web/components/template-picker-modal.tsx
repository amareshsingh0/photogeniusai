'use client'

/**
 * TemplatePickerModal — browse & select from 10 pre-built poster templates.
 * Clicking a template pre-fills the generate page with prompt, poster_design, ad_copy & ratio.
 */

import React, { useMemo, useState } from 'react'
import { X, Search, Sparkles, ArrowRight } from 'lucide-react'
import { POSTER_TEMPLATES, TEMPLATE_CATEGORIES, getTemplatesByCategory, type PosterTemplate } from '@/lib/poster-templates'

interface Props {
  onSelect: (template: PosterTemplate) => void
  onClose:  () => void
}

const TABS = ['All', ...TEMPLATE_CATEGORIES]

const QUALITY_LABELS: Record<string, string> = {
  balanced: 'Fast',
  quality:  'Quality',
  ultra:    'Ultra',
}
const QUALITY_COLORS: Record<string, string> = {
  balanced: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
  quality:  'text-blue-400 bg-blue-400/10 border-blue-400/20',
  ultra:    'text-purple-400 bg-purple-400/10 border-purple-400/20',
}

export function TemplatePickerModal({ onSelect, onClose }: Props) {
  const [activeTab, setActiveTab]   = useState('All')
  const [query, setQuery]           = useState('')
  const [hovered, setHovered]       = useState<string | null>(null)

  const filtered = useMemo(() => {
    let list = activeTab === 'All' ? POSTER_TEMPLATES : getTemplatesByCategory(activeTab)
    if (query.trim()) {
      const q = query.toLowerCase()
      list = list.filter(t =>
        t.name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q) ||
        t.tags.some(tag => tag.toLowerCase().includes(q))
      )
    }
    return list
  }, [activeTab, query])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-4xl max-h-[90vh] flex flex-col bg-[#0E0E18] border border-white/8 rounded-2xl shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-white/8 shrink-0">
          <Sparkles className="w-5 h-5 text-purple-400" />
          <div className="flex-1">
            <h2 className="text-sm font-semibold text-white">Start from a Template</h2>
            <p className="text-xs text-white/40 mt-0.5">10 pro templates — one click to pre-fill your prompt</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/8 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Search + Start Scratch row */}
        <div className="flex items-center gap-3 px-6 py-3 border-b border-white/6 shrink-0">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/30" />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search templates…"
              className="w-full bg-white/5 border border-white/8 rounded-lg pl-9 pr-4 py-1.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-purple-500/50 focus:bg-white/8 transition-all"
            />
          </div>
          <button
            onClick={() => onSelect({
              id: 'scratch',
              name: 'Start from Scratch',
              emoji: '✏️',
              category: 'Custom',
              description: 'Blank canvas',
              prompt_prefix: '',
              poster_design: {
                accent_color: '#6366F1', bg_color: '#0A0A1A',
                text_color_primary: '#FFFFFF', text_color_secondary: '#A5B4FC',
                font_style: 'modern_sans', layout: 'centered',
                has_feature_grid: false, has_cta_button: true, hero_occupies: 'top_60',
              },
              ad_copy: { headline: '', subheadline: '', body: '', cta: 'Get Started', tagline: '', features: [] },
              recommended_ratio: '9:16',
              quality: 'quality',
              tags: [],
            })}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white/50 hover:text-white hover:border-white/20 hover:bg-white/5 transition-colors shrink-0"
          >
            <span>✏️</span> Start from Scratch
          </button>
        </div>

        {/* Category tabs */}
        <div className="flex gap-1 px-6 py-2 border-b border-white/6 overflow-x-auto shrink-0 scrollbar-none">
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={[
                'px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all',
                activeTab === tab
                  ? 'bg-purple-600 text-white'
                  : 'text-white/40 hover:text-white/70 hover:bg-white/5',
              ].join(' ')}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Template grid */}
        <div className="flex-1 overflow-y-auto p-6">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 gap-2 text-white/30">
              <Search className="w-8 h-8" />
              <p className="text-sm">No templates match "{query}"</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {filtered.map(template => (
                <TemplateCard
                  key={template.id}
                  template={template}
                  hovered={hovered === template.id}
                  onMouseEnter={() => setHovered(template.id)}
                  onMouseLeave={() => setHovered(null)}
                  onSelect={() => onSelect(template)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Template Card ──────────────────────────────────────────────────────────────

function TemplateCard({
  template, hovered, onMouseEnter, onMouseLeave, onSelect,
}: {
  template:    PosterTemplate
  hovered:     boolean
  onMouseEnter: () => void
  onMouseLeave: () => void
  onSelect:    () => void
}) {
  return (
    <button
      onClick={onSelect}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={[
        'relative flex flex-col items-start gap-2 p-3 rounded-xl border text-left transition-all duration-200',
        hovered
          ? 'bg-white/8 border-purple-500/40 shadow-lg shadow-purple-500/5 scale-[1.02]'
          : 'bg-white/3 border-white/8 hover:border-white/15',
      ].join(' ')}
    >
      {/* Color preview strip */}
      <div className="w-full h-16 rounded-lg overflow-hidden relative shrink-0"
        style={{ background: template.poster_design.bg_color }}>
        {/* Simulated poster preview */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 px-2">
          <div
            className="h-1.5 rounded-full w-2/3 opacity-90"
            style={{ background: template.poster_design.text_color_primary }}
          />
          <div
            className="h-1 rounded-full w-1/2 opacity-50"
            style={{ background: template.poster_design.text_color_secondary }}
          />
          <div
            className="h-4 rounded-md w-1/3 mt-1"
            style={{ background: template.poster_design.accent_color }}
          />
        </div>
        {/* Emoji badge */}
        <div className="absolute top-1.5 left-2 text-base leading-none">{template.emoji}</div>
        {/* Ratio badge */}
        <div className="absolute top-1.5 right-2 text-[9px] text-white/40 bg-black/40 rounded px-1">
          {template.recommended_ratio}
        </div>
      </div>

      {/* Name + category */}
      <div className="w-full">
        <p className="text-xs font-semibold text-white leading-tight">{template.name}</p>
        <p className="text-[10px] text-white/40 mt-0.5 line-clamp-1">{template.description}</p>
      </div>

      {/* Tags row */}
      <div className="flex flex-wrap gap-1 w-full">
        <span className={[
          'text-[9px] px-1.5 py-0.5 rounded-full border font-medium',
          QUALITY_COLORS[template.quality],
        ].join(' ')}>
          {QUALITY_LABELS[template.quality]}
        </span>
        {template.tags.slice(0, 2).map(tag => (
          <span key={tag} className="text-[9px] px-1.5 py-0.5 rounded-full border border-white/8 text-white/35">
            {tag}
          </span>
        ))}
      </div>

      {/* Hover overlay */}
      {hovered && (
        <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-purple-600/10 border border-purple-500/30 transition-all">
          <div className="flex items-center gap-1.5 bg-purple-600 text-white text-xs font-semibold px-3 py-1.5 rounded-full shadow-lg">
            Use Template <ArrowRight className="w-3 h-3" />
          </div>
        </div>
      )}
    </button>
  )
}

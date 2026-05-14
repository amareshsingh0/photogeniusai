'use client'

/**
 * Brand Kit Settings — /settings/brand-kit
 * Save brand colors, font style, tone, and logo so every generation auto-applies them.
 */

import React, { useEffect, useState } from 'react'
import { Palette, Type, Megaphone, Save, CheckCircle, Loader2, RotateCcw, Globe } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003'

const FONT_STYLES = [
  { key: 'modern_sans',    label: 'Modern Sans',   preview: 'Inter / Poppins',      sample: 'Aa' },
  { key: 'elegant_serif',  label: 'Elegant Serif', preview: 'Playfair / Lora',       sample: 'Aa' },
  { key: 'bold_tech',      label: 'Bold Tech',     preview: 'Space Grotesk / Syne', sample: 'Aa' },
  { key: 'playful_round',  label: 'Playful Round', preview: 'Nunito / Fredoka',      sample: 'Aa' },
  { key: 'minimal_light',  label: 'Minimal Light', preview: 'DM Sans / Outfit',      sample: 'Aa' },
  { key: 'luxury_display', label: 'Luxury Display', preview: 'Cormorant / Libre',    sample: 'Aa' },
]

const BRAND_TONES = [
  { key: 'professional', label: 'Professional', desc: 'Corporate, trustworthy, formal' },
  { key: 'casual',       label: 'Casual',       desc: 'Friendly, conversational, warm' },
  { key: 'luxury',       label: 'Luxury',       desc: 'Premium, exclusive, sophisticated' },
  { key: 'energetic',    label: 'Energetic',    desc: 'Bold, dynamic, high-energy' },
  { key: 'trustworthy',  label: 'Trustworthy',  desc: 'Reliable, safe, established' },
  { key: 'playful',      label: 'Playful',      desc: 'Fun, youthful, creative' },
]

const INDUSTRIES = [
  'Technology / SaaS', 'E-commerce / Retail', 'Food & Beverage',
  'Fashion & Beauty', 'Health & Fitness', 'Real Estate',
  'Finance / Fintech', 'Education', 'Events & Entertainment',
  'Travel & Hospitality', 'Healthcare', 'Non-profit / Social',
]

interface BrandKit {
  primary_color:   string
  secondary_color: string
  accent_color:    string
  bg_color:        string
  font_style:      string
  brand_tone:      string
  brand_name:      string
  logo_url:        string
  industry:        string
}

const DEFAULTS: BrandKit = {
  primary_color:   '#6366F1',
  secondary_color: '#8B5CF6',
  accent_color:    '#F59E0B',
  bg_color:        '#0A0A1A',
  font_style:      'modern_sans',
  brand_tone:      'professional',
  brand_name:      '',
  logo_url:        '',
  industry:        '',
}

export default function BrandKitPage() {
  const [kit, setKit]         = useState<BrandKit>(DEFAULTS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving]   = useState(false)
  const [saved, setSaved]     = useState(false)
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [researching, setResearching] = useState(false)
  const [researchMsg, setResearchMsg] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/preferences/brand-kit`, {
          credentials: 'include',
        })
        if (res.ok) {
          const data = await res.json()
          if (data.brand_kit && Object.keys(data.brand_kit).length > 0) {
            setKit({ ...DEFAULTS, ...data.brand_kit })
          }
        }
      } catch { /* use defaults */ }
      finally { setLoading(false) }
    }
    load()
  }, [])

  const update = (key: keyof BrandKit, val: string) =>
    setKit(prev => ({ ...prev, [key]: val }))

  const handleResearch = async () => {
    if (!websiteUrl.trim()) return
    setResearching(true)
    setResearchMsg('')
    try {
      const res = await fetch(`${API_BASE}/api/v1/preferences/brand-kit/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ url: websiteUrl.trim() }),
      })
      const data = await res.json()
      if (!data.success) {
        setResearchMsg(`Failed: ${data.error || 'Unknown error'}`)
        return
      }
      setKit(prev => ({
        ...prev,
        ...(data.brand_name      ? { brand_name:      data.brand_name }      : {}),
        ...(data.primary_color   ? { primary_color:   data.primary_color }   : {}),
        ...(data.secondary_color ? { secondary_color: data.secondary_color } : {}),
        ...(data.logo_url        ? { logo_url:        data.logo_url }        : {}),
        ...(data.tone            ? { brand_tone:      data.tone }            : {}),
      }))
      setResearchMsg('Brand identity imported — review and save.')
    } catch {
      setResearchMsg('Could not reach server.')
    } finally {
      setResearching(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await fetch(`${API_BASE}/api/v1/preferences/brand-kit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(kit),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch { /* silent */ }
    finally { setSaving(false) }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-white/50" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 pb-24 space-y-6">
      <div>
        <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Brand Kit</h1>
        <p className="mt-1 text-sm text-white/50">Your brand identity is auto-applied to every generated ad and poster.</p>
      </div>

      {/* Import from website */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div className="flex items-center gap-2"><Globe className="h-4 w-4 text-white/60" /><p className="kerned text-white/40">IMPORT FROM WEBSITE</p></div>
        <p className="text-xs text-white/50">Paste your website URL — we'll extract your brand name, colors, and tone automatically.</p>
        <div className="flex items-center gap-2">
          <input
            type="url"
            value={websiteUrl}
            onChange={e => setWebsiteUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleResearch()}
            placeholder="https://yourbrand.com"
            className="flex-1 rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30"
          />
          <button
            onClick={handleResearch}
            disabled={researching || !websiteUrl.trim()}
            className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition disabled:opacity-40 whitespace-nowrap"
          >
            {researching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Globe className="h-3.5 w-3.5" />}
            {researching ? 'Analysing…' : 'Import'}
          </button>
        </div>
        {researchMsg && (
          <p className={`text-xs ${researchMsg.startsWith('Failed') || researchMsg.startsWith('Could') ? 'text-red-400' : 'text-emerald-400'}`}>{researchMsg}</p>
        )}
      </div>

      {/* Brand identity */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div className="flex items-center gap-2"><Megaphone className="h-4 w-4 text-white/60" /><p className="kerned text-white/40">BRAND IDENTITY</p></div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <p className="kerned text-white/40 mb-2">BRAND / COMPANY NAME</p>
            <input type="text" value={kit.brand_name} onChange={e => update('brand_name', e.target.value)} placeholder="e.g. Pixium AI" className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30" />
          </div>
          <div>
            <p className="kerned text-white/40 mb-2">INDUSTRY</p>
            <select value={kit.industry} onChange={e => update('industry', e.target.value)} className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30">
              <option value="">Select industry…</option>
              {INDUSTRIES.map(i => <option key={i} value={i}>{i}</option>)}
            </select>
          </div>
        </div>
        <div>
          <p className="kerned text-white/40 mb-2">LOGO URL</p>
          <input type="url" value={kit.logo_url} onChange={e => update('logo_url', e.target.value)} placeholder="https://yourdomain.com/logo.png" className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30" />
          {kit.logo_url && <img src={kit.logo_url} alt="logo preview" className="mt-2 h-10 rounded object-contain" />}
        </div>
      </div>

      {/* Brand colors */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div className="flex items-center gap-2"><Palette className="h-4 w-4 text-white/60" /><p className="kerned text-white/40">BRAND COLORS</p></div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <ColorPicker label="PRIMARY COLOR" value={kit.primary_color} onChange={v => update('primary_color', v)} />
          <ColorPicker label="SECONDARY COLOR" value={kit.secondary_color} onChange={v => update('secondary_color', v)} />
          <ColorPicker label="ACCENT / CTA COLOR" value={kit.accent_color} onChange={v => update('accent_color', v)} />
          <ColorPicker label="BACKGROUND COLOR" value={kit.bg_color} onChange={v => update('bg_color', v)} />
        </div>
        <div className="flex h-10 items-center justify-center gap-2 overflow-hidden rounded-lg text-xs font-medium" style={{ background: kit.bg_color }}>
          <span style={{ color: kit.primary_color }}>Headline</span>
          <span style={{ color: kit.secondary_color }}>Body text</span>
          <span className="rounded px-2 py-0.5" style={{ background: kit.accent_color, color: '#000' }}>CTA Button</span>
        </div>
      </div>

      {/* Font style */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div className="flex items-center gap-2"><Type className="h-4 w-4 text-white/60" /><p className="kerned text-white/40">FONT STYLE</p></div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {FONT_STYLES.map(f => (
            <button
              key={f.key}
              onClick={() => update('font_style', f.key)}
              className={`hairline flex flex-col items-start gap-1 rounded-xl p-3 text-left transition ${kit.font_style === f.key ? 'bg-white/10 ring-1 ring-white/30' : 'hover:bg-white/[0.04]'}`}
            >
              <span className="text-xl leading-none" style={{ fontFamily: f.key.includes('serif') ? 'Georgia, serif' : 'inherit' }}>{f.sample}</span>
              <span className="text-xs text-white/85">{f.label}</span>
              <span className="text-[10px] text-white/50">{f.preview}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Brand tone */}
      <div className="glass-panel rounded-2xl p-5 space-y-4">
        <div className="flex items-center gap-2"><Megaphone className="h-4 w-4 text-white/60" /><p className="kerned text-white/40">BRAND VOICE & TONE</p></div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {BRAND_TONES.map(t => (
            <button
              key={t.key}
              onClick={() => update('brand_tone', t.key)}
              className={`hairline flex flex-col gap-0.5 rounded-xl p-3 text-left transition ${kit.brand_tone === t.key ? 'bg-white/10 ring-1 ring-white/30' : 'hover:bg-white/[0.04]'}`}
            >
              <span className="text-xs text-white/85">{t.label}</span>
              <span className="text-[10px] leading-snug text-white/50">{t.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-black transition disabled:opacity-60"
          style={{ background: 'var(--gradient-aurora)' }}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : saved ? <CheckCircle className="h-4 w-4" /> : <Save className="h-4 w-4" />}
          {saved ? 'Saved!' : saving ? 'Saving…' : 'Save brand kit'}
        </button>
        <button onClick={() => setKit(DEFAULTS)} className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition">
          <RotateCcw className="h-3.5 w-3.5" /> Reset
        </button>
      </div>
    </div>
  )
}

function ColorPicker({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <p className="kerned text-white/40 mb-2">{label}</p>
      <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-2 py-1.5">
        <label className="relative cursor-pointer">
          <div className="h-6 w-6 rounded-md border border-white/20" style={{ background: value }} />
          <input type="color" value={value} onChange={e => onChange(e.target.value)} className="absolute inset-0 h-full w-full cursor-pointer opacity-0" />
        </label>
        <input
          type="text"
          value={value}
          onChange={e => { const v = e.target.value; if (/^#[0-9A-Fa-f]{0,6}$/.test(v)) onChange(v) }}
          className="flex-1 bg-transparent font-mono text-sm text-white/85 outline-none"
          maxLength={7}
        />
      </div>
    </div>
  )
}

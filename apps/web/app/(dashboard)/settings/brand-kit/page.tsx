'use client'

/**
 * Brand Kit Settings — /settings/brand-kit
 * Save brand colors, font style, tone, and logo so every generation auto-applies them.
 */

import React, { useEffect, useState } from 'react'
import { Palette, Type, Megaphone, Image, Save, CheckCircle, Loader2, RotateCcw, Globe } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003'

const FONT_STYLES = [
  { key: 'modern_sans',    label: 'Modern Sans',   preview: 'Inter / Poppins',      sample: 'Aa' },
  { key: 'elegant_serif',  label: 'Elegant Serif', preview: 'Playfair / Lora',       sample: 'Aa' },
  { key: 'bold_tech',      label: 'Bold Tech',     preview: 'Space Grotesk / Syne', sample: 'Aa' },
  { key: 'playful_round',  label: 'Playful Round', preview: 'Nunito / Fredoka',      sample: 'Aa' },
  { key: 'minimal_light',  label: 'Minimal Light', preview: 'DM Sans / Outfit',      sample: 'Aa' },
  { key: 'luxury_display', label: 'Luxury Display','preview': 'Cormorant / Libre',    sample: 'Aa' },
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
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-white">Brand Kit</h1>
        <p className="text-sm text-white/40 mt-1">
          Your brand identity is auto-applied to every generated ad and poster.
        </p>
      </div>

      {/* Import from Website */}
      <Section icon={<Globe className="w-4 h-4" />} title="Import from Website">
        <p className="text-xs text-white/40">
          Paste your website URL — we'll extract your brand name, colors, and tone automatically.
        </p>
        <div className="flex items-center gap-2">
          <input
            type="url"
            value={websiteUrl}
            onChange={e => setWebsiteUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleResearch()}
            placeholder="https://yourbrand.com"
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/50"
          />
          <button
            onClick={handleResearch}
            disabled={researching || !websiteUrl.trim()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/8 hover:bg-white/12 disabled:opacity-40 text-white text-sm font-medium transition-colors whitespace-nowrap border border-white/10"
          >
            {researching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Globe className="w-4 h-4" />}
            {researching ? 'Analysing…' : 'Import'}
          </button>
        </div>
        {researchMsg && (
          <p className={`text-xs ${researchMsg.startsWith('Failed') || researchMsg.startsWith('Could') ? 'text-red-400' : 'text-emerald-400'}`}>
            {researchMsg}
          </p>
        )}
      </Section>

      {/* Brand Info */}
      <Section icon={<Megaphone className="w-4 h-4" />} title="Brand Identity">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-white/50 mb-1.5">Brand / Company Name</label>
            <input
              type="text"
              value={kit.brand_name}
              onChange={e => update('brand_name', e.target.value)}
              placeholder="e.g. PhotoGenius AI"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/50 focus:bg-white/8"
            />
          </div>
          <div>
            <label className="block text-xs text-white/50 mb-1.5">Industry</label>
            <select
              value={kit.industry}
              onChange={e => update('industry', e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/50 appearance-none"
            >
              <option value="">Select industry…</option>
              {INDUSTRIES.map(i => <option key={i} value={i}>{i}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="block text-xs text-white/50 mb-1.5">Logo URL</label>
          <input
            type="url"
            value={kit.logo_url}
            onChange={e => update('logo_url', e.target.value)}
            placeholder="https://yourdomain.com/logo.png"
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/50"
          />
          {kit.logo_url && (
            <img src={kit.logo_url} alt="logo preview" className="mt-2 h-10 object-contain rounded" />
          )}
        </div>
      </Section>

      {/* Brand Colors */}
      <Section icon={<Palette className="w-4 h-4" />} title="Brand Colors">
        <div className="grid grid-cols-2 gap-4">
          <ColorPicker label="Primary Color" value={kit.primary_color} onChange={v => update('primary_color', v)} />
          <ColorPicker label="Secondary Color" value={kit.secondary_color} onChange={v => update('secondary_color', v)} />
          <ColorPicker label="Accent / CTA Color" value={kit.accent_color} onChange={v => update('accent_color', v)} />
          <ColorPicker label="Background Color" value={kit.bg_color} onChange={v => update('bg_color', v)} />
        </div>
        {/* Preview swatch */}
        <div
          className="mt-3 h-10 rounded-lg flex items-center justify-center gap-2 text-xs font-medium overflow-hidden"
          style={{ background: kit.bg_color }}
        >
          <span style={{ color: kit.primary_color }}>Headline</span>
          <span style={{ color: kit.secondary_color }}>Body text</span>
          <span
            className="px-2 py-0.5 rounded"
            style={{ background: kit.accent_color, color: '#000' }}
          >
            CTA Button
          </span>
        </div>
      </Section>

      {/* Font Style */}
      <Section icon={<Type className="w-4 h-4" />} title="Font Style">
        <div className="grid grid-cols-3 gap-2">
          {FONT_STYLES.map(f => (
            <button
              key={f.key}
              onClick={() => update('font_style', f.key)}
              className={[
                'flex flex-col items-start gap-1 p-3 rounded-xl border text-left transition-all',
                kit.font_style === f.key
                  ? 'bg-purple-600/15 border-purple-500/50 text-white'
                  : 'bg-white/3 border-white/8 text-white/50 hover:border-white/20 hover:text-white',
              ].join(' ')}
            >
              <span className="text-xl font-bold leading-none" style={{ fontFamily: f.key.includes('serif') ? 'Georgia, serif' : 'inherit' }}>
                {f.sample}
              </span>
              <span className="text-xs font-medium">{f.label}</span>
              <span className="text-[10px] opacity-60">{f.preview}</span>
            </button>
          ))}
        </div>
      </Section>

      {/* Brand Tone */}
      <Section icon={<Megaphone className="w-4 h-4" />} title="Brand Voice & Tone">
        <div className="grid grid-cols-3 gap-2">
          {BRAND_TONES.map(t => (
            <button
              key={t.key}
              onClick={() => update('brand_tone', t.key)}
              className={[
                'flex flex-col gap-0.5 p-3 rounded-xl border text-left transition-all',
                kit.brand_tone === t.key
                  ? 'bg-purple-600/15 border-purple-500/50 text-white'
                  : 'bg-white/3 border-white/8 text-white/50 hover:border-white/20 hover:text-white',
              ].join(' ')}
            >
              <span className="text-xs font-semibold">{t.label}</span>
              <span className="text-[10px] opacity-60 leading-snug">{t.desc}</span>
            </button>
          ))}
        </div>
      </Section>

      {/* Actions */}
      <div className="flex items-center gap-3 pb-8">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-60 text-white text-sm font-medium transition-colors"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : saved ? (
            <CheckCircle className="w-4 h-4" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          {saved ? 'Saved!' : saving ? 'Saving…' : 'Save Brand Kit'}
        </button>
        <button
          onClick={() => setKit(DEFAULTS)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-white/10 text-white/40 hover:text-white hover:border-white/20 text-sm transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" /> Reset
        </button>
      </div>
    </div>
  )
}

// ── Helpers ─────────────────────────────────────────────────────────────────────

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-white/60">
        {icon}
        <h2 className="text-xs font-semibold uppercase tracking-widest">{title}</h2>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function ColorPicker({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-xs text-white/50 mb-1.5">{label}</label>
      <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-2 py-1.5">
        <label className="relative cursor-pointer">
          <div
            className="w-6 h-6 rounded-md border border-white/20 shadow-inner"
            style={{ background: value }}
          />
          <input
            type="color"
            value={value}
            onChange={e => onChange(e.target.value)}
            className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
          />
        </label>
        <input
          type="text"
          value={value}
          onChange={e => {
            const v = e.target.value
            if (/^#[0-9A-Fa-f]{0,6}$/.test(v)) onChange(v)
          }}
          className="flex-1 bg-transparent text-sm text-white focus:outline-none font-mono"
          maxLength={7}
        />
      </div>
    </div>
  )
}

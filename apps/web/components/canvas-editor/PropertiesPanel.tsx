'use client'

import React from 'react'
import { Sparkles, RefreshCw, Palette, Type, AlignLeft, AlignCenter, AlignRight, Loader2 } from 'lucide-react'
import type { DesignBrief } from '@/lib/canvas-bridge'

interface PropertiesPanelProps {
  selectedId: string | null
  selectedProps: any
  designBrief: DesignBrief
  onChange: (prop: string, value: any) => void
  onAIAssist: (type: 'copy' | 'recolor' | 'regen_bg' | 'apply_brand') => void
  aiLoading: boolean
}

const FONT_OPTIONS = [
  { value: 'Bebas Neue, Impact, sans-serif',       label: 'Bebas Neue'       },
  { value: 'Anton, Impact, sans-serif',             label: 'Anton'            },
  { value: 'Montserrat, sans-serif',                label: 'Montserrat'       },
  { value: 'Playfair Display, Georgia, serif',      label: 'Playfair Display' },
  { value: 'Oswald, sans-serif',                    label: 'Oswald'           },
  { value: 'Inter, system-ui, sans-serif',          label: 'Inter'            },
  { value: 'Raleway, sans-serif',                   label: 'Raleway'          },
  { value: 'Poppins, sans-serif',                   label: 'Poppins'          },
  { value: 'Roboto, sans-serif',                    label: 'Roboto'           },
  { value: 'DM Sans, sans-serif',                   label: 'DM Sans'          },
  { value: 'Plus Jakarta Sans, sans-serif',         label: 'Jakarta Sans'     },
  { value: 'Black Han Sans, sans-serif',            label: 'Black Han Sans'   },
]

const BRAND_ACCENT_COLORS = [
  '#F59E0B', '#EF4444', '#6366F1', '#10B981', '#3B82F6',
  '#F472B6', '#8B5CF6', '#14B8A6', '#F97316', '#FFFFFF',
]

export function PropertiesPanel({
  selectedId, selectedProps, designBrief, onChange, onAIAssist, aiLoading,
}: PropertiesPanelProps) {
  const isText  = selectedProps?.fabricType === 'textbox'
  const isShape = selectedProps?.fabricType === 'rect'
  const isImage = selectedProps?.fabricType === 'image'
  const hasSelection = !!selectedId && selectedId !== 'hero_image'

  return (
    <div className="w-60 bg-[#13131A] border-l border-white/8 flex flex-col shrink-0 overflow-y-auto">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-white/8">
        <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">
          {hasSelection ? (selectedProps?.elementId ?? 'Properties') : 'Properties'}
        </span>
      </div>

      {/* AI Assist — always visible */}
      <div className="px-3 py-3 border-b border-white/8 space-y-2">
        <p className="text-xs text-white/40 font-medium uppercase tracking-wider mb-2">AI Assist</p>

        {isText && (
          <AIButton
            icon={<Sparkles className="w-3.5 h-3.5" />}
            label="Improve Copy"
            onClick={() => onAIAssist('copy')}
            loading={aiLoading}
          />
        )}
        <AIButton
          icon={<RefreshCw className="w-3.5 h-3.5" />}
          label="Regenerate Background"
          onClick={() => onAIAssist('regen_bg')}
          loading={aiLoading}
        />
        <AIButton
          icon={<Palette className="w-3.5 h-3.5" />}
          label="Apply Brand Colors"
          onClick={() => onAIAssist('apply_brand')}
          loading={aiLoading}
        />
      </div>

      {/* Text properties */}
      {isText && selectedProps?.editable && (
        <div className="px-3 py-3 border-b border-white/8 space-y-3">
          <p className="text-xs text-white/40 font-medium uppercase tracking-wider">Typography</p>

          {/* Font family */}
          <div>
            <label className="text-xs text-white/50 block mb-1">Font</label>
            <select
              value={selectedProps.fontFamily ?? ''}
              onChange={(e) => onChange('fontFamily', e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500"
            >
              {FONT_OPTIONS.map(f => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </div>

          {/* Font size */}
          <div>
            <label className="text-xs text-white/50 block mb-1">Size: {selectedProps.fontSize ?? 48}px</label>
            <input
              type="range"
              min={8} max={200}
              value={selectedProps.fontSize ?? 48}
              onChange={(e) => onChange('fontSize', Number(e.target.value))}
              className="w-full accent-purple-500"
            />
          </div>

          {/* Font weight */}
          <div>
            <label className="text-xs text-white/50 block mb-1">Weight</label>
            <div className="flex gap-1">
              {['400', '600', '700', '900'].map(w => (
                <button
                  key={w}
                  onClick={() => onChange('fontWeight', w)}
                  className={[
                    'flex-1 py-1 rounded text-xs transition-colors',
                    selectedProps.fontWeight === w
                      ? 'bg-purple-500 text-white'
                      : 'bg-white/5 text-white/50 hover:bg-white/10',
                  ].join(' ')}
                  style={{ fontWeight: w }}
                >
                  {w === '400' ? 'Reg' : w === '600' ? 'Sem' : w === '700' ? 'Bold' : 'Black'}
                </button>
              ))}
            </div>
          </div>

          {/* Text align */}
          <div>
            <label className="text-xs text-white/50 block mb-1">Align</label>
            <div className="flex gap-1">
              {[
                { value: 'left',   icon: <AlignLeft   className="w-3.5 h-3.5" /> },
                { value: 'center', icon: <AlignCenter className="w-3.5 h-3.5" /> },
                { value: 'right',  icon: <AlignRight  className="w-3.5 h-3.5" /> },
              ].map(({ value, icon }) => (
                <button
                  key={value}
                  onClick={() => onChange('textAlign', value)}
                  className={[
                    'flex-1 flex items-center justify-center py-1.5 rounded transition-colors',
                    selectedProps.textAlign === value
                      ? 'bg-purple-500 text-white'
                      : 'bg-white/5 text-white/50 hover:bg-white/10',
                  ].join(' ')}
                >
                  {icon}
                </button>
              ))}
            </div>
          </div>

          {/* Text color */}
          <div>
            <label className="text-xs text-white/50 block mb-1">Color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={selectedProps.fill ?? '#FFFFFF'}
                onChange={(e) => onChange('fill', e.target.value)}
                className="w-8 h-8 rounded cursor-pointer bg-transparent border-0"
              />
              <span className="text-xs text-white/40 font-mono">{selectedProps.fill ?? '#FFFFFF'}</span>
            </div>
            {/* Quick swatches */}
            <div className="flex gap-1 mt-2 flex-wrap">
              {BRAND_ACCENT_COLORS.map(c => (
                <button
                  key={c}
                  onClick={() => onChange('fill', c)}
                  className="w-5 h-5 rounded-full border border-white/20 hover:scale-110 transition-transform"
                  style={{ backgroundColor: c }}
                  title={c}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Shape properties */}
      {isShape && selectedProps?.editable && (
        <div className="px-3 py-3 border-b border-white/8 space-y-3">
          <p className="text-xs text-white/40 font-medium uppercase tracking-wider">Shape</p>

          {/* Fill color */}
          <div>
            <label className="text-xs text-white/50 block mb-1">Fill Color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={selectedProps.fill ?? '#F59E0B'}
                onChange={(e) => onChange('fill', e.target.value)}
                className="w-8 h-8 rounded cursor-pointer bg-transparent border-0"
              />
              <span className="text-xs text-white/40 font-mono">{selectedProps.fill ?? '#F59E0B'}</span>
            </div>
            <div className="flex gap-1 mt-2 flex-wrap">
              {BRAND_ACCENT_COLORS.map(c => (
                <button key={c} onClick={() => onChange('fill', c)}
                  className="w-5 h-5 rounded-full border border-white/20 hover:scale-110 transition-transform"
                  style={{ backgroundColor: c }} />
              ))}
            </div>
          </div>

          {/* Border radius */}
          <div>
            <label className="text-xs text-white/50 block mb-1">Corner Radius: {selectedProps.rx ?? 0}px</label>
            <input
              type="range" min={0} max={60}
              value={selectedProps.rx ?? 0}
              onChange={(e) => { onChange('rx', Number(e.target.value)); onChange('ry', Number(e.target.value)) }}
              className="w-full accent-purple-500"
            />
          </div>
        </div>
      )}

      {/* Opacity — all types */}
      {hasSelection && (
        <div className="px-3 py-3 space-y-2">
          <p className="text-xs text-white/40 font-medium uppercase tracking-wider">General</p>
          <div>
            <label className="text-xs text-white/50 block mb-1">
              Opacity: {Math.round((selectedProps?.opacity ?? 1) * 100)}%
            </label>
            <input
              type="range" min={0} max={1} step={0.01}
              value={selectedProps?.opacity ?? 1}
              onChange={(e) => onChange('opacity', Number(e.target.value))}
              className="w-full accent-purple-500"
            />
          </div>
        </div>
      )}

      {/* No selection state */}
      {!hasSelection && (
        <div className="flex-1 flex flex-col items-center justify-center px-4 py-8 text-center">
          <Type className="w-8 h-8 text-white/15 mb-3" />
          <p className="text-xs text-white/30 leading-relaxed">
            Click any element on the canvas to edit its properties
          </p>
        </div>
      )}
    </div>
  )
}

function AIButton({
  icon, label, onClick, loading,
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
  loading: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-purple-500/15 border border-white/8 hover:border-purple-500/40 text-xs text-white/70 hover:text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : icon}
      <span>{label}</span>
    </button>
  )
}

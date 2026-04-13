"use client"

/**
 * World-Class Generation Controls V2
 * Redesigned following Ideogram/Recraft/Leonardo patterns
 * - Compact horizontal pills for primary controls
 * - Prominent prompt area
 * - Elegant collapsible advanced panel
 * - Professional spacing and hierarchy
 */

import React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import {
  ImageIcon,
  Zap,
  Palette,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
  Check,
  Sparkles,
} from "lucide-react"

// ─── TYPES ───

interface DimensionPreset {
  label: string
  width: number
  height: number
  aspect: string
}

interface QualityOption {
  value: string
  label: string
  hint: string
  note: string
}

interface StyleOption {
  id: string
  icon: React.ElementType
  label: string
  from: string
  to: string
}

interface GenerationControlsV2Props {
  // Aspect Ratio
  dimensionPresets: DimensionPreset[]
  selectedDimension: DimensionPreset
  onDimensionChange: (preset: DimensionPreset) => void
  sizeMode: "preset" | "custom"
  customWidth: number
  customHeight: number
  onCustomWidthChange: (width: number) => void
  onCustomHeightChange: (height: number) => void
  onSizeModeChange: (mode: "preset" | "custom") => void

  // Quality
  qualityOptions: QualityOption[]
  qualityTier: string
  onQualityChange: (quality: string) => void

  // Style
  styles: StyleOption[]
  selectedStyle: string
  onStyleChange: (style: string) => void

  // Advanced
  negativePrompt: string
  onNegativePromptChange: (prompt: string) => void
  showAdvanced: boolean
  onAdvancedToggle: () => void

  // State
  isGenerating: boolean
  creationMode?: "image" | "poster"
}

// ─── QUALITY COLOR MAPPING ───
const QUALITY_COLORS: Record<string, string> = {
  fast: "#71717a",
  balanced: "#3b82f6",
  quality: "#8b5cf6",
  ultra: "#d97706",
}

export function GenerationControlsV2({
  dimensionPresets,
  selectedDimension,
  onDimensionChange,
  sizeMode,
  customWidth,
  customHeight,
  onCustomWidthChange,
  onCustomHeightChange,
  onSizeModeChange,
  qualityOptions,
  qualityTier,
  onQualityChange,
  styles,
  selectedStyle,
  onStyleChange,
  negativePrompt,
  onNegativePromptChange,
  showAdvanced,
  onAdvancedToggle,
  isGenerating,
  creationMode = "image",
}: GenerationControlsV2Props) {
  const snap64 = (v: number) => Math.min(2048, Math.max(64, Math.round(v / 64) * 64))

  return (
    <div className="space-y-4">
      {/* ─── COMPACT CONTROL BAR ─── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4 space-y-4"
      >
        {/* Aspect Ratio Pills */}
        <div>
          <label className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <ImageIcon className="h-3 w-3" /> Aspect Ratio
          </label>
          <div className="flex flex-wrap gap-1.5">
            {dimensionPresets.map((preset) => {
              const isSel = sizeMode === "preset" && selectedDimension.label === preset.label
              const isAuto = preset.aspect === "auto"
              const [w, h] = isAuto ? [1, 1] : preset.aspect.split(":").map(Number)
              const ratio = w / h
              const base = 16
              const boxW = ratio >= 1 ? base : Math.round(base * ratio)
              const boxH = ratio >= 1 ? Math.round(base / ratio) : base

              return (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => {
                    onDimensionChange(preset)
                    onSizeModeChange("preset")
                  }}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 rounded-xl border transition-all",
                    isSel
                      ? "border-primary/50 bg-primary/15 text-primary"
                      : "border-white/[0.08] bg-white/[0.025] text-muted-foreground hover:text-foreground hover:bg-white/[0.06] hover:border-white/15"
                  )}
                >
                  {isAuto ? (
                    <span className="flex items-center justify-center opacity-70 font-bold text-xs">
                      ✦
                    </span>
                  ) : (
                    <span
                      className="rounded-[3px] bg-current opacity-70 shrink-0 block"
                      style={{ width: Math.max(boxW, 8), height: Math.max(boxH, 8) }}
                    />
                  )}
                  <div className="flex flex-col items-start">
                    <span className="text-xs font-semibold leading-none">{preset.label}</span>
                    <span className={cn("text-[9px] leading-none mt-0.5", isSel ? "opacity-60" : "opacity-35")}>
                      {isAuto ? "any" : preset.aspect}
                    </span>
                  </div>
                  {isSel && (
                    <Check className="h-3 w-3 ml-auto opacity-70" />
                  )}
                </button>
              )
            })}
            <button
              type="button"
              onClick={() => {
                const d = sizeMode === "custom"
                  ? { width: customWidth, height: customHeight }
                  : { width: selectedDimension.width, height: selectedDimension.height }
                onSizeModeChange("custom")
                onCustomWidthChange(d.width)
                onCustomHeightChange(d.height)
              }}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-xl border transition-all",
                sizeMode === "custom"
                  ? "border-primary/50 bg-primary/15 text-primary"
                  : "border-white/[0.08] bg-white/[0.025] text-muted-foreground hover:text-foreground hover:bg-white/[0.06] hover:border-white/15"
              )}
            >
              <span className="flex items-center justify-center opacity-70 font-bold text-xs">⊞</span>
              <div className="flex flex-col items-start">
                <span className="text-xs font-semibold leading-none">Custom</span>
                <span className={cn("text-[9px] leading-none mt-0.5", sizeMode === "custom" ? "opacity-60" : "opacity-35")}>W×H</span>
              </div>
            </button>
          </div>

          {/* Custom Size Inputs - Slides down */}
          <AnimatePresence>
            {sizeMode === "custom" && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden mt-3"
              >
                <div className="flex items-center gap-3">
                  {/* Width */}
                  <div className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.03] p-2.5">
                    <p className="text-[9px] text-muted-foreground/50 font-semibold uppercase tracking-wider mb-1.5">
                      Width
                    </p>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => onCustomWidthChange(snap64(customWidth - 64))}
                        className="h-7 w-7 rounded-lg bg-white/[0.05] border border-white/[0.08] text-foreground/70 hover:bg-white/10 hover:text-foreground flex items-center justify-center text-base font-bold transition-all shrink-0"
                      >
                        −
                      </button>
                      <input
                        type="number"
                        value={customWidth}
                        min={64}
                        max={2048}
                        step={64}
                        onChange={(e) => onCustomWidthChange(Number(e.target.value))}
                        onBlur={(e) => onCustomWidthChange(snap64(Number(e.target.value)))}
                        className="flex-1 min-w-0 text-center text-sm font-semibold text-foreground bg-transparent outline-none tabular-nums"
                      />
                      <button
                        type="button"
                        onClick={() => onCustomWidthChange(snap64(customWidth + 64))}
                        className="h-7 w-7 rounded-lg bg-white/[0.05] border border-white/[0.08] text-foreground/70 hover:bg-white/10 hover:text-foreground flex items-center justify-center text-base font-bold transition-all shrink-0"
                      >
                        +
                      </button>
                    </div>
                  </div>
                  <span className="text-muted-foreground/40 text-sm font-bold shrink-0">×</span>
                  {/* Height */}
                  <div className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.03] p-2.5">
                    <p className="text-[9px] text-muted-foreground/50 font-semibold uppercase tracking-wider mb-1.5">
                      Height
                    </p>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => onCustomHeightChange(snap64(customHeight - 64))}
                        className="h-7 w-7 rounded-lg bg-white/[0.05] border border-white/[0.08] text-foreground/70 hover:bg-white/10 hover:text-foreground flex items-center justify-center text-base font-bold transition-all shrink-0"
                      >
                        −
                      </button>
                      <input
                        type="number"
                        value={customHeight}
                        min={64}
                        max={2048}
                        step={64}
                        onChange={(e) => onCustomHeightChange(Number(e.target.value))}
                        onBlur={(e) => onCustomHeightChange(snap64(Number(e.target.value)))}
                        className="flex-1 min-w-0 text-center text-sm font-semibold text-foreground bg-transparent outline-none tabular-nums"
                      />
                      <button
                        type="button"
                        onClick={() => onCustomHeightChange(snap64(customHeight + 64))}
                        className="h-7 w-7 rounded-lg bg-white/[0.05] border border-white/[0.08] text-foreground/70 hover:bg-white/10 hover:text-foreground flex items-center justify-center text-base font-bold transition-all shrink-0"
                      >
                        +
                      </button>
                    </div>
                  </div>
                </div>
                <p className="text-[10px] text-muted-foreground/35 mt-2">
                  Steps of 64px · max 2048px · values auto-snap
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Quality Pills */}
        <div>
          <label className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <Zap className="h-3 w-3" /> Quality Tier
          </label>
          <div className="flex flex-wrap gap-1.5">
            {qualityOptions
              .filter((q) => !(creationMode === "poster" && q.value === "fast"))
              .map((q) => {
                const isSel = qualityTier === q.value
                return (
                  <button
                    key={q.value}
                    type="button"
                    onClick={() => onQualityChange(q.value)}
                    className={cn(
                      "flex items-center gap-2.5 px-3 py-2 rounded-xl border transition-all",
                      isSel
                        ? "border-primary/50 bg-primary/15 text-primary"
                        : "border-white/[0.08] bg-white/[0.025] text-muted-foreground hover:text-foreground hover:bg-white/[0.06] hover:border-white/15"
                    )}
                  >
                    <span
                      className="h-2 w-2 rounded-full shrink-0"
                      style={{
                        backgroundColor: QUALITY_COLORS[q.value],
                        opacity: isSel ? 1 : 0.4,
                      }}
                    />
                    <div className="flex flex-col items-start">
                      <span className="text-xs font-semibold leading-none">{q.label}</span>
                      <span className={cn("text-[9px] leading-none mt-0.5", isSel ? "opacity-60" : "opacity-35")}>
                        {q.hint}
                      </span>
                    </div>
                    {isSel && <Check className="h-3 w-3 ml-auto opacity-70" />}
                  </button>
                )
              })}
          </div>
        </div>

        {/* Style Pills - Horizontal scroll on mobile */}
        <div>
          <label className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <Palette className="h-3 w-3" /> Style
          </label>
          <div className="flex gap-1.5 overflow-x-auto no-scrollbar pb-1">
            {styles.map(({ id, icon: Icon, label, from, to }) => {
              const isSel = selectedStyle === id
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => onStyleChange(id)}
                  className={cn(
                    "relative shrink-0 w-[72px] h-[90px] rounded-xl overflow-hidden border transition-all",
                    isSel
                      ? "border-primary ring-2 ring-primary/40 scale-[1.02]"
                      : "border-white/[0.1] hover:border-white/25"
                  )}
                >
                  <div
                    className="absolute inset-0"
                    style={{ background: `linear-gradient(160deg, ${from}, ${to})` }}
                  />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Icon className="h-5 w-5 text-white/50" />
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 pb-2 pt-4 text-center bg-gradient-to-t from-black/80 via-black/30 to-transparent">
                    <span className="text-[10px] font-semibold text-white/90 leading-none">
                      {label}
                    </span>
                  </div>
                  {isSel && (
                    <div className="absolute top-1.5 right-1.5 h-4 w-4 rounded-full bg-primary flex items-center justify-center shadow-sm">
                      <Check className="h-2.5 w-2.5 text-white" />
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      </motion.div>

      {/* ─── ADVANCED PANEL ─── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="rounded-xl border border-white/[0.07] bg-white/[0.015] overflow-hidden"
      >
        <button
          type="button"
          onClick={onAdvancedToggle}
          className="flex items-center gap-2 px-4 py-2.5 text-[11px] font-semibold text-muted-foreground/60 hover:text-foreground/80 w-full uppercase tracking-wider transition-colors"
        >
          <SlidersHorizontal className="h-3 w-3" />
          Advanced Options
          <div className="flex-1" />
          {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
        <AnimatePresence>
          {showAdvanced && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden border-t border-white/[0.06]"
            >
              <div className="p-4 space-y-2">
                <label className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider">
                  Negative Prompt
                </label>
                <textarea
                  value={negativePrompt}
                  onChange={(e) => onNegativePromptChange(e.target.value)}
                  placeholder="What to avoid — blurry, low quality, distorted..."
                  rows={3}
                  disabled={isGenerating}
                  className="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-xs text-foreground placeholder:text-muted-foreground/40 outline-none focus:border-primary/30 focus:bg-primary/5 resize-none disabled:opacity-50 transition-colors"
                />
                <p className="text-[10px] text-muted-foreground/40 flex items-center gap-1.5">
                  <Sparkles className="h-3 w-3 shrink-0" /> AI automatically adds quality negatives for better results
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}

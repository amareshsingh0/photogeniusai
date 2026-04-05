"use client"

/**
 * PosterInlineEditor v2 — Sprint 4
 *
 * Production fixes applied (v1 → v2):
 * - AbortController: cancels in-flight fetch when newer request starts
 * - Race condition guard: renderIdRef ensures only the latest response updates UI
 * - isRendering correctly tied to the current request (not cleared by stale finishers)
 * - Unmount cleanup: debounce timer and AbortController both cancelled
 * - Props → state sync: useEffect resets local state when parent passes new generation
 * - Manual re-render button cancels pending debounce before firing
 * - HTTP error handling: distinct messages for 429 / 401 / 5xx before JSON parse
 * - color picker: fires only on change; hex normalized for swatch active-check
 * - adCopyRef / designRef: updateCopy/updateAccent always use latest committed state
 * - triggerRecomposeRef: debounce closure always calls the current callback
 * - 30s timeout abort on slow compositor
 * - InlineField: maxLength prop + character count indicator + React.memo
 * - onUpdated: passes back (dataUri, newAdCopy, newDesign) so parent stays in sync
 * - Reset button: restores original AI-generated values
 * - Feature grid + CTA toggles
 * - bg_color dark/light toggle
 * - AI accent color prepended to swatches if not already present
 */

import React, {
  useState, useCallback, useRef, useEffect, useMemo, useReducer,
} from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Loader2, RefreshCw, Palette, Type,
  ChevronDown, ChevronUp, Check, RotateCcw,
  Sun, Moon, Grid, MousePointerClick,
} from "lucide-react"
import { cn } from "@/lib/utils"

// ── Types ─────────────────────────────────────────────────────────────────────

interface AdCopy {
  brand_name?: string
  headline?: string
  subheadline?: string
  body?: string
  cta?: string
  tagline?: string
  features?: { icon?: string; title?: string; desc?: string }[]
}

interface PosterDesign {
  layout?: string
  accent_color?: string
  bg_color?: string
  font_style?: string
  has_feature_grid?: boolean
  has_cta_button?: boolean
  hero_occupies?: string
}

interface PosterInlineEditorProps {
  heroUrl: string
  adCopy: AdCopy
  posterDesign: PosterDesign
  width?: number
  height?: number
  /** Called with (newDataUri, newAdCopy, newDesign) after successful recompose */
  onUpdated?: (dataUri: string, newAdCopy: AdCopy, newDesign: PosterDesign) => void
}

// ── State reducer (eliminates stale-closure bugs between adCopy + design) ────

type EditorState = { adCopy: AdCopy; design: PosterDesign }
type EditorAction =
  | { type: "SET_COPY_FIELD"; key: keyof AdCopy; value: string }
  | { type: "SET_ACCENT"; color: string }
  | { type: "SET_FONT_STYLE"; fs: string }
  | { type: "TOGGLE_FEATURES" }
  | { type: "TOGGLE_CTA" }
  | { type: "TOGGLE_BG" }
  | { type: "RESET"; adCopy: AdCopy; design: PosterDesign }
  | { type: "SYNC_PROPS"; adCopy: AdCopy; design: PosterDesign }

function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "SET_COPY_FIELD":
      return { ...state, adCopy: { ...state.adCopy, [action.key]: action.value } }
    case "SET_ACCENT":
      return { ...state, design: { ...state.design, accent_color: action.color } }
    case "SET_FONT_STYLE":
      return { ...state, design: { ...state.design, font_style: action.fs } }
    case "TOGGLE_FEATURES":
      return { ...state, design: { ...state.design, has_feature_grid: !state.design.has_feature_grid } }
    case "TOGGLE_CTA":
      return { ...state, design: { ...state.design, has_cta_button: !state.design.has_cta_button } }
    case "TOGGLE_BG":
      return {
        ...state,
        design: {
          ...state.design,
          bg_color: state.design.bg_color === "#F8FAFC" ? "#0F172A" : "#F8FAFC",
        },
      }
    case "RESET":
    case "SYNC_PROPS":
      return { adCopy: { ...action.adCopy }, design: { ...action.design } }
  }
}

// ── Constants ─────────────────────────────────────────────────────────────────

const BASE_SWATCHES = [
  "#F59E0B", "#EF4444", "#10B981", "#3B82F6",
  "#8B5CF6", "#EC4899", "#F97316", "#06B6D4",
]

const FONT_STYLES = [
  { value: "bold_tech",          label: "Bold Tech"       },
  { value: "expressive_display", label: "Expressive"      },
  { value: "elegant_serif",      label: "Elegant Serif"   },
  { value: "clean_sans",         label: "Clean Sans"      },
  { value: "modern_sans",        label: "Modern Sans"     },
  { value: "friendly_round",     label: "Friendly Round"  },
  { value: "luxury_display",     label: "Luxury Display"  },
  { value: "minimal_light",      label: "Minimal Light"   },
]

const MAX_WAIT_MS = 3000  // max debounce wait (fire at least once per 3s of continuous typing)

function normalizeHex(h = "") {
  return h.trim().toUpperCase()
}

// ── Component ─────────────────────────────────────────────────────────────────

export function PosterInlineEditor({
  heroUrl,
  adCopy: initialAdCopy,
  posterDesign: initialDesign,
  width = 1024,
  height = 1536,
  onUpdated,
}: PosterInlineEditorProps) {
  const [state, dispatch] = useReducer(editorReducer, {
    adCopy: { ...(initialAdCopy ?? {}) },
    design: { ...(initialDesign ?? {}) },
  })
  const { adCopy, design } = state

  const [isRendering, setIsRendering]   = useState(false)
  const [expanded, setExpanded]         = useState(true)
  const [lastError, setLastError]       = useState<string | null>(null)

  // Refs for race-condition and stale-closure protection
  const debounceRef        = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastFireTimeRef    = useRef<number>(Date.now())
  const renderIdRef        = useRef(0)
  const abortRef           = useRef<AbortController | null>(null)

  // Always-current function ref (debounce closure never goes stale)
  const triggerRecomposeRef = useRef<(copy: AdCopy, d: PosterDesign) => void>(() => {})

  // ── Sync props → state when parent passes a new generation ────────────────
  const prevInitialRef = useRef({ adCopy: initialAdCopy, design: initialDesign })
  useEffect(() => {
    if (
      initialAdCopy !== prevInitialRef.current.adCopy ||
      initialDesign !== prevInitialRef.current.design
    ) {
      prevInitialRef.current = { adCopy: initialAdCopy, design: initialDesign }
      dispatch({ type: "SYNC_PROPS", adCopy: initialAdCopy ?? {}, design: initialDesign ?? {} })
    }
  }, [initialAdCopy, initialDesign])

  // ── Unmount cleanup ───────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      abortRef.current?.abort()
    }
  }, [])

  // ── Core recompose function ───────────────────────────────────────────────
  const triggerRecompose = useCallback(
    async (copy: AdCopy, d: PosterDesign) => {
      if (!heroUrl) return

      // Cancel previous in-flight request
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      // 30s safety timeout
      const timeoutId = setTimeout(() => controller.abort(), 30_000)

      // Race condition guard: only the latest request may update UI
      const id = ++renderIdRef.current
      setIsRendering(true)
      setLastError(null)

      try {
        const res = await fetch("/api/generate/poster-recompose", {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          signal:  controller.signal,
          body: JSON.stringify({
            hero_url: heroUrl,
            ad_copy: {
              brand_name:  copy.brand_name  ?? "",
              headline:    copy.headline    ?? "",
              subheadline: copy.subheadline ?? "",
              body:        copy.body        ?? "",
              cta:         copy.cta         ?? "",
              tagline:     copy.tagline     ?? "",
              features:    copy.features    ?? [],
            },
            poster_design: {
              layout:           d.layout           ?? "hero_top_features_bottom",
              accent_color:     d.accent_color      ?? "#F59E0B",
              bg_color:         d.bg_color          ?? "#0F172A",
              font_style:       d.font_style        ?? "bold_tech",
              has_feature_grid: d.has_feature_grid  ?? true,
              has_cta_button:   d.has_cta_button    ?? true,
              hero_occupies:    d.hero_occupies     ?? "top_60",
            },
            width,
            height,
          }),
        })

        // HTTP error handling before JSON parse
        if (!res.ok) {
          const msg = res.status === 429 ? "Too many requests — slow down"
                    : res.status === 401 ? "Session expired — please refresh"
                    : `Server error (${res.status})`
          if (id === renderIdRef.current) setLastError(msg)
          return
        }

        const data = await res.json()

        // Ignore superseded responses
        if (id !== renderIdRef.current) return

        if (data.success && data.image_data_uri) {
          onUpdated?.(data.image_data_uri, copy, d)
        } else {
          setLastError(data.error ?? "Re-render failed")
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return  // intentionally cancelled
        if (id === renderIdRef.current) {
          setLastError("Re-render service unavailable")
        }
      } finally {
        clearTimeout(timeoutId)
        if (id === renderIdRef.current) setIsRendering(false)
      }
    },
    [heroUrl, width, height, onUpdated]
  )

  // Keep ref current so debounce closure never calls a stale version
  useEffect(() => { triggerRecomposeRef.current = triggerRecompose }, [triggerRecompose])

  // ── Debounced schedule (max-wait cap prevents indefinite delay) ───────────
  const scheduleRerender = useCallback((copy: AdCopy, d: PosterDesign) => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const elapsed  = Date.now() - lastFireTimeRef.current
    const waitMs   = Math.min(900, Math.max(0, MAX_WAIT_MS - elapsed))
    debounceRef.current = setTimeout(() => {
      lastFireTimeRef.current = Date.now()
      triggerRecomposeRef.current(copy, d)
    }, waitMs)
  }, [])

  // ── Update handlers (use reducer so adCopy + design are always consistent) ─
  const handleCopyField = useCallback((key: keyof AdCopy, value: string) => {
    dispatch({ type: "SET_COPY_FIELD", key, value })
    // Read latest from the reducer via a functional update trick is unnecessary here —
    // we pass the new value explicitly, so the request is always consistent.
    scheduleRerender({ ...adCopy, [key]: value }, design)
  }, [adCopy, design, scheduleRerender])

  const handleAccent = useCallback((color: string) => {
    if (normalizeHex(color) === normalizeHex(design.accent_color)) return  // skip no-op
    dispatch({ type: "SET_ACCENT", color })
    scheduleRerender(adCopy, { ...design, accent_color: color })
  }, [adCopy, design, scheduleRerender])

  const handleFontStyle = useCallback((fs: string) => {
    dispatch({ type: "SET_FONT_STYLE", fs })
    scheduleRerender(adCopy, { ...design, font_style: fs })
  }, [adCopy, design, scheduleRerender])

  const handleToggleFeatures = useCallback(() => {
    const next = { ...design, has_feature_grid: !design.has_feature_grid }
    dispatch({ type: "TOGGLE_FEATURES" })
    scheduleRerender(adCopy, next)
  }, [adCopy, design, scheduleRerender])

  const handleToggleCta = useCallback(() => {
    const next = { ...design, has_cta_button: !design.has_cta_button }
    dispatch({ type: "TOGGLE_CTA" })
    scheduleRerender(adCopy, next)
  }, [adCopy, design, scheduleRerender])

  const handleToggleBg = useCallback(() => {
    const newBg = design.bg_color === "#F8FAFC" ? "#0F172A" : "#F8FAFC"
    const next  = { ...design, bg_color: newBg }
    dispatch({ type: "TOGGLE_BG" })
    scheduleRerender(adCopy, next)
  }, [adCopy, design, scheduleRerender])

  const handleReset = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    dispatch({ type: "RESET", adCopy: initialAdCopy ?? {}, design: initialDesign ?? {} })
    triggerRecomposeRef.current(initialAdCopy ?? {}, initialDesign ?? {})
  }, [initialAdCopy, initialDesign])

  const handleManualRerender = useCallback(() => {
    // Cancel pending debounce before firing immediately
    if (debounceRef.current) clearTimeout(debounceRef.current)
    triggerRecompose(adCopy, design)
  }, [adCopy, design, triggerRecompose])

  // ── Accent swatches: prepend AI color if not in BASE_SWATCHES ────────────
  const accentSwatches = useMemo(() => {
    const aiColor = normalizeHex(initialDesign?.accent_color ?? "")
    const hasAi   = BASE_SWATCHES.some(s => normalizeHex(s) === aiColor)
    return hasAi || !aiColor
      ? BASE_SWATCHES
      : [initialDesign!.accent_color!, ...BASE_SWATCHES.slice(0, 7)]
  }, [initialDesign?.accent_color])

  const isDarkBg = (design.bg_color ?? "#0F172A") !== "#F8FAFC"

  // Don't render if no initial data
  if (!initialAdCopy?.headline && !initialAdCopy?.brand_name) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-white/[0.08] bg-white/[0.025] overflow-hidden mt-3"
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-white/[0.03] transition-colors"
      >
        <Type className="h-3.5 w-3.5 text-primary shrink-0" />
        <span className="text-xs font-semibold text-foreground/80 flex-1 text-left">Edit Poster</span>
        {isRendering && <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />}
        {expanded
          ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="body"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="border-t border-white/[0.06]"
          >
            <div className="px-4 pb-4 pt-3 space-y-4">

              {/* Text fields */}
              <div className="space-y-2.5">
                <InlineField
                  label="Headline"
                  value={adCopy.headline ?? ""}
                  onChange={v => handleCopyField("headline", v)}
                  placeholder="HEADLINE TEXT"
                  maxLength={80}
                />
                <InlineField
                  label="Subheadline"
                  value={adCopy.subheadline ?? ""}
                  onChange={v => handleCopyField("subheadline", v)}
                  placeholder="Supporting text..."
                  maxLength={120}
                />
                <InlineField
                  label="CTA"
                  value={adCopy.cta ?? ""}
                  onChange={v => handleCopyField("cta", v)}
                  placeholder="GET STARTED"
                  maxLength={30}
                />
                <InlineField
                  label="Brand"
                  value={adCopy.brand_name ?? ""}
                  onChange={v => handleCopyField("brand_name", v)}
                  placeholder="Brand name"
                  maxLength={40}
                />
              </div>

              {/* Accent color */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Palette className="h-3 w-3 text-muted-foreground" />
                  <span className="text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-wide">
                    Accent Color
                  </span>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {accentSwatches.map((color) => {
                    const isActive = normalizeHex(design.accent_color) === normalizeHex(color)
                    return (
                      <button
                        key={color}
                        type="button"
                        onClick={() => handleAccent(color)}
                        aria-label={`Set accent color to ${color}`}
                        className={cn(
                          "w-7 h-7 rounded-lg border-2 transition-all",
                          isActive ? "border-white scale-110" : "border-white/20 hover:border-white/50"
                        )}
                        style={{ backgroundColor: color }}
                      >
                        {isActive && <Check className="h-3.5 w-3.5 text-white mx-auto" />}
                      </button>
                    )
                  })}
                  {/* Custom color picker — only schedules on actual color change */}
                  <label
                    className="w-7 h-7 rounded-lg border-2 border-dashed border-white/20 hover:border-white/50 flex items-center justify-center cursor-pointer overflow-hidden relative"
                    title="Custom color"
                    aria-label="Pick custom accent color"
                  >
                    <input
                      type="color"
                      value={design.accent_color ?? "#F59E0B"}
                      onChange={e => handleAccent(e.target.value)}
                      className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                    />
                    <Palette className="h-3 w-3 text-muted-foreground pointer-events-none" />
                  </label>
                </div>
              </div>

              {/* Font style */}
              <div>
                <span className="text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-wide block mb-2">
                  Font Style
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {FONT_STYLES.map(f => (
                    <button
                      key={f.value}
                      type="button"
                      onClick={() => handleFontStyle(f.value)}
                      className={cn(
                        "px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-all",
                        design.font_style === f.value
                          ? "border-primary/60 bg-primary/15 text-primary"
                          : "border-white/[0.08] bg-white/[0.03] text-muted-foreground hover:border-white/20"
                      )}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Layout toggles */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-wide">
                  Layout
                </span>
                <ToggleChip
                  icon={<Grid className="h-3 w-3" />}
                  label="Features"
                  active={design.has_feature_grid ?? true}
                  onToggle={handleToggleFeatures}
                />
                <ToggleChip
                  icon={<MousePointerClick className="h-3 w-3" />}
                  label="CTA"
                  active={design.has_cta_button ?? true}
                  onToggle={handleToggleCta}
                />
                <ToggleChip
                  icon={isDarkBg ? <Moon className="h-3 w-3" /> : <Sun className="h-3 w-3" />}
                  label={isDarkBg ? "Dark BG" : "Light BG"}
                  active={true}
                  onToggle={handleToggleBg}
                />
              </div>

              {/* Actions row */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleManualRerender}
                  disabled={isRendering}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium transition-all",
                    "border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20",
                    isRendering && "opacity-60 cursor-not-allowed"
                  )}
                >
                  {isRendering
                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Re-rendering…</>
                    : <><RefreshCw className="h-4 w-4" /> Re-render</>}
                </button>
                <button
                  type="button"
                  onClick={handleReset}
                  disabled={isRendering}
                  title="Reset to original AI values"
                  className="p-2.5 rounded-xl border border-white/[0.08] text-muted-foreground hover:text-white hover:border-white/20 transition-colors disabled:opacity-40"
                  aria-label="Reset to original poster"
                >
                  <RotateCcw className="h-4 w-4" />
                </button>
              </div>

              {lastError && (
                <p className="text-[11px] text-red-400 text-center">{lastError}</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ── InlineField ───────────────────────────────────────────────────────────────

const InlineField = React.memo(function InlineField({
  label,
  value,
  onChange,
  placeholder,
  maxLength,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  maxLength?: number
}) {
  const nearLimit = maxLength && value.length > maxLength * 0.8
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-muted-foreground/60 w-20 shrink-0">{label}</span>
      <div className="flex-1 relative">
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          maxLength={maxLength}
          aria-label={label}
          className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/40 transition-colors"
        />
        {maxLength && value.length > 0 && (
          <span
            className={cn(
              "absolute right-2 top-1/2 -translate-y-1/2 text-[9px] pointer-events-none",
              nearLimit ? "text-amber-400" : "text-muted-foreground/25"
            )}
          >
            {value.length}/{maxLength}
          </span>
        )}
      </div>
    </div>
  )
})

// ── ToggleChip ────────────────────────────────────────────────────────────────

const ToggleChip = React.memo(function ToggleChip({
  icon, label, active, onToggle,
}: {
  icon: React.ReactNode
  label: string
  active: boolean
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={active}
      className={cn(
        "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-all",
        active
          ? "border-primary/40 bg-primary/10 text-primary"
          : "border-white/[0.08] bg-white/[0.03] text-muted-foreground/50 line-through hover:border-white/20"
      )}
    >
      {icon}{label}
    </button>
  )
})

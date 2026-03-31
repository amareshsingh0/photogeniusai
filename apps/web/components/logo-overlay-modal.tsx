"use client"

/**
 * LogoOverlayModal
 *
 * Add a brand logo to an image:
 *  - Upload PNG/WebP logo
 *  - Choose position: 3×3 grid (9 spots) OR "AI Smart" (Gemini picks best ad position)
 *  - Size (% of image width) + Opacity sliders
 *  - Preview the result, then confirm → returns composited image
 */

import React, { useRef, useState, useCallback } from "react"
import { motion } from "framer-motion"
import {
  X, Upload, Sparkles, Loader2, Check, Image as ImageIcon,
  AlignStartVertical, AlignCenterVertical, AlignEndVertical,
  ArrowUpLeft, ArrowUp, ArrowUpRight,
  ArrowLeft, Crosshair, ArrowRight,
  ArrowDownLeft, ArrowDown, ArrowDownRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type Position =
  | "top_left"    | "top_center"    | "top_right"
  | "center_left" | "center"        | "center_right"
  | "bottom_left" | "bottom_center" | "bottom_right"
  | "auto"

interface Props {
  imageUrl:  string
  onClose:   () => void
  onResult:  (newImageUrl: string) => void
}

const POSITION_GRID: { id: Position; label: string; icon: React.ReactNode }[][] = [
  [
    { id: "top_left",    label: "Top Left",    icon: <ArrowUpLeft    className="h-3.5 w-3.5" /> },
    { id: "top_center",  label: "Top Center",  icon: <ArrowUp        className="h-3.5 w-3.5" /> },
    { id: "top_right",   label: "Top Right",   icon: <ArrowUpRight   className="h-3.5 w-3.5" /> },
  ],
  [
    { id: "center_left", label: "Mid Left",    icon: <ArrowLeft      className="h-3.5 w-3.5" /> },
    { id: "center",      label: "Center",      icon: <Crosshair      className="h-3.5 w-3.5" /> },
    { id: "center_right",label: "Mid Right",   icon: <ArrowRight     className="h-3.5 w-3.5" /> },
  ],
  [
    { id: "bottom_left", label: "Bot Left",    icon: <ArrowDownLeft  className="h-3.5 w-3.5" /> },
    { id: "bottom_center",label:"Bot Center",  icon: <ArrowDown      className="h-3.5 w-3.5" /> },
    { id: "bottom_right",label: "Bot Right",   icon: <ArrowDownRight className="h-3.5 w-3.5" /> },
  ],
]

export default function LogoOverlayModal({ imageUrl, onClose, onResult }: Props) {
  const [logoData, setLogoData]         = useState<string | null>(null)
  const [logoName, setLogoName]         = useState<string>("")
  const [position, setPosition]         = useState<Position>("auto")
  const [sizePct, setSizePct]           = useState(20)
  const [opacity, setOpacity]           = useState(90)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [positionUsed, setPositionUsed] = useState<string | null>(null)
  const [error, setError]               = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleLogoUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith("image/")) {
      setError("Please upload an image file (PNG, WebP, SVG)")
      return
    }
    setLogoName(file.name)
    const reader = new FileReader()
    reader.onload = (ev) => {
      setLogoData(ev.target?.result as string)
      setError(null)
    }
    reader.readAsDataURL(file)
    e.target.value = ""
  }, [])

  const handleApply = async () => {
    if (!logoData) {
      setError("Upload a logo first")
      return
    }
    setError(null)
    setIsSubmitting(true)

    try {
      const res = await fetch("/api/logo-overlay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_url:   imageUrl,
          logo_data:   logoData,
          position,
          size_pct:    sizePct,
          opacity,
          padding_pct: 3,
        }),
      })
      const data = await res.json()
      if (!res.ok || !data.success) throw new Error(data.error || `Failed (${res.status})`)

      setPositionUsed(data.position_used ?? position)
      onResult(data.image_b64)
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Logo overlay failed")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.18 }}
        className="relative w-full max-w-2xl bg-[#0d0d0d] border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        style={{ maxHeight: "92vh" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <ImageIcon className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold text-white">Add Brand Logo</span>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-white p-1 rounded-lg hover:bg-white/[0.06] transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* Image preview (left) */}
          <div className="flex-1 bg-black/40 flex items-center justify-center p-4 overflow-hidden">
            <img
              src={imageUrl}
              alt="Base image"
              className="rounded-xl max-h-[60vh] max-w-full object-contain"
            />
          </div>

          {/* Controls (right) */}
          <div className="w-72 shrink-0 flex flex-col gap-5 border-l border-white/[0.06] p-5 overflow-y-auto">

            {/* Logo upload */}
            <div>
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-2">Your Logo</p>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/webp,image/svg+xml"
                onChange={handleLogoUpload}
                className="hidden"
              />
              {logoData ? (
                <div className="flex items-center gap-3">
                  <img
                    src={logoData}
                    alt="Logo preview"
                    className="h-14 w-14 object-contain rounded-lg border border-white/[0.08] bg-white/[0.04] p-1"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-white truncate">{logoName}</p>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="text-[11px] text-primary hover:underline mt-0.5"
                    >
                      Change
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full flex flex-col items-center gap-2 py-5 rounded-xl border-2 border-dashed border-white/[0.1] hover:border-primary/40 hover:bg-primary/5 transition-all text-muted-foreground hover:text-white"
                >
                  <Upload className="h-5 w-5" />
                  <span className="text-xs">Upload PNG / WebP logo</span>
                  <span className="text-[10px] opacity-60">Transparent background recommended</span>
                </button>
              )}
            </div>

            {/* Position */}
            <div>
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-2">Position</p>

              {/* AI Smart button */}
              <button
                onClick={() => setPosition("auto")}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2.5 rounded-xl border text-xs font-medium mb-2 transition-all",
                  position === "auto"
                    ? "border-primary/60 bg-primary/15 text-primary"
                    : "border-white/[0.08] bg-white/[0.03] text-muted-foreground hover:text-white hover:border-white/15"
                )}
              >
                <Sparkles className="h-3.5 w-3.5" />
                AI Smart Position
                <span className="ml-auto text-[10px] opacity-60">Gemini picks best spot</span>
              </button>

              {/* 3×3 grid */}
              <div className="grid grid-rows-3 gap-1">
                {POSITION_GRID.map((row, ri) => (
                  <div key={ri} className="grid grid-cols-3 gap-1">
                    {row.map(cell => (
                      <button
                        key={cell.id}
                        onClick={() => setPosition(cell.id)}
                        title={cell.label}
                        className={cn(
                          "flex items-center justify-center py-2 rounded-lg border text-xs transition-all",
                          position === cell.id
                            ? "border-primary/60 bg-primary/15 text-primary"
                            : "border-white/[0.06] bg-white/[0.02] text-muted-foreground hover:text-white hover:border-white/15"
                        )}
                      >
                        {cell.icon}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            {/* Size */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest">Logo Size</p>
                <span className="text-xs text-white">{sizePct}%</span>
              </div>
              <input
                type="range"
                min={5}
                max={40}
                step={1}
                value={sizePct}
                onChange={e => setSizePct(Number(e.target.value))}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground/40 mt-1">
                <span>Subtle</span>
                <span>Bold</span>
              </div>
            </div>

            {/* Opacity */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest">Opacity</p>
                <span className="text-xs text-white">{opacity}%</span>
              </div>
              <input
                type="range"
                min={20}
                max={100}
                step={5}
                value={opacity}
                onChange={e => setOpacity(Number(e.target.value))}
                className="w-full accent-primary"
              />
            </div>

            {error && <p className="text-[11px] text-red-400">{error}</p>}

            <Button
              onClick={handleApply}
              disabled={isSubmitting || !logoData}
              className="w-full btn-premium text-white rounded-xl mt-auto"
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {position === "auto" ? "AI placing logo..." : "Applying logo..."}
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Check className="h-3.5 w-3.5" />
                  Apply Logo
                </span>
              )}
            </Button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

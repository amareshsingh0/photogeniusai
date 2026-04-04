"use client"

/**
 * LogoOverlayModal — 100% client-side Canvas compositing
 *
 * No API call. No regeneration. Pure browser Canvas 2D.
 * - Upload logo PNG/WebP
 * - Live preview with real-time position/size/opacity sliders
 * - 9-position grid OR drag logo on canvas
 * - Apply → returns composited data URL instantly
 */

import React, { useRef, useState, useCallback, useEffect } from "react"
import { motion } from "framer-motion"
import {
  X, Upload, Check, Image as ImageIcon,
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

interface Props {
  imageUrl:  string
  onClose:   () => void
  onResult:  (newImageUrl: string) => void
}

const POSITION_GRID: { id: Position; icon: React.ReactNode }[][] = [
  [
    { id: "top_left",     icon: <ArrowUpLeft    className="h-3.5 w-3.5" /> },
    { id: "top_center",   icon: <ArrowUp        className="h-3.5 w-3.5" /> },
    { id: "top_right",    icon: <ArrowUpRight   className="h-3.5 w-3.5" /> },
  ],
  [
    { id: "center_left",  icon: <ArrowLeft      className="h-3.5 w-3.5" /> },
    { id: "center",       icon: <Crosshair      className="h-3.5 w-3.5" /> },
    { id: "center_right", icon: <ArrowRight     className="h-3.5 w-3.5" /> },
  ],
  [
    { id: "bottom_left",  icon: <ArrowDownLeft  className="h-3.5 w-3.5" /> },
    { id: "bottom_center",icon: <ArrowDown      className="h-3.5 w-3.5" /> },
    { id: "bottom_right", icon: <ArrowDownRight className="h-3.5 w-3.5" /> },
  ],
]

const PAD = 0.03 // 3% padding from edges

function calcLogoXY(
  pos: Position,
  canvasW: number, canvasH: number,
  logoW: number, logoH: number,
): { x: number; y: number } {
  const padX = canvasW * PAD
  const padY = canvasH * PAD
  const col = pos.includes("left") ? "left" : pos.includes("right") ? "right" : "center"
  const row = pos.startsWith("top") ? "top" : pos.startsWith("bottom") ? "bottom" : "center"

  const x =
    col === "left"   ? padX :
    col === "right"  ? canvasW - logoW - padX :
                       (canvasW - logoW) / 2

  const y =
    row === "top"    ? padY :
    row === "bottom" ? canvasH - logoH - padY :
                       (canvasH - logoH) / 2

  return { x, y }
}

export default function LogoOverlayModal({ imageUrl, onClose, onResult }: Props) {
  const [logoSrc, setLogoSrc]       = useState<string | null>(null)
  const [logoName, setLogoName]     = useState("")
  const [position, setPosition]     = useState<Position>("bottom_right")
  const [sizePct, setSizePct]       = useState(20)
  const [opacity, setOpacity]       = useState(90)
  const [error, setError]           = useState<string | null>(null)
  // drag state (fractional 0-1 offsets from top-left of canvas)
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number } | null>(null)
  const isDragging = useRef(false)
  const dragStart  = useRef<{ mx: number; my: number; lx: number; ly: number } | null>(null)

  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const baseImgRef = useRef<HTMLImageElement | null>(null)
  const logoImgRef = useRef<HTMLImageElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Load base image once ───────────────────────────────────────────────────
  useEffect(() => {
    const img = new Image()
    img.crossOrigin = "anonymous"
    img.onload = () => {
      baseImgRef.current = img
      redraw()
    }
    img.onerror = () => {
      // Retry without crossOrigin (some CDN URLs block it)
      const img2 = new Image()
      img2.onload = () => { baseImgRef.current = img2; redraw() }
      img2.src = imageUrl
    }
    img.src = imageUrl
  }, [imageUrl]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Load logo when uploaded ────────────────────────────────────────────────
  useEffect(() => {
    if (!logoSrc) { logoImgRef.current = null; redraw(); return }
    const img = new Image()
    img.onload = () => { logoImgRef.current = img; setDragOffset(null); redraw() }
    img.src = logoSrc
  }, [logoSrc]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Redraw whenever any param changes ─────────────────────────────────────
  useEffect(() => { redraw() }, [position, sizePct, opacity, dragOffset]) // eslint-disable-line react-hooks/exhaustive-deps

  const redraw = useCallback(() => {
    const canvas = canvasRef.current
    const base   = baseImgRef.current
    if (!canvas || !base) return

    // Size canvas to base image (capped for display)
    const MAX_DIM = 900
    const scale   = Math.min(1, MAX_DIM / Math.max(base.naturalWidth, base.naturalHeight))
    canvas.width  = Math.round(base.naturalWidth  * scale)
    canvas.height = Math.round(base.naturalHeight * scale)

    const ctx = canvas.getContext("2d")!
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(base, 0, 0, canvas.width, canvas.height)

    const logo = logoImgRef.current
    if (!logo) return

    // Logo width = sizePct% of canvas width
    const logoW = Math.round(canvas.width * sizePct / 100)
    const logoH = Math.round(logo.naturalHeight * (logoW / logo.naturalWidth))

    let lx: number, ly: number
    if (dragOffset) {
      lx = Math.round(dragOffset.x * canvas.width  - logoW / 2)
      ly = Math.round(dragOffset.y * canvas.height - logoH / 2)
    } else {
      const pos = calcLogoXY(position, canvas.width, canvas.height, logoW, logoH)
      lx = pos.x; ly = pos.y
    }

    // Clamp inside canvas
    lx = Math.max(0, Math.min(canvas.width  - logoW, lx))
    ly = Math.max(0, Math.min(canvas.height - logoH, ly))

    ctx.globalAlpha = opacity / 100
    ctx.drawImage(logo, lx, ly, logoW, logoH)
    ctx.globalAlpha = 1
  }, [position, sizePct, opacity, dragOffset])

  // ── Logo file upload ───────────────────────────────────────────────────────
  const handleLogoUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith("image/")) { setError("Please upload an image (PNG, WebP, SVG)"); return }
    setLogoName(file.name)
    const reader = new FileReader()
    reader.onload = ev => { setLogoSrc(ev.target?.result as string); setError(null) }
    reader.readAsDataURL(file)
    e.target.value = ""
  }, [])

  // ── Canvas drag handlers ───────────────────────────────────────────────────
  const getCanvasXY = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current!
    const rect   = canvas.getBoundingClientRect()
    const scaleX = canvas.width  / rect.width
    const scaleY = canvas.height / rect.height
    const clientX = "touches" in e ? e.touches[0].clientX : e.clientX
    const clientY = "touches" in e ? e.touches[0].clientY : e.clientY
    return {
      cx: (clientX - rect.left) * scaleX,
      cy: (clientY - rect.top)  * scaleY,
    }
  }

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (!logoImgRef.current) return
    const { cx, cy } = getCanvasXY(e)
    const canvas = canvasRef.current!
    const logoW  = Math.round(canvas.width * sizePct / 100)
    const logoH  = Math.round(logoImgRef.current.naturalHeight * (logoW / logoImgRef.current.naturalWidth))

    // Figure out current logo position
    let lx: number, ly: number
    if (dragOffset) {
      lx = dragOffset.x * canvas.width  - logoW / 2
      ly = dragOffset.y * canvas.height - logoH / 2
    } else {
      const pos = calcLogoXY(position, canvas.width, canvas.height, logoW, logoH)
      lx = pos.x; ly = pos.y
    }

    // Hit test
    if (cx >= lx && cx <= lx + logoW && cy >= ly && cy <= ly + logoH) {
      isDragging.current = true
      dragStart.current  = { mx: cx, my: cy, lx, ly }
      e.preventDefault()
    }
  }, [dragOffset, position, sizePct])

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging.current || !dragStart.current || !canvasRef.current) return
    const { cx, cy } = getCanvasXY(e)
    const canvas = canvasRef.current
    const logoW  = Math.round(canvas.width * sizePct / 100)
    const logoH  = logoImgRef.current
      ? Math.round(logoImgRef.current.naturalHeight * (logoW / logoImgRef.current.naturalWidth))
      : 0
    const dx = cx - dragStart.current.mx
    const dy = cy - dragStart.current.my
    const newLx = dragStart.current.lx + dx
    const newLy = dragStart.current.ly + dy
    setDragOffset({
      x: (newLx + logoW / 2) / canvas.width,
      y: (newLy + logoH / 2) / canvas.height,
    })
  }, [sizePct])

  const onMouseUp = useCallback(() => { isDragging.current = false }, [])

  // ── Apply — composite at FULL resolution and return ───────────────────────
  const handleApply = useCallback(() => {
    const base = baseImgRef.current
    const logo = logoImgRef.current
    if (!base || !logo) { setError("Upload a logo first"); return }

    const out   = document.createElement("canvas")
    out.width   = base.naturalWidth
    out.height  = base.naturalHeight
    const ctx   = out.getContext("2d")!
    ctx.drawImage(base, 0, 0)

    const logoW = Math.round(out.width * sizePct / 100)
    const logoH = Math.round(logo.naturalHeight * (logoW / logo.naturalWidth))

    let lx: number, ly: number
    if (dragOffset && canvasRef.current) {
      // Map fractional offset back to full-res coordinates
      const scaleX = out.width  / canvasRef.current.width
      const scaleY = out.height / canvasRef.current.height
      lx = dragOffset.x * canvasRef.current.width  * scaleX - logoW / 2
      ly = dragOffset.y * canvasRef.current.height * scaleY - logoH / 2
    } else {
      const pos = calcLogoXY(position, out.width, out.height, logoW, logoH)
      lx = pos.x; ly = pos.y
    }

    lx = Math.max(0, Math.min(out.width  - logoW, lx))
    ly = Math.max(0, Math.min(out.height - logoH, ly))

    ctx.globalAlpha = opacity / 100
    ctx.drawImage(logo, lx, ly, logoW, logoH)
    ctx.globalAlpha = 1

    onResult(out.toDataURL("image/png"))
    onClose()
  }, [dragOffset, position, sizePct, opacity, onResult, onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.18 }}
        className="relative w-full max-w-3xl bg-[#0d0d0d] border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        style={{ maxHeight: "94vh" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <ImageIcon className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold text-white">Add Brand Logo</span>
            <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full font-medium">Instant · No API</span>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-white p-1 rounded-lg hover:bg-white/[0.06] transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* Canvas preview */}
          <div className="flex-1 bg-black/40 flex items-center justify-center p-4 overflow-hidden">
            <canvas
              ref={canvasRef}
              className="rounded-xl max-h-[65vh] max-w-full object-contain cursor-move select-none"
              style={{ imageRendering: "crisp-edges" }}
              onMouseDown={onMouseDown}
              onMouseMove={onMouseMove}
              onMouseUp={onMouseUp}
              onMouseLeave={onMouseUp}
            />
          </div>

          {/* Controls */}
          <div className="w-68 shrink-0 flex flex-col gap-5 border-l border-white/[0.06] p-5 overflow-y-auto" style={{ width: 272 }}>

            {/* Logo upload */}
            <div>
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-2">Your Logo</p>
              <input ref={fileInputRef} type="file" accept="image/png,image/webp,image/svg+xml" onChange={handleLogoUpload} className="hidden" />
              {logoSrc ? (
                <div className="flex items-center gap-3">
                  <img src={logoSrc} alt="Logo" className="h-14 w-14 object-contain rounded-lg border border-white/[0.08] bg-white/[0.04] p-1" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-white truncate">{logoName}</p>
                    <button onClick={() => fileInputRef.current?.click()} className="text-[11px] text-primary hover:underline mt-0.5">Change</button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full flex flex-col items-center gap-2 py-5 rounded-xl border-2 border-dashed border-white/[0.1] hover:border-primary/40 hover:bg-primary/5 transition-all text-muted-foreground hover:text-white"
                >
                  <Upload className="h-5 w-5" />
                  <span className="text-xs">Upload PNG / WebP / SVG</span>
                  <span className="text-[10px] opacity-60">Transparent background recommended</span>
                </button>
              )}
            </div>

            {/* Position grid */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest">Position</p>
                {dragOffset && (
                  <button
                    onClick={() => setDragOffset(null)}
                    className="text-[10px] text-primary hover:underline"
                  >
                    Reset drag
                  </button>
                )}
              </div>
              <p className="text-[10px] text-muted-foreground/40 mb-2">Or drag logo on the preview</p>
              <div className="grid grid-rows-3 gap-1">
                {POSITION_GRID.map((row, ri) => (
                  <div key={ri} className="grid grid-cols-3 gap-1">
                    {row.map(cell => (
                      <button
                        key={cell.id}
                        onClick={() => { setPosition(cell.id); setDragOffset(null) }}
                        className={cn(
                          "flex items-center justify-center py-2 rounded-lg border text-xs transition-all",
                          position === cell.id && !dragOffset
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
              <input type="range" min={5} max={50} step={1} value={sizePct} onChange={e => setSizePct(Number(e.target.value))} className="w-full accent-primary" />
              <div className="flex justify-between text-[10px] text-muted-foreground/40 mt-1">
                <span>Subtle</span><span>Bold</span>
              </div>
            </div>

            {/* Opacity */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest">Opacity</p>
                <span className="text-xs text-white">{opacity}%</span>
              </div>
              <input type="range" min={10} max={100} step={5} value={opacity} onChange={e => setOpacity(Number(e.target.value))} className="w-full accent-primary" />
            </div>

            {error && <p className="text-[11px] text-red-400">{error}</p>}

            <Button
              onClick={handleApply}
              disabled={!logoSrc}
              className="w-full btn-premium text-white rounded-xl mt-auto"
            >
              <Check className="h-3.5 w-3.5 mr-2" />
              Apply Logo
            </Button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

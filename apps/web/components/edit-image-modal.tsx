"use client"

/**
 * EditImageModal
 *
 * Two-tab advanced image editor:
 *  Tab 1 — Targeted Edit: draw a mask with Brush / Circle / Rectangle / Eraser
 *           then type an instruction → Flux Fill inpainting
 *  Tab 2 — Global Edit:   plain text instruction → Flux Kontext editing
 */

import React, {
  useRef, useState, useEffect, useCallback, MouseEvent, TouchEvent,
} from "react"
import { motion, AnimatePresence } from "framer-motion"
import { X, Brush, Circle, Square, Eraser, Trash2, Loader2, Wand2, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type Tool = "brush" | "circle" | "rect" | "eraser"

interface Props {
  imageUrl: string
  onClose: () => void
  onResult: (newImageUrl: string) => void
}

const BRUSH_SIZES = [8, 16, 28, 44]

export default function EditImageModal({ imageUrl, onClose, onResult }: Props) {
  const [tab, setTab] = useState<"targeted" | "global">("targeted")
  const [tool, setTool] = useState<Tool>("brush")
  const [brushSize, setBrushSize] = useState(16)
  const [instruction, setInstruction] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasMask, setHasMask] = useState(false)

  const containerRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const maskCanvasRef = useRef<HTMLCanvasElement>(null)
  const displayCanvasRef = useRef<HTMLCanvasElement>(null)

  // Drawing state
  const isDrawing = useRef(false)
  const circleStart = useRef<{ x: number; y: number } | null>(null)
  const rectStart = useRef<{ x: number; y: number } | null>(null)
  const snapshotRef = useRef<ImageData | null>(null)  // for live circle/rect preview

  // ── Setup canvas size when image loads ──────────────────────────────────
  const setupCanvases = useCallback(() => {
    const img = imgRef.current
    const mask = maskCanvasRef.current
    const display = displayCanvasRef.current
    if (!img || !mask || !display) return
    const w = img.clientWidth
    const h = img.clientHeight
    if (w === 0 || h === 0) return
    mask.width    = w;  mask.height    = h
    display.width = w;  display.height = h
    // Clear
    const mCtx = mask.getContext("2d")!
    mCtx.fillStyle = "black"
    mCtx.fillRect(0, 0, w, h)
    redrawDisplay()
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const img = imgRef.current
    if (!img) return
    if (img.complete) { setupCanvases(); return }
    img.onload = setupCanvases
  }, [imageUrl, setupCanvases])

  // Re-setup on window resize
  useEffect(() => {
    window.addEventListener("resize", setupCanvases)
    return () => window.removeEventListener("resize", setupCanvases)
  }, [setupCanvases])

  // ── Draw red overlay on display canvas from mask ─────────────────────────
  const redrawDisplay = useCallback(() => {
    const mask    = maskCanvasRef.current
    const display = displayCanvasRef.current
    if (!mask || !display) return
    const dCtx = display.getContext("2d")!
    const w = display.width; const h = display.height
    dCtx.clearRect(0, 0, w, h)
    // Painted (white) areas → red semi-transparent
    const mData = mask.getContext("2d")!.getImageData(0, 0, w, h)
    const dData = dCtx.createImageData(w, h)
    for (let i = 0; i < mData.data.length; i += 4) {
      if (mData.data[i] > 128) {          // white pixel in mask
        dData.data[i]     = 255            // R
        dData.data[i + 1] = 50             // G
        dData.data[i + 2] = 50             // B
        dData.data[i + 3] = 140            // A (semi-transparent)
      }
    }
    dCtx.putImageData(dData, 0, 0)
  }, [])

  // ── Pointer coordinates relative to canvas ───────────────────────────────
  const getPos = (e: MouseEvent | TouchEvent): { x: number; y: number } => {
    const canvas = maskCanvasRef.current!
    const rect = canvas.getBoundingClientRect()
    const src = "touches" in e ? e.touches[0] : e
    return {
      x: (src.clientX - rect.left) * (canvas.width / rect.width),
      y: (src.clientY - rect.top)  * (canvas.height / rect.height),
    }
  }

  // ── Paint white circle at pos (brush/eraser) ─────────────────────────────
  const paintAt = (ctx: CanvasRenderingContext2D, x: number, y: number, size: number, erase: boolean) => {
    ctx.beginPath()
    ctx.arc(x, y, size / 2, 0, Math.PI * 2)
    ctx.fillStyle = erase ? "black" : "white"
    ctx.fill()
  }

  // ── Mouse/touch handlers ──────────────────────────────────────────────────
  const onPointerDown = (e: MouseEvent | TouchEvent) => {
    e.preventDefault()
    isDrawing.current = true
    const pos = getPos(e)
    const mCtx = maskCanvasRef.current!.getContext("2d")!

    if (tool === "brush" || tool === "eraser") {
      paintAt(mCtx, pos.x, pos.y, brushSize, tool === "eraser")
      setHasMask(true)
      redrawDisplay()
    } else if (tool === "circle" || tool === "rect") {
      circleStart.current = pos
      rectStart.current   = pos
      // Snapshot current mask for live preview
      const w = maskCanvasRef.current!.width
      const h = maskCanvasRef.current!.height
      snapshotRef.current = mCtx.getImageData(0, 0, w, h)
    }
  }

  const onPointerMove = (e: MouseEvent | TouchEvent) => {
    if (!isDrawing.current) return
    e.preventDefault()
    const pos = getPos(e)
    const mCtx = maskCanvasRef.current!.getContext("2d")!

    if (tool === "brush" || tool === "eraser") {
      paintAt(mCtx, pos.x, pos.y, brushSize, tool === "eraser")
      setHasMask(true)
      redrawDisplay()
    } else if (tool === "circle" && circleStart.current) {
      // Live preview: restore snapshot then draw circle
      mCtx.putImageData(snapshotRef.current!, 0, 0)
      const cx = (circleStart.current.x + pos.x) / 2
      const cy = (circleStart.current.y + pos.y) / 2
      const rx = Math.abs(pos.x - circleStart.current.x) / 2
      const ry = Math.abs(pos.y - circleStart.current.y) / 2
      mCtx.beginPath()
      mCtx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2)
      mCtx.fillStyle = "white"
      mCtx.fill()
      redrawDisplay()
    } else if (tool === "rect" && rectStart.current) {
      mCtx.putImageData(snapshotRef.current!, 0, 0)
      const x = Math.min(rectStart.current.x, pos.x)
      const y = Math.min(rectStart.current.y, pos.y)
      const w = Math.abs(pos.x - rectStart.current.x)
      const h = Math.abs(pos.y - rectStart.current.y)
      mCtx.fillStyle = "white"
      mCtx.fillRect(x, y, w, h)
      redrawDisplay()
    }
  }

  const onPointerUp = (e: MouseEvent | TouchEvent) => {
    if (!isDrawing.current) return
    isDrawing.current = false
    if (tool === "circle" || tool === "rect") {
      setHasMask(true)
    }
    circleStart.current = null
    rectStart.current   = null
    snapshotRef.current = null
  }

  // ── Clear mask ────────────────────────────────────────────────────────────
  const clearMask = () => {
    const mask = maskCanvasRef.current!
    const mCtx = mask.getContext("2d")!
    mCtx.fillStyle = "black"
    mCtx.fillRect(0, 0, mask.width, mask.height)
    setHasMask(false)
    redrawDisplay()
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!instruction.trim() || instruction.trim().length < 3) {
      setError("Please describe what you want to change (at least 3 characters)")
      return
    }
    if (tab === "targeted" && !hasMask) {
      setError("Draw on the area you want to edit first, then describe the change")
      return
    }
    setError(null)
    setIsSubmitting(true)

    try {
      let maskData: string | undefined

      if (tab === "targeted") {
        // Export mask canvas as PNG base64
        maskData = maskCanvasRef.current!.toDataURL("image/png")
      }

      const res = await fetch("/api/generate/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_url:   imageUrl,
          instruction: instruction.trim(),
          quality:     "balanced",
          mask_data:   maskData,
        }),
      })

      const data = await res.json()
      if (!res.ok || !data.success) {
        throw new Error(data.error || `Edit failed (${res.status})`)
      }

      onResult(data.image_url)
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Edit failed. Please try again.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const TOOLS: { id: Tool; icon: React.ReactNode; label: string }[] = [
    { id: "brush",  icon: <Brush  className="h-4 w-4" />, label: "Brush" },
    { id: "circle", icon: <Circle className="h-4 w-4" />, label: "Circle" },
    { id: "rect",   icon: <Square className="h-4 w-4" />, label: "Box" },
    { id: "eraser", icon: <Eraser className="h-4 w-4" />, label: "Eraser" },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.18 }}
        className="relative w-full max-w-4xl bg-[#0d0d0d] border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        style={{ maxHeight: "95vh" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <Wand2 className="h-4.5 w-4.5 text-primary" />
            <span className="text-sm font-semibold text-white">Edit Image</span>
          </div>
          <div className="flex items-center gap-2">
            {/* Tabs */}
            <div className="flex gap-1 bg-white/[0.04] rounded-lg p-1 mr-2">
              {(["targeted", "global"] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    "px-3 py-1 rounded-md text-xs font-medium transition-all",
                    tab === t
                      ? "bg-primary text-white"
                      : "text-muted-foreground hover:text-white"
                  )}
                >
                  {t === "targeted" ? "🎯 Targeted" : "✦ Global"}
                </button>
              ))}
            </div>
            <button onClick={onClose} className="text-muted-foreground hover:text-white p-1 rounded-lg hover:bg-white/[0.06] transition-colors">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* Canvas area */}
          <div className="flex-1 overflow-auto bg-black/40 flex items-center justify-center p-4">
            <div
              ref={containerRef}
              className="relative select-none"
              style={{ touchAction: "none" }}
            >
              {/* Source image */}
              <img
                ref={imgRef}
                src={imageUrl}
                alt="Edit target"
                className="rounded-xl max-h-[65vh] max-w-full block"
                onLoad={setupCanvases}
                draggable={false}
              />
              {/* Mask overlay (invisible mask canvas for data) */}
              <canvas
                ref={maskCanvasRef}
                className="absolute inset-0 opacity-0 pointer-events-none"
                style={{ borderRadius: "inherit" }}
              />
              {/* Display canvas (red overlay) */}
              <canvas
                ref={displayCanvasRef}
                className={cn(
                  "absolute inset-0 rounded-xl",
                  tab === "targeted" ? "cursor-crosshair" : "pointer-events-none"
                )}
                onMouseDown={tab === "targeted" ? onPointerDown : undefined}
                onMouseMove={tab === "targeted" ? onPointerMove : undefined}
                onMouseUp={tab === "targeted" ? onPointerUp : undefined}
                onMouseLeave={tab === "targeted" ? onPointerUp : undefined}
                onTouchStart={tab === "targeted" ? onPointerDown : undefined}
                onTouchMove={tab === "targeted" ? onPointerMove : undefined}
                onTouchEnd={tab === "targeted" ? onPointerUp : undefined}
              />

              {/* Targeted hint overlay */}
              {tab === "targeted" && !hasMask && (
                <div className="absolute inset-0 flex items-end justify-center pb-4 pointer-events-none rounded-xl">
                  <div className="bg-black/70 text-white/80 text-xs px-3 py-1.5 rounded-full backdrop-blur-sm">
                    Draw on the part you want to edit
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right panel */}
          <div className="w-64 shrink-0 flex flex-col border-l border-white/[0.06] p-4 gap-4 overflow-y-auto">
            <AnimatePresence mode="wait">
              {tab === "targeted" ? (
                <motion.div
                  key="targeted"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  className="flex flex-col gap-4"
                >
                  {/* Tools */}
                  <div>
                    <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-2">Drawing Tool</p>
                    <div className="grid grid-cols-2 gap-1.5">
                      {TOOLS.map(t => (
                        <button
                          key={t.id}
                          onClick={() => setTool(t.id)}
                          className={cn(
                            "flex items-center gap-1.5 px-2 py-2 rounded-lg border text-xs font-medium transition-all",
                            tool === t.id
                              ? "border-primary/60 bg-primary/15 text-primary"
                              : "border-white/[0.06] bg-white/[0.02] text-muted-foreground hover:text-white hover:border-white/15"
                          )}
                        >
                          {t.icon} {t.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Brush size (only for brush/eraser) */}
                  {(tool === "brush" || tool === "eraser") && (
                    <div>
                      <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-2">Brush Size</p>
                      <div className="flex gap-1.5">
                        {BRUSH_SIZES.map(s => (
                          <button
                            key={s}
                            onClick={() => setBrushSize(s)}
                            className={cn(
                              "flex-1 aspect-square rounded-lg border flex items-center justify-center transition-all",
                              brushSize === s
                                ? "border-primary/60 bg-primary/15"
                                : "border-white/[0.06] bg-white/[0.02] hover:border-white/15"
                            )}
                          >
                            <div
                              className="rounded-full bg-white/70"
                              style={{ width: Math.max(4, s / 3), height: Math.max(4, s / 3) }}
                            />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Clear */}
                  {hasMask && (
                    <button
                      onClick={clearMask}
                      className="flex items-center gap-1.5 text-xs text-red-400/70 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="h-3 w-3" /> Clear mask
                    </button>
                  )}
                </motion.div>
              ) : (
                <motion.div
                  key="global"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                >
                  <p className="text-xs text-muted-foreground/80">
                    Describe what to change globally — no mask needed.
                  </p>
                  <div className="mt-3 space-y-1.5">
                    {[
                      "Change background to studio white",
                      "Make it sunset golden hour",
                      "Remove all text from image",
                      "Add dramatic cinematic lighting",
                    ].map(s => (
                      <button
                        key={s}
                        onClick={() => setInstruction(s)}
                        className="w-full text-left text-[11px] text-muted-foreground/60 hover:text-white px-2 py-1.5 rounded-lg hover:bg-white/[0.04] transition-colors border border-transparent hover:border-white/[0.06]"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Instruction */}
            <div className="mt-auto flex flex-col gap-2">
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest">
                {tab === "targeted" ? "What to do to selected area" : "Edit instruction"}
              </p>
              <textarea
                value={instruction}
                onChange={e => setInstruction(e.target.value)}
                placeholder={
                  tab === "targeted"
                    ? "e.g. make it red, remove this, add bokeh blur..."
                    : "e.g. change background to white, add snow..."
                }
                rows={3}
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2.5 text-sm text-white placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/40 resize-none"
              />

              {error && (
                <p className="text-[11px] text-red-400">{error}</p>
              )}

              <Button
                onClick={handleSubmit}
                disabled={isSubmitting || !instruction.trim()}
                className="w-full btn-premium text-white rounded-xl"
              >
                {isSubmitting ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    {tab === "targeted" ? "Applying targeted edit..." : "Applying edit..."}
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Wand2 className="h-3.5 w-3.5" />
                    Apply Edit
                  </span>
                )}
              </Button>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

"use client"

/**
 * EditImageModal — full-featured AI image editor.
 *
 * Operations (ChatGPT/Gemini-style):
 *   Enhance          — one-click auto-enhance
 *   Edit             — natural-language instruction edit
 *   Remix            — restyle with theme presets or custom prompt
 *   Inpaint          — mask + prompt → repaint masked region
 *   Add Object       — insert logos / objects / images into the scene
 *   Compose          — blend multiple images
 *   Add Text         — replace/add text in the image
 *   Remove Object    — remove an object cleanly
 *   Background Swap  — change background, keep subject
 *
 * The backend auto-picks the capable model per operation — model names are
 * never exposed to the user.
 */

import React, {
  useRef, useState, useEffect, useCallback, MouseEvent, TouchEvent,
} from "react"
import { motion } from "framer-motion"
import {
  X, Brush, Circle, Square, Eraser, Trash2, Loader2, Wand2,
  Sparkles, Layers, Type, Eraser as RemoveIcon, Image as BgIcon, Plus,
  Zap, PackagePlus,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type Tool = "brush" | "circle" | "rect" | "eraser"
type EditMode =
  | "instruction_edit"
  | "style_remix"
  | "inpaint_mask"
  | "compose"
  | "text_replace"
  | "object_add"
  | "object_remove"
  | "background_swap"

interface Props {
  imageUrl: string
  onClose: () => void
  onResult: (newImageUrl: string) => void
}

interface OpDef {
  id: EditMode
  label: string
  icon: React.ReactNode
  hint: string
  placeholder: string
  suggestions: string[]
}

const OPERATIONS: OpDef[] = [
  {
    id: "instruction_edit",
    label: "Edit",
    icon: <Wand2 className="h-3.5 w-3.5" />,
    hint: "Describe the change in plain language.",
    placeholder: "e.g. make the sky purple, add dramatic lighting...",
    suggestions: [
      "Make it golden hour",
      "Add dramatic cinematic lighting",
      "Turn it into night scene",
    ],
  },
  {
    id: "style_remix",
    label: "Remix",
    icon: <Sparkles className="h-3.5 w-3.5" />,
    hint: "Restyle the image with a new creative direction.",
    placeholder: "e.g. make it anime, oil painting, cyberpunk...",
    suggestions: [
      "Make it look like an anime still",
      "Render as watercolor painting",
      "Cyberpunk neon style",
    ],
  },
  {
    id: "inpaint_mask",
    label: "Inpaint",
    icon: <Brush className="h-3.5 w-3.5" />,
    hint: "Draw on the area to change, then describe the replacement.",
    placeholder: "e.g. a bouquet of roses, a silver watch...",
    suggestions: [
      "A bouquet of roses",
      "A cup of coffee",
      "Clean white wall",
    ],
  },
  {
    id: "object_add",
    label: "Add Object",
    icon: <PackagePlus className="h-3.5 w-3.5" />,
    hint: "Insert a new object, logo, or image into the scene. Upload references (optional) and describe placement.",
    placeholder: "e.g. add a coffee cup on the table, add the uploaded logo to the top-right corner...",
    suggestions: [
      "Add the uploaded logo to the top-right corner",
      "Add a small bouquet of flowers in the foreground",
      "Add a coffee cup on the table, steaming, natural shadow",
    ],
  },
  {
    id: "compose",
    label: "Compose",
    icon: <Layers className="h-3.5 w-3.5" />,
    hint: "Combine this image with one or more reference images.",
    placeholder: "e.g. put the subject into the reference scene...",
    suggestions: [
      "Place the subject into the reference scene",
      "Blend the style of the references",
      "Combine elements from all images",
    ],
  },
  {
    id: "text_replace",
    label: "Add Text",
    icon: <Type className="h-3.5 w-3.5" />,
    hint: 'Describe the text to add or replace. Tip: put exact text in "quotes".',
    placeholder: 'e.g. Replace the title with "GRAND OPENING"',
    suggestions: [
      'Replace the title with "GRAND OPENING"',
      'Add the text "SALE 50% OFF" at the top',
      'Change the brand name to "ACME"',
    ],
  },
  {
    id: "object_remove",
    label: "Remove Object",
    icon: <RemoveIcon className="h-3.5 w-3.5" />,
    hint: "Name the object to remove cleanly.",
    placeholder: "e.g. the car in the background, the watermark...",
    suggestions: [
      "The person in the background",
      "The watermark in the corner",
      "All text from the image",
    ],
  },
  {
    id: "background_swap",
    label: "Background",
    icon: <BgIcon className="h-3.5 w-3.5" />,
    hint: "Describe the new background — subject stays the same.",
    placeholder: "e.g. studio white, sunset beach, neon city street...",
    suggestions: [
      "Clean studio white",
      "Sunset beach with soft waves",
      "Neon-lit Tokyo street at night",
    ],
  },
]

const BRUSH_SIZES = [8, 16, 28, 44]
const MAX_EXTRAS = 3

// Theme preset chips — one-click styles for the Remix panel
const THEME_PRESETS: { label: string; prompt: string }[] = [
  { label: "Cinematic",       prompt: "cinematic film still, teal-orange color grade, 35mm lens, shallow depth of field, dramatic moody lighting" },
  { label: "Anime",           prompt: "anime illustration, cel-shaded, vibrant colors, expressive line art, studio-quality" },
  { label: "Watercolor",      prompt: "soft watercolor painting, paper texture, delicate brush strokes, pastel palette" },
  { label: "Oil Painting",    prompt: "classical oil painting, rich thick brush strokes, dramatic chiaroscuro lighting, museum quality" },
  { label: "Cyberpunk",       prompt: "cyberpunk neon aesthetic, synthwave palette, chrome and holograms, rainy night city" },
  { label: "Vintage 70s",     prompt: "vintage 1970s photograph, warm film grain, faded color, nostalgic mood, Kodachrome" },
  { label: "3D Pixar",        prompt: "Pixar-style 3D render, soft global illumination, expressive features, cinematic composition" },
  { label: "Minimal",         prompt: "minimalist design, vast negative space, single accent color, clean geometric composition" },
  { label: "Pencil Sketch",   prompt: "detailed graphite pencil sketch, cross-hatching, subtle shading, artistic line work" },
  { label: "Pop Art",         prompt: "pop art, bold outlines, halftone dot patterns, saturated primary colors, Lichtenstein-inspired" },
  { label: "Black & White",   prompt: "high-contrast black and white photography, dramatic shadows, film noir mood, tri-x grain" },
  { label: "Vaporwave",       prompt: "vaporwave aesthetic, pastel pink and teal, retro 80s CRT glow, dreamlike mood" },
  { label: "Studio Ghibli",   prompt: "Studio Ghibli hand-painted animation style, soft watercolor backgrounds, warm whimsical atmosphere" },
  { label: "Lego Blocks",     prompt: "render the scene built entirely out of Lego bricks, studio product-photo lighting" },
  { label: "Claymation",      prompt: "stop-motion claymation style, visible fingerprints in clay, charming handmade feel" },
  { label: "Pixel Art",       prompt: "16-bit pixel art, limited palette, crisp pixels, retro video-game aesthetic" },
]

// One-click quick actions — apply without typing
const QUICK_ACTIONS: {
  id: string; label: string; icon: React.ReactNode;
  mode: EditMode; instruction: string;
}[] = [
  {
    id: "enhance",
    label: "Auto-Enhance",
    icon: <Zap className="h-3 w-3" />,
    mode: "instruction_edit",
    instruction: "enhance overall quality: boost color vibrancy, sharpen fine details, improve lighting and contrast, fix any blur, professional photography finish",
  },
  {
    id: "hd_upscale",
    label: "HD Upscale",
    icon: <Sparkles className="h-3 w-3" />,
    mode: "instruction_edit",
    instruction: "upscale to high resolution, enhance fine textures, sharpen edges, clean noise, preserve original composition exactly",
  },
  {
    id: "remove_bg",
    label: "Clean BG",
    icon: <BgIcon className="h-3 w-3" />,
    mode: "background_swap",
    instruction: "clean seamless studio white background, subject cleanly isolated, soft contact shadow",
  },
  {
    id: "fix_faces",
    label: "Fix Faces",
    icon: <Wand2 className="h-3 w-3" />,
    mode: "instruction_edit",
    instruction: "fix any facial distortions, ensure natural skin texture, correct eye alignment and catchlights, realistic features",
  },
]

export default function EditImageModal({ imageUrl, onClose, onResult }: Props) {
  const [mode, setMode] = useState<EditMode>("instruction_edit")
  const [tool, setTool] = useState<Tool>("brush")
  const [brushSize, setBrushSize] = useState(16)
  const [instruction, setInstruction] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasMask, setHasMask] = useState(false)
  const [extras, setExtras] = useState<string[]>([])   // data: URLs

  const op = OPERATIONS.find(o => o.id === mode) ?? OPERATIONS[0]
  const showMaskTools = mode === "inpaint_mask"
  const showExtraImages = mode === "compose" || mode === "object_add"
  const showThemePresets = mode === "style_remix"

  const containerRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const maskCanvasRef = useRef<HTMLCanvasElement>(null)
  const displayCanvasRef = useRef<HTMLCanvasElement>(null)
  const extraFileRef = useRef<HTMLInputElement>(null)

  const isDrawing = useRef(false)
  const circleStart = useRef<{ x: number; y: number } | null>(null)
  const rectStart = useRef<{ x: number; y: number } | null>(null)
  const snapshotRef = useRef<ImageData | null>(null)

  // ── Canvas setup ─────────────────────────────────────────────────────────
  const redrawDisplay = useCallback(() => {
    const mask = maskCanvasRef.current
    const display = displayCanvasRef.current
    if (!mask || !display) return
    const dCtx = display.getContext("2d")!
    const w = display.width; const h = display.height
    dCtx.clearRect(0, 0, w, h)
    const mData = mask.getContext("2d")!.getImageData(0, 0, w, h)
    const dData = dCtx.createImageData(w, h)
    for (let i = 0; i < mData.data.length; i += 4) {
      if (mData.data[i] > 128) {
        dData.data[i]     = 255
        dData.data[i + 1] = 50
        dData.data[i + 2] = 50
        dData.data[i + 3] = 140
      }
    }
    dCtx.putImageData(dData, 0, 0)
  }, [])

  const setupCanvases = useCallback(() => {
    try {
      const img = imgRef.current
      const mask = maskCanvasRef.current
      const display = displayCanvasRef.current
      if (!img || !mask || !display) return
      const w = img.clientWidth
      const h = img.clientHeight
      if (w === 0 || h === 0) return
      mask.width = w;  mask.height = h
      display.width = w;  display.height = h
      const mCtx = mask.getContext("2d")
      if (!mCtx) return
      mCtx.fillStyle = "black"
      mCtx.fillRect(0, 0, w, h)
      setHasMask(false)
      redrawDisplay()
    } catch (e) {
      console.error("[edit-modal] setupCanvases failed:", e)
    }
  }, [redrawDisplay])

  useEffect(() => {
    const img = imgRef.current
    if (!img) return
    if (img.complete) { setupCanvases(); return }
    img.onload = setupCanvases
  }, [imageUrl, setupCanvases])

  useEffect(() => {
    window.addEventListener("resize", setupCanvases)
    return () => window.removeEventListener("resize", setupCanvases)
  }, [setupCanvases])

  // ── Drawing handlers (only active in inpaint mode) ───────────────────────
  const getPos = (e: MouseEvent | TouchEvent): { x: number; y: number } => {
    const canvas = maskCanvasRef.current!
    const rect = canvas.getBoundingClientRect()
    const src = "touches" in e ? e.touches[0] : e
    return {
      x: (src.clientX - rect.left) * (canvas.width / rect.width),
      y: (src.clientY - rect.top)  * (canvas.height / rect.height),
    }
  }

  const paintAt = (ctx: CanvasRenderingContext2D, x: number, y: number, size: number, erase: boolean) => {
    ctx.beginPath()
    ctx.arc(x, y, size / 2, 0, Math.PI * 2)
    ctx.fillStyle = erase ? "black" : "white"
    ctx.fill()
  }

  const onPointerDown = (e: MouseEvent | TouchEvent) => {
    e.preventDefault()
    isDrawing.current = true
    const pos = getPos(e)
    const mCtx = maskCanvasRef.current!.getContext("2d")!
    if (tool === "brush" || tool === "eraser") {
      paintAt(mCtx, pos.x, pos.y, brushSize, tool === "eraser")
      setHasMask(true)
      redrawDisplay()
    } else {
      circleStart.current = pos
      rectStart.current = pos
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

  const onPointerUp = () => {
    if (!isDrawing.current) return
    isDrawing.current = false
    if (tool === "circle" || tool === "rect") setHasMask(true)
    circleStart.current = null
    rectStart.current = null
    snapshotRef.current = null
  }

  const clearMask = () => {
    const mask = maskCanvasRef.current!
    const mCtx = mask.getContext("2d")!
    mCtx.fillStyle = "black"
    mCtx.fillRect(0, 0, mask.width, mask.height)
    setHasMask(false)
    redrawDisplay()
  }

  // ── Extra image upload (compose) ─────────────────────────────────────────
  const addExtraFiles = async (files: FileList | null) => {
    if (!files) return
    const dataUrls: string[] = []
    for (const f of Array.from(files)) {
      if (extras.length + dataUrls.length >= MAX_EXTRAS) break
      if (!f.type.startsWith("image/")) continue
      const du = await new Promise<string>((res, rej) => {
        const r = new FileReader()
        r.onload = () => res(r.result as string)
        r.onerror = () => rej(new Error("Read failed"))
        r.readAsDataURL(f)
      })
      dataUrls.push(du)
    }
    if (dataUrls.length) setExtras(prev => [...prev, ...dataUrls].slice(0, MAX_EXTRAS))
  }

  const removeExtra = (i: number) => setExtras(prev => prev.filter((_, idx) => idx !== i))

  // ── Reset mode-specific state when switching ─────────────────────────────
  useEffect(() => {
    setError(null)
    // Don't wipe instruction — user may want to reuse across modes
    if (mode !== "inpaint_mask" && hasMask) {
      // Clear mask so it doesn't linger
      const m = maskCanvasRef.current
      if (m) {
        const ctx = m.getContext("2d")!
        ctx.fillStyle = "black"
        ctx.fillRect(0, 0, m.width, m.height)
        setHasMask(false)
        redrawDisplay()
      }
    }
    if (mode !== "compose" && mode !== "object_add") setExtras([])
  }, [mode])  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Submit ───────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    const trimmed = instruction.trim()
    if (trimmed.length < 3) {
      setError("Please describe what you want (at least 3 characters).")
      return
    }
    if (mode === "inpaint_mask" && !hasMask) {
      setError("Draw on the area you want to edit first.")
      return
    }
    if (mode === "compose" && extras.length === 0) {
      setError("Add at least one reference image for Compose.")
      return
    }
    // object_add allows extras to be optional (pure-text "add a cup" works)
    setError(null)
    setIsSubmitting(true)

    try {
      const body: Record<string, unknown> = {
        image_url: imageUrl,
        instruction: trimmed,
        quality: "1k",
        edit_mode: mode,
      }
      if (mode === "inpaint_mask") {
        body.mask_data = maskCanvasRef.current!.toDataURL("image/png")
      }
      if ((mode === "compose" || mode === "object_add") && extras.length) {
        body.extra_image_urls = extras
      }

      const res = await fetch("/api/generate/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
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

  // One-click quick action: set mode + instruction, then submit immediately.
  const runQuickAction = async (qa: (typeof QUICK_ACTIONS)[number]) => {
    if (isSubmitting) return
    setMode(qa.mode)
    setInstruction(qa.instruction)
    setError(null)
    setIsSubmitting(true)
    try {
      const res = await fetch("/api/generate/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_url: imageUrl,
          instruction: qa.instruction,
          quality: "1k",
          edit_mode: qa.mode,
        }),
      })
      const data = await res.json()
      if (!res.ok || !data.success) {
        throw new Error(data.error || `Quick action failed (${res.status})`)
      }
      onResult(data.image_url)
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Quick action failed.")
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
        transition={{ duration: 0.18 }}
        className="relative w-full max-w-5xl bg-[#0d0d0d] border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        style={{ maxHeight: "95vh" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <Wand2 className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold text-white">Edit Image</span>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-white p-1 rounded-lg hover:bg-white/[0.06] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Operation picker */}
        <div className="px-5 pt-3 pb-2 border-b border-white/[0.04] overflow-x-auto">
          <div className="flex gap-1.5 min-w-max">
            {OPERATIONS.map(o => (
              <button
                key={o.id}
                onClick={() => setMode(o.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap border",
                  mode === o.id
                    ? "bg-primary/15 border-primary/50 text-primary"
                    : "bg-white/[0.02] border-white/[0.06] text-muted-foreground hover:text-white hover:border-white/15"
                )}
              >
                {o.icon} {o.label}
              </button>
            ))}
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
              <img
                ref={imgRef}
                src={imageUrl}
                alt="Edit target"
                className="rounded-xl max-h-[60vh] max-w-full block"
                onLoad={setupCanvases}
                draggable={false}
              />
              <canvas
                ref={maskCanvasRef}
                className="absolute inset-0 opacity-0 pointer-events-none"
                style={{ borderRadius: "inherit" }}
              />
              <canvas
                ref={displayCanvasRef}
                className={cn(
                  "absolute inset-0 rounded-xl",
                  showMaskTools ? "cursor-crosshair" : "pointer-events-none"
                )}
                onMouseDown={showMaskTools ? onPointerDown : undefined}
                onMouseMove={showMaskTools ? onPointerMove : undefined}
                onMouseUp={showMaskTools ? onPointerUp : undefined}
                onMouseLeave={showMaskTools ? onPointerUp : undefined}
                onTouchStart={showMaskTools ? onPointerDown : undefined}
                onTouchMove={showMaskTools ? onPointerMove : undefined}
                onTouchEnd={showMaskTools ? onPointerUp : undefined}
              />

              {showMaskTools && !hasMask && (
                <div className="absolute inset-0 flex items-end justify-center pb-4 pointer-events-none rounded-xl">
                  <div className="bg-black/70 text-white/80 text-xs px-3 py-1.5 rounded-full backdrop-blur-sm">
                    Draw on the part you want to edit
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right panel */}
          <div className="w-80 shrink-0 flex flex-col border-l border-white/[0.06] p-4 gap-3 overflow-y-auto">
            <p className="text-[11px] text-muted-foreground/80 leading-relaxed">{op.hint}</p>

            {/* One-click quick actions */}
            <div>
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-2">Quick Actions</p>
              <div className="grid grid-cols-2 gap-1.5">
                {QUICK_ACTIONS.map(qa => (
                  <button
                    key={qa.id}
                    onClick={() => runQuickAction(qa)}
                    disabled={isSubmitting}
                    className="flex items-center gap-1.5 px-2 py-2 rounded-lg border border-white/[0.06] bg-white/[0.02] text-muted-foreground hover:text-white hover:border-primary/40 hover:bg-primary/5 text-[11px] font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {qa.icon} {qa.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Inpaint tools */}
            {showMaskTools && (
              <div className="space-y-3">
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

                {hasMask && (
                  <button
                    onClick={clearMask}
                    className="flex items-center gap-1.5 text-xs text-red-400/70 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="h-3 w-3" /> Clear mask
                  </button>
                )}
              </div>
            )}

            {/* Theme presets (Remix only) */}
            {showThemePresets && (
              <div>
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-2">Theme Presets</p>
                <div className="grid grid-cols-2 gap-1.5 max-h-56 overflow-y-auto pr-1">
                  {THEME_PRESETS.map(t => (
                    <button
                      key={t.label}
                      onClick={() => setInstruction(t.prompt)}
                      className="text-left text-[11px] text-muted-foreground/80 hover:text-white px-2 py-1.5 rounded-lg bg-white/[0.02] hover:bg-primary/10 border border-white/[0.06] hover:border-primary/40 transition-all"
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Compose / Add Object: extra image uploader */}
            {showExtraImages && (
              <div>
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-2">
                  {mode === "object_add" ? "Object / Logo" : "Reference Images"} ({extras.length}/{MAX_EXTRAS})
                  {mode === "object_add" && <span className="ml-1 normal-case tracking-normal text-muted-foreground/40">· optional</span>}
                </p>
                <div className="grid grid-cols-3 gap-1.5">
                  {extras.map((u, i) => (
                    <div key={i} className="relative aspect-square rounded-lg overflow-hidden border border-white/[0.06]">
                      <img src={u} alt={`ref ${i + 1}`} className="w-full h-full object-cover" />
                      <button
                        onClick={() => removeExtra(i)}
                        className="absolute top-1 right-1 p-0.5 bg-black/70 rounded hover:bg-red-500/70 transition-colors"
                      >
                        <X className="h-3 w-3 text-white" />
                      </button>
                    </div>
                  ))}
                  {extras.length < MAX_EXTRAS && (
                    <button
                      onClick={() => extraFileRef.current?.click()}
                      className="aspect-square rounded-lg border border-dashed border-white/15 hover:border-primary/50 hover:bg-primary/5 flex items-center justify-center transition-all text-muted-foreground/70 hover:text-primary"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <input
                  ref={extraFileRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={e => {
                    addExtraFiles(e.target.files)
                    if (e.target) e.target.value = ""
                  }}
                />
              </div>
            )}

            {/* Suggestions */}
            {op.suggestions.length > 0 && (
              <div>
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-1.5">Quick ideas</p>
                <div className="space-y-1">
                  {op.suggestions.map(s => (
                    <button
                      key={s}
                      onClick={() => setInstruction(s)}
                      className="w-full text-left text-[11px] text-muted-foreground/70 hover:text-white px-2 py-1.5 rounded-lg hover:bg-white/[0.04] transition-colors border border-transparent hover:border-white/[0.06]"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Instruction + submit */}
            <div className="mt-auto flex flex-col gap-2">
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest">Instruction</p>
              <textarea
                value={instruction}
                onChange={e => setInstruction(e.target.value)}
                placeholder={op.placeholder}
                rows={3}
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2.5 text-sm text-white placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/40 resize-none"
              />
              {error && <p className="text-[11px] text-red-400">{error}</p>}
              <Button
                onClick={handleSubmit}
                disabled={isSubmitting || !instruction.trim()}
                className="w-full btn-premium text-white rounded-xl"
              >
                {isSubmitting ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Applying {op.label.toLowerCase()}...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Wand2 className="h-3.5 w-3.5" />
                    Apply {op.label}
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

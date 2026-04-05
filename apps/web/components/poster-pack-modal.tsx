"use client"

/**
 * PosterPackModal — Sprint 4
 *
 * Generates 4 aspect-ratio variants in parallel and shows download thumbnails.
 * Free users: 1:1 only. Pro users: all 4 sizes.
 *
 * Props:
 *   heroUrl      — raw hero image URL
 *   adCopy       — current ad copy state
 *   posterDesign — current poster design state
 *   open         — modal open state
 *   onClose      — close handler
 */

import React, { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { X, Download, Loader2, Package, ExternalLink } from "lucide-react"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"

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

interface PackSize {
  image_b64: string
  image_data_uri: string
  width: number
  height: number
}

interface PosterPackModalProps {
  heroUrl: string
  adCopy: AdCopy
  posterDesign: PosterDesign
  open: boolean
  onClose: () => void
  isPro?: boolean
  /** If provided, "Open in Editor" button creates a project and navigates */
  designBrief?: object
}

const SIZE_LABELS: Record<string, { label: string; desc: string }> = {
  "1:1":  { label: "Square 1:1",   desc: "Instagram Post • 1024×1024" },
  "9:16": { label: "Story 9:16",   desc: "Instagram Story • 1080×1920" },
  "16:9": { label: "Widescreen 16:9", desc: "YouTube / LinkedIn • 1920×1080" },
  "4:5":  { label: "Feed 4:5",     desc: "Instagram Feed • 1080×1350" },
}

export function PosterPackModal({
  heroUrl,
  adCopy,
  posterDesign,
  open,
  onClose,
  isPro = true,
  designBrief,
}: PosterPackModalProps) {
  const router = useRouter()
  const [loading, setLoading]           = useState(false)
  const [sizes, setSizes]               = useState<Record<string, PackSize>>({})
  const [error, setError]               = useState<string | null>(null)
  const [failedSizes, setFailedSizes]   = useState<string[]>([])
  const [openingEditor, setOpeningEditor] = useState<string | null>(null)

  const includeSizes = isPro ? ["1:1", "9:16", "16:9", "4:5"] : ["1:1"]

  useEffect(() => {
    if (!open) return
    setSizes({})
    setError(null)
    setLoading(true)

    fetch("/api/generate/poster-pack", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        hero_url: heroUrl,
        ad_copy: {
          brand_name:  adCopy.brand_name  ?? "",
          headline:    adCopy.headline    ?? "HEADLINE",
          subheadline: adCopy.subheadline ?? "",
          body:        adCopy.body        ?? "",
          cta:         adCopy.cta         ?? "GET STARTED",
          tagline:     adCopy.tagline     ?? "",
          features:    adCopy.features    ?? [],
        },
        poster_design: {
          layout:           posterDesign.layout        ?? "hero_top_features_bottom",
          accent_color:     posterDesign.accent_color  ?? "#F59E0B",
          bg_color:         posterDesign.bg_color      ?? "#0F172A",
          font_style:       posterDesign.font_style    ?? "bold_tech",
          has_feature_grid: posterDesign.has_feature_grid ?? true,
          has_cta_button:   posterDesign.has_cta_button   ?? true,
          hero_occupies:    posterDesign.hero_occupies    ?? "top_60",
        },
        include: includeSizes,
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.sizes && Object.keys(data.sizes).length > 0) {
          setSizes(data.sizes)
          setFailedSizes(data.failed ?? [])
        } else {
          setError(data.error ?? data.detail ?? "Pack generation failed")
        }
      })
      .catch(() => setError("Pack service unavailable"))
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const downloadOne = (key: string, size: PackSize) => {
    const link = document.createElement("a")
    link.href = size.image_data_uri
    link.download = `photogenius-${key.replace(":", "x")}-${Date.now()}.jpg`
    link.click()
  }

  const openInEditor = async (key: string, size: PackSize) => {
    setOpeningEditor(key)
    try {
      const ratioMap: Record<string, { w: number; h: number }> = {
        "1:1": { w: 1024, h: 1024 }, "9:16": { w: 1080, h: 1920 },
        "16:9": { w: 1920, h: 1080 }, "4:5": { w: 1080, h: 1350 },
      }
      const dim = ratioMap[key] ?? { w: size.width, h: size.height }
      const res = await fetch("/api/projects/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          heroUrl,
          adCopy,
          posterDesign,
          designBrief,
          imageUrl: size.image_data_uri,
          width: dim.w,
          height: dim.h,
          name: `${adCopy.headline ?? "Poster"} — ${key}`,
        }),
      })
      const data = await res.json()
      if (data.projectId) router.push(`/editor/${data.projectId}`)
    } catch { /* silent */ }
    finally { setOpeningEditor(null) }
  }

  const downloadAll = async () => {
    // Dynamic import jszip only when needed
    try {
      const JSZip = (await import("jszip")).default
      const zip = new JSZip()
      for (const [key, size] of Object.entries(sizes)) {
        zip.file(
          `photogenius-${key.replace(":", "x")}.jpg`,
          size.image_b64,
          { base64: true }
        )
      }
      const blob = await zip.generateAsync({ type: "blob" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `photogenius-pack-${Date.now()}.zip`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // Fallback: download individually
      Object.entries(sizes).forEach(([key, size]) => downloadOne(key, size))
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 16 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="pointer-events-auto w-full max-w-2xl rounded-2xl border border-white/[0.1] bg-[#0f1117] shadow-2xl overflow-hidden">

              {/* Header */}
              <div className="flex items-center gap-3 px-5 py-4 border-b border-white/[0.08]">
                <Package className="h-4 w-4 text-primary shrink-0" />
                <div className="flex-1">
                  <h2 className="text-sm font-semibold text-foreground">Download Pack</h2>
                  <p className="text-[11px] text-muted-foreground/60">
                    {isPro ? "4 sizes ready for every platform" : "Free — Square 1:1 only. Upgrade for all 4 sizes."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="p-1.5 rounded-lg hover:bg-white/10 text-muted-foreground transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Body */}
              <div className="p-5">
                {loading && (
                  <div className="flex flex-col items-center gap-3 py-10">
                    <Loader2 className="h-8 w-8 text-primary animate-spin" />
                    <p className="text-sm text-muted-foreground">Generating {includeSizes.length} sizes…</p>
                  </div>
                )}

                {error && (
                  <div className="py-8 text-center">
                    <p className="text-sm text-red-400">{error}</p>
                  </div>
                )}

                {!loading && !error && Object.keys(sizes).length > 0 && (
                  <>
                    {failedSizes.length > 0 && (
                      <div className="mb-3 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-400">
                        ⚠ {failedSizes.join(", ")} failed to generate — download the rest below
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3 mb-4">
                      {["1:1", "9:16", "16:9", "4:5"].map((key) => {
                        const size = sizes[key]
                        const meta = SIZE_LABELS[key]
                        const locked = !isPro && key !== "1:1"

                        return (
                          <div
                            key={key}
                            className={cn(
                              "relative rounded-xl border overflow-hidden",
                              locked ? "border-white/[0.05] opacity-40" : "border-white/[0.08]"
                            )}
                          >
                            {size ? (
                              <div
                                className="relative w-full bg-black/40"
                                style={{ paddingTop: key === "9:16" ? "100%" : key === "16:9" ? "56.25%" : key === "4:5" ? "125%" : "100%" }}
                              >
                                <Image
                                  src={size.image_data_uri}
                                  alt={meta.label}
                                  fill
                                  className="object-contain"
                                  unoptimized
                                />
                              </div>
                            ) : (
                              <div className="aspect-square flex items-center justify-center bg-white/[0.02]">
                                {locked ? (
                                  <span className="text-[11px] text-muted-foreground/50">Pro only</span>
                                ) : (
                                  <Loader2 className="h-5 w-5 text-muted-foreground/40 animate-spin" />
                                )}
                              </div>
                            )}

                            <div className="p-2.5">
                              <p className="text-[11px] font-semibold text-foreground/80">{meta.label}</p>
                              <p className="text-[10px] text-muted-foreground/50">{meta.desc}</p>
                            </div>

                            {size && !locked && (
                              <div className="absolute top-2 right-2 flex gap-1">
                                <button
                                  type="button"
                                  onClick={() => openInEditor(key, size)}
                                  disabled={openingEditor === key}
                                  className="p-1.5 rounded-lg bg-black/50 hover:bg-purple-600 text-white transition-colors"
                                  title="Open in Editor"
                                >
                                  {openingEditor === key
                                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    : <ExternalLink className="h-3.5 w-3.5" />}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => downloadOne(key, size)}
                                  className="p-1.5 rounded-lg bg-black/50 hover:bg-black/80 text-white transition-colors"
                                  title={`Download ${meta.label}`}
                                >
                                  <Download className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>

                    {isPro && (
                      <button
                        type="button"
                        onClick={downloadAll}
                        className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
                      >
                        <Download className="h-4 w-4" /> Download All as ZIP
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

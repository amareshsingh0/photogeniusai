"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import {
  Image as ImageIcon,
  Search,
  Download,
  Trash2,
  X,
  Heart,
  Loader2,
  Sparkles,
  Globe,
} from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { brandedImageUrl } from "@/lib/image-url"

interface Generation {
  id: string
  url: string
  prompt: string
  mode: string
  createdAt: string
  isPublic?: boolean
  publishedAt?: string | null
  galleryModeration?: string | null
  scores?: {
    face_match?: number
    aesthetic?: number
    technical?: number
    total?: number
  }
  identity?: {
    id: string
    name: string
  }
  liked?: boolean
}

// All modes from Prisma GenerationMode (aligned with backend)
const MODES = [
  { value: "", label: "All modes" },
  { value: "REALISM", label: "Realism" },
  { value: "CREATIVE", label: "Creative" },
  { value: "ROMANTIC", label: "Romantic" },
  { value: "CINEMATIC", label: "Cinematic" },
  { value: "FASHION", label: "Fashion" },
  { value: "COOL_EDGY", label: "Cool / Edgy" },
  { value: "ARTISTIC", label: "Artistic" },
  { value: "MAX_SURPRISE", label: "Max Surprise" },
]

export default function GalleryPage() {
  const [images, setImages] = useState<Generation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [filterFavorites, setFilterFavorites] = useState<"all" | "favorites">("all")
  const [filterMode, setFilterMode] = useState("")
  const [selectedImage, setSelectedImage] = useState<Generation | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [publishingId, setPublishingId] = useState<string | null>(null)
  const [favoriteLoadingId, setFavoriteLoadingId] = useState<string | null>(null)
  const [stats, setStats] = useState<{ total: number; favoritesCount: number } | null>(null)

  useEffect(() => {
    fetchGenerations()
  }, [filterFavorites, filterMode])

  useEffect(() => {
    let cancelled = false
    fetch("/api/gallery/stats")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (!cancelled && data) setStats({ total: data.total ?? 0, favoritesCount: data.favoritesCount ?? 0 })
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [images.length])

  async function fetchGenerations() {
    setIsLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterFavorites === "favorites") params.set("isFavorite", "true")
      if (filterMode) params.set("mode", filterMode)
      const res = await fetch(`/api/generations?${params.toString()}`)
      if (res.ok) {
        const data = await res.json()
        const gens = Array.isArray(data) ? data : []
        setImages(gens.map((g: any) => ({
          id: g.id,
          url: g.selectedUrl || (g.outputUrls && g.outputUrls[0]) || "",
          prompt: g.prompt || "",
          mode: g.mode || "REALISM",
          createdAt: g.createdAt,
          isPublic: g.isPublic ?? false,
          publishedAt: g.publishedAt ?? null,
          galleryModeration: g.galleryModeration ?? null,
          scores: g.scores,
          identity: g.identity,
          liked: g.isFavorite ?? false,
        })))
      }
    } catch (error) {
      console.error("Failed to fetch generations:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const filteredImages = searchQuery
    ? images.filter((img) =>
        img.prompt?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : images

  const handleDownload = async (img: Generation) => {
    try {
      if (img.url.startsWith("data:")) {
        const link = document.createElement("a")
        link.href = img.url
        link.download = `pixium-${img.id}.png`
        link.click()
      } else {
        const response = await fetch(img.url)
        const blob = await response.blob()
        const url = URL.createObjectURL(blob)
        const link = document.createElement("a")
        link.href = url
        link.download = `pixium-${img.id}.png`
        link.click()
        URL.revokeObjectURL(url)
      }
    } catch (error) {
      console.error("Download failed:", error)
    }
  }

  const handleDelete = async (id: string) => {
    setDeletingId(id)
    try {
      const res = await fetch(`/api/generations/${id}`, { method: "DELETE" })
      if (res.ok) {
        setImages((prev) => prev.filter((img) => img.id !== id))
        if (selectedImage?.id === id) setSelectedImage(null)
      }
    } catch (error) {
      console.error("Delete failed:", error)
    } finally {
      setDeletingId(null)
      setConfirmDeleteId(null)
    }
  }

  const toggleLike = async (id: string) => {
    const img = images.find((i) => i.id === id)
    if (!img) return
    const nextFavorite = !img.liked
    setFavoriteLoadingId(id)
    setImages((prev) =>
      prev.map((i) => (i.id === id ? { ...i, liked: nextFavorite } : i))
    )
    if (selectedImage?.id === id) {
      setSelectedImage({ ...selectedImage, liked: nextFavorite })
    }
    try {
      const res = await fetch(`/api/generations/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ isFavorite: nextFavorite }),
      })
      if (!res.ok) {
        setImages((prev) =>
          prev.map((i) => (i.id === id ? { ...i, liked: img.liked } : i))
        )
        if (selectedImage?.id === id) setSelectedImage({ ...selectedImage, liked: img.liked })
      } else {
        fetch("/api/gallery/stats").then((r) => r.ok && r.json()).then((data) => {
          if (data) setStats({ total: data.total ?? 0, favoritesCount: data.favoritesCount ?? 0 })
        }).catch(() => {})
      }
    } catch (e) {
      console.error("Failed to update favorite:", e)
      setImages((prev) =>
        prev.map((i) => (i.id === id ? { ...i, liked: img.liked } : i))
      )
      if (selectedImage?.id === id) setSelectedImage({ ...selectedImage, liked: img.liked })
    } finally {
      setFavoriteLoadingId(null)
    }
  }

  const handlePublishToggle = async (img: Generation) => {
    setPublishingId(img.id)
    try {
      if (img.isPublic) {
        const res = await fetch(`/api/generations/${img.id}/publish`, { method: "DELETE" })
        if (res.ok) {
          setImages((prev) => prev.map((i) => (i.id === img.id ? { ...i, isPublic: false, publishedAt: null } : i)))
          if (selectedImage?.id === img.id) setSelectedImage({ ...selectedImage, isPublic: false, publishedAt: null })
        }
      } else {
        const res = await fetch(`/api/generations/${img.id}/publish`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        })
        if (res.ok) {
          setImages((prev) => prev.map((i) => (i.id === img.id ? { ...i, isPublic: true, publishedAt: new Date().toISOString() } : i)))
          if (selectedImage?.id === img.id) setSelectedImage({ ...selectedImage, isPublic: true, publishedAt: new Date().toISOString() })
        }
      }
    } catch (e) {
      console.error("Publish toggle failed:", e)
    } finally {
      setPublishingId(null)
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-24 space-y-6">
      <div className="flex items-center gap-3">
        <ImageIcon className="h-5 w-5 text-white/60" />
        <div>
          <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Gallery</h1>
          <p className="mt-1 text-sm text-white/50">
            {isLoading
              ? "Loading…"
              : stats
                ? `${filteredImages.length} of ${stats.total} images${stats.favoritesCount ? ` · ${stats.favoritesCount} favorites` : ""}`
                : `${filteredImages.length} images`}
          </p>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
          <input
            placeholder="Search by prompt…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-black/20 py-2 pl-10 pr-3 text-sm outline-none focus:border-white/30"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => setFilterFavorites("all")}
            className={`rounded-full px-2.5 py-1 text-[11px] transition ${filterFavorites === "all" ? "bg-white text-black" : "bg-white/5 text-white/70 hover:bg-white/10"}`}
          >
            All
          </button>
          <button
            onClick={() => setFilterFavorites("favorites")}
            className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] transition ${filterFavorites === "favorites" ? "bg-white text-black" : "bg-white/5 text-white/70 hover:bg-white/10"}`}
          >
            <Heart className="h-3 w-3" /> Favorites
          </button>
          <span className="mx-1 h-4 w-px bg-white/10" />
          {MODES.map((m) => (
            <button
              key={m.value || "all"}
              onClick={() => setFilterMode(m.value)}
              className={`rounded-full px-2.5 py-1 text-[11px] transition ${filterMode === m.value ? "bg-white text-black" : "bg-white/5 text-white/70 hover:bg-white/10"}`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="explore-masonry">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div key={i} className="explore-card mb-4 aspect-square animate-pulse rounded-2xl bg-white/[0.02]" />
          ))}
        </div>
      ) : filteredImages.length === 0 ? (
        <div className="glass-panel rounded-2xl p-12 text-center">
          <h3 className="font-display text-2xl tracking-tight">
            {searchQuery ? "No images found" : "No images yet"}
          </h3>
          <p className="mx-auto mt-2 max-w-sm text-sm text-white/50">
            {searchQuery ? "Try a different search term." : "Start generating to build your gallery."}
          </p>
          {!searchQuery && filterFavorites === "all" && filterMode === "" && (
            <Link href="/generate" className="mt-5 inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-black transition" style={{ background: "var(--gradient-aurora)" }}>
              <Sparkles className="h-4 w-4" /> Create your first image
            </Link>
          )}
          {filterFavorites === "favorites" && (
            <p className="mt-3 text-sm text-white/40">Mark images as favorite in All view to see them here.</p>
          )}
        </div>
      ) : (
        <div className="explore-masonry">
          {filteredImages.map((img) => (
            <div
              key={img.id}
              className="explore-card group relative mb-4 cursor-pointer overflow-hidden rounded-2xl border border-white/5 transition hover:-translate-y-0.5"
              onClick={() => setSelectedImage(img)}
            >
              {img.url ? (
                <img src={brandedImageUrl(img.url)} alt={img.prompt || "Generated image"} className="w-full" />
              ) : (
                <div className="flex aspect-square w-full items-center justify-center bg-white/[0.02]">
                  <ImageIcon className="h-8 w-8 text-white/40" />
                </div>
              )}
              {/* Quality badge */}
              {img.scores?.total ? (
                <span className="glass-panel kerned absolute left-2 top-2 rounded-full px-2 py-0.5 text-white/70">
                  {img.scores.total.toFixed(1)}
                </span>
              ) : (
                <span className="glass-panel kerned absolute left-2 top-2 rounded-full px-2 py-0.5 text-white/70">
                  {img.mode}
                </span>
              )}
              {img.liked && <Heart className="absolute right-2 top-2 h-4 w-4 fill-white text-white" />}
              {/* Hover overlay */}
              <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/80 via-black/10 to-transparent p-3 opacity-0 transition-opacity group-hover:opacity-100">
                <p className="line-clamp-2 font-mono text-[10px] text-white/60">{img.prompt}</p>
                <div className="mt-2 flex items-center gap-1.5">
                  <button onClick={(e) => { e.stopPropagation(); handleDownload(img) }} className="rounded-lg border border-white/10 bg-white/5 p-1.5 hover:bg-white/10 transition" title="Download">
                    <Download className="h-3.5 w-3.5" />
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); toggleLike(img.id) }} disabled={favoriteLoadingId === img.id} className="rounded-lg border border-white/10 bg-white/5 p-1.5 hover:bg-white/10 transition" title="Like">
                    {favoriteLoadingId === img.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Heart className={cn("h-3.5 w-3.5", img.liked && "fill-current")} />}
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); handlePublishToggle(img) }} disabled={publishingId === img.id} className="rounded-lg border border-white/10 bg-white/5 p-1.5 hover:bg-white/10 transition" title={img.isPublic ? "Unpublish" : "Publish"}>
                    {publishingId === img.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Globe className={cn("h-3.5 w-3.5", img.isPublic && "text-emerald-400")} />}
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(img.id) }} className="rounded-lg border border-red-500/30 bg-red-500/10 p-1.5 text-red-200 hover:bg-red-500/15 transition" title="Delete">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail modal */}
      {selectedImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
          onClick={() => setSelectedImage(null)}
        >
          <div
            className="glass-panel relative w-full max-w-4xl overflow-hidden rounded-2xl"
            style={{ boxShadow: "var(--shadow-float)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="absolute right-3 top-3 z-10 rounded-xl border border-white/10 bg-black/40 p-1.5 text-white hover:bg-black/60 transition"
              onClick={() => setSelectedImage(null)}
            >
              <X className="h-4 w-4" />
            </button>

            <div className="grid md:grid-cols-2">
              <div className="relative min-h-[300px] bg-black md:min-h-[400px]">
                {selectedImage.url ? (
                  <Image src={selectedImage.url} alt={selectedImage.prompt || "Generated image"} fill className="object-contain" unoptimized />
                ) : (
                  <div className="flex h-full w-full items-center justify-center"><ImageIcon className="h-16 w-16 text-white/40" /></div>
                )}
              </div>

              <div className="flex flex-col p-6">
                <div className="flex-1">
                  <span className="kerned mb-3 inline-block rounded-full bg-white/5 px-2 py-0.5 text-white/60">{selectedImage.mode}</span>
                  <h3 className="font-display text-lg tracking-tight">Generated image</h3>
                  <p className="mt-2 font-mono text-[10px] text-white/60">{selectedImage.prompt}</p>

                  {selectedImage.scores && (selectedImage.scores.face_match || selectedImage.scores.aesthetic) && (
                    <div className="mt-4 grid grid-cols-2 gap-2">
                      {selectedImage.scores.face_match !== undefined && selectedImage.scores.face_match > 0 && (
                        <div className="hairline rounded-xl p-3">
                          <p className="kerned text-white/40">Face match</p>
                          <p className="font-mono text-sm text-white/85">{Math.round(selectedImage.scores.face_match * 100)}%</p>
                        </div>
                      )}
                      {selectedImage.scores.aesthetic !== undefined && selectedImage.scores.aesthetic > 0 && (
                        <div className="hairline rounded-xl p-3">
                          <p className="kerned text-white/40">Aesthetic</p>
                          <p className="font-mono text-sm text-white/85">{Math.round(selectedImage.scores.aesthetic * 100)}%</p>
                        </div>
                      )}
                    </div>
                  )}

                  {selectedImage.identity && <p className="mt-3 text-xs text-white/50">Identity: {selectedImage.identity.name}</p>}
                  <p className="mt-2 font-mono text-[11px] text-white/60">{new Date(selectedImage.createdAt).toLocaleDateString()}</p>
                </div>

                <div className="mt-4 flex flex-wrap gap-2 border-t border-white/5 pt-4">
                  <button
                    onClick={() => handlePublishToggle(selectedImage)}
                    disabled={publishingId === selectedImage.id}
                    className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition disabled:opacity-50"
                  >
                    {publishingId === selectedImage.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Globe className="h-3.5 w-3.5" />}
                    {selectedImage.isPublic ? "Unpublish" : "Publish to Explore"}
                  </button>
                  <button
                    onClick={() => toggleLike(selectedImage.id)}
                    disabled={favoriteLoadingId === selectedImage.id}
                    className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition disabled:opacity-50"
                  >
                    {favoriteLoadingId === selectedImage.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Heart className={cn("h-3.5 w-3.5", selectedImage.liked && "fill-current")} />}
                    {selectedImage.liked ? "Liked" : "Like"}
                  </button>
                  <button
                    onClick={() => handleDownload(selectedImage)}
                    className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition"
                  >
                    <Download className="h-3.5 w-3.5" /> Download
                  </button>
                  <button
                    onClick={() => setConfirmDeleteId(selectedImage.id)}
                    disabled={deletingId === selectedImage.id}
                    className="flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-sm text-red-200 hover:bg-red-500/15 transition disabled:opacity-50"
                  >
                    {deletingId === selectedImage.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />} Delete
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirm modal */}
      {confirmDeleteId && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm" onClick={() => setConfirmDeleteId(null)}>
          <div className="glass-panel w-full max-w-sm rounded-2xl p-5" style={{ boxShadow: "var(--shadow-float)" }} onClick={(e) => e.stopPropagation()}>
            <h3 className="font-display text-lg tracking-tight">Delete image?</h3>
            <p className="mt-2 text-sm text-white/50">This permanently removes the generation. This cannot be undone.</p>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setConfirmDeleteId(null)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition">Cancel</button>
              <button
                onClick={() => confirmDeleteId && handleDelete(confirmDeleteId)}
                disabled={!!deletingId}
                className="flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-sm text-red-200 hover:bg-red-500/15 transition disabled:opacity-50"
              >
                {deletingId ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />} Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

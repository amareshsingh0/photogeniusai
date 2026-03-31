"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
        link.download = `photogenius-${img.id}.png`
        link.click()
      } else {
        const response = await fetch(img.url)
        const blob = await response.blob()
        const url = URL.createObjectURL(blob)
        const link = document.createElement("a")
        link.href = url
        link.download = `photogenius-${img.id}.png`
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
    <div className="max-w-6xl mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
            <span className="inline-flex p-2 rounded-xl bg-primary/10">
              <ImageIcon className="h-6 w-6 text-primary" />
            </span>
            <span className="gradient-text">Gallery</span>
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? "Loading..."
              : stats
                ? `${filteredImages.length} of ${stats.total} images${stats.favoritesCount ? ` · ${stats.favoritesCount} favorites` : ""}`
                : `${filteredImages.length} images`}
          </p>
        </div>
      </motion.div>

      <div className="flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between">
        <div className="relative max-w-md w-full">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by prompt..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-11 rounded-xl glass-card border-white/[0.06] focus:border-primary/30"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-xl overflow-hidden border border-white/[0.06] bg-white/[0.02] p-0.5">
            <button
              type="button"
              onClick={() => setFilterFavorites("all")}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-lg transition-colors",
                filterFavorites === "all"
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setFilterFavorites("favorites")}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5",
                filterFavorites === "favorites"
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Heart className="h-3.5 w-3.5" />
              Favorites
            </button>
          </div>
          <select
            value={filterMode}
            onChange={(e) => setFilterMode(e.target.value)}
            className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-foreground focus:border-primary/30 outline-none"
          >
            {MODES.map((m) => (
              <option key={m.value || "all"} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div key={i} className="aspect-square rounded-2xl shimmer" />
          ))}
        </div>
      ) : filteredImages.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="text-center py-20 rounded-2xl glass-card border border-white/[0.06]"
        >
          <div className="w-20 h-20 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-5">
            <ImageIcon className="h-10 w-10 text-primary" />
          </div>
          <h3 className="text-xl font-semibold text-foreground mb-2">
            {searchQuery ? "No images found" : "No images yet"}
          </h3>
          <p className="text-sm text-muted-foreground mb-6 max-w-sm mx-auto">
            {searchQuery
              ? "Try a different search term"
              : "Start generating to build your gallery"}
          </p>
          {!searchQuery && filterFavorites === "all" && filterMode === "" && (
            <Link href="/generate">
              <Button className="btn-premium text-white rounded-xl">
                <Sparkles className="mr-2 h-4 w-4" />
                Create Your First Image
              </Button>
            </Link>
          )}
          {filterFavorites === "favorites" && (
            <p className="text-sm text-muted-foreground mt-2">
              Mark images as favorite in All view to see them here.
            </p>
          )}
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4"
        >
          {filteredImages.map((img, idx) => (
            <motion.div
              key={img.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: Math.min(idx * 0.03, 0.2) }}
              className="group relative aspect-square rounded-2xl overflow-hidden glass-card border border-white/[0.06] hover:border-white/15 cursor-pointer transition-colors"
              onClick={() => setSelectedImage(img)}
            >
              {img.url ? (
                <Image
                  src={img.url}
                  alt={img.prompt || "Generated image"}
                  fill
                  className="object-cover transition-transform duration-300 group-hover:scale-105"
                  unoptimized
                />
              ) : (
                <div className="w-full h-full bg-muted flex items-center justify-center">
                  <ImageIcon className="h-8 w-8 text-muted-foreground" />
                </div>
              )}
              {/* Overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="absolute bottom-0 left-0 right-0 p-3">
                  <p className="text-xs text-white/90 line-clamp-2">
                    {img.prompt}
                  </p>
                </div>
              </div>
              {/* Like Badge */}
              {img.liked && (
                <div className="absolute top-2 right-2">
                  <Heart className="h-5 w-5 text-red-500 fill-red-500" />
                </div>
              )}
              {/* Mode Badge */}
              <div className="absolute top-2 left-2">
                <span className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded-md font-medium",
                  img.mode === "REALISM" ? "bg-blue-500/80 text-white" :
                  img.mode === "CREATIVE" ? "bg-purple-500/80 text-white" :
                  img.mode === "ROMANTIC" ? "bg-pink-500/80 text-white" :
                  "bg-gray-500/80 text-white"
                )}>
                  {img.mode}
                </span>
              </div>
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* Image Modal */}
      {selectedImage && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setSelectedImage(null)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25 }}
            className="relative max-w-4xl w-full glass-card rounded-2xl overflow-hidden border border-white/10 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-3 right-3 z-10 rounded-xl bg-black/50 hover:bg-black/70 text-white"
              onClick={() => setSelectedImage(null)}
            >
              <X className="h-5 w-5" />
            </Button>

            <div className="grid md:grid-cols-2">
              <div className="relative aspect-auto min-h-[300px] md:min-h-[400px] bg-black">
                {selectedImage.url ? (
                  <Image
                    src={selectedImage.url}
                    alt={selectedImage.prompt || "Generated image"}
                    fill
                    className="object-contain"
                    unoptimized
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <ImageIcon className="h-16 w-16 text-muted-foreground" />
                  </div>
                )}
              </div>

              <div className="p-6 flex flex-col">
                <div className="flex-1">
                  <span className={cn(
                    "inline-block px-2.5 py-1 rounded-lg text-xs font-medium mb-3",
                    selectedImage.mode === "REALISM"
                      ? "bg-blue-500/10 text-blue-500"
                      : selectedImage.mode === "CREATIVE"
                      ? "bg-purple-500/10 text-purple-500"
                      : "bg-pink-500/10 text-pink-500"
                  )}>
                    {selectedImage.mode}
                  </span>
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    Generated Image
                  </h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    {selectedImage.prompt}
                  </p>

                  {selectedImage.scores && (selectedImage.scores.face_match || selectedImage.scores.aesthetic) && (
                    <div className="grid grid-cols-2 gap-2 mb-4">
                      {selectedImage.scores.face_match !== undefined && selectedImage.scores.face_match > 0 && (
                        <div className="p-3 rounded-xl glass-card border border-white/[0.06]">
                          <p className="text-[10px] text-muted-foreground">Face Match</p>
                          <p className="text-sm font-semibold text-foreground">
                            {Math.round(selectedImage.scores.face_match * 100)}%
                          </p>
                        </div>
                      )}
                      {selectedImage.scores.aesthetic !== undefined && selectedImage.scores.aesthetic > 0 && (
                        <div className="p-3 rounded-xl glass-card border border-white/[0.06]">
                          <p className="text-[10px] text-muted-foreground">Aesthetic</p>
                          <p className="text-sm font-semibold text-foreground">
                            {Math.round(selectedImage.scores.aesthetic * 100)}%
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {selectedImage.identity && (
                    <p className="text-xs text-muted-foreground mb-2">
                      Identity: {selectedImage.identity.name}
                    </p>
                  )}

                  <p className="text-xs text-muted-foreground">
                    {new Date(selectedImage.createdAt).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2 pt-4 border-t border-white/[0.08]">
                  <Button
                    variant={selectedImage.isPublic ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => handlePublishToggle(selectedImage)}
                    disabled={publishingId === selectedImage.id}
                  >
                    {publishingId === selectedImage.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Globe className="h-4 w-4 mr-2" />
                    )}
                    {selectedImage.isPublic ? "Unpublish" : "Publish to Explore"}
                  </Button>
                  <Button
                    variant={selectedImage.liked ? "default" : "outline"}
                    size="sm"
                    className="flex-1"
                    onClick={() => toggleLike(selectedImage.id)}
                    disabled={favoriteLoadingId === selectedImage.id}
                  >
                    {favoriteLoadingId === selectedImage.id ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Heart className={cn(
                        "h-4 w-4 mr-2",
                        selectedImage.liked && "fill-current"
                      )} />
                    )}
                    {selectedImage.liked ? "Liked" : "Like"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => handleDownload(selectedImage)}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => handleDelete(selectedImage.id)}
                    disabled={deletingId === selectedImage.id}
                  >
                    {deletingId === selectedImage.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  )
}

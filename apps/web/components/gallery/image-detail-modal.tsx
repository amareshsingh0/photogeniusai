"use client"

import NextImage from "next/image"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  Download,
  Share2,
  Heart,
  Copy,
  Trash2,
  ThumbsUp,
  ThumbsDown,
  ExternalLink,
  RefreshCw,
} from "lucide-react"
import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"

export interface GenerationImage {
  id: string
  url: string
  prompt: string
  mode: string
  identity?: { id: string; name: string }
  scores?: {
    face_match: number
    aesthetic: number
    technical: number
    total: number
  }
  createdAt: string
  favorite: boolean
}

interface ImageDetailModalProps {
  image: GenerationImage | null
  isOpen: boolean
  onClose: () => void
  onDelete?: (id: string) => void
  onToggleFavorite?: (id: string, url: string) => void
}

export function ImageDetailModal({ image, isOpen, onClose, onDelete, onToggleFavorite }: ImageDetailModalProps) {
  const [isFavorite, setIsFavorite] = useState(image?.favorite || false)
  const [thumbsLoading, setThumbsLoading] = useState<"up" | "down" | null>(null)
  const [copied, setCopied] = useState(false)
  const router = useRouter()

  useEffect(() => {
    if (image) {
      setIsFavorite(image.favorite || false)
    }
  }, [image])

  if (!image) return null

  const handleDownload = async () => {
    const a = document.createElement("a")
    a.href = image.url
    a.download = `portrait-${image.id}.jpg`
    a.target = "_blank"
    a.rel = "noopener"
    a.click()
    try {
      await fetch(`/api/generations/${image.id}/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageUrl: image.url }),
      })
    } catch {
      // ignore
    }
  }

  const handleThumbs = async (thumbs: "up" | "down") => {
    setThumbsLoading(thumbs)
    try {
      await fetch("/api/preferences/thumbs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          generationId: image.id,
          imageUrl: image.url,
          thumbs,
        }),
      })
    } catch {
      // ignore
    } finally {
      setThumbsLoading(null)
    }
  }

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: "PhotoGenius AI Portrait",
          text: image.prompt,
          url: image.url,
        })
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          console.error("Error sharing:", err)
        }
      }
    } else {
      try {
        await navigator.clipboard.writeText(image.url)
      } catch {
        // ignore
      }
    }
  }

  const handleCopyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(image.prompt)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }

  const handleDelete = () => {
    if (onDelete) {
      onDelete(image.id)
      onClose()
    }
  }

  const handleToggleFavorite = () => {
    const newFavoriteState = !isFavorite
    setIsFavorite(newFavoriteState)
    if (onToggleFavorite) {
      onToggleFavorite(image.id, image.url)
    }
  }

  const handleRegenerate = () => {
    onClose()
    router.push(`/generate?prompt=${encodeURIComponent(image.prompt)}`)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto bg-zinc-950 border-zinc-800 text-zinc-100">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">Image Details</DialogTitle>
          <DialogDescription className="text-zinc-500">
            View and manage your generated image
          </DialogDescription>
        </DialogHeader>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Image */}
          <div className="relative aspect-square rounded-xl overflow-hidden bg-zinc-900 border border-zinc-800">
            <NextImage
              src={image.url}
              alt={image.prompt}
              fill
              className="object-contain"
              sizes="(max-width: 768px) 100vw, 50vw"
            />
          </div>

          {/* Details */}
          <div className="space-y-5">
            {/* Actions row */}
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={handleDownload}
                className="flex-1 bg-white text-zinc-900 hover:bg-zinc-100"
              >
                <Download className="mr-2 h-4 w-4" />
                Download
              </Button>
              <Button
                variant="outline"
                onClick={handleShare}
                className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
              >
                <Share2 className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                onClick={handleToggleFavorite}
                className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
              >
                <Heart
                  className={cn("h-4 w-4", isFavorite ? "fill-red-500 text-red-500" : "")}
                />
              </Button>
              <Button
                variant="outline"
                onClick={() => handleThumbs("up")}
                disabled={thumbsLoading !== null}
                title="Good image"
                className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-40"
              >
                <ThumbsUp className={cn("h-4 w-4", thumbsLoading === "up" && "animate-pulse text-emerald-400")} />
              </Button>
              <Button
                variant="outline"
                onClick={() => handleThumbs("down")}
                disabled={thumbsLoading !== null}
                title="Not great"
                className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-40"
              >
                <ThumbsDown className={cn("h-4 w-4", thumbsLoading === "down" && "animate-pulse text-red-400")} />
              </Button>
              <Button
                variant="outline"
                onClick={handleDelete}
                className="border-zinc-700 text-zinc-300 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/30"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>

            <Separator className="bg-zinc-800" />

            {/* Metadata */}
            <div className="space-y-4">
              {/* Prompt */}
              <div>
                <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">
                  Prompt
                </h4>
                <div className="flex items-start gap-2">
                  <p className="text-sm text-zinc-300 flex-1 leading-relaxed bg-zinc-900/50 p-3 rounded-lg border border-zinc-800">
                    {image.prompt}
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopyPrompt}
                    className="text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 flex-shrink-0"
                  >
                    {copied ? (
                      <span className="text-xs text-emerald-400">Copied!</span>
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Mode</h4>
                  <Badge className="bg-zinc-800 text-zinc-300 border-zinc-700">{image.mode}</Badge>
                </div>
                {image.identity && (
                  <div>
                    <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Identity</h4>
                    <p className="text-sm text-zinc-300">{image.identity.name}</p>
                  </div>
                )}
              </div>

              <div>
                <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Created</h4>
                <p className="text-sm text-zinc-300">
                  {new Date(image.createdAt).toLocaleString()}
                </p>
              </div>
            </div>

            {/* Quality Scores — only show if available */}
            {image.scores && (
              <>
                <Separator className="bg-zinc-800" />
                <div>
                  <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
                    Quality Scores
                  </h4>
                  <div className="space-y-3">
                    <ScoreBar label="Face Match" score={image.scores.face_match} color="blue" />
                    <ScoreBar label="Aesthetic" score={image.scores.aesthetic} color="purple" />
                    <ScoreBar label="Technical" score={image.scores.technical} color="emerald" />
                    <div className="pt-2 border-t border-zinc-800">
                      <ScoreBar label="Overall" score={image.scores.total} color="indigo" bold />
                    </div>
                  </div>
                </div>
              </>
            )}

            <Separator className="bg-zinc-800" />

            {/* Quick actions */}
            <div className="space-y-2">
              <Button
                variant="outline"
                className="w-full justify-start border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
                onClick={handleRegenerate}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Regenerate with Same Prompt
              </Button>
              {image.identity && (
                <Button
                  variant="outline"
                  className="w-full justify-start border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
                  onClick={() => { onClose(); router.push(`/generate?ref=${image.id}`) }}
                >
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Use as Reference
                </Button>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ScoreBar({
  label,
  score,
  color,
  bold = false,
}: {
  label: string
  score: number
  color: string
  bold?: boolean
}) {
  const getColorClass = (color: string) => {
    switch (color) {
      case "blue": return "bg-blue-500"
      case "purple": return "bg-purple-500"
      case "emerald": return "bg-emerald-500"
      case "indigo": return "bg-indigo-400"
      default: return "bg-zinc-400"
    }
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className={bold ? "font-semibold text-zinc-200" : "text-zinc-400"}>{label}</span>
        <span className={bold ? "font-bold text-zinc-100" : "font-medium text-zinc-300"}>{Math.round(score)}/100</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", getColorClass(color))}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  )
}

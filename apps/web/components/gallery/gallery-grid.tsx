"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Download,
  Trash2,
  Share2,
  Heart,
  Sparkles,
  CheckCircle,
  MoreVertical,
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import Image from "next/image"
import { formatDistanceToNow } from "date-fns"
import { cn } from "@/lib/utils"

interface GalleryGridProps {
  images: any[]
  viewMode: "grid" | "list" | "masonry"
  selectedImages: Set<string>
  onSelectImage: (id: string) => void
  onImageClick: (image: any) => void
  onLike: (id: string) => void
  onDelete: (id: string) => void
  onShare: (image: any) => void
}

export function GalleryGrid({
  images,
  viewMode,
  selectedImages,
  onSelectImage,
  onImageClick,
  onLike,
  onDelete,
  onShare,
}: GalleryGridProps) {
  const handleDownload = (e: React.MouseEvent, imageUrl: string, imageId: string) => {
    e.stopPropagation()
    const link = document.createElement("a")
    link.href = imageUrl
    link.download = `photogenius-${imageId}.png`
    link.click()
  }

  if (viewMode === "list") {
    return (
      <div className="space-y-4">
        {images.map((image) => {
          const isSelected = selectedImages.has(image.id)

          return (
            <Card
              key={image.id}
              className={cn(
                "glass-card transition-all cursor-pointer hover:shadow-lg border-border/50",
                isSelected && "ring-2 ring-primary"
              )}
              onClick={() => onImageClick(image)}
            >
              <div className="p-3 sm:p-4 flex items-center space-x-3 sm:space-x-4">
                {/* Checkbox */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelectImage(image.id)
                  }}
                  className={cn(
                    "h-4 w-4 sm:h-5 sm:w-5 rounded border-2 flex items-center justify-center cursor-pointer transition-all flex-shrink-0",
                    isSelected
                      ? "bg-primary border-primary"
                      : "border-border hover:border-primary"
                  )}
                >
                  {isSelected && <CheckCircle className="h-3 w-3 sm:h-4 sm:w-4 text-primary-foreground" />}
                </div>

                {/* Thumbnail */}
                <div className="relative h-16 w-16 sm:h-20 sm:w-20 rounded-lg overflow-hidden flex-shrink-0 border border-border/50">
                  <Image
                    src={image.thumbnail}
                    alt="Gallery image"
                    fill
                    className="object-cover"
                    sizes="80px"
                    loading="lazy"
                  />
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-1 sm:gap-2 mb-1">
                    <Badge variant="secondary" className="text-[10px] sm:text-xs border-primary/30">
                      {image.mode}
                    </Badge>
                    <Badge variant="outline" className="text-[10px] sm:text-xs border-border/50">
                      {image.identityName}
                    </Badge>
                    <Badge variant="outline" className="text-[10px] sm:text-xs border-primary/30">
                      <Sparkles className="h-2.5 w-2.5 sm:h-3 sm:w-3 mr-0.5 sm:mr-1 text-primary" />
                      {image.score}%
                    </Badge>
                  </div>
                  <p className="text-xs sm:text-sm text-foreground truncate mb-1">
                    {image.prompt}
                  </p>
                  <p className="text-[10px] sm:text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(image.createdAt), {
                      addSuffix: true,
                    })}
                  </p>
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-1 sm:space-x-2 flex-shrink-0">
                  <Button
                    variant={image.liked ? "default" : "outline"}
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      onLike(image.id)
                    }}
                  >
                    <Heart
                      className={cn(
                        "h-4 w-4",
                        image.liked && "fill-current"
                      )}
                    />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={(e) => handleDownload(e, image.url, image.id)}
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="icon">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="glass-card">
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation()
                          onShare(image)
                        }}
                      >
                        <Share2 className="mr-2 h-4 w-4" />
                        Share
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation()
                          onDelete(image.id)
                        }}
                        className="text-destructive focus:text-destructive"
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    )
  }

  // Masonry view
  if (viewMode === "masonry") {
    return (
      <div className="columns-1 sm:columns-2 md:columns-3 lg:columns-4 gap-3 sm:gap-4">
        {images.map((image) => {
          const isSelected = selectedImages.has(image.id)
          // Use aspect ratio for masonry - images will naturally vary in height
          const idx = parseInt(image.id.replace(/\D/g, "") || "0", 10)
          const aspectRatio = 0.75 + (idx % 5) * 0.1 // Deterministic between 0.75 and 1.15

          return (
            <div
              key={image.id}
              className={cn(
                "relative group rounded-lg overflow-hidden border-2 transition-all cursor-pointer glass-card break-inside-avoid mb-4",
                isSelected
                  ? "border-primary ring-2 ring-primary ring-offset-2"
                  : "border-border/50 hover:border-primary/50"
              )}
              onClick={() => onImageClick(image)}
            >
              {/* Image */}
              <div className="relative" style={{ aspectRatio: aspectRatio.toString() }}>
                <Image
                  src={image.thumbnail}
                  alt="Gallery image"
                  fill
                  className="object-cover"
                  sizes="(max-width: 768px) 50vw, (max-width: 1024px) 33vw, 25vw"
                  loading="lazy"
                />

                {/* Overlay on hover */}
                <div className="absolute inset-0 bg-background/80 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center space-x-2">
                  <Button
                    variant="secondary"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      onLike(image.id)
                    }}
                  >
                    <Heart
                      className={cn(
                        "h-4 w-4",
                        image.liked && "fill-current"
                      )}
                    />
                  </Button>
                  <Button
                    variant="secondary"
                    size="icon"
                    onClick={(e) => handleDownload(e, image.url, image.id)}
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="secondary"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      onShare(image)
                    }}
                  >
                    <Share2 className="h-4 w-4" />
                  </Button>
                </div>

                {/* Selection checkbox */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelectImage(image.id)
                  }}
                  className={cn(
                    "absolute top-3 left-3 h-6 w-6 rounded-full border-2 flex items-center justify-center cursor-pointer transition-all bg-background/90 z-10",
                    isSelected
                      ? "border-primary"
                      : "border-border opacity-0 group-hover:opacity-100"
                  )}
                >
                  {isSelected && <CheckCircle className="h-5 w-5 text-primary" />}
                </div>

                {/* Liked indicator */}
                {image.liked && (
                  <div className="absolute top-3 right-3 z-10">
                    <div className="h-6 w-6 rounded-full bg-secondary flex items-center justify-center">
                      <Heart className="h-4 w-4 text-secondary-foreground fill-current" />
                    </div>
                  </div>
                )}

                {/* Score badge */}
                <div className="absolute bottom-3 right-3 z-10">
                  <Badge className="bg-primary border-primary/30">
                    <Sparkles className="h-3 w-3 mr-1" />
                    {image.score}%
                  </Badge>
                </div>
              </div>

              {/* Info */}
              <div className="p-2 sm:p-3 bg-background/50 backdrop-blur-sm">
                <div className="flex flex-wrap items-center gap-1 sm:gap-2 mb-1">
                  <Badge variant="secondary" className="text-[10px] sm:text-xs border-primary/30">
                    {image.mode}
                  </Badge>
                  <Badge variant="outline" className="text-[10px] sm:text-xs border-border/50">
                    {image.identityName}
                  </Badge>
                </div>
                <p className="text-xs sm:text-sm text-foreground truncate">
                  {image.prompt}
                </p>
                <p className="text-[10px] sm:text-xs text-muted-foreground mt-1">
                  {formatDistanceToNow(new Date(image.createdAt), {
                    addSuffix: true,
                  })}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  // Grid view
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
      {images.map((image) => {
        const isSelected = selectedImages.has(image.id)

        return (
          <div
            key={image.id}
            className={cn(
              "relative group rounded-lg overflow-hidden border-2 transition-all cursor-pointer glass-card",
              isSelected
                ? "border-primary ring-2 ring-primary ring-offset-2"
                : "border-border/50 hover:border-primary/50"
            )}
            onClick={() => onImageClick(image)}
          >
            {/* Image */}
            <div className="relative aspect-square">
              <Image
                src={image.thumbnail}
                alt="Gallery image"
                fill
                className="object-cover"
                sizes="(max-width: 768px) 50vw, (max-width: 1024px) 33vw, 25vw"
                loading="lazy"
              />

              {/* Overlay on hover */}
              <div className="absolute inset-0 bg-background/80 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center space-x-2">
                <Button
                  variant="secondary"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation()
                    onLike(image.id)
                  }}
                >
                  <Heart
                    className={cn(
                      "h-4 w-4",
                      image.liked && "fill-current"
                    )}
                  />
                </Button>
                <Button
                  variant="secondary"
                  size="icon"
                  onClick={(e) => handleDownload(e, image.url, image.id)}
                >
                  <Download className="h-4 w-4" />
                </Button>
                <Button
                  variant="secondary"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation()
                    onShare(image)
                  }}
                >
                  <Share2 className="h-4 w-4" />
                </Button>
              </div>

              {/* Selection checkbox */}
              <div
                onClick={(e) => {
                  e.stopPropagation()
                  onSelectImage(image.id)
                }}
                className={cn(
                  "absolute top-3 left-3 h-6 w-6 rounded-full border-2 flex items-center justify-center cursor-pointer transition-all bg-background/90",
                  isSelected
                    ? "border-primary"
                    : "border-border opacity-0 group-hover:opacity-100"
                )}
              >
                {isSelected && <CheckCircle className="h-5 w-5 text-primary" />}
              </div>

              {/* Liked indicator */}
              {image.liked && (
                <div className="absolute top-3 right-3">
                  <div className="h-6 w-6 rounded-full bg-secondary flex items-center justify-center">
                    <Heart className="h-4 w-4 text-secondary-foreground fill-current" />
                  </div>
                </div>
              )}

              {/* Score badge */}
              <div className="absolute bottom-3 right-3">
                <Badge className="bg-primary border-primary/30">
                  <Sparkles className="h-3 w-3 mr-1" />
                  {image.score}%
                </Badge>
              </div>
            </div>

            {/* Info */}
            <div className="p-3 bg-background/50 backdrop-blur-sm">
              <div className="flex items-center space-x-2 mb-1">
                <Badge variant="secondary" className="text-xs border-primary/30">
                  {image.mode}
                </Badge>
                <Badge variant="outline" className="text-xs border-border/50">
                  {image.identityName}
                </Badge>
              </div>
              <p className="text-sm text-foreground truncate">
                {image.prompt}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {formatDistanceToNow(new Date(image.createdAt), {
                  addSuffix: true,
                })}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

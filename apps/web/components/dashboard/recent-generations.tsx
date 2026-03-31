"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Download,
  Share2,
  MoreVertical,
  Clock,
  Image as ImageIcon,
} from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { fetchGenerations, type GenerationListItem } from "@/lib/api"

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diff = (now.getTime() - d.getTime()) / 60000
  if (diff < 1) return "Just now"
  if (diff < 60) return `${Math.floor(diff)} min ago`
  if (diff < 1440) return `${Math.floor(diff / 60)} hr ago`
  if (diff < 2880) return "1 day ago"
  return `${Math.floor(diff / 1440)} days ago`
}

const creditCosts: Record<string, number> = {
  REALISM: 3,
  CREATIVE: 5,
  ROMANTIC: 4,
}

export function RecentGenerations() {
  const { data: generations = [], isLoading } = useQuery({
    queryKey: ["generations"],
    queryFn: fetchGenerations,
  })

  const recentGenerations = generations.slice(0, 3)

  if (isLoading) {
    return (
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Recent Generations</span>
            <Link href="/gallery">
              <Button variant="ghost" size="sm">
                View All
              </Button>
            </Link>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="glass-card">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Recent Generations</span>
          <Link href="/gallery">
            <Button variant="ghost" size="sm">
              View All
            </Button>
          </Link>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {recentGenerations.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <p className="text-sm">No generations yet</p>
            <Link href="/generate">
              <Button className="mt-4">Generate Your First Image</Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {recentGenerations.map((gen) => {
              const imageUrl = gen.selectedUrl ?? gen.outputUrls[0] ?? gen.previewUrl
              const credits = creditCosts[gen.mode] || 3

              return (
                <div
                  key={gen.id}
                  className="flex items-center space-x-4 p-3 rounded-lg border border-border/50 hover:bg-muted/30 transition-colors"
                >
                  {/* Thumbnail */}
                  <div className="relative h-20 w-20 rounded-lg overflow-hidden flex-shrink-0 border border-border/50">
                    {imageUrl ? (
                      <Image
                        src={imageUrl}
                        alt={gen.prompt || "Generated image"}
                        fill
                        className="object-cover"
                        unoptimized
                      />
                    ) : (
                      <div className="h-full w-full bg-muted flex items-center justify-center">
                        <ImageIcon className="h-8 w-8 text-muted-foreground" />
                      </div>
                    )}
                  </div>

                  {/* Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between mb-1">
                      <p className="text-sm font-medium text-foreground truncate">
                        {gen.prompt || "AI Generated Portrait"}
                      </p>
                      <Badge variant="secondary" className="ml-2 border-primary/30">
                        {gen.mode}
                      </Badge>
                    </div>
                    <div className="flex items-center text-xs text-muted-foreground space-x-3">
                      <span className="flex items-center">
                        <Clock className="h-3 w-3 mr-1" />
                        {formatDate(gen.createdAt)}
                      </span>
                      <span>•</span>
                      <span>{credits} credits</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        if (imageUrl) {
                          const a = document.createElement("a")
                          a.href = imageUrl
                          a.download = `portrait-${gen.id}.jpg`
                          a.target = "_blank"
                          a.rel = "noopener"
                          a.click()
                        }
                      }}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon">
                      <Share2 className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

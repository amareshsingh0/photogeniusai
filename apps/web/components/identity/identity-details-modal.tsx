"use client"

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent } from "@/components/ui/card"
import {
  Image as ImageIcon,
  Sparkles,
  Download,
  Calendar,
  CheckCircle,
} from "lucide-react"
import Image from "next/image"

interface IdentityDetailsModalProps {
  identity: any
  isOpen: boolean
  onClose: () => void
}

export function IdentityDetailsModal({
  identity,
  isOpen,
  onClose,
}: IdentityDetailsModalProps) {
  const mockReferencePhotos = Array(identity.referencePhotos)
    .fill(null)
    .map((_, i) => `https://picsum.photos/seed/${identity.id}-${i}/400/400`)

  const mockGenerations = Array(Math.min(identity.generations, 12))
    .fill(null)
    .map((_, i) => ({
      id: `${identity.id}-gen-${i}`,
      image: `https://picsum.photos/seed/${identity.id}-gen-${i}/400/400`,
      prompt: "Sample generation prompt",
      createdAt: new Date(Date.now() - i * 86400000).toISOString(),
    }))

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto glass-card">
        <DialogHeader>
          <div className="flex items-start justify-between">
            <div>
              <DialogTitle className="text-2xl">{identity.name}</DialogTitle>
              <div className="flex items-center space-x-2 mt-2">
                <Badge variant="secondary" className={identity.status === "READY" ? "border-primary/30 bg-primary/10" : ""}>
                  {identity.status === "READY" ? (
                    <>
                      <CheckCircle className="h-3 w-3 mr-1" />
                      Ready
                    </>
                  ) : (
                    identity.status
                  )}
                </Badge>
                {identity.qualityScore && (
                  <Badge variant="secondary" className="border-primary/30">
                    Quality: {(identity.qualityScore * 100).toFixed(0)}%
                  </Badge>
                )}
              </div>
            </div>
            {identity.status === "READY" && (
              <Button>
                <Sparkles className="mr-2 h-4 w-4" />
                Generate
              </Button>
            )}
          </div>
        </DialogHeader>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <Card className="glass-card border-primary/20">
            <CardContent className="pt-6 text-center">
              <ImageIcon className="h-8 w-8 text-primary mx-auto mb-2" />
              <p className="text-2xl font-bold text-foreground">
                {identity.referencePhotos}
              </p>
              <p className="text-sm text-muted-foreground">Reference Photos</p>
            </CardContent>
          </Card>

          <Card className="glass-card border-secondary/20">
            <CardContent className="pt-6 text-center">
              <Sparkles className="h-8 w-8 text-secondary mx-auto mb-2" />
              <p className="text-2xl font-bold text-foreground">
                {identity.generations}
              </p>
              <p className="text-sm text-muted-foreground">Generations</p>
            </CardContent>
          </Card>

          <Card className="glass-card border-accent/20">
            <CardContent className="pt-6 text-center">
              <Calendar className="h-8 w-8 text-accent mx-auto mb-2" />
              <p className="text-2xl font-bold text-foreground">
                {new Date(identity.createdAt).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })}
              </p>
              <p className="text-sm text-muted-foreground">Created</p>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="reference">
          <TabsList className="w-full">
            <TabsTrigger value="reference" className="flex-1">
              Reference Photos ({identity.referencePhotos})
            </TabsTrigger>
            <TabsTrigger value="generations" className="flex-1">
              Generations ({identity.generations})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="reference" className="mt-6">
            <div className="grid grid-cols-4 gap-4">
              {mockReferencePhotos.map((photo, index) => (
                <div
                  key={index}
                  className="aspect-square relative rounded-lg overflow-hidden border border-border/50 group cursor-pointer hover:border-primary/50 transition-colors"
                >
                  <Image
                    src={photo}
                    alt={`Reference ${index + 1}`}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                  <div className="absolute inset-0 bg-background/80 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <Button variant="secondary" size="icon">
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="generations" className="mt-6">
            {mockGenerations.length === 0 ? (
              <div className="text-center py-12">
                <Sparkles className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  No generations yet with this identity
                </p>
                <Button className="mt-4">
                  Create Your First Generation
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-4">
                {mockGenerations.map((gen) => (
                  <div
                    key={gen.id}
                    className="aspect-square relative rounded-lg overflow-hidden border border-border/50 group cursor-pointer hover:border-primary/50 transition-colors"
                  >
                    <Image
                      src={gen.image}
                      alt="Generation"
                      fill
                      className="object-cover"
                      unoptimized
                    />
                    <div className="absolute inset-0 bg-background/80 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <Button variant="secondary" size="icon">
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}

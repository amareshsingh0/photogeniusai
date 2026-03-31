"use client"

import { useState } from "react"
import Image from "next/image"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  CheckCircle,
  Clock,
  AlertCircle,
  MoreVertical,
  Edit,
  Trash2,
  Download,
  Eye,
  Sparkles,
  Image as ImageIcon,
} from "lucide-react"
import { IdentityDetailsModal } from "./identity-details-modal"
import { RenameIdentityDialog } from "./rename-identity-dialog"
import { DeleteIdentityDialog } from "./delete-identity-dialog"
import { cn } from "@/lib/utils"

interface Identity {
  id: string
  name: string
  status: "READY" | "TRAINING" | "FAILED"
  progress: number
  createdAt: string
  referencePhotos: number
  generations: number
  qualityScore: number | null
  loraPath: string | null
  thumbnail: string
}

interface IdentityCardProps {
  identity: Identity
  onUpdate: (identity: Identity) => void
  onDelete: (id: string) => void
}

export function IdentityCard({ identity, onUpdate, onDelete }: IdentityCardProps) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [renameOpen, setRenameOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const statusConfig = {
    READY: {
      icon: CheckCircle,
      bgColor: "bg-primary/20",
      textColor: "text-primary",
      borderColor: "border-primary/30",
      label: "Ready",
    },
    TRAINING: {
      icon: Clock,
      bgColor: "bg-accent/20",
      textColor: "text-accent",
      borderColor: "border-accent/30",
      label: "Training",
    },
    FAILED: {
      icon: AlertCircle,
      bgColor: "bg-destructive/20",
      textColor: "text-destructive",
      borderColor: "border-destructive/30",
      label: "Failed",
    },
  }

  const status = statusConfig[identity.status]
  const StatusIcon = status.icon

  return (
    <>
      <Card className="glass-card overflow-hidden hover:shadow-lg transition-shadow border-border/50">
        <CardContent className="p-0">
          {/* Thumbnail */}
          <div className="relative aspect-square">
            <Image
              src={identity.thumbnail}
              alt={identity.name}
              fill
              className="object-cover"
              unoptimized
            />
            {/* Status Badge */}
            <div className="absolute top-3 left-3">
              <Badge
                variant="secondary"
                className={cn(
                  "border",
                  status.bgColor,
                  status.textColor,
                  status.borderColor
                )}
              >
                <StatusIcon className={cn("h-3 w-3 mr-1", status.textColor)} />
                {status.label}
              </Badge>
            </div>
            {/* Actions Menu */}
            <div className="absolute top-3 right-3">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="secondary"
                    size="icon"
                    className="h-8 w-8 bg-background/90 hover:bg-background border border-border/50"
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="glass-card">
                  <DropdownMenuItem onClick={() => setDetailsOpen(true)}>
                    <Eye className="h-4 w-4 mr-2" />
                    View Details
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setRenameOpen(true)}>
                    <Edit className="h-4 w-4 mr-2" />
                    Rename
                  </DropdownMenuItem>
                  {identity.status === "READY" && (
                    <DropdownMenuItem>
                      <Download className="h-4 w-4 mr-2" />
                      Download LoRA
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => setDeleteOpen(true)}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {/* Details */}
          <div className="p-4 space-y-3">
            {/* Name */}
            <div>
              <h3 className="font-semibold text-foreground text-lg">
                {identity.name}
              </h3>
              <p className="text-sm text-muted-foreground">
                Created {new Date(identity.createdAt).toLocaleDateString()}
              </p>
            </div>

            {/* Training Progress */}
            {identity.status === "TRAINING" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Training Progress</span>
                  <span className={cn("font-semibold", status.textColor)}>
                    {identity.progress}%
                  </span>
                </div>
                <Progress value={identity.progress} className="h-2" />
              </div>
            )}

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border/50">
              <div>
                <div className="flex items-center space-x-1 text-muted-foreground mb-1">
                  <ImageIcon className="h-4 w-4" />
                  <span className="text-xs">Photos</span>
                </div>
                <p className="text-lg font-semibold text-foreground">
                  {identity.referencePhotos}
                </p>
              </div>
              <div>
                <div className="flex items-center space-x-1 text-muted-foreground mb-1">
                  <Sparkles className="h-4 w-4" />
                  <span className="text-xs">Generations</span>
                </div>
                <p className="text-lg font-semibold text-foreground">
                  {identity.generations}
                </p>
              </div>
            </div>

            {/* Quality Score */}
            {identity.qualityScore !== null && (
              <div className="pt-2 border-t border-border/50">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Quality Score</span>
                  <Badge variant="secondary" className="border-primary/30">
                    {(identity.qualityScore * 100).toFixed(0)}%
                  </Badge>
                </div>
              </div>
            )}

            {/* Action Button */}
            {identity.status === "READY" && (
              <Button
                className="w-full"
                onClick={() => {
                  // Navigate to generate page with this identity
                  window.location.href = `/generate?identity=${identity.id}`
                }}
              >
                <Sparkles className="mr-2 h-4 w-4" />
                Generate with this Identity
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Modals */}
      <IdentityDetailsModal
        identity={identity}
        isOpen={detailsOpen}
        onClose={() => setDetailsOpen(false)}
      />

      <RenameIdentityDialog
        identity={identity}
        isOpen={renameOpen}
        onClose={() => setRenameOpen(false)}
        onRename={(newName) => {
          onUpdate({ ...identity, name: newName })
          setRenameOpen(false)
        }}
      />

      <DeleteIdentityDialog
        identity={identity}
        isOpen={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onDelete={() => {
          onDelete(identity.id)
          setDeleteOpen(false)
        }}
      />
    </>
  )
}

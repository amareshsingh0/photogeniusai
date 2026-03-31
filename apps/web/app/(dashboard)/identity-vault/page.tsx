"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import {
  Plus,
  Users,
  Clock,
  Sparkles,
  MoreVertical,
  Trash2,
  ArrowRight,
  Loader2,
  CheckCircle,
  Play,
  AlertCircle,
} from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { CreateIdentityModal } from "@/components/identity/create-identity-modal"
import { DeleteIdentityDialog } from "@/components/identity/delete-identity-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useToast } from "@/components/ui/use-toast"

const MIN_PHOTOS_FOR_TRAINING = 8

interface Identity {
  id: string
  name: string
  status: "PENDING" | "TRAINING" | "READY" | "FAILED"
  imageUrls: string[]
  createdAt: string
  /** 0–100 when READY; optional from API */
  consistencyScore?: number
  /** 0–100 when TRAINING; optional from API */
  trainingProgress?: number
}

export default function IdentityVaultPage() {
  const [identities, setIdentities] = useState<Identity[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [trainingIds, setTrainingIds] = useState<Set<string>>(new Set())
  const [identityToDelete, setIdentityToDelete] = useState<Identity | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    async function fetchIdentities() {
      try {
        const response = await fetch("/api/identities")
        if (response.ok) {
          const data = await response.json()
          setIdentities(Array.isArray(data) ? data : [])
        }
      } catch (err) {
        console.error("Failed to fetch identities:", err)
      } finally {
        setIsLoading(false)
      }
    }
    fetchIdentities()
  }, [])

  const handleDeleteClick = (identity: Identity) => {
    setIdentityToDelete(identity)
  }

  const handleDeleteConfirm = async (hardErase: boolean) => {
    if (!identityToDelete) return
    const id = identityToDelete.id
    setIsDeleting(true)
    try {
      const url = hardErase ? `/api/identities/${id}?hard=true` : `/api/identities/${id}`
      const response = await fetch(url, { method: "DELETE" })
      if (response.ok) {
        setIdentities((prev) => prev.filter((i) => i.id !== id))
        setIdentityToDelete(null)
        toast({ title: "Identity deleted", description: "It has been removed from your vault." })
      } else {
        const data = await response.json().catch(() => ({}))
        toast({ title: "Delete failed", description: data.error || "Could not delete identity.", variant: "destructive" })
      }
    } catch (err) {
      console.error("Failed to delete identity:", err)
      toast({ title: "Delete failed", description: "Something went wrong.", variant: "destructive" })
    } finally {
      setIsDeleting(false)
    }
  }

  const handleStartTraining = async (id: string) => {
    setTrainingIds((prev) => new Set(prev).add(id))
    try {
      const response = await fetch(`/api/identities/${id}/train`, {
        method: "POST",
      })
      if (response.ok) {
        // Update the identity status to TRAINING
        setIdentities((prev) =>
          prev.map((identity) =>
            identity.id === id ? { ...identity, status: "TRAINING" as const } : identity
          )
        )
      } else {
        const error = await response.json()
        console.error("Training failed:", error)
        alert(error.error || "Failed to start training")
      }
    } catch (err) {
      console.error("Failed to start training:", err)
      alert("Failed to start training")
    } finally {
      setTrainingIds((prev) => {
        const newSet = new Set(prev)
        newSet.delete(id)
        return newSet
      })
    }
  }

  const getThumbnail = (identity: Identity) => {
    if (identity.imageUrls?.length > 0) return identity.imageUrls[0]
    return `https://picsum.photos/seed/${identity.id}/400/400`
  }

  const getStatusInfo = (status: string) => {
    switch (status) {
      case "READY":
        return { label: "Ready", color: "text-emerald-500 bg-emerald-500/10", icon: CheckCircle }
      case "TRAINING":
        return { label: "Training", color: "text-amber-500 bg-amber-500/10", icon: Loader2 }
      case "PENDING":
        return { label: "Pending", color: "text-blue-500 bg-blue-500/10", icon: Clock }
      default:
        return { label: "Failed", color: "text-red-500 bg-red-500/10", icon: Clock }
    }
  }

  const readyCount = identities.filter((i) => i.status === "READY").length
  const trainingCount = identities.filter((i) => i.status === "TRAINING").length

  return (
    <div className="identity-page-bg min-h-screen">
      <div className="max-w-5xl mx-auto space-y-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4"
      >
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground tracking-tight flex items-center gap-2">
            <span className="inline-flex p-2 rounded-xl bg-primary/10 relative">
              <span className="identity-scan-ring" aria-hidden />
              <Users className="h-6 w-6 text-primary relative z-10" />
            </span>
            <span className="gradient-text">Identity Vault</span>
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            📸 Upload photos → 🧠 AI trains → ✨ Use in generations
          </p>
        </div>
        <Button
          onClick={() => setCreateModalOpen(true)}
          variant="outline"
          className="shrink-0 rounded-xl border-white/15 bg-white/[0.04] hover:bg-white/[0.08] text-foreground"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Identity
        </Button>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05 }}
        className="grid grid-cols-2 sm:grid-cols-3 gap-4"
      >
        <div className="identity-stat-card p-5 rounded-2xl">
          <p className="text-2xl font-bold tabular-nums text-foreground">{identities.length}</p>
          <p className="text-xs text-muted-foreground font-medium">Total</p>
        </div>
        <div
          className={cn(
            "identity-stat-card p-5 rounded-2xl transition-colors",
            readyCount > 0 && "identity-stat-ready"
          )}
        >
          <p
            className={cn(
              "text-2xl font-bold tabular-nums",
              readyCount > 0 ? "text-emerald-400" : "text-muted-foreground"
            )}
          >
            {readyCount}
          </p>
          <p className="text-xs text-muted-foreground font-medium">Ready</p>
        </div>
        <div
          className={cn(
            "identity-stat-card p-5 rounded-2xl hidden sm:block",
            trainingCount > 0 && "identity-stat-training identity-training"
          )}
        >
          <p
            className={cn(
              "text-2xl font-bold tabular-nums",
              trainingCount > 0 ? "text-amber-400" : "text-muted-foreground"
            )}
          >
            {trainingCount}
          </p>
          <p className="text-xs text-muted-foreground font-medium">Training</p>
          {trainingCount > 0 && (
            <p className="text-xs text-amber-400/90 mt-1">
              Training • — ≈15–20 min remaining
            </p>
          )}
        </div>
      </motion.div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="aspect-[4/5] rounded-2xl shimmer" />
          ))}
        </div>
      ) : identities.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="identity-empty-state text-center py-16 rounded-2xl"
        >
          <div className="flex justify-center gap-6 mb-8">
            {[1, 2, 3].map((i) => (
              <button
                key={i}
                type="button"
                onClick={() => setCreateModalOpen(true)}
                className="w-24 h-28 rounded-2xl border-2 border-dashed border-white/15 bg-white/[0.02] flex items-center justify-center hover:border-white/25 hover:bg-white/[0.04] transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <Plus className="h-8 w-8 text-muted-foreground/60" />
              </button>
            ))}
          </div>
          <p className="text-sm text-muted-foreground mb-8">Your identities will appear here</p>
          <div className="flex flex-wrap justify-center gap-6 text-left mb-8 max-w-md mx-auto">
            <div className="flex items-center gap-2">
              <span className="text-lg">📸</span>
              <span className="text-sm text-muted-foreground">Upload 8–20 photos</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-lg">🧠</span>
              <span className="text-sm text-muted-foreground">AI learns your face</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-lg">✨</span>
              <span className="text-sm text-muted-foreground">Generate consistent faces forever</span>
            </div>
          </div>
          <Button onClick={() => setCreateModalOpen(true)} className="identity-primary-btn text-white rounded-xl px-8 py-6 text-base font-semibold border-0">
            <Plus className="h-5 w-5 mr-2" />
            Create First Identity
          </Button>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {identities.map((identity, idx) => {
            const statusInfo = getStatusInfo(identity.status)
            const StatusIcon = statusInfo.icon
            const isReady = identity.status === "READY"

            return (
              <motion.div
                key={identity.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: Math.min(idx * 0.05, 0.15) }}
                className="group relative rounded-2xl glass-card border border-white/[0.06] overflow-hidden hover:border-white/15 transition-colors"
              >
                {/* Image */}
                <div className="aspect-square relative">
                  <Image
                    src={getThumbnail(identity)}
                    alt={identity.name}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                  {/* Gradient Overlay */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />

                  {/* Status Badge */}
                  <div className={cn(
                    "absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium",
                    statusInfo.color
                  )}>
                    <StatusIcon className={cn("h-3 w-3", identity.status === "TRAINING" && "animate-spin")} />
                    {statusInfo.label}
                  </div>

                  {/* Menu */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="absolute top-2 right-2 h-8 w-8 bg-black/40 hover:bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => handleDeleteClick(identity)}
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>

                  {/* Bottom Info */}
                  <div className="absolute bottom-0 left-0 right-0 p-4">
                    <h3 className="text-lg font-semibold text-white mb-1">
                      {identity.name}
                    </h3>
                    <p className="text-xs text-white/70">
                      {identity.imageUrls?.length || 0} reference photos
                    </p>
                  </div>
                </div>

                {/* Face Consistency — READY only */}
                {isReady && (
                  <div className="px-4 py-2 border-t border-white/[0.06]">
                    <p className="text-xs text-muted-foreground flex justify-between mb-1">
                      <span>Face Consistency</span>
                      <span className="font-medium text-foreground">
                        {identity.consistencyScore ?? 92}%
                      </span>
                    </p>
                    <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-emerald-500/80 transition-all duration-500"
                        style={{ width: `${identity.consistencyScore ?? 92}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Action */}
                {isReady && (
                  <div className="p-3 border-t border-white/[0.06]">
                    <Link href={`/generate?identity=${identity.id}`}>
                      <Button variant="ghost" size="sm" className="w-full justify-between rounded-xl text-muted-foreground hover:text-foreground">
                        <span className="flex items-center gap-2">
                          <Sparkles className="h-4 w-4" />
                          Generate with this identity
                        </span>
                        <ArrowRight className="h-4 w-4" />
                      </Button>
                    </Link>
                  </div>
                )}

                {identity.status === "TRAINING" && (
                  <div className="p-3 border-t border-white/[0.06]">
                    <div className="flex items-center gap-2 text-amber-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm">Training in progress...</span>
                    </div>
                  </div>
                )}

                {identity.status === "PENDING" && (
                  <div className="p-3 border-t border-white/[0.06]">
                    {(identity.imageUrls?.length || 0) >= MIN_PHOTOS_FOR_TRAINING ? (
                      <Button
                        onClick={() => handleStartTraining(identity.id)}
                        disabled={trainingIds.has(identity.id)}
                        className="w-full btn-premium text-white"
                        size="sm"
                      >
                        {trainingIds.has(identity.id) ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Starting...
                          </>
                        ) : (
                          <>
                            <Play className="h-4 w-4 mr-2" />
                            Start Training
                          </>
                        )}
                      </Button>
                    ) : (
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <AlertCircle className="h-4 w-4 text-amber-500" />
                        <span className="text-xs">
                          Need {MIN_PHOTOS_FOR_TRAINING - (identity.imageUrls?.length || 0)} more photos
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {identity.status === "FAILED" && (
                  <div className="p-3 border-t border-white/[0.06]">
                    <Button
                      onClick={() => handleStartTraining(identity.id)}
                      disabled={trainingIds.has(identity.id)}
                      variant="outline"
                      className="w-full rounded-xl"
                      size="sm"
                    >
                      {trainingIds.has(identity.id) ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Retrying...
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4 mr-2" />
                          Retry Training
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </motion.div>
            )
          })}
        </motion.div>
      )}

      {trainingCount > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-5 rounded-2xl glass-card border border-amber-500/20"
        >
          <div className="flex items-start gap-3">
            <Clock className="h-5 w-5 text-amber-500 mt-0.5" />
            <div>
              <h4 className="font-medium text-foreground">Training in Progress</h4>
              <p className="text-sm text-muted-foreground mt-1">
                {trainingCount} {trainingCount === 1 ? "identity is" : "identities are"} being trained. This usually takes 15-20 minutes. You can close this page - training continues in the background.
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Create Modal */}
      <CreateIdentityModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={(newIdentity: any) => {
          setIdentities((prev) => [newIdentity, ...prev])
          setCreateModalOpen(false)
        }}
      />

      {/* Delete confirmation */}
      <DeleteIdentityDialog
        identity={identityToDelete ? { ...identityToDelete, imageUrls: identityToDelete.imageUrls } : null}
        isOpen={!!identityToDelete}
        onClose={() => !isDeleting && setIdentityToDelete(null)}
        onDelete={handleDeleteConfirm}
        isDeleting={isDeleting}
      />
      </div>
    </div>
  )
}

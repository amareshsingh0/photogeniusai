"use client"

import { useState, useEffect } from "react"
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

  const statusMeta = (status: string) => {
    switch (status) {
      case "READY": return { label: "Ready", dot: "bg-emerald-500/80", icon: CheckCircle }
      case "TRAINING": return { label: "Training", dot: "bg-amber-500/80", icon: Loader2 }
      case "PENDING": return { label: "Pending", dot: "bg-white/40", icon: Clock }
      default: return { label: "Failed", dot: "bg-red-500/80", icon: AlertCircle }
    }
  }

  const readyCount = identities.filter((i) => i.status === "READY").length
  const trainingCount = identities.filter((i) => i.status === "TRAINING").length
  const photosTrained = identities.filter((i) => i.status === "READY").reduce((n, i) => n + (i.imageUrls?.length || 0), 0)

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-24 space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <Users className="h-5 w-5 text-white/60" />
          <div>
            <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Identity Vault</h1>
            <p className="mt-1 text-sm text-white/50">Upload photos → AI trains → use in generations.</p>
          </div>
        </div>
        <button
          onClick={() => setCreateModalOpen(true)}
          className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-black transition"
          style={{ background: "var(--gradient-aurora)" }}
        >
          <Plus className="h-4 w-4" /> New identity
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "TOTAL", value: identities.length },
          { label: "READY", value: readyCount },
          { label: "TRAINING", value: trainingCount },
          { label: "PHOTOS TRAINED", value: photosTrained },
        ].map((s) => (
          <div key={s.label} className="glass-panel rounded-2xl p-4">
            <p className="kerned text-white/40 mb-2">{s.label}</p>
            <p className="font-mono text-3xl text-aurora">{s.value}</p>
          </div>
        ))}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => <div key={i} className="aspect-[4/5] animate-pulse rounded-2xl bg-white/[0.02]" />)}
        </div>
      ) : identities.length === 0 ? (
        <div className="glass-panel rounded-2xl p-12 text-center">
          <h3 className="font-display text-2xl tracking-tight">Create your first identity</h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-white/50">
            Upload 8–20 photos, let the AI learn the face, then generate consistent likenesses forever.
          </p>
          <Link
            href="/identity-vault/new"
            className="mt-5 inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-black transition"
            style={{ background: "var(--gradient-aurora)" }}
          >
            <Plus className="h-4 w-4" /> Create identity
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {identities.map((identity) => {
            const meta = statusMeta(identity.status)
            const isReady = identity.status === "READY"
            const photos = identity.imageUrls?.length || 0
            return (
              <div key={identity.id} className="glass-panel group relative overflow-hidden rounded-2xl p-4 transition hover:-translate-y-0.5">
                <div className="flex items-start gap-3">
                  <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-white/[0.04]">
                    {photos > 0 ? (
                      <Image src={getThumbnail(identity)} alt={identity.name} fill className="object-cover" unoptimized />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center"><Users className="h-6 w-6 text-white/30" /></div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-display text-lg tracking-tight truncate">{identity.name}</h3>
                      <DropdownMenu>
                        <DropdownMenuTrigger className="rounded-lg p-1 text-white/30 opacity-0 transition hover:text-white/70 group-hover:opacity-100">
                          <MoreVertical className="h-4 w-4" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem className="text-red-300 focus:text-red-300" onClick={() => handleDeleteClick(identity)}>
                            <Trash2 className="mr-2 h-4 w-4" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-white/70 inline-flex items-center gap-1.5">
                        <span className={cn("h-2 w-2 rounded-full", meta.dot)} />
                        {meta.label}
                      </span>
                      <span className="font-mono text-[10px] text-white/60">{photos} photos</span>
                    </div>
                  </div>
                </div>

                {isReady && (
                  <div className="mt-4">
                    <div className="mb-1 flex justify-between text-xs text-white/50">
                      <span>Consistency</span>
                      <span className="font-mono text-[11px] text-white/70">{identity.consistencyScore ?? 92}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/10">
                      <div className="h-full rounded-full bg-white/70 transition-all duration-500" style={{ width: `${identity.consistencyScore ?? 92}%` }} />
                    </div>
                  </div>
                )}

                {identity.status === "TRAINING" && (
                  <div className="mt-4 flex items-center gap-2 text-sm text-amber-300">
                    <Loader2 className="h-4 w-4 animate-spin" /> Training in progress…
                  </div>
                )}

                {identity.status === "PENDING" && (
                  <div className="mt-4">
                    {photos >= MIN_PHOTOS_FOR_TRAINING ? (
                      <button
                        onClick={() => handleStartTraining(identity.id)}
                        disabled={trainingIds.has(identity.id)}
                        className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition disabled:opacity-50"
                      >
                        {trainingIds.has(identity.id) ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                        {trainingIds.has(identity.id) ? "Starting…" : "Start training"}
                      </button>
                    ) : (
                      <p className="flex items-center gap-2 text-xs text-white/50">
                        <AlertCircle className="h-3.5 w-3.5 text-amber-400" />
                        Need {MIN_PHOTOS_FOR_TRAINING - photos} more photos
                      </p>
                    )}
                  </div>
                )}

                {identity.status === "FAILED" && (
                  <div className="mt-4">
                    <button
                      onClick={() => handleStartTraining(identity.id)}
                      disabled={trainingIds.has(identity.id)}
                      className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition disabled:opacity-50"
                    >
                      {trainingIds.has(identity.id) ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                      {trainingIds.has(identity.id) ? "Retrying…" : "Retry training"}
                    </button>
                  </div>
                )}

                <div className="mt-4 flex items-center gap-2">
                  <Link href={`/identity-vault/${identity.id}`} className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition">
                    Open
                  </Link>
                  {isReady && (
                    <Link href={`/generate?identity=${identity.id}`} className="flex flex-1 items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition">
                      <span className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" /> Generate</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {trainingCount > 0 && (
        <div className="glass-panel rounded-2xl p-4">
          <div className="flex items-start gap-3">
            <Clock className="mt-0.5 h-4 w-4 text-amber-400" />
            <div>
              <p className="text-sm text-white/85">Training in progress</p>
              <p className="mt-1 text-sm text-white/50">
                {trainingCount} {trainingCount === 1 ? "identity is" : "identities are"} being trained. This usually takes 15–20 minutes — you can close this page.
              </p>
            </div>
          </div>
        </div>
      )}

      <CreateIdentityModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={(newIdentity: any) => {
          setIdentities((prev) => [newIdentity, ...prev])
          setCreateModalOpen(false)
        }}
      />

      <DeleteIdentityDialog
        identity={identityToDelete ? { ...identityToDelete, imageUrls: identityToDelete.imageUrls } : null}
        isOpen={!!identityToDelete}
        onClose={() => !isDeleting && setIdentityToDelete(null)}
        onDelete={handleDeleteConfirm}
        isDeleting={isDeleting}
      />
    </div>
  )
}

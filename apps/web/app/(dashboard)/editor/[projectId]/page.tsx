'use client'

/**
 * Canvas Editor Page — /editor/[projectId]
 *
 * Full-screen Fabric.js editor for poster projects.
 * - Loads PosterProject from DB on mount
 * - Auto-saves canvas state every 2s (debounced)
 * - Exports full-resolution PNG
 * - "Back to Gallery" and "Download Pack" in header
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Loader2, Package, Share2, MoreHorizontal } from 'lucide-react'
import dynamic from 'next/dynamic'
import type { DesignBrief } from '@/lib/canvas-bridge'

// Dynamically import CanvasEditor (Fabric.js won't run SSR)
const CanvasEditor = dynamic(
  () => import('@/components/canvas-editor').then((m) => m.CanvasEditor),
  { ssr: false, loading: () => <EditorSkeleton /> },
)
const PosterPackModal = dynamic(
  () => import('@/components/poster-pack-modal').then((m) => m.PosterPackModal),
  { ssr: false },
)

// ── Types ─────────────────────────────────────────────────────────────────────

interface PosterProject {
  id:           string
  name:         string
  canvasState:  object | null
  designBrief:  DesignBrief | null
  heroUrl:      string | null
  thumbnail:    string | null
  width:        number
  height:       number
  platform:     string | null
  juryScore:    number | null
  juryGrade:    string | null
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function EditorPage() {
  const params = useParams<{ projectId: string }>()
  const router = useRouter()
  const projectId = params.projectId

  const [project, setProject]       = useState<PosterProject | null>(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [projectName, setName]      = useState('Untitled Poster')
  const [editingName, setEditName]  = useState(false)
  const [showPack, setShowPack]     = useState(false)
  const [saved, setSaved]           = useState<'idle' | 'saving' | 'saved'>('idle')

  const autoSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Load project ───────────────────────────────────────────────────────────

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`/api/projects/${projectId}`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setProject(data.project)
        setName(data.project.name || 'Untitled Poster')
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [projectId])

  // ── Auto-save ──────────────────────────────────────────────────────────────

  const handleSave = useCallback(async ({
    canvasJson, thumbnailDataUrl,
  }: { canvasJson: object; thumbnailDataUrl: string }) => {
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current)
    setSaved('saving')
    autoSaveRef.current = setTimeout(async () => {
      try {
        await fetch(`/api/projects/${projectId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            canvasState:  canvasJson,
            thumbnail:    thumbnailDataUrl,
            name:         projectName,
          }),
        })
        setSaved('saved')
        setTimeout(() => setSaved('idle'), 2000)
      } catch {
        setSaved('idle')
      }
    }, 2000)
  }, [projectId, projectName])

  // ── Rename ────────────────────────────────────────────────────────────────

  const handleRename = async (newName: string) => {
    setName(newName)
    setEditName(false)
    await fetch(`/api/projects/${projectId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName }),
    })
  }

  // ── Render states ─────────────────────────────────────────────────────────

  if (loading) return <EditorSkeleton />
  if (error || !project) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center px-4">
        <div className="glass-panel rounded-2xl p-8 text-center">
          <p className="mb-4 text-sm text-red-300">{error || 'Project not found'}</p>
          <button
            onClick={() => router.push('/gallery')}
            className="rounded-xl px-4 py-2 text-sm font-medium text-black"
            style={{ background: 'var(--gradient-aurora)' }}
          >
            Back to Gallery
          </button>
        </div>
      </div>
    )
  }

  const brief = project.designBrief ?? {}
  const heroUrl = project.heroUrl ?? ''

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col overflow-hidden">
      {/* Top header */}
      <header className="glass-panel z-10 flex h-12 shrink-0 items-center gap-3 rounded-2xl px-4">
        {/* Back */}
        <button
          onClick={() => router.push('/gallery')}
          className="flex items-center gap-1.5 text-xs text-white/55 transition hover:text-white"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>

        <div className="h-5 w-px bg-white/10" />

        {/* Project name */}
        {editingName ? (
          <input
            autoFocus
            defaultValue={projectName}
            onBlur={(e) => handleRename(e.target.value || 'Untitled')}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleRename((e.target as HTMLInputElement).value || 'Untitled')
              if (e.key === 'Escape') setEditName(false)
            }}
            className="w-48 rounded-lg border border-white/10 bg-black/20 px-2 py-0.5 font-display text-sm outline-none focus:border-white/30"
          />
        ) : (
          <button
            onClick={() => setEditName(true)}
            className="max-w-[200px] truncate font-display text-sm text-white/85 transition hover:text-white"
            title="Click to rename"
          >
            {projectName}
          </button>
        )}

        {/* Platform badge */}
        {project.platform && (
          <span className="kerned shrink-0 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-white/50">
            {project.platform}
          </span>
        )}

        {/* Jury score */}
        {project.juryGrade && (
          <span className="kerned shrink-0 rounded-full border border-white/10 bg-white/10 px-2 py-0.5 text-white/70">
            Grade {project.juryGrade}
          </span>
        )}

        {/* Save status */}
        <div className="flex-1" />
        <span className="kerned shrink-0 text-white/30">
          {saved === 'saving' ? 'Saving…' : saved === 'saved' ? 'Saved' : ''}
        </span>

        {/* Actions */}
        <button
          onClick={() => setShowPack(true)}
          className="flex shrink-0 items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/75 transition hover:bg-white/10 hover:text-white"
        >
          <Package className="h-3.5 w-3.5" />
          Download Pack
        </button>
      </header>

      {/* Canvas Editor */}
      <div className="mt-2 flex-1 overflow-hidden rounded-2xl hairline">
        <CanvasEditor
          designBrief={brief as DesignBrief}
          heroImageSrc={heroUrl}
          projectId={projectId}
          canvasWidth={project.width}
          canvasHeight={project.height}
          onSave={handleSave}
          className="h-full"
        />
      </div>

      {/* Pack Modal */}
      {showPack && project.heroUrl && brief.ad_copy && (
        <PosterPackModal
          open={showPack}
          heroUrl={project.heroUrl}
          adCopy={brief.ad_copy as any}
          posterDesign={(brief.poster_design || {}) as any}
          onClose={() => setShowPack(false)}
        />
      )}
    </div>
  )
}

// ── Skeleton ───────────────────────────────────────────────────────────────────

function EditorSkeleton() {
  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col">
      <div className="glass-panel flex h-12 items-center gap-3 rounded-2xl px-4">
        <div className="h-4 w-16 animate-pulse rounded bg-white/5" />
        <div className="h-4 w-40 animate-pulse rounded bg-white/5" />
      </div>
      <div className="mt-2 flex flex-1 gap-2">
        <div className="w-52 animate-pulse rounded-2xl bg-white/[0.03]" />
        <div className="flex flex-1 items-center justify-center rounded-2xl hairline">
          <Loader2 className="h-8 w-8 animate-spin text-white/30" />
        </div>
        <div className="w-60 animate-pulse rounded-2xl bg-white/[0.03]" />
      </div>
    </div>
  )
}

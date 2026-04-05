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
      <div className="h-screen flex items-center justify-center bg-[#0A0A0F] text-white">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error || 'Project not found'}</p>
          <button onClick={() => router.push('/generate')} className="text-sm text-white/50 underline">
            Back to Generate
          </button>
        </div>
      </div>
    )
  }

  const brief = project.designBrief ?? {}
  const heroUrl = project.heroUrl ?? ''

  return (
    <div className="h-screen flex flex-col bg-[#0A0A0F] overflow-hidden">
      {/* Top header */}
      <header className="h-12 flex items-center gap-3 px-4 bg-[#0E0E16] border-b border-white/8 shrink-0 z-10">
        {/* Back */}
        <button
          onClick={() => router.push('/generate')}
          className="flex items-center gap-1.5 text-xs text-white/50 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back
        </button>

        <div className="w-px h-5 bg-white/10" />

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
            className="bg-white/10 text-white text-sm font-semibold rounded px-2 py-0.5 focus:outline-none focus:bg-white/15 w-48"
          />
        ) : (
          <button
            onClick={() => setEditName(true)}
            className="text-sm font-semibold text-white/80 hover:text-white transition-colors truncate max-w-[200px]"
            title="Click to rename"
          >
            {projectName}
          </button>
        )}

        {/* Platform badge */}
        {project.platform && (
          <span className="text-xs text-white/30 bg-white/5 px-2 py-0.5 rounded-full border border-white/8 shrink-0">
            {project.platform}
          </span>
        )}

        {/* Jury score */}
        {project.juryGrade && (
          <span className={[
            'text-xs font-bold px-2 py-0.5 rounded-full shrink-0',
            project.juryGrade === 'A' ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
            project.juryGrade === 'B' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
            project.juryGrade === 'C' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
            'bg-red-500/20 text-red-400 border border-red-500/30',
          ].join(' ')}>
            Grade {project.juryGrade}
          </span>
        )}

        {/* Save status */}
        <div className="flex-1" />
        <span className="text-xs text-white/25 shrink-0">
          {saved === 'saving' ? '⟳ Saving...' : saved === 'saved' ? '✓ Saved' : ''}
        </span>

        {/* Actions */}
        <button
          onClick={() => setShowPack(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/8 hover:bg-white/15 border border-white/10 text-white/70 hover:text-white text-xs font-medium transition-colors shrink-0"
        >
          <Package className="w-3.5 h-3.5" />
          Download Pack
        </button>
      </header>

      {/* Canvas Editor */}
      <div className="flex-1 overflow-hidden">
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
    <div className="h-screen flex flex-col bg-[#0A0A0F]">
      <div className="h-12 bg-[#0E0E16] border-b border-white/8 flex items-center px-4 gap-3">
        <div className="w-16 h-4 bg-white/5 rounded animate-pulse" />
        <div className="w-40 h-4 bg-white/5 rounded animate-pulse" />
      </div>
      <div className="flex flex-1">
        <div className="w-52 bg-[#13131A] border-r border-white/8 animate-pulse" />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-purple-400/50" />
        </div>
        <div className="w-60 bg-[#13131A] border-l border-white/8 animate-pulse" />
      </div>
    </div>
  )
}

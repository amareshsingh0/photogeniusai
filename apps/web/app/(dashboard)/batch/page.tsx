'use client'

import React, { useState, useEffect, useRef } from 'react'
import {
  Zap, Plus, Trash2, Play, X, CheckCircle2,
  AlertCircle, Loader2, Download, ChevronDown, ChevronUp,
} from 'lucide-react'

interface TaskInput {
  id:       string
  prompt:   string
  quality:  string
  platform: string
}

interface TaskStatus {
  id:         string
  prompt:     string
  status:     'pending' | 'running' | 'done' | 'failed'
  image_url?: string
  error?:     string
  platform:   string
}

interface JobStatus {
  job_id:  string
  name:    string
  status:  string
  total:   number
  done:    number
  failed:  number
  pending: number
  tasks:   TaskStatus[]
}

const QUALITY_OPTIONS = [
  { key: 'fast',     label: 'Fast'    },
  { key: 'balanced', label: 'Quality' },
  { key: 'ultra',    label: 'Ultra'   },
]
const PLATFORMS = ['instagram', 'linkedin', 'twitter', 'general']

function makeId() { return Math.random().toString(36).slice(2, 9) }

const STATUS_ICON = {
  pending: <div className="h-4 w-4 rounded-full border-2 border-white/15" />,
  running: <Loader2 className="h-4 w-4 animate-spin text-white/60" />,
  done:    <CheckCircle2 className="h-4 w-4 text-emerald-400" />,
  failed:  <AlertCircle  className="h-4 w-4 text-red-400" />,
}

export default function BatchPage() {
  const [jobName,  setJobName]  = useState('My Batch Job')
  const [inputs,   setInputs]   = useState<TaskInput[]>([
    { id: makeId(), prompt: '', quality: 'balanced', platform: 'instagram' },
  ])
  const [running,  setRunning]  = useState(false)
  const [job,      setJob]      = useState<JobStatus | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const pollRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (!job || job.status === 'done' || job.status === 'cancelled' || job.status === 'failed') {
      if (pollRef.current) clearInterval(pollRef.current)
      if (job?.status === 'done') setRunning(false)
      return
    }
    pollRef.current = setInterval(async () => {
      try {
        const res  = await fetch(`/api/batch/${job.job_id}`)
        const data = await res.json()
        setJob(data)
      } catch { /* silent */ }
    }, 3000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [job])

  const addTask    = () => setInputs(p => [...p, { id: makeId(), prompt: '', quality: 'balanced', platform: 'instagram' }])
  const removeTask = (id: string) => setInputs(p => p.filter(t => t.id !== id))
  const updateTask = (id: string, key: keyof TaskInput, val: string) =>
    setInputs(p => p.map(t => t.id === id ? { ...t, [key]: val } : t))

  const startBatch = async () => {
    const valid = inputs.filter(t => t.prompt.trim())
    if (!valid.length) return
    setRunning(true)
    setJob(null)
    try {
      const res  = await fetch('/api/batch/start', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          name:  jobName,
          tasks: valid.map(t => ({ prompt: t.prompt.trim(), quality: t.quality, platform: t.platform })),
        }),
      })
      const data = await res.json()
      if (data.job_id) {
        setJob({ job_id: data.job_id, name: jobName, status: 'running',
          total: data.total, done: 0, failed: 0, pending: data.total, tasks: [] })
      }
    } catch { setRunning(false) }
  }

  const cancelJob = async () => {
    if (!job) return
    await fetch(`/api/batch/${job.job_id}`, { method: 'DELETE' })
    setJob(p => p ? { ...p, status: 'cancelled' } : p)
    setRunning(false)
  }

  const progress = job ? Math.round(((job.done + job.failed) / Math.max(job.total, 1)) * 100) : 0
  const validCount = inputs.filter(t => t.prompt.trim()).length

  const Pill = ({ active, children, onClick, disabled }: { active: boolean; children: React.ReactNode; onClick: () => void; disabled?: boolean }) => (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded-full px-2.5 py-1 text-[11px] transition disabled:opacity-40 ${active ? 'bg-white text-black' : 'bg-white/5 text-white/70 hover:bg-white/10'}`}
    >
      {children}
    </button>
  )

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-24">
      <div className="mb-6 flex items-center gap-3">
        <Zap className="h-5 w-5 text-white/60" />
        <div>
          <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Batch Generate</h1>
          <p className="mt-1 text-sm text-white/50">Run up to 50 prompts — max 3 concurrently.</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Compose */}
        <div className="glass-panel rounded-2xl p-5 space-y-5">
          <p className="kerned text-white/40 mb-2">COMPOSE</p>

          <div>
            <p className="kerned text-white/40 mb-2">JOB NAME</p>
            <input
              value={jobName}
              onChange={e => setJobName(e.target.value)}
              disabled={running}
              className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30 disabled:opacity-40"
            />
          </div>

          <div className="space-y-3">
            <p className="kerned text-white/40">PROMPTS</p>
            {inputs.map((task, idx) => (
              <div key={task.id} className="hairline rounded-xl p-3 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-white/40 w-5 text-center shrink-0">{idx + 1}</span>
                  <input
                    value={task.prompt}
                    onChange={e => updateTask(task.id, 'prompt', e.target.value)}
                    disabled={running}
                    placeholder={`Prompt ${idx + 1}…`}
                    className="flex-1 rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30 disabled:opacity-40"
                  />
                  {inputs.length > 1 && !running && (
                    <button onClick={() => removeTask(task.id)} className="text-white/30 hover:text-red-400 transition">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pl-7">
                  <div className="flex items-center gap-1.5">
                    <span className="kerned text-white/40">QUALITY</span>
                    {QUALITY_OPTIONS.map(q => (
                      <Pill key={q.key} active={task.quality === q.key} disabled={running} onClick={() => updateTask(task.id, 'quality', q.key)}>{q.label}</Pill>
                    ))}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="kerned text-white/40">PLATFORM</span>
                    {PLATFORMS.map(p => (
                      <Pill key={p} active={task.platform === p} disabled={running} onClick={() => updateTask(task.id, 'platform', p)}>{p.charAt(0).toUpperCase() + p.slice(1)}</Pill>
                    ))}
                  </div>
                </div>
              </div>
            ))}

            {!running && inputs.length < 50 && (
              <button
                onClick={addTask}
                className="w-full flex items-center justify-center gap-2 rounded-xl border border-dashed border-white/10 py-2.5 text-xs text-white/40 hover:text-white/70 hover:bg-white/[0.02] transition"
              >
                <Plus className="h-3.5 w-3.5" /> Add prompt
              </button>
            )}
          </div>

          <div className="flex items-center gap-3 pt-1">
            {!running ? (
              <button
                onClick={startBatch}
                disabled={validCount === 0}
                className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-black transition disabled:opacity-40"
                style={{ background: 'var(--gradient-aurora)' }}
              >
                <Play className="h-4 w-4" />
                Run batch{validCount > 0 ? ` (${validCount})` : ''}
              </button>
            ) : (
              <button
                onClick={cancelJob}
                className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-sm text-red-200 hover:bg-red-500/15 transition"
              >
                <X className="h-4 w-4" /> Cancel
              </button>
            )}
          </div>
        </div>

        {/* Jobs */}
        <div className="glass-panel rounded-2xl p-5 space-y-4">
          <p className="kerned text-white/40 mb-2">JOBS</p>

          {!job && (
            <div className="hairline rounded-xl p-8 text-center">
              <p className="text-sm text-white/50">No batch running. Compose prompts and hit run.</p>
            </div>
          )}

          {job && (
            <div className="space-y-4">
              <div className="hairline rounded-xl p-4 space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-white/70">{job.name}</span>
                  <span className={
                    job.status === 'done'      ? 'text-emerald-400' :
                    job.status === 'cancelled' || job.status === 'failed' ? 'text-red-400' : 'text-white/60'
                  }>{job.status} · {progress}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-white/70 transition-all duration-500" style={{ width: `${progress}%` }} />
                </div>
                <div className="flex gap-4 font-mono text-[11px]">
                  <span className="text-emerald-400">{job.done} done</span>
                  {job.failed > 0 && <span className="text-red-400">{job.failed} failed</span>}
                  <span className="text-white/40">{job.pending} pending</span>
                </div>
              </div>

              {job.tasks.length > 0 && (
                <div className="space-y-2">
                  <p className="kerned text-white/40">RESULTS</p>
                  {job.tasks.map(task => (
                    <div key={task.id} className="hairline rounded-xl overflow-hidden">
                      <button
                        className="w-full flex items-center gap-3 p-3 text-left"
                        onClick={() => setExpanded(expanded === task.id ? null : task.id)}
                      >
                        {STATUS_ICON[task.status]}
                        <span className="flex-1 text-xs text-white/70 truncate">{task.prompt}</span>
                        {task.status === 'done' && task.image_url && (
                          <a href={task.image_url} download onClick={e => e.stopPropagation()}
                            className="p-1 text-white/40 hover:text-white transition">
                            <Download className="h-3.5 w-3.5" />
                          </a>
                        )}
                        {expanded === task.id
                          ? <ChevronUp   className="h-3.5 w-3.5 text-white/40" />
                          : <ChevronDown className="h-3.5 w-3.5 text-white/40" />}
                      </button>

                      {expanded === task.id && (
                        <div className="border-t border-white/5 px-3 pb-3">
                          {task.status === 'done' && task.image_url && (
                            <img src={task.image_url} alt="" className="mt-2 w-full max-h-48 rounded-lg object-contain" />
                          )}
                          {task.status === 'failed' && task.error && (
                            <p className="mt-2 text-xs text-red-400">{task.error}</p>
                          )}
                          {task.status === 'pending' && (
                            <p className="mt-2 text-xs text-white/40">Waiting in queue…</p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

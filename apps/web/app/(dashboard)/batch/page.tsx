'use client'

/**
 * Batch Generation — /batch
 * Run up to 50 prompts simultaneously with progress tracking.
 */

import React, { useState, useEffect, useRef } from 'react'
import {
  Zap, Plus, Trash2, Play, X, CheckCircle2,
  AlertCircle, Loader2, Download, ChevronDown, ChevronUp,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface TaskInput {
  id:       string
  prompt:   string
  quality:  string
  platform: string
}

interface TaskStatus {
  id:        string
  prompt:    string
  status:    'pending' | 'running' | 'done' | 'failed'
  image_url?: string
  error?:    string
  platform:  string
}

interface JobStatus {
  job_id:   string
  name:     string
  status:   string
  total:    number
  done:     number
  failed:   number
  pending:  number
  tasks:    TaskStatus[]
}

// ── Constants ─────────────────────────────────────────────────────────────────

const QUALITY_OPTIONS = [
  { key: 'fast',     label: 'Fast',    color: 'text-emerald-400' },
  { key: 'balanced', label: 'Quality', color: 'text-blue-400' },
  { key: 'ultra',    label: 'Ultra',   color: 'text-purple-400' },
]
const PLATFORMS = ['instagram', 'linkedin', 'twitter', 'general']

function makeId() { return Math.random().toString(36).slice(2, 9) }

const STATUS_ICON = {
  pending: <div className="w-4 h-4 rounded-full border-2 border-white/20" />,
  running: <Loader2 className="w-4 h-4 animate-spin text-blue-400" />,
  done:    <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
  failed:  <AlertCircle className="w-4 h-4 text-red-400" />,
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function BatchPage() {
  const [jobName,  setJobName]  = useState('My Batch Job')
  const [inputs,   setInputs]   = useState<TaskInput[]>([
    { id: makeId(), prompt: '', quality: 'balanced', platform: 'instagram' },
  ])
  const [running,  setRunning]  = useState(false)
  const [job,      setJob]      = useState<JobStatus | null>(null)
  const pollRef = useRef<NodeJS.Timeout | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  // Poll job status while running
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

  const addTask = () =>
    setInputs(prev => [...prev, { id: makeId(), prompt: '', quality: 'balanced', platform: 'instagram' }])

  const removeTask = (id: string) =>
    setInputs(prev => prev.filter(t => t.id !== id))

  const updateTask = (id: string, key: keyof TaskInput, val: string) =>
    setInputs(prev => prev.map(t => t.id === id ? { ...t, [key]: val } : t))

  const startBatch = async () => {
    const validTasks = inputs.filter(t => t.prompt.trim())
    if (!validTasks.length) return
    setRunning(true)
    setJob(null)
    try {
      const res  = await fetch('/api/batch/start', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          name:  jobName,
          tasks: validTasks.map(t => ({
            prompt:   t.prompt.trim(),
            quality:  t.quality,
            platform: t.platform,
          })),
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
    setJob(prev => prev ? { ...prev, status: 'cancelled' } : prev)
    setRunning(false)
  }

  const progress = job ? Math.round(((job.done + job.failed) / Math.max(job.total, 1)) * 100) : 0

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Zap className="w-5 h-5 text-yellow-400" /> Batch Generate
          </h1>
          <p className="text-sm text-white/40 mt-0.5">Run up to 50 prompts simultaneously (max 3 at a time)</p>
        </div>
      </div>

      {/* Job name */}
      <div>
        <label className="text-xs text-white/40 mb-1 block">Job Name</label>
        <input
          value={jobName}
          onChange={e => setJobName(e.target.value)}
          disabled={running}
          className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/50 disabled:opacity-50"
        />
      </div>

      {/* Task list */}
      <div className="space-y-2">
        {inputs.map((task, idx) => (
          <div key={task.id} className="bg-white/3 border border-white/8 rounded-xl p-3 space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-white/30 w-5 shrink-0 text-center">{idx + 1}</span>
              <input
                value={task.prompt}
                onChange={e => updateTask(task.id, 'prompt', e.target.value)}
                disabled={running}
                placeholder={`Prompt ${idx + 1}…`}
                className="flex-1 bg-transparent border-b border-white/10 py-1 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/50 disabled:opacity-50"
              />
              <select
                value={task.quality}
                onChange={e => updateTask(task.id, 'quality', e.target.value)}
                disabled={running}
                className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-xs text-white focus:outline-none disabled:opacity-50 appearance-none"
              >
                {QUALITY_OPTIONS.map(q => <option key={q.key} value={q.key}>{q.label}</option>)}
              </select>
              <select
                value={task.platform}
                onChange={e => updateTask(task.id, 'platform', e.target.value)}
                disabled={running}
                className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-xs text-white focus:outline-none disabled:opacity-50 appearance-none"
              >
                {PLATFORMS.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase()+p.slice(1)}</option>)}
              </select>
              {inputs.length > 1 && !running && (
                <button onClick={() => removeTask(task.id)} className="text-white/20 hover:text-red-400 transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        ))}

        {!running && inputs.length < 50 && (
          <button
            onClick={addTask}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-dashed border-white/10 text-white/30 hover:border-white/20 hover:text-white/60 text-sm transition-colors"
          >
            <Plus className="w-3.5 h-3.5" /> Add Task
          </button>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        {!running ? (
          <button
            onClick={startBatch}
            disabled={!inputs.some(t => t.prompt.trim())}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-sm font-semibold transition-colors"
          >
            <Play className="w-4 h-4" />
            Start Batch ({inputs.filter(t => t.prompt.trim()).length} tasks)
          </button>
        ) : (
          <button
            onClick={cancelJob}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-600/30 text-sm font-semibold transition-colors"
          >
            <X className="w-4 h-4" /> Cancel Job
          </button>
        )}
      </div>

      {/* Progress */}
      {job && (
        <div className="space-y-4">
          {/* Progress bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-white/40">
              <span>{job.name} — <span className={
                job.status === 'done' ? 'text-emerald-400' :
                job.status === 'cancelled' ? 'text-red-400' : 'text-blue-400'
              }>{job.status}</span></span>
              <span>{job.done + job.failed}/{job.total} ({progress}%)</span>
            </div>
            <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  job.failed > 0 ? 'bg-gradient-to-r from-purple-500 to-red-500' : 'bg-purple-500'
                }`}
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex gap-4 text-[11px] text-white/30">
              <span className="text-emerald-400">{job.done} done</span>
              {job.failed > 0 && <span className="text-red-400">{job.failed} failed</span>}
              <span>{job.pending} pending</span>
            </div>
          </div>

          {/* Task results */}
          {job.tasks.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs text-white/40 uppercase tracking-wider">Results</h3>
              {job.tasks.map(task => (
                <div key={task.id} className="bg-white/3 border border-white/8 rounded-xl overflow-hidden">
                  <button
                    className="w-full flex items-center gap-3 p-3 text-left"
                    onClick={() => setExpanded(expanded === task.id ? null : task.id)}
                  >
                    {STATUS_ICON[task.status]}
                    <span className="flex-1 text-xs text-white/70 truncate">{task.prompt}</span>
                    {task.status === 'done' && task.image_url && (
                      <a
                        href={task.image_url}
                        download
                        onClick={e => e.stopPropagation()}
                        className="p-1 text-white/30 hover:text-white transition-colors"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </a>
                    )}
                    {expanded === task.id
                      ? <ChevronUp className="w-3.5 h-3.5 text-white/20" />
                      : <ChevronDown className="w-3.5 h-3.5 text-white/20" />}
                  </button>

                  {expanded === task.id && (
                    <div className="px-3 pb-3 border-t border-white/5">
                      {task.status === 'done' && task.image_url && (
                        <img src={task.image_url} alt="" className="w-full max-h-48 object-contain rounded-lg mt-2" />
                      )}
                      {task.status === 'failed' && task.error && (
                        <p className="text-xs text-red-400 mt-2">{task.error}</p>
                      )}
                      {task.status === 'pending' && (
                        <p className="text-xs text-white/30 mt-2">Waiting in queue…</p>
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
  )
}

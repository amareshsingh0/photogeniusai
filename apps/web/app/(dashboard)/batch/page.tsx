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
  pending: <div className="w-4 h-4 rounded-full border-2 border-white/15" />,
  running: <Loader2 className="w-4 h-4 animate-spin text-blue-400" />,
  done:    <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
  failed:  <AlertCircle  className="w-4 h-4 text-red-400" />,
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

  return (
    <div className="max-w-2xl space-y-5">

      {/* Header */}
      <div>
        <h1 className="text-lg font-bold text-white flex items-center gap-2">
          <Zap className="w-4.5 h-4.5 text-yellow-400" />
          Batch Generate
        </h1>
        <p className="text-xs text-white/30 mt-0.5">Run up to 50 prompts simultaneously — max 3 at a time</p>
      </div>

      {/* Job name */}
      <div>
        <label className="text-[10px] text-white/30 uppercase tracking-wider mb-1.5 block">Job Name</label>
        <input
          value={jobName}
          onChange={e => setJobName(e.target.value)}
          disabled={running}
          className="w-full bg-white/5 border border-white/8 rounded-xl px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/40 disabled:opacity-40"
        />
      </div>

      {/* Tasks */}
      <div className="space-y-2">
        {inputs.map((task, idx) => (
          <div key={task.id} className="rounded-xl p-3 space-y-2"
            style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.07)' }}>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-white/20 w-5 text-center shrink-0">{idx + 1}</span>
              <input
                value={task.prompt}
                onChange={e => updateTask(task.id, 'prompt', e.target.value)}
                disabled={running}
                placeholder={`Prompt ${idx + 1}…`}
                className="flex-1 bg-transparent border-b border-white/8 py-1 text-sm text-white placeholder-white/20 focus:outline-none focus:border-purple-500/40 disabled:opacity-40"
              />
              <select
                value={task.quality}
                onChange={e => updateTask(task.id, 'quality', e.target.value)}
                disabled={running}
                style={{ colorScheme: 'dark' }}
                className="bg-[#1a1a2e] border border-white/8 rounded-lg px-2 py-1 text-xs text-white focus:outline-none disabled:opacity-40 appearance-none cursor-pointer"
              >
                {QUALITY_OPTIONS.map(q => (
                  <option key={q.key} value={q.key} style={{ background: '#1a1a2e', color: '#fff' }}>{q.label}</option>
                ))}
              </select>
              <select
                value={task.platform}
                onChange={e => updateTask(task.id, 'platform', e.target.value)}
                disabled={running}
                style={{ colorScheme: 'dark' }}
                className="bg-[#1a1a2e] border border-white/8 rounded-lg px-2 py-1 text-xs text-white focus:outline-none disabled:opacity-40 appearance-none cursor-pointer"
              >
                {PLATFORMS.map(p => (
                  <option key={p} value={p} style={{ background: '#1a1a2e', color: '#fff' }}>
                    {p.charAt(0).toUpperCase()+p.slice(1)}
                  </option>
                ))}
              </select>
              {inputs.length > 1 && !running && (
                <button onClick={() => removeTask(task.id)} className="text-white/15 hover:text-red-400 transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        ))}

        {!running && inputs.length < 50 && (
          <button
            onClick={addTask}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs text-white/25 hover:text-white/60 transition-colors"
            style={{ border: '1px dashed rgba(255,255,255,0.1)' }}
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
            disabled={validCount === 0}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-white text-sm font-semibold transition-all disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', boxShadow: '0 0 16px rgba(124,58,237,0.25)' }}
          >
            <Play className="w-4 h-4" />
            Start Batch {validCount > 0 && `(${validCount})`}
          </button>
        ) : (
          <button
            onClick={cancelJob}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-red-400 text-sm font-semibold transition-colors"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            <X className="w-4 h-4" /> Cancel
          </button>
        )}
      </div>

      {/* Progress */}
      {job && (
        <div className="space-y-4">
          {/* Bar */}
          <div className="rounded-2xl p-4 space-y-3"
            style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="flex justify-between text-xs">
              <span className="text-white/50">{job.name}</span>
              <span className={
                job.status === 'done'      ? 'text-emerald-400' :
                job.status === 'cancelled' ? 'text-red-400'     : 'text-blue-400'
              }>{job.status} · {progress}%</span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${progress}%`,
                  background: job.failed > 0
                    ? 'linear-gradient(90deg, #7c3aed, #ef4444)'
                    : 'linear-gradient(90deg, #7c3aed, #4f46e5)',
                }}
              />
            </div>
            <div className="flex gap-4 text-[11px]">
              <span className="text-emerald-400">{job.done} done</span>
              {job.failed > 0 && <span className="text-red-400">{job.failed} failed</span>}
              <span className="text-white/25">{job.pending} pending</span>
            </div>
          </div>

          {/* Results */}
          {job.tasks.length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] text-white/25 uppercase tracking-wider">Results</p>
              {job.tasks.map(task => (
                <div key={task.id} className="rounded-xl overflow-hidden"
                  style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <button
                    className="w-full flex items-center gap-3 p-3 text-left"
                    onClick={() => setExpanded(expanded === task.id ? null : task.id)}
                  >
                    {STATUS_ICON[task.status]}
                    <span className="flex-1 text-xs text-white/60 truncate">{task.prompt}</span>
                    {task.status === 'done' && task.image_url && (
                      <a href={task.image_url} download onClick={e => e.stopPropagation()}
                        className="p-1 text-white/20 hover:text-white transition-colors">
                        <Download className="w-3.5 h-3.5" />
                      </a>
                    )}
                    {expanded === task.id
                      ? <ChevronUp   className="w-3.5 h-3.5 text-white/15" />
                      : <ChevronDown className="w-3.5 h-3.5 text-white/15" />}
                  </button>

                  {expanded === task.id && (
                    <div className="px-3 pb-3" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                      {task.status === 'done' && task.image_url && (
                        <img src={task.image_url} alt="" className="w-full max-h-48 object-contain rounded-lg mt-2" />
                      )}
                      {task.status === 'failed' && task.error && (
                        <p className="text-xs text-red-400 mt-2">{task.error}</p>
                      )}
                      {task.status === 'pending' && (
                        <p className="text-xs text-white/25 mt-2">Waiting in queue…</p>
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

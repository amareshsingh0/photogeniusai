/**
 * GET  /api/batch/[jobId] — poll job status
 * DELETE /api/batch/[jobId] — cancel job
 * Proxy → Python /api/v1/batch/{job_id}
 */
export const dynamic = 'force-dynamic'

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003'

export async function GET(_req: Request, { params }: { params: { jobId: string } }) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/batch/${params.jobId}`)
    return Response.json(await res.json(), { status: res.status })
  } catch {
    return Response.json({ error: 'Batch service unavailable' }, { status: 503 })
  }
}

export async function DELETE(_req: Request, { params }: { params: { jobId: string } }) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/batch/${params.jobId}`, { method: 'DELETE' })
    return Response.json(await res.json(), { status: res.status })
  } catch {
    return Response.json({ error: 'Batch service unavailable' }, { status: 503 })
  }
}

/**
 * POST /api/batch/start
 * Proxy → Python POST /api/v1/batch/start
 */
export const dynamic = 'force-dynamic'
export const maxDuration = 30

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003'

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const res  = await fetch(`${API_BASE}/api/v1/batch/start`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    })
    return Response.json(await res.json(), { status: res.status })
  } catch {
    return Response.json({ error: 'Batch service unavailable' }, { status: 503 })
  }
}

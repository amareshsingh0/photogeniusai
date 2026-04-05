/**
 * POST /api/content/plan
 * Proxy → Python POST /api/v1/content/plan
 * Returns 30-day AI-generated content calendar.
 */
export const dynamic = 'force-dynamic'
export const maxDuration = 90

export async function POST(req: Request) {
  const body = await req.json()
  const apiBase =
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8003'

  try {
    const res = await fetch(`${apiBase}/api/v1/content/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return Response.json(data, { status: res.status })
  } catch {
    return Response.json({ error: 'Content planner unavailable' }, { status: 503 })
  }
}

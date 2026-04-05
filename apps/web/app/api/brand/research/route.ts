/**
 * POST /api/brand/research
 * Proxy to FastAPI brand research agent — scrapes a URL for brand identity.
 */
export const dynamic = "force-dynamic"

export async function POST(req: Request) {
  const apiBase =
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8003"

  let body: { url?: string }
  try { body = await req.json() } catch { return Response.json({ error: "Invalid body" }, { status: 400 }) }

  if (!body.url?.trim()) {
    return Response.json({ error: "url is required" }, { status: 400 })
  }

  try {
    const res  = await fetch(`${apiBase}/api/v1/preferences/brand-kit/research`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ url: body.url.trim() }),
    })
    const data = await res.json()
    return Response.json(data, { status: res.status })
  } catch {
    return Response.json({ error: "Brand research service unavailable" }, { status: 503 })
  }
}

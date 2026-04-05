/**
 * POST /api/generate/poster-recompose
 * Proxy → FastAPI POST /api/v1/poster/recompose
 * Used by poster-inline-editor for live re-render (~1-2s, PIL only, no AI cost)
 */
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.json();

  const apiBase =
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8003";

  try {
    const res = await fetch(`${apiBase}/api/v1/poster/recompose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json({ error: "Recompose service unavailable" }, { status: 503 });
  }
}

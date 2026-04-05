/**
 * POST /api/generate/poster-pack
 * Proxy → FastAPI POST /api/v1/poster/pack
 * Returns 4 aspect-ratio variants concurrently
 */
export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function POST(req: Request) {
  const body = await req.json();

  const apiBase =
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8003";

  try {
    const res = await fetch(`${apiBase}/api/v1/poster/pack`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json({ error: "Pack service unavailable" }, { status: 503 });
  }
}

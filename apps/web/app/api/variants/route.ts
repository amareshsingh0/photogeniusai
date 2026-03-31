import { NextResponse } from "next/server"
import { auth } from "@clerk/nextjs/server"

export const dynamic = "force-dynamic"

const FASTAPI_URL =
  process.env.FASTAPI_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8003"

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { prompt, user_id, include_personalized = true, include_model_optimized = true } = body

    if (!prompt || typeof prompt !== "string" || prompt.trim().length < 1) {
      return NextResponse.json(
        { error: "prompt is required and must be a non-empty string" },
        { status: 400 }
      )
    }

    const { userId } = await auth()
    const res = await fetch(`${FASTAPI_URL}/api/v1/variants/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: prompt.trim(),
        user_id: user_id ?? userId ?? null,
        include_personalized: !!include_personalized,
        include_model_optimized: !!include_model_optimized,
      }),
    })

    const data = await res.json()
    if (!res.ok) {
      return NextResponse.json(
        { error: data.detail ?? "Variants request failed" },
        { status: res.status }
      )
    }
    return NextResponse.json(data)
  } catch (e) {
    console.error("[variants]", e)
    return NextResponse.json(
      { error: "Failed to fetch variants" },
      { status: 502 }
    )
  }
}

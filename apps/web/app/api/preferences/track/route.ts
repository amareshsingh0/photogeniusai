import { NextResponse } from "next/server"
import { auth } from "@clerk/nextjs/server"

export const dynamic = "force-dynamic"

const FASTAPI_URL =
  process.env.FASTAPI_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8003"

export async function POST(req: Request) {
  try {
    const { userId } = await auth()
    if (!userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 }
      )
    }

    const body = await req.json()
    const {
      action_type,
      prompt,
      variant_index,
      variant_style,
      rating,
      style_analysis,
      enhanced_prompt,
    } = body

    if (
      !action_type ||
      !prompt ||
      typeof variant_index !== "number" ||
      variant_index < 0 ||
      variant_index > 5 ||
      !variant_style
    ) {
      return NextResponse.json(
        {
          error:
            "action_type, prompt, variant_index (0-5), and variant_style are required",
        },
        { status: 400 }
      )
    }

    const res = await fetch(`${FASTAPI_URL}/api/v1/preferences/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        action_type,
        prompt,
        variant_index,
        variant_style,
        rating: rating ?? null,
        style_analysis: style_analysis ?? null,
        enhanced_prompt: enhanced_prompt ?? null,
      }),
    })

    const data = await res.json()
    if (!res.ok) {
      return NextResponse.json(
        { error: data.detail ?? "Track request failed" },
        { status: res.status }
      )
    }
    return NextResponse.json(data)
  } catch (e) {
    console.error("[preferences/track]", e)
    return NextResponse.json(
      { error: "Failed to track preference" },
      { status: 502 }
    )
  }
}

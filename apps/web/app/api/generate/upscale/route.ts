import { NextResponse } from "next/server";
import axios from "axios";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function POST(req: Request) {
  try {
    const body = await req.json() as { image_url?: string; scale?: number };
    const { image_url, scale = 4 } = body;

    if (!image_url) return NextResponse.json({ success: false, error: "image_url required" }, { status: 400 });

    const apiBase = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

    const res = await axios.post(
      `${apiBase}/api/v1/upscale`,
      { image_url, scale },
      { timeout: 60_000, headers: { "Content-Type": "application/json" }, validateStatus: null }
    );

    if (res.status >= 400) {
      return NextResponse.json(
        { success: false, error: res.data?.detail || `Backend error ${res.status}` },
        { status: res.status >= 500 ? 502 : res.status }
      );
    }

    return NextResponse.json(res.data);
  } catch (err) {
    console.error("[upscale/route] error:", err);
    return NextResponse.json({ success: false, error: "Upscale service unavailable" }, { status: 503 });
  }
}

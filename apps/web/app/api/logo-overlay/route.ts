import { NextResponse } from "next/server";
import axios from "axios";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function POST(req: Request) {
  try {
    const body = await req.json() as {
      image_url?: string;
      logo_data?: string;
      position?: string;
      size_pct?: number;
      opacity?: number;
      padding_pct?: number;
    };

    const { image_url, logo_data, position = "auto", size_pct = 20, opacity = 90, padding_pct = 3 } = body;

    if (!image_url) return NextResponse.json({ success: false, error: "image_url required" }, { status: 400 });
    if (!logo_data)  return NextResponse.json({ success: false, error: "logo_data required" }, { status: 400 });

    const apiBase = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

    const res = await axios.post(
      `${apiBase}/api/v1/logo-overlay`,
      { image_url, logo_data, position, size_pct, opacity, padding_pct },
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
    console.error("[logo-overlay/route] error:", err);
    return NextResponse.json({ success: false, error: "Logo overlay service unavailable" }, { status: 503 });
  }
}

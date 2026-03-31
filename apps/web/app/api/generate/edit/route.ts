import { NextResponse } from "next/server";
import axios from "axios";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

export async function POST(req: Request) {
  try {
    const body = await req.json() as {
      image_url?: string;
      instruction?: string;
      quality?: string;
    };

    const { image_url, instruction, quality = "balanced" } = body;

    if (!image_url) return NextResponse.json({ success: false, error: "image_url required" }, { status: 400 });
    if (!instruction || instruction.trim().length < 3)
      return NextResponse.json({ success: false, error: "instruction must be at least 3 characters" }, { status: 400 });

    const apiBase = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

    const res = await axios.post(
      `${apiBase}/api/v1/edit`,
      { image_url, instruction: instruction.trim(), quality },
      { timeout: 120_000, headers: { "Content-Type": "application/json" }, validateStatus: null }
    );

    if (res.status >= 400) {
      return NextResponse.json(
        { success: false, error: res.data?.detail || `Backend error ${res.status}` },
        { status: res.status >= 500 ? 502 : res.status }
      );
    }

    return NextResponse.json(res.data);
  } catch (err) {
    console.error("[edit/route] error:", err);
    return NextResponse.json({ success: false, error: "Edit service unavailable" }, { status: 503 });
  }
}

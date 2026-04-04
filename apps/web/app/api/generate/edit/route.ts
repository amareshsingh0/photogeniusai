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
      mask_data?: string;
    };

    const { image_url, instruction, quality = "balanced", mask_data } = body;

    if (!image_url) return NextResponse.json({ success: false, error: "image_url required" }, { status: 400 });
    if (!instruction || instruction.trim().length < 3)
      return NextResponse.json({ success: false, error: "instruction must be at least 3 characters" }, { status: 400 });

    const apiBase = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

    // If image_url is a data: URL, upload it to fal.ai storage first via API
    let resolvedUrl = image_url;
    if (image_url.startsWith("data:")) {
      const uploadRes = await axios.post(
        `${apiBase}/api/v1/storage/upload-data-url`,
        { data_url: image_url },
        { timeout: 30_000, headers: { "Content-Type": "application/json" }, validateStatus: null }
      );
      if (uploadRes.status >= 400 || !uploadRes.data?.url) {
        return NextResponse.json(
          { success: false, error: "Failed to upload image before editing" },
          { status: 502 }
        );
      }
      resolvedUrl = uploadRes.data.url;
    }

    const res = await axios.post(
      `${apiBase}/api/v1/edit`,
      { image_url: resolvedUrl, instruction: instruction.trim(), quality, mask_data },
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

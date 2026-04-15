import { NextResponse } from "next/server";
import axios from "axios";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const LEGACY_QUALITY_MAP: Record<string, string> = {
  fast: "1k",
  standard: "2k",
  balanced: "2k",
  premium: "2k",
  quality: "2k",
  ultra: "4k",
};

function normalizeQualityTier(quality?: string): string {
  const normalized = quality?.trim().toLowerCase() ?? "";
  if (normalized === "1k" || normalized === "2k" || normalized === "4k") return normalized;
  return LEGACY_QUALITY_MAP[normalized] ?? "1k";
}

export async function POST(req: Request) {
  try {
    const body = await req.json() as {
      image_url?: string;
      instruction?: string;
      quality?: string;
      mask_data?: string;
    };

    const { image_url, instruction, quality = "1k", mask_data } = body;
    const normalizedQuality = normalizeQualityTier(quality);

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
      { image_url: resolvedUrl, instruction: instruction.trim(), quality: normalizedQuality, mask_data },
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

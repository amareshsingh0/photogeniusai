import { NextResponse } from "next/server";
import axios from "axios";

export const dynamic = "force-dynamic";
// Bumped May 5 2026 from 120s -> 300s. GPT Image 2 edit takes ~72s for
// text_replace + ~30s overhead (image upload, storage URL fetch, response).
// Plus the cross-model fallback path (Gemini 503 -> retry on GPT) can stack
// up to ~150s total. 300s gives comfortable headroom; user sees progress
// in the UI rather than HTML 504 timeout pages.
export const maxDuration = 300;

const LEGACY_QUALITY_MAP: Record<string, string> = {
  fast: "1k",
  standard: "2k",
  balanced: "2k",
  premium: "2k",
  quality: "2k",
  ultra: "4k",
};

const VALID_EDIT_MODES = new Set([
  "instruction_edit",
  "inpaint_mask",
  "style_remix",
  "compose",
  "object_add",
  "object_remove",
  "background_swap",
  "text_replace",
]);

function normalizeQualityTier(quality?: string): string {
  const normalized = quality?.trim().toLowerCase() ?? "";
  if (normalized === "1k" || normalized === "2k" || normalized === "4k") return normalized;
  return LEGACY_QUALITY_MAP[normalized] ?? "1k";
}

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as {
      image_url?: string;
      instruction?: string;
      quality?: string;
      mask_data?: string;
      edit_mode?: string;
      extra_image_urls?: string[];
    };

    const { image_url, instruction, quality = "1k", mask_data, edit_mode, extra_image_urls } = body;
    const normalizedQuality = normalizeQualityTier(quality);

    if (!image_url)
      return NextResponse.json({ success: false, error: "image_url required" }, { status: 400 });
    if (!instruction || instruction.trim().length < 3)
      return NextResponse.json(
        { success: false, error: "instruction must be at least 3 characters" },
        { status: 400 }
      );

    const safeMode = edit_mode && VALID_EDIT_MODES.has(edit_mode) ? edit_mode : undefined;

    const apiBase =
      process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

    // If image_url is a data: URL, upload to fal.ai storage first
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

    // Resolve extra_image_urls (compose mode) — upload any data: URLs
    let resolvedExtras: string[] | undefined;
    if (extra_image_urls && extra_image_urls.length > 0) {
      resolvedExtras = [];
      for (const url of extra_image_urls) {
        if (url.startsWith("data:")) {
          const upRes = await axios.post(
            `${apiBase}/api/v1/storage/upload-data-url`,
            { data_url: url },
            { timeout: 30_000, headers: { "Content-Type": "application/json" }, validateStatus: null }
          );
          if (upRes.status < 400 && upRes.data?.url) {
            resolvedExtras.push(upRes.data.url);
          }
        } else {
          resolvedExtras.push(url);
        }
      }
    }

    const res = await axios.post(
      `${apiBase}/api/v1/edit`,
      {
        image_url: resolvedUrl,
        instruction: instruction.trim(),
        quality: normalizedQuality,
        mask_data,
        edit_mode: safeMode,
        extra_image_urls: resolvedExtras,
      },
      { timeout: 280_000, headers: { "Content-Type": "application/json" }, validateStatus: null }
    );

    if (res.status >= 400) {
      return NextResponse.json(
        { success: false, error: res.data?.detail || `Backend error ${res.status}` },
        { status: res.status >= 500 ? 502 : res.status }
      );
    }

    // Strip any model_used field from upstream response — never expose to client
    const { model_used: _strip, ...safeData } = res.data || {};
    return NextResponse.json(safeData);
  } catch (err) {
    console.error("[edit/route] error:", err);
    // Differentiate timeout vs other errors so frontend shows useful message
    const errMsg = err instanceof Error ? err.message : String(err);
    const isTimeout = /timeout|ETIMEDOUT|ECONNABORTED|socket hang up/i.test(errMsg);
    return NextResponse.json(
      {
        success: false,
        error: isTimeout
          ? "Edit took too long and timed out. The model is under heavy demand - please try again in a moment."
          : "Edit service unavailable",
      },
      { status: isTimeout ? 504 : 503 }
    );
  }
}

/**
 * Instant Magic Preview – calls /api/ai/generation (FastAPI).
 * When AI service is down, returns mock data using local placeholders.
 */

export type PreviewResult = {
  preview_image: string;
  message: string;
  estimated_time: string;
  quality_level: string;
};

export type FullQualityResult = {
  final_image: string;
  message: string;
};

export const FULL_QUALITY_DELAY_MS = 6000;

/** True when last API call fell back to mock (e.g. AI service not running). */
export let lastCallWasMock = false;

const API_BASE = "/api/ai";
const MOCK_PREVIEW = "/images/preview.jpg";
const MOCK_FULL = "/images/full.jpg";

function toPublicImage(path: string): string {
  if (path.startsWith("http")) return path;
  // AI service returns paths like /api/generated/xxx.png — proxy them via /api/ai
  if (path.startsWith("/api/generated/")) return `/api/ai${path.slice(4)}`;
  if (path.startsWith("/") && !path.startsWith("//")) return path;
  return path.startsWith("/") ? path : `/${path}`;
}

async function apiPost<T>(path: string, body: { prompt?: string }): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

function mockPreview(prompt: string): PreviewResult {
  lastCallWasMock = true;
  return {
    preview_image: MOCK_PREVIEW,
    message: "Quick preview ready! (Demo – AI service offline)",
    estimated_time: "6 seconds",
    quality_level: "Preview (mock)",
  };
}

function mockFull(): FullQualityResult {
  return {
    final_image: MOCK_FULL,
    message: "Final best-of-2 ready (demo)",
  };
}

export async function generatePreview(prompt: string): Promise<PreviewResult> {
  try {
    const data = await apiPost<PreviewResult>("/generation/preview", { prompt });
    lastCallWasMock = false;
    data.preview_image = toPublicImage(data.preview_image);
    return data;
  } catch (e) {
    return mockPreview(prompt);
  }
}

export async function generateFullQuality(prompt: string): Promise<FullQualityResult> {
  try {
    const data = await apiPost<FullQualityResult>("/generation/full", { prompt });
    lastCallWasMock = false;
    data.final_image = toPublicImage(data.final_image);
    return data;
  } catch {
    return mockFull();
  }
}

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { auth } from "@/lib/auth";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";
import axios from "axios";

export const dynamic = "force-dynamic";
export const maxDuration = 800; // 800s max (Vercel Pro limit) — PREMIUM warm≈690s, cold-start up to 1390s (first request after deploy)

const DOMAIN_TO_MODE: Record<string, "REALISM" | "CREATIVE" | "ROMANTIC" | "CINEMATIC" | "FASHION" | "COOL_EDGY" | "ARTISTIC" | "MAX_SURPRISE"> = {
  portrait:     "REALISM",
  landscape:    "REALISM",
  architecture: "REALISM",
  product:      "REALISM",
  anime:        "ARTISTIC",
  fantasy:      "CREATIVE",
  food:         "REALISM",
  fashion:      "FASHION",
};

/**
 * POST /api/generate/smart
 *
 * Dev-mode-compatible generation endpoint.
 * Proxies to the FastAPI backend (NEXT_PUBLIC_API_URL/api/v1/generate)
 * which handles: Qwen2/Llama prompt enhancement → PixArt/FLUX generation → CLIP scoring.
 *
 * Request body: { prompt, width?, height?, quality? } — quality: fast | balanced | quality | ultra
 * Response:     { success, image_url, enhanced_prompt, detected_settings, model_used }
 */
export async function POST(req: Request) {
  try {
    // Allow dev-session or any logged-in user (no strict auth enforced here)
    await cookies(); // ensure dynamic context

    const body = await req.json() as {
      prompt?: string;
      width?: number;
      height?: number;
      quality?: string;
      style?: string;
      reference_image?: string; // base64 data URL for image-to-image
      negative_prompt?: string; // user-specified negative prompt
    };
    const { prompt, width = 1024, height = 1024, quality: bodyQuality, style, reference_image, negative_prompt } = body;

    if (!prompt || prompt.trim().length < 3) {
      return NextResponse.json(
        { success: false, error: "Prompt must be at least 3 characters" },
        { status: 400 }
      );
    }

    const apiBase =
      process.env.INTERNAL_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8003";

    // ── Fetch Style DNA for this user ────────────────────────────────────────
    let userPreferences: Record<string, unknown> | null = null;
    try {
      const session = await auth();
      const clerkId = session?.userId ?? null;
      if (clerkId) {
        const dbUser = await prisma.user.findUnique({
          where: { clerkId },
          select: { preferences: true },
        });
        if (dbUser?.preferences) {
          userPreferences = dbUser.preferences as Record<string, unknown>;
        }
      }
    } catch { /* auth/db optional — never block generation */ }

    let backendData: {
      success: boolean;
      image_url: string;
      enhanced_prompt?: string;
      domain?: string;
      model_used?: string;
      quality_score?: number;
      total_time?: number;
      creative_os?: Record<string, unknown>; // intent, graph, layout, jury, brand, variants, ctr
    };
    try {
      const resolvedQuality = ["fast", "balanced", "quality", "ultra"].includes(bodyQuality ?? "")
        ? bodyQuality!
        : "balanced";
      // Use axios instead of fetch — axios has reliable socket-level timeout configuration.
      // Node.js built-in fetch uses node:internal/deps/undici with a 300s headersTimeout
      // default that cannot be patched via setGlobalDispatcher from other undici instances.
      // axios bypasses this entirely using its own http.Agent with a single timeout param.
      // Timeout: 1860s = PREMIUM max_wait(1800s) + GPU2 enhancement(8s) + network overhead(52s).
      const axiosRes = await axios.post(
        `${apiBase}/api/v1/generate`,
        {
          prompt: prompt.trim(),
          wow_intensity: 0.85,
          quality: resolvedQuality,
          width,
          height,
          ...(style && { style }),
          skip_quality_check: false,
          async_mode: false,
          ...(reference_image && { reference_image }),
          ...(negative_prompt && { negative_prompt }),
          ...(userPreferences && { user_preferences: userPreferences }),
        },
        {
          timeout: 1_860_000, // 1860s (31 min) — PREMIUM max_wait=1800s + GPU2(8s) + overhead
          headers: { "Content-Type": "application/json" },
          validateStatus: null, // don't throw on non-2xx (handled below)
        }
      );
      if (axiosRes.status >= 400) {
        console.error("[smart/generate] Backend error:", axiosRes.status, JSON.stringify(axiosRes.data));
        const detail = axiosRes.data?.detail || `Backend error ${axiosRes.status}`;
        return NextResponse.json(
          { success: false, error: typeof detail === 'string' ? detail : JSON.stringify(detail) },
          { status: axiosRes.status >= 500 ? 502 : axiosRes.status }
        );
      }
      backendData = axiosRes.data;
    } catch (networkErr) {
      console.error("[smart/generate] Backend unreachable:", networkErr);
      return NextResponse.json(
        {
          success: false,
          error:
            "AI backend is not reachable. Ensure the API server is running at " + apiBase,
        },
        { status: 503 }
      );
    }

    const data = backendData;

    // Map backend domain → UI detected_settings (shown in generate page banner)
    const domainMap: Record<string, { style: string; mood: string; lighting: string; quality: string; category: string }> = {
      portrait:     { style: "Portrait",     mood: "Cinematic",   lighting: "Studio",    quality: "Premium", category: "portrait" },
      landscape:    { style: "Landscape",    mood: "Serene",      lighting: "Natural",   quality: "Premium", category: "landscape" },
      architecture: { style: "Architectural",mood: "Bold",        lighting: "Daylight",  quality: "Premium", category: "architecture" },
      product:      { style: "Product",      mood: "Clean",       lighting: "Softbox",   quality: "Premium", category: "product" },
      anime:        { style: "Anime",        mood: "Expressive",  lighting: "Flat",      quality: "Premium", category: "anime" },
      fantasy:      { style: "Fantasy",      mood: "Epic",        lighting: "Dramatic",  quality: "Premium", category: "fantasy" },
      food:         { style: "Food",         mood: "Appetizing",  lighting: "Natural",   quality: "Premium", category: "food" },
      fashion:      { style: "Fashion",      mood: "Editorial",   lighting: "High-Key",  quality: "Premium", category: "fashion" },
    };

    const domain = (data.domain ?? "portrait").toLowerCase();
    const detected_settings = domainMap[domain] ?? domainMap.portrait;
    const mode = DOMAIN_TO_MODE[domain] ?? "REALISM";
    const qualityUsed = ["fast", "balanced", "quality", "ultra"].includes(bodyQuality ?? "") ? bodyQuality! : (height >= 1024 ? "quality" : "balanced");
    const creditsUsed = qualityUsed === "quality" || qualityUsed === "ultra" ? 3 : qualityUsed === "balanced" ? 2 : 1;

    // Save generation to DB → shows in gallery, dashboard stats, enables publish
    let generationId: string | undefined;
    try {
      const { userId: clerkId } = await auth();
      if (clerkId) {
        const dbUser = await prisma.user.upsert({
          where: { clerkId },
          create: { clerkId, email: `${clerkId}@photogenius.local`, creditsBalance: 1000 },
          update: {},
          select: { id: true },
        });
        if (dbUser) {
          const gen = await prisma.generation.create({
            data: {
              userId: dbUser.id,
              originalPrompt: prompt.trim(),
              mode,
              outputUrls: [data.image_url],
              selectedOutputUrl: data.image_url,
              postGenSafetyPassed: true, // AI pipeline already handles safety
              isDeleted: false,
              creditsUsed,
              qualityTierUsed: qualityUsed,
              aestheticScore: data.quality_score != null ? Math.round(data.quality_score * 100) : null,
            },
          });
          generationId = gen.id;
          // Deduct credits (non-fatal)
          await prisma.user.update({
            where: { id: dbUser.id },
            data: { creditsBalance: { decrement: creditsUsed } },
          }).catch(() => {});
        }
      }
    } catch (saveErr) {
      if (!isPrismaDbUnavailable(saveErr)) {
        console.error("[smart/generate] DB save failed:", saveErr);
      }
      // Non-fatal: return image even if DB save fails
    }

    return NextResponse.json({
      success: true,
      image_url: data.image_url,
      enhanced_prompt: data.enhanced_prompt ?? prompt,
      detected_settings,
      model_used: data.model_used ?? "AI",
      quality_score: data.quality_score,
      total_time: data.total_time,
      generationId,
      creative_os: data.creative_os ?? null,
    });
  } catch (err) {
    console.error("[smart/generate] Unhandled error:", err);
    return NextResponse.json(
      { success: false, error: "Internal server error" },
      { status: 500 }
    );
  }
}

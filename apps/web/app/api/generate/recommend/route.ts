import { NextResponse } from "next/server";
import { classifyPromptComplexity, type QualityTier } from "@/lib/prompt-complexity";

export const dynamic = "force-dynamic";

/**
 * GET /api/generate/recommend?prompt=...&hasIdentity=false&userTier=STANDARD
 * Returns recommended tier for the prompt (for UI: "We recommend STANDARD (save 50%)").
 */
export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const prompt = searchParams.get("prompt") ?? "";
  const hasIdentity = searchParams.get("hasIdentity") === "true";
  const userTier = (searchParams.get("userTier") as QualityTier) || "STANDARD";

  if (!prompt.trim()) {
    return NextResponse.json(
      { error: "prompt query parameter required" },
      { status: 400 }
    );
  }

  const result = classifyPromptComplexity({
    prompt: prompt.trim(),
    hasIdentity,
    userTier,
  });

  return NextResponse.json({
    recommended_tier: result.recommendedTier,
    reason: result.reason,
    savings_fraction: result.savingsFraction,
    confidence: result.confidence,
    user_tier: userTier,
  });
}

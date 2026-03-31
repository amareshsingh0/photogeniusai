/**
 * Prompt complexity classifier for smart routing.
 * Recommends FAST / STANDARD / PREMIUM / PERFECT based on prompt and context.
 * Goal: route simple prompts to cheaper tiers to reduce cost ~30%.
 */

export type QualityTier = "FAST" | "STANDARD" | "PREMIUM" | "PERFECT";

export interface ComplexityInput {
  prompt: string;
  wordCount?: number;
  hasIdentity?: boolean;
  hasMultiPerson?: boolean;
  styleComplexity?: "simple" | "moderate" | "complex";
  /** User-requested tier; we may recommend a lower one. */
  userTier?: QualityTier;
}

export interface ComplexityResult {
  recommendedTier: QualityTier;
  /** Reason for recommendation (for UI: "We recommend STANDARD for this prompt (save 50%)") */
  reason: string;
  /** Estimated savings vs user tier if we downgrade (0–1). */
  savingsFraction?: number;
  /** Confidence 0–1. */
  confidence: number;
}

const SIMPLE_WORD_MAX = 12;
const COMPLEX_WORD_MIN = 35;
const PREMIUM_KEYWORDS = [
  "masterpiece", "8k", "ultra", "best quality", "perfect", "award", "premium",
  "hyperrealistic", "photorealistic", "cinematic", "anamorphic", "professional",
  "detailed", "intricate", "volumetric", "dramatic lighting", "film grain",
];
const MULTI_PERSON_MARKERS = ["two people", "group", "couple", "family", "friends", "crowd", "multiple people", "they "];

function countWords(prompt: string): number {
  return prompt.trim().split(/\s+/).filter(Boolean).length;
}

function detectMultiPerson(prompt: string): boolean {
  const lower = prompt.toLowerCase();
  return MULTI_PERSON_MARKERS.some((m) => lower.includes(m));
}

function detectStyleComplexity(prompt: string): "simple" | "moderate" | "complex" {
  const lower = prompt.toLowerCase();
  const premiumCount = PREMIUM_KEYWORDS.filter((k) => lower.includes(k)).length;
  if (premiumCount >= 3) return "complex";
  if (premiumCount >= 1) return "moderate";
  return "simple";
}

/** Tier order for savings: FAST < STANDARD < PREMIUM < PERFECT. */
const TIER_ORDER: QualityTier[] = ["FAST", "STANDARD", "PREMIUM", "PERFECT"];
function tierRank(t: QualityTier): number {
  const i = TIER_ORDER.indexOf(t);
  return i >= 0 ? i : 1;
}

/** Approximate cost ratio vs STANDARD (for savings message). */
const TIER_COST_RATIO: Record<QualityTier, number> = {
  FAST: 0.5,
  STANDARD: 1,
  PREMIUM: 1.8,
  PERFECT: 2.2,
};

export function classifyPromptComplexity(input: ComplexityInput): ComplexityResult {
  const prompt = (input.prompt || "").trim();
  const wordCount = input.wordCount ?? countWords(prompt);
  const hasIdentity = input.hasIdentity ?? false;
  const hasMultiPerson = input.hasMultiPerson ?? detectMultiPerson(prompt);
  const styleComplexity = input.styleComplexity ?? detectStyleComplexity(prompt);
  const userTier = input.userTier ?? "STANDARD";

  // Rule 1: Very short, simple prompts → FAST
  if (wordCount <= SIMPLE_WORD_MAX && styleComplexity === "simple" && !hasIdentity && !hasMultiPerson) {
    const recommendedTier: QualityTier = "FAST";
    const savings = userTier !== "FAST" ? 1 - TIER_COST_RATIO.FAST / TIER_COST_RATIO[userTier] : 0;
    return {
      recommendedTier,
      reason: "Short, simple prompt — FAST tier is enough (fastest & cheapest).",
      savingsFraction: savings,
      confidence: 0.85,
    };
  }

  // Rule 2: Multi-person or identity → at least STANDARD, often PREMIUM
  if (hasMultiPerson || hasIdentity) {
    const recommendedTier: QualityTier = hasIdentity ? "PREMIUM" : "STANDARD";
    const savings = tierRank(userTier) > tierRank(recommendedTier) ? 1 - TIER_COST_RATIO[recommendedTier] / TIER_COST_RATIO[userTier] : 0;
    return {
      recommendedTier,
      reason: hasIdentity
        ? "Identity/face lock works best with PREMIUM tier."
        : "Multiple people in scene — STANDARD or higher recommended.",
      savingsFraction: savings,
      confidence: 0.8,
    };
  }

  // Rule 3: Long or style-complex → STANDARD or PREMIUM
  if (wordCount >= COMPLEX_WORD_MIN || styleComplexity === "complex") {
    const recommendedTier: QualityTier = styleComplexity === "complex" ? "PREMIUM" : "STANDARD";
    return {
      recommendedTier,
      reason: styleComplexity === "complex"
        ? "Complex style keywords — PREMIUM for best quality."
        : "Long prompt — STANDARD tier recommended.",
      confidence: 0.75,
    };
  }

  // Rule 4: Moderate length, moderate style → STANDARD
  if (styleComplexity === "moderate" || wordCount > SIMPLE_WORD_MAX) {
    const recommendedTier: QualityTier = "STANDARD";
    const savings = userTier === "PREMIUM" || userTier === "PERFECT" ? 1 - 1 / TIER_COST_RATIO[userTier] : 0;
    return {
      recommendedTier,
      reason: "STANDARD tier is a good balance of quality and cost.",
      savingsFraction: savings,
      confidence: 0.8,
    };
  }

  // Default: STANDARD
  return {
    recommendedTier: "STANDARD",
    reason: "STANDARD tier recommended for this prompt.",
    confidence: 0.7,
  };
}

/**
 * Decide effective tier: use recommended tier if it's <= user tier and confidence is high enough;
 * otherwise use user tier. Set forceRecommendation=true to always prefer classifier (for "save 50%" UX).
 */
export function getEffectiveTier(
  input: ComplexityInput,
  options: { forceRecommendation?: boolean; minConfidenceForOverride?: number } = {}
): { tier: QualityTier; fromRecommendation: boolean; result: ComplexityResult } {
  const result = classifyPromptComplexity(input);
  const minConf = options.minConfidenceForOverride ?? 0.75;
  const force = options.forceRecommendation ?? false;

  const userRank = tierRank(input.userTier ?? "STANDARD");
  const recRank = tierRank(result.recommendedTier);
  const useRecommendation =
    force || (result.confidence >= minConf && recRank <= userRank);

  const tier: QualityTier = useRecommendation ? result.recommendedTier : (input.userTier ?? "STANDARD");
  return {
    tier,
    fromRecommendation: useRecommendation,
    result,
  };
}

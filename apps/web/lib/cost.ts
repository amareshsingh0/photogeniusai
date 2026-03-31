/**
 * Cost profiling: approximate USD per generation for SageMaker, Lambda, S3.
 * Used for cost_usd storage and dashboards. Update rates via env or config.
 *
 * Reference (us-east-1, approximate):
 * - SageMaker ml.g5.xlarge ~$1.10/hr → $0.0003056/sec
 * - SageMaker ml.g5.2xlarge ~$1.52/hr → $0.0004222/sec
 * - Lambda: $0.20/1M requests + $0.0000166667/GB-sec (128MB default)
 * - S3: $0.023/GB PUT + storage
 */

export type QualityTier = "FAST" | "STANDARD" | "PREMIUM" | "PERFECT";

/** USD per second for SageMaker by instance (approximate). */
const SAGEMAKER_USD_PER_SEC: Record<string, number> = {
  "ml.g5.xlarge": 1.1 / 3600,
  "ml.g5.2xlarge": 1.52 / 3600,
  "ml.g5.4xlarge": 2.8 / 3600,
  default: 1.1 / 3600,
};

/** Lambda: ~$0.20 per 1M requests + $0.0000166667 per GB-sec. 128MB, 5s ≈ 0.00001. */
const LAMBDA_USD_PER_INVOCATION = 0.00002;

/** S3: ~$0.023/GB. 1 image ~2MB = 0.002 GB → ~$0.00005 per image. */
const S3_USD_PER_GB = 0.023;

/** Instance type by tier (from endpoint_config). */
const TIER_INSTANCE: Record<string, string> = {
  FAST: "ml.g5.xlarge",
  STANDARD: "ml.g5.xlarge",
  PREMIUM: "ml.g5.2xlarge",
  PERFECT: "ml.g5.xlarge",
};

export interface CostBreakdown {
  sagemakerUsd: number;
  lambdaUsd: number;
  s3Usd: number;
  totalUsd: number;
  tier: QualityTier | string;
  inferenceSeconds?: number;
  imageCount?: number;
}

/**
 * Compute cost for a generation from Lambda response (inference_seconds, tier, image_count, bytes).
 */
export function computeGenerationCost(params: {
  tier?: QualityTier | string;
  inferenceSeconds?: number;
  imageCount?: number;
  totalBytes?: number;
}): CostBreakdown {
  const tier = (params.tier ?? "STANDARD") as string;
  const instance = TIER_INSTANCE[tier] ?? SAGEMAKER_USD_PER_SEC.default;
  const usdPerSec = SAGEMAKER_USD_PER_SEC[instance] ?? SAGEMAKER_USD_PER_SEC.default;
  const inferenceSeconds = params.inferenceSeconds ?? 10;

  const sagemakerUsd = inferenceSeconds * usdPerSec;
  const lambdaUsd = LAMBDA_USD_PER_INVOCATION;
  const imageCount = params.imageCount ?? 1;
  const totalBytes = params.totalBytes ?? imageCount * 2 * 1024 * 1024; // 2MB per image default
  const s3Usd = (totalBytes / (1024 * 1024 * 1024)) * S3_USD_PER_GB;

  return {
    sagemakerUsd,
    lambdaUsd,
    s3Usd,
    totalUsd: sagemakerUsd + lambdaUsd + s3Usd,
    tier,
    inferenceSeconds,
    imageCount,
  };
}

/**
 * Round to 6 decimal places for storage.
 */
export function roundCost(usd: number): number {
  return Math.round(usd * 1e6) / 1e6;
}

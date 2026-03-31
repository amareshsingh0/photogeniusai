/**
 * Generation types for two-pass preview and quality tier (AWS orchestrator).
 */

export type QualityTier = "FAST" | "STANDARD" | "PREMIUM" | "PERFECT";

/** Physics / realism hints for generation (optional backend use). */
export interface PhysicsOptions {
  wetness?: boolean;
  lighting?: boolean;
  gravity?: boolean;
}

export interface TwoPassGenerationResult {
  images: {
    preview: string | null; // base64
    final: string | null;   // base64
  };
  metadata: {
    quality_tier: QualityTier;
    original_prompt: string;
    enhanced_prompt: string;
    mode: string;
    preview_time?: number;
    final_time?: number;
    total_time: number;
    generation_id?: string;
    image_url?: string;
  };
  error?: string;
}

export interface GenerationRequest {
  prompt: string;
  quality_tier: QualityTier;
  mode: string;
  identity_id?: string;
  user_id?: string;
  style_lora?: string;
  negative_prompt?: string;
  width?: number;
  height?: number;
  num_inference_steps?: number;
  guidance_scale?: number;
  seed?: number;
  /** Number of images to generate (1, 2, or 4). */
  num_images?: number;
  /** Physics / realism toggles (wetness, lighting, gravity). */
  physics?: PhysicsOptions;
  /** Boost surprise/creativity (e.g. MAX_SURPRISE mode). */
  surprise_me?: boolean;
}

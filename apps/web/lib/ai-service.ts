/**
 * AI Service Abstraction Layer
 *
 * Unified interface for all AI operations across cloud providers.
 * Automatically handles:
 * - Provider detection (AWS default; optional GCP, Lightning, backend)
 * - Authentication
 * - Error handling
 * - Retries with exponential backoff
 *
 * Usage:
 *   import { AIService } from "@/lib/ai-service";
 *
 *   // Generate images
 *   const result = await AIService.generate({
 *     prompt: "Professional headshot",
 *     mode: "REALISM",
 *   });
 */

import {
  getServiceUrl,
  getAuthHeaders,
  getCurrentProvider,
  type ServiceName,
  type CloudProvider,
} from "./cloud-config";

// ==================== Types ====================

/** All AI pipeline types supported by backend and ai-pipeline */
export type GenerationModeType =
  | "REALISM"
  | "CREATIVE"
  | "ROMANTIC"
  | "CINEMATIC"
  | "FASHION"
  | "COOL_EDGY"
  | "ARTISTIC"
  | "MAX_SURPRISE";

export interface GenerationParams {
  prompt: string;
  mode?: GenerationModeType;
  identityId?: string;
  userId?: string;
  numCandidates?: number;
  seed?: number;
  faceEmbedding?: number[];
  /** S3 or URL path to identity LoRA weights (for face-consistent generation) */
  loraPath?: string | null;
  qualityTier?: "FAST" | "STANDARD" | "BALANCED" | "PREMIUM" | "ULTRA";
  width?: number;
  height?: number;
  /** Full-stack tracing: X-Request-ID */
  correlationId?: string;
}

export interface GenerationResult {
  success: boolean;
  images: Array<{
    url: string;
    seed?: number;
    scores?: {
      face_match?: number;
      aesthetic?: number;
      technical?: number;
      total?: number;
    };
  }>;
  error?: string;
  jobId?: string;
}

export interface SafetyCheckParams {
  prompt: string;
  mode?: string;
}

export interface SafetyCheckResult {
  allowed: boolean;
  violations: string[];
  confidence?: number;
}

export interface RefinementParams {
  imageBase64: string;
  refinementRequest: string;
  generationHistory: Array<{ role: string; content: string }>;
  mode?: string;
  seed?: number;
}

export interface RefinementResult {
  success: boolean;
  imageBase64?: string;
  error?: string;
}

export interface TrainingParams {
  userId: string;
  identityId: string;
  imageUrls: string[];
  triggerWord?: string;
  trainingSteps?: number;
}

export interface TrainingResult {
  success: boolean;
  jobId?: string;
  loraPath?: string;
  faceEmbedding?: number[];
  faceQuality?: number;
  error?: string;
}

// ==================== Helper Functions ====================

async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries = 3,
  timeoutMs = 600000
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Don't retry on client errors (4xx)
      if (response.status >= 400 && response.status < 500) {
        return response;
      }

      // Retry on server errors (5xx) or network issues
      if (!response.ok && attempt < maxRetries - 1) {
        const delay = Math.pow(2, attempt) * 1000; // Exponential backoff
        await new Promise((resolve) => setTimeout(resolve, delay));
        continue;
      }

      return response;
    } catch (error) {
      lastError = error as Error;

      // Don't retry on abort/timeout
      if ((error as Error).name === "AbortError") {
        throw new Error("Request timed out");
      }

      // Exponential backoff before retry
      if (attempt < maxRetries - 1) {
        const delay = Math.pow(2, attempt) * 1000;
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError || new Error("Request failed after retries");
}

// ==================== AI Service Class ====================

export class AIService {
  private static provider: CloudProvider = getCurrentProvider();

  /**
   * Get current cloud provider
   */
  static getProvider(): CloudProvider {
    return this.provider;
  }

  /**
   * Safety check for prompts
   */
  static async checkSafety(params: SafetyCheckParams): Promise<SafetyCheckResult> {
    const url = getServiceUrl("safety");
    const headers = {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    };

    try {
      const response = await fetchWithRetry(
        url,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            prompt: params.prompt,
            mode: params.mode || "REALISM",
          }),
        },
        3,
        30000 // 30s timeout for safety checks
      );

      if (!response.ok) {
        console.error(`[AIService.checkSafety] Error: ${response.status}`);
        // Default to allowed on error (can be configured)
        return { allowed: true, violations: [] };
      }

      const result = await response.json();
      return {
        allowed: result.allowed === true,
        violations: result.violations || [],
        confidence: result.confidence,
      };
    } catch (error) {
      console.error("[AIService.checkSafety] Error:", error);
      // Default to allowed on error
      return { allowed: true, violations: [] };
    }
  }

  /**
   * Generate images
   */
  static async generate(params: GenerationParams): Promise<GenerationResult> {
    const url = getServiceUrl("generation");
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    };
    if (params.correlationId) headers["X-Request-ID"] = params.correlationId;

    try {
      const response = await fetchWithRetry(
        url,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            user_id: params.userId,
            identity_id: params.identityId || "default",
            prompt: params.prompt,
            mode: params.mode || "REALISM",
            num_candidates: params.numCandidates || 4,
            guidance_scale: 7.5,
            num_inference_steps: 30,
            seed: params.seed || null,
            face_embedding: params.faceEmbedding,
            lora_path: params.loraPath ?? undefined,
            quality_tier: params.qualityTier || "BALANCED",
            width: params.width || 1024,
            height: params.height || 1024,
            correlation_id: params.correlationId ?? undefined,
          }),
        },
        3,
        600000 // 10 min timeout for generation
      );

      if (!response.ok) {
        const errorText = await response.text().catch(() => "Unknown error");
        console.error(`[AIService.generate] Error: ${response.status} - ${errorText}`);
        return {
          success: false,
          images: [],
          error: `Generation failed: ${response.status}`,
        };
      }

      const data = await response.json();

      // Normalize response format across providers
      const images = Array.isArray(data)
        ? data
        : data.images || data.results || [];

      return {
        success: true,
        images: images.map((img: any) => ({
          url: img.image_base64
            ? `data:image/png;base64,${img.image_base64}`
            : img.url || "",
          seed: img.seed,
          scores: img.scores,
        })),
        jobId: data.job_id,
      };
    } catch (error) {
      console.error("[AIService.generate] Error:", error);
      return {
        success: false,
        images: [],
        error: (error as Error).message,
      };
    }
  }

  /**
   * Refine an existing image
   */
  static async refine(params: RefinementParams): Promise<RefinementResult> {
    const url = getServiceUrl("refinement");
    const headers = {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    };

    try {
      const response = await fetchWithRetry(
        url,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            image_base64: params.imageBase64,
            refinement_request: params.refinementRequest,
            generation_history: params.generationHistory,
            mode: params.mode || "REALISM",
            seed: params.seed,
          }),
        },
        3,
        300000 // 5 min timeout for refinement
      );

      if (!response.ok) {
        const errorText = await response.text().catch(() => "Unknown error");
        console.error(`[AIService.refine] Error: ${response.status} - ${errorText}`);
        return {
          success: false,
          error: `Refinement failed: ${response.status}`,
        };
      }

      const data = await response.json();
      return {
        success: true,
        imageBase64: data.image_base64 || data.refined_image,
      };
    } catch (error) {
      console.error("[AIService.refine] Error:", error);
      return {
        success: false,
        error: (error as Error).message,
      };
    }
  }

  /**
   * Start LoRA training for an identity
   */
  static async startTraining(params: TrainingParams): Promise<TrainingResult> {
    const url = getServiceUrl("training");
    const headers = {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    };

    try {
      const response = await fetchWithRetry(
        url,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            user_id: params.userId,
            identity_id: params.identityId,
            image_urls: params.imageUrls,
            trigger_word: params.triggerWord || "sks",
            training_steps: params.trainingSteps || 1000,
          }),
        },
        3,
        60000 // 1 min timeout for starting training (it runs async)
      );

      if (!response.ok) {
        const errorText = await response.text().catch(() => "Unknown error");
        console.error(`[AIService.startTraining] Error: ${response.status} - ${errorText}`);
        return {
          success: false,
          error: `Training failed to start: ${response.status}`,
        };
      }

      const data = await response.json();
      return {
        success: true,
        jobId: data.job_id,
        loraPath: data.lora_path,
        faceEmbedding: data.face_embedding,
        faceQuality: data.face_quality,
      };
    } catch (error) {
      console.error("[AIService.startTraining] Error:", error);
      return {
        success: false,
        error: (error as Error).message,
      };
    }
  }

  /**
   * Use orchestrator for intelligent generation
   */
  static async orchestrate(params: GenerationParams): Promise<GenerationResult> {
    const url = getServiceUrl("orchestrator");
    const headers = {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    };

    try {
      const response = await fetchWithRetry(
        url,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            prompt: params.prompt,
            mode: params.mode || "REALISM",
            identity_id: params.identityId,
            user_id: params.userId,
            num_candidates: params.numCandidates || 4,
            seed: params.seed,
            face_embedding: params.faceEmbedding,
            lora_path: params.loraPath ?? undefined,
            quality_tier: params.qualityTier || "BALANCED",
            width: params.width || 1024,
            height: params.height || 1024,
          }),
        },
        3,
        600000 // 10 min timeout
      );

      if (!response.ok) {
        const errorText = await response.text().catch(() => "Unknown error");
        console.error(`[AIService.orchestrate] Error: ${response.status} - ${errorText}`);
        return {
          success: false,
          images: [],
          error: `Orchestration failed: ${response.status}`,
        };
      }

      const data = await response.json();
      const images = data.images || [];

      return {
        success: true,
        images: images.map((img: any) => ({
          url: img.image_base64
            ? `data:image/png;base64,${img.image_base64}`
            : img.url || "",
          seed: img.seed,
          scores: img.scores,
        })),
        jobId: data.request_id,
      };
    } catch (error) {
      console.error("[AIService.orchestrate] Error:", error);
      return {
        success: false,
        images: [],
        error: (error as Error).message,
      };
    }
  }
}

// Export types for external use
export type { CloudProvider, ServiceName };

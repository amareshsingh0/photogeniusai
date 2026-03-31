import { create } from "zustand"
import type { QualityTier, PhysicsOptions, TwoPassGenerationResult } from "@/lib/types/generation"

interface GeneratedImage {
  id: string
  url: string
  seed?: number
  scores?: {
    face_match?: number
    aesthetic?: number
    technical?: number
    total?: number
  }
}

interface GenerationResult {
  success: boolean
  jobId: string
  status: string
  message: string
  images: GeneratedImage[]
  error?: string
  violations?: any[]
}

interface GenerationData {
  identityId?: string
  prompt: string
  mode: string
  style_lora?: string
  numImages?: number
  guidanceScale?: number
  numInferenceSteps?: number
  seed?: number
  quality_tier?: QualityTier
  physics?: PhysicsOptions
  surprise_me?: boolean
}

interface TwoPassParams {
  prompt: string
  quality_tier: QualityTier
  mode?: string
  identity_id?: string
  user_id?: string
  style_lora?: string
  negative_prompt?: string
  width?: number
  height?: number
  num_inference_steps?: number
  guidance_scale?: number
  seed?: number
  num_images?: number
  physics?: PhysicsOptions
  surprise_me?: boolean
}

interface GenerationState {
  progress: number
  status: "idle" | "generating" | "completed" | "failed" | "blocked"
  currentStep: string
  estimatedTime: number
  generationId: string | null
  error: string | null
  violations: any[]
  results: GeneratedImage[]

  setProgress: (progress: number) => void
  setStatus: (status: GenerationState["status"]) => void
  setCurrentStep: (step: string) => void
  startGeneration: (data: GenerationData) => Promise<GenerationResult>
  /** Two-pass: call /api/generate with quality_tier; returns orchestrator result (preview + final). */
  generateWithQualityTier: (params: TwoPassParams) => Promise<TwoPassGenerationResult>
  resetGeneration: () => void
}

// Step names must match GenerationProgress component
const STEPS = {
  SAFETY_CHECK: "Safety Check",
  GENERATING: "Generating Images",
  QUALITY_SCORING: "Quality Scoring",
  FINALIZING: "Finalizing",
  COMPLETED: "Generation complete!",
  FAILED: "Generation failed",
  BLOCKED: "Content blocked by safety filters",
}

export const useGenerationStore = create<GenerationState>((set, get) => ({
  progress: 0,
  status: "idle",
  currentStep: STEPS.SAFETY_CHECK,
  estimatedTime: 45,
  generationId: null,
  error: null,
  violations: [],
  results: [],

  setProgress: (progress) => set({ progress }),
  setStatus: (status) => set({ status }),
  setCurrentStep: (currentStep) => set({ currentStep }),

  startGeneration: async (data) => {
    // Reset state and start
    set({
      status: "generating",
      progress: 0,
      currentStep: STEPS.SAFETY_CHECK,
      error: null,
      violations: [],
      results: [],
      generationId: null,
    })

    try {
      // Update progress for safety check
      set({ progress: 10, currentStep: STEPS.SAFETY_CHECK })

      // Start a progress animation interval (fake progress while waiting)
      let currentProgress = 10
      const progressInterval = setInterval(() => {
        currentProgress = Math.min(currentProgress + 5, 85)
        const step = currentProgress < 25 ? STEPS.SAFETY_CHECK 
                   : currentProgress < 70 ? STEPS.GENERATING 
                   : STEPS.QUALITY_SCORING
        set({ progress: currentProgress, currentStep: step })
      }, 2000)

      // Call AWS GPU (Lambda/SageMaker) via Next.js API route (no FastAPI needed)
      let response: Response
      try {
        response = await fetch("/api/generate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            prompt: data.prompt,
            mode: data.mode || "REALISM",
            identityId: data.identityId || null,
            style_lora: data.style_lora || undefined,
            numImages: data.numImages || 2,
            quality_tier: data.quality_tier,
            physics: data.physics,
            surprise_me: data.surprise_me,
          }),
        })
      } finally {
        clearInterval(progressInterval)
      }

      // Check for errors BEFORE parsing JSON
      if (!response.ok) {
        // Handle authentication errors
        if (response.status === 401) {
          const errorData = await response.json().catch(() => ({ error: "Authentication required" }))
          set({
            status: "failed",
            progress: 0,
            currentStep: STEPS.FAILED,
            error: errorData.error || "Please sign in to generate images. Click 'Sign In' in the top right.",
          })
          return {
            success: false,
            jobId: "",
            status: "failed",
            message: errorData.error || "Authentication required",
            images: [],
            error: errorData.error || "Authentication required",
          }
        }

        // Handle blocked content
        if (response.status === 403) {
          const errorData = await response.json().catch(() => ({ error: "Content blocked" }))
          set({
            status: "blocked",
            currentStep: STEPS.BLOCKED,
            error: errorData.message || errorData.error || "Content blocked by safety filters",
            violations: errorData.violations || [],
            progress: 0,
          })
          return {
            success: false,
            jobId: "",
            status: "blocked",
            message: errorData.message || errorData.error,
            images: [],
            error: errorData.error,
            violations: errorData.violations,
          }
        }

        // Handle other errors
        const errorData = await response.json().catch(() => ({ error: "Generation failed" }))
        set({
          status: "failed",
          currentStep: STEPS.FAILED,
          error: errorData.error || errorData.message || `Generation failed: ${response.statusText}`,
          progress: 0,
        })
        return {
          success: false,
          jobId: "",
          status: "failed",
          message: errorData.error || errorData.message || "Generation failed",
          images: [],
          error: errorData.error,
        }
      }

      // Update progress - finalizing
      set({ progress: 90, currentStep: STEPS.FINALIZING })

      const result = await response.json()

      // Success - update state with results
      // Backend returns snake_case: job_id, images[].url, etc.
      const images: GeneratedImage[] = (result.images || []).map(
        (img: any, idx: number) => ({
          id: `${result.job_id}_${idx}`,
          url: img.url,
          seed: img.seed,
          scores: img.scores,
        })
      )

      set({
        status: "completed",
        currentStep: STEPS.COMPLETED,
        progress: 100,
        generationId: result.job_id,
        results: images,
      })

      return {
        success: true,
        jobId: result.job_id,
        status: "completed",
        message: result.message || `Generated ${images.length} images`,
        images,
      }
    } catch (error) {
      console.error("Generation error:", error)
      const errorMessage =
        error instanceof Error ? error.message : "Generation failed"

      set({
        status: "failed",
        currentStep: STEPS.FAILED,
        error: errorMessage,
        progress: 0,
      })

      return {
        success: false,
        jobId: "",
        status: "failed",
        message: errorMessage,
        images: [],
        error: errorMessage,
      }
    }
  },

  generateWithQualityTier: async (params) => {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: params.prompt,
        quality_tier: params.quality_tier,
        mode: params.mode || "REALISM",
        identityId: params.identity_id,
        user_id: params.user_id,
        style_lora: params.style_lora,
        negative_prompt: params.negative_prompt,
        width: params.width,
        height: params.height,
        num_inference_steps: params.num_inference_steps,
        guidance_scale: params.guidance_scale,
        seed: params.seed,
        num_images: params.num_images,
        physics: params.physics,
        surprise_me: params.surprise_me,
      }),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: "Generation failed" }))
      throw new Error(err.error || err.message || "Generation failed")
    }
    return response.json()
  },

  resetGeneration: () =>
    set({
      progress: 0,
      status: "idle",
      currentStep: STEPS.SAFETY_CHECK,
      generationId: null,
      error: null,
      violations: [],
      results: [],
    }),
}))

// Export types for use in components
export type { GenerationState, GeneratedImage, GenerationResult, GenerationData, TwoPassParams }

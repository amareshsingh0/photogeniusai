import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = "force-dynamic";

const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

/**
 * POST /api/generate/sync - Synchronous image generation
 * 
 * This waits for the generation to complete before returning.
 * WARNING: Can take 30-60 seconds. Use for testing or when real-time polling is not needed.
 */
export async function POST(req: Request) {
  try {
    const { userId: clerkId, getToken } = await auth();
    if (!clerkId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 }
      );
    }

    // Get the Clerk JWT token to pass to FastAPI
    const token = await getToken();

    const body = await req.json();
    const { prompt, mode, identityId, numImages, guidanceScale, numInferenceSteps, seed } = body;

    // Validate input
    if (!prompt || prompt.trim().length < 10) {
      return NextResponse.json(
        { error: "Prompt must be at least 10 characters" },
        { status: 400 }
      );
    }

    console.log("[api/generate/sync] Starting generation:", { prompt, mode, identityId });

    // Call FastAPI SYNC generation endpoint (waits for result) with Bearer token
    const response = await fetch(`${FASTAPI_URL}/api/v1/generation/sync`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        prompt: prompt.trim(),
        mode: mode || "REALISM",
        identity_id: identityId || null,
        num_images: numImages || 2,
        guidance_scale: guidanceScale || 7.5,
        num_inference_steps: numInferenceSteps || 40,
        seed: seed || null,
      }),
    });

    const data = await response.json();

    console.log("[api/generate/sync] FastAPI response:", { status: response.status, data });

    if (!response.ok) {
      // Handle specific error types
      if (response.status === 403) {
        // Safety check failed
        return NextResponse.json(
          {
            success: false,
            error: "Content blocked",
            message: data.detail?.error || "Your prompt was blocked by safety filters",
            violations: data.detail?.violations || [],
          },
          { status: 403 }
        );
      }
      
      return NextResponse.json(
        { 
          success: false,
          error: data.detail || data.error || "Generation failed", 
          message: data.message || "Unknown error",
        },
        { status: response.status }
      );
    }

    // Success - return generated images
    return NextResponse.json({
      success: true,
      jobId: data.job_id,
      status: data.status,
      message: data.message,
      images: data.images || [],
    });
  } catch (error) {
    console.error("[api/generate/sync POST] Error:", error);
    return NextResponse.json(
      { 
        success: false,
        error: "Failed to generate images",
        message: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}

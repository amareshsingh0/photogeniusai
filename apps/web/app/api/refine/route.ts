/**
 * API Route for Image Refinement
 *
 * Supports multiple cloud providers (AWS primary; GCP, Lightning optional)
 * Provider is auto-detected from environment variables.
 */

import { NextRequest, NextResponse } from "next/server";
import { AIService } from "@/lib/ai-service";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate required fields
    if (!body.image_base64) {
      return NextResponse.json(
        { error: "image_base64 is required" },
        { status: 400 }
      );
    }

    if (!body.refinement_request) {
      return NextResponse.json(
        { error: "refinement_request is required" },
        { status: 400 }
      );
    }

    if (!body.generation_history || !Array.isArray(body.generation_history)) {
      return NextResponse.json(
        { error: "generation_history is required and must be an array" },
        { status: 400 }
      );
    }

    // Call AI Service for refinement
    const result = await AIService.refine({
      imageBase64: body.image_base64,
      refinementRequest: body.refinement_request,
      generationHistory: body.generation_history,
      mode: body.mode || "REALISM",
      seed: body.seed,
    });

    if (!result.success) {
      return NextResponse.json(
        { error: result.error || "Refinement failed" },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      image_base64: result.imageBase64,
      provider: AIService.getProvider(),
    });
  } catch (error) {
    console.error("Refinement API error:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}

// Health check endpoint
export async function GET() {
  return NextResponse.json({
    status: "ok",
    service: "refinement-api",
    provider: AIService.getProvider(),
  });
}

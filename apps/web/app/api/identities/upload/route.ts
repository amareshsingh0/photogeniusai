import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export const dynamic = "force-dynamic";

// API base URL for the Python backend (has S3 configured)
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

/**
 * POST /api/identities/upload - Upload identity reference photos
 * Converts photos to base64 and forwards to Python API for S3 upload
 * Returns array of S3 URLs
 */
export async function POST(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const formData = await req.formData();
    const photos = formData.getAll("photos") as File[];

    if (!photos || photos.length === 0) {
      return NextResponse.json({ error: "No photos provided" }, { status: 400 });
    }

    if (photos.length > 20) {
      return NextResponse.json({ error: "Maximum 20 photos allowed" }, { status: 400 });
    }

    // Convert photos to base64
    const base64Photos: { data: string; filename: string; contentType: string }[] = [];
    
    for (const photo of photos) {
      if (!photo.type.startsWith("image/")) {
        continue;
      }
      
      const arrayBuffer = await photo.arrayBuffer();
      const base64 = Buffer.from(arrayBuffer).toString("base64");
      base64Photos.push({
        data: base64,
        filename: photo.name,
        contentType: photo.type,
      });
    }

    if (base64Photos.length === 0) {
      return NextResponse.json({ error: "No valid images provided" }, { status: 400 });
    }

    // Forward to Python API for S3 upload
    const response = await fetch(`${API_URL}/api/v1/identities/upload`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": clerkId,
      },
      body: JSON.stringify({
        photos: base64Photos,
        userId: clerkId,
      }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      console.error("[Upload to API failed]", errData);
      return NextResponse.json(
        { error: errData.detail || "Failed to upload photos" },
        { status: response.status }
      );
    }

    const result = await response.json();
    
    return NextResponse.json({
      success: true,
      urls: result.urls || [],
      count: result.urls?.length || 0,
    });
  } catch (error) {
    console.error("[api/identities/upload POST]", error);
    return NextResponse.json(
      { error: "Failed to upload photos" },
      { status: 500 }
    );
  }
}

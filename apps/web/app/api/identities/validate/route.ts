import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = 'force-dynamic';

/**
 * POST /api/identities/validate – validate photos before upload.
 * Body: { photos: File[] } (multipart/form-data).
 * Returns: { valid: boolean, errors: string[] }.
 */
export async function POST(req: Request) {
  try {
    const { userId: clerkId } = await auth();
    if (!clerkId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const formData = await req.formData();
    const files = formData.getAll("photos") as File[];

    if (!files || files.length === 0) {
      return NextResponse.json(
        { valid: false, errors: ["No photos provided"] },
        { status: 400 }
      );
    }

    const errors: string[] = [];
    const MIN_PHOTOS = 8;
    const MAX_PHOTOS = 20;
    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

    // Validate count
    if (files.length < MIN_PHOTOS) {
      errors.push(`At least ${MIN_PHOTOS} photos required`);
    }
    if (files.length > MAX_PHOTOS) {
      errors.push(`Maximum ${MAX_PHOTOS} photos allowed`);
    }

    // Validate each file
    files.forEach((file, index) => {
      if (file.size > MAX_FILE_SIZE) {
        errors.push(`Photo ${index + 1} (${file.name}) exceeds 10MB limit`);
      }
      if (!file.type.startsWith("image/")) {
        errors.push(`Photo ${index + 1} (${file.name}) is not a valid image`);
      }
    });

    // TODO: Add face detection validation
    // This would require calling the AI service to detect faces
    // For now, we just validate file properties

    return NextResponse.json({
      valid: errors.length === 0,
      errors,
      photoCount: files.length,
    });
  } catch (e) {
    console.error("[api/identities/validate]", e);
    return NextResponse.json(
      { valid: false, errors: ["Validation failed"] },
      { status: 500 }
    );
  }
}

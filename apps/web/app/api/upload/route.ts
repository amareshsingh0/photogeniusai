import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { createAdminClient } from "@/lib/supabase/admin";

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = 'force-dynamic';

const BUCKET = "uploads";
const MAX_SIZE = 10 * 1024 * 1024; // 10MB

/**
 * POST /api/upload – upload a file to Supabase Storage.
 * Returns { url: string } or 401/501.
 */
export async function POST(req: Request) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    let admin;
    try {
      admin = createAdminClient();
    } catch {
      return NextResponse.json(
        { error: "Upload not configured (Supabase keys missing)" },
        { status: 501 }
      );
    }

    const formData = await req.formData();
    const file = formData.get("file") as File | null;
    if (!file || !file.size) {
      return NextResponse.json(
        { error: "No file provided" },
        { status: 400 }
      );
    }
    if (file.size > MAX_SIZE) {
      return NextResponse.json(
        { error: "File too large (max 10MB)" },
        { status: 400 }
      );
    }
    if (!file.type.startsWith("image/")) {
      return NextResponse.json(
        { error: "Only images allowed" },
        { status: 400 }
      );
    }

    const ext = file.name.split(".").pop() || "jpg";
    const path = `${userId}/${Date.now()}-${Math.random().toString(36).slice(2, 9)}.${ext}`;

    const buf = Buffer.from(await file.arrayBuffer());

    const { error } = await admin.storage.from(BUCKET).upload(path, buf, {
      contentType: file.type,
      upsert: false,
    });

    if (error) {
      console.error("[api/upload]", error);
      return NextResponse.json(
        { error: "Upload failed. Ensure bucket '" + BUCKET + "' exists." },
        { status: 500 }
      );
    }

    const { data: urlData } = admin.storage.from(BUCKET).getPublicUrl(path);
    return NextResponse.json({ url: urlData.publicUrl });
  } catch (e) {
    console.error("[api/upload]", e);
    return NextResponse.json(
      { error: "Upload failed" },
      { status: 500 }
    );
  }
}

import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/admin-auth";
import { readFileSync, writeFileSync } from "fs";
import { join } from "path";

export const dynamic = "force-dynamic";

/**
 * GET /api/admin/settings - Get system settings from .env files
 */
export async function GET() {
  try {
    await requireAdmin();

    // Read API .env.local
    const apiEnvPath = join(process.cwd(), "..", "api", ".env.local");
    const apiEnv = readFileSync(apiEnvPath, "utf-8");

    // Parse environment variables
    const parseEnv = (content: string) => {
      const lines = content.split("\n");
      const settings: Record<string, any> = {};

      lines.forEach((line) => {
        const trimmed = line.trim();
        if (trimmed && !trimmed.startsWith("#")) {
          const [key, ...valueParts] = trimmed.split("=");
          if (key) {
            settings[key.trim()] = valueParts.join("=").trim();
          }
        }
      });

      return settings;
    };

    const apiSettings = parseEnv(apiEnv);

    // Extract relevant settings (hide sensitive keys)
    const settings = {
      generation: {
        backend: apiSettings.GENERATION_BACKEND || "sagemaker",
        useIdeogram: apiSettings.USE_IDEOGRAM === "true",
        useGeminiEngine: apiSettings.USE_GEMINI_ENGINE === "true",
        useTogether: apiSettings.USE_TOGETHER === "true",
        useBfl: apiSettings.USE_BFL === "true",
        useKie: apiSettings.USE_KIE === "true",
        usePixazo: apiSettings.USE_PIXAZO === "true",
      },
      quality: {
        threshold: parseFloat(apiSettings.QUALITY_CRITIC_THRESHOLD || "8.5"),
        dimensionFloor: parseFloat(apiSettings.QUALITY_DIMENSION_FLOOR || "7.0"),
        maxImages: parseInt(apiSettings.QUALITY_MAX_IMAGES || "2"),
        thresholds: {
          standard: parseFloat(apiSettings.QUALITY_CRITIC_THRESHOLD_STANDARD || "8.0"),
          premium: parseFloat(apiSettings.QUALITY_CRITIC_THRESHOLD_PREMIUM || "8.5"),
          ultra: parseFloat(apiSettings.QUALITY_CRITIC_THRESHOLD_ULTRA || "9.0"),
        },
      },
      aws: {
        region: apiSettings.AWS_REGION || "us-east-1",
        sagemakerEndpoint: apiSettings.SAGEMAKER_ENDPOINT || "",
        s3Bucket: apiSettings.S3_BUCKET || "",
      },
      providers: {
        hasGeminiKey: !!apiSettings.GEMINI_API_KEY,
        hasTogetherKey: !!apiSettings.TOGETHER_API_KEY,
        hasBflKey: !!apiSettings.BFL_API_KEY,
        hasKieKey: !!apiSettings.KIE_API_KEY,
        hasPixazoKey: !!apiSettings.PIXAZO_API_KEY,
        hasFalKey: !!apiSettings.FAL_KEY,
      },
    };

    return NextResponse.json({ settings });
  } catch (error: any) {
    console.error("[admin/settings] GET error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to fetch settings" },
      { status: error.message?.includes("Admin") ? 403 : 500 }
    );
  }
}

/**
 * PATCH /api/admin/settings - Update system settings
 */
export async function PATCH(req: Request) {
  try {
    await requireAdmin();

    const body = await req.json();
    const { category, key, value } = body;

    if (!category || !key || value === undefined) {
      return NextResponse.json(
        { error: "category, key, and value are required" },
        { status: 400 }
      );
    }

    // Map to actual environment variable names
    const envKeyMap: Record<string, string> = {
      "generation.useIdeogram": "USE_IDEOGRAM",
      "generation.useGeminiEngine": "USE_GEMINI_ENGINE",
      "generation.useTogether": "USE_TOGETHER",
      "generation.useBfl": "USE_BFL",
      "generation.useKie": "USE_KIE",
      "generation.usePixazo": "USE_PIXAZO",
      "quality.threshold": "QUALITY_CRITIC_THRESHOLD",
      "quality.dimensionFloor": "QUALITY_DIMENSION_FLOOR",
      "quality.maxImages": "QUALITY_MAX_IMAGES",
    };

    const envKey = envKeyMap[`${category}.${key}`];
    if (!envKey) {
      return NextResponse.json(
        { error: "Invalid setting key" },
        { status: 400 }
      );
    }

    // Read and update .env file
    const apiEnvPath = join(process.cwd(), "..", "api", ".env.local");
    let envContent = readFileSync(apiEnvPath, "utf-8");

    // Update or add the setting
    const regex = new RegExp(`^${envKey}=.*$`, "m");
    const newLine = `${envKey}=${value}`;

    if (regex.test(envContent)) {
      envContent = envContent.replace(regex, newLine);
    } else {
      envContent += `\n${newLine}`;
    }

    writeFileSync(apiEnvPath, envContent, "utf-8");

    return NextResponse.json({
      success: true,
      message: "Setting updated. Restart API server to apply changes.",
    });
  } catch (error: any) {
    console.error("[admin/settings] PATCH error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to update settings" },
      { status: error.message?.includes("Admin") ? 403 : 500 }
    );
  }
}

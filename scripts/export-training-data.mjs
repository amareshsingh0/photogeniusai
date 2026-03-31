#!/usr/bin/env node
/**
 * Data export pipeline for training data (GDPR/CCPA compliant).
 *
 * Exports opted-in generations to JSONL and uploads to S3 (photogenius-training-data/).
 * Filters: allowTrainingDataExport=true, quality (overallScore) > 7/10, no abuse reports,
 * user has not withdrawn consent. Anonymizes user IDs (hash).
 *
 * Usage:
 *   DATABASE_URL=postgresql://... AWS_REGION=us-east-1 node scripts/export-training-data.mjs
 *   Optional: BUCKET=photogenius-training-data MIN_QUALITY=70 BALANCE_CATEGORIES=1
 */

import { createHash } from "crypto";
import { writeFileSync, unlinkSync, readFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

const DATABASE_URL = process.env.DATABASE_URL;
const BUCKET = process.env.BUCKET || "photogenius-training-data";
const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const MIN_QUALITY = Number(process.env.MIN_QUALITY) || 70;
const BALANCE_CATEGORIES = process.env.BALANCE_CATEGORIES === "1";

function hashId(id) {
  return createHash("sha256").update(String(id)).digest("hex").slice(0, 16);
}

async function getPrisma() {
  const { PrismaClient } = await import("@prisma/client");
  return new PrismaClient({ datasources: { db: { url: DATABASE_URL } } });
}

async function main() {
  if (!DATABASE_URL) {
    console.error("Set DATABASE_URL");
    process.exit(1);
  }

  const prisma = await getPrisma();

  const withdrawnUserIds = await prisma.consentRecord
    .findMany({ where: { withdrawnAt: { not: null } }, select: { userId: true } })
    .then((rows) => new Set(rows.map((r) => r.userId)));

  const reportedGenerationIds = await prisma.abuseReport
    .findMany({ select: { generationId: true } })
    .then((rows) => new Set(rows.map((r) => r.generationId)));

  const generations = await prisma.generation.findMany({
    where: {
      allowTrainingDataExport: true,
      isDeleted: false,
      isQuarantined: false,
      overallScore: { gte: MIN_QUALITY },
      userId: { notIn: [...withdrawnUserIds] },
      id: { notIn: [...reportedGenerationIds] },
    },
    select: {
      id: true,
      userId: true,
      originalPrompt: true,
      selectedOutputUrl: true,
      outputUrls: true,
      overallScore: true,
      userRating: true,
      mode: true,
    },
    orderBy: { createdAt: "desc" },
  });

  let toExport = generations;
  if (BALANCE_CATEGORIES && generations.length > 0) {
    const byMode = {};
    for (const g of generations) {
      const m = g.mode || "REALISM";
      if (!byMode[m]) byMode[m] = [];
      byMode[m].push(g);
    }
    const minCount = Math.min(...Object.values(byMode).map((a) => a.length));
    toExport = Object.values(byMode).flatMap((arr) => arr.slice(0, minCount));
  }

  const lines = toExport.map((g) => {
    const imageUrl = g.selectedOutputUrl || (Array.isArray(g.outputUrls) ? g.outputUrls[0] : null) || "";
    const qualityScore = g.overallScore != null ? Math.round(g.overallScore * 10) / 10 : null;
    return JSON.stringify({
      prompt: g.originalPrompt,
      image_url: imageUrl,
      quality_score: qualityScore,
      user_rating: g.userRating ?? null,
      mode: g.mode,
      anonymized_user_id: hashId(g.userId),
    });
  });

  const tmpPath = join(tmpdir(), `photogenius-export-${Date.now()}.jsonl`);
  writeFileSync(tmpPath, lines.join("\n") + (lines.length ? "\n" : ""), "utf8");

  let uploaded = false;
  if (process.env.AWS_ACCESS_KEY_ID || process.env.AWS_PROFILE) {
    try {
      const { S3Client, PutObjectCommand } = await import("@aws-sdk/client-s3");
      const prefix = new Date().toISOString().slice(0, 10);
      const key = `${prefix}/export.jsonl`;
      const body = readFileSync(tmpPath);
      const s3 = new S3Client({ region: AWS_REGION });
      await s3.send(
        new PutObjectCommand({
          Bucket: BUCKET,
          Key: key,
          Body: body,
          ContentType: "application/jsonl",
        })
      );
      console.log(`Uploaded ${toExport.length} rows to s3://${BUCKET}/${key}`);
      uploaded = true;
    } catch (e) {
      console.error("S3 upload failed:", e.message);
    }
  } else {
    console.log("AWS credentials not set; skipping S3 upload. Output written to:", tmpPath);
  }

  console.log(`Exported ${toExport.length} generations (quality >= ${MIN_QUALITY}/100, excluded reported/withdrawn).`);
  if (!uploaded) console.log("Local file:", tmpPath);
  try {
    if (uploaded) unlinkSync(tmpPath);
  } catch (_) {}

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

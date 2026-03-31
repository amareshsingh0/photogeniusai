#!/usr/bin/env node
/**
 * Export preference_pairs from Postgres to JSONL for reward model training.
 * Usage: DATABASE_URL=postgresql://... node scripts/export-preference-pairs.mjs [--limit 5000] [--out pairs.jsonl]
 */

import { createWriteStream } from "fs";

const args = process.argv.slice(2);
const limitIdx = args.indexOf("--limit");
const limit = limitIdx >= 0 && args[limitIdx + 1] ? parseInt(args[limitIdx + 1], 10) : 50_000;
const outIdx = args.indexOf("--out");
const outPath = outIdx >= 0 && args[outIdx + 1] ? args[outIdx + 1] : "preference_pairs.jsonl";

const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL) {
  console.error("Set DATABASE_URL");
  process.exit(1);
}

async function main() {
  const { PrismaClient } = await import("@prisma/client");
  const prisma = new PrismaClient({ datasources: { db: { url: DATABASE_URL } } });

  const pairs = await prisma.preferencePair.findMany({
    take: limit,
    orderBy: { createdAt: "desc" },
    select: {
      prompt: true,
      imageAUrl: true,
      imageBUrl: true,
      preferred: true,
      source: true,
      strength: true,
    },
  });

  const stream = createWriteStream(outPath, { encoding: "utf8" });
  for (const p of pairs) {
    stream.write(JSON.stringify({
      prompt: p.prompt,
      image_a_url: p.imageAUrl,
      image_b_url: p.imageBUrl,
      preferred: p.preferred,
      source: p.source,
      strength: p.strength ?? null,
    }) + "\n");
  }
  stream.end();

  console.log(`Exported ${pairs.length} preference pairs to ${outPath}`);
  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

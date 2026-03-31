-- Cost profiling & smart routing: cost_usd, quality_tier_used, cache_hit
ALTER TABLE generations ADD COLUMN IF NOT EXISTS "costUsd" DOUBLE PRECISION;
ALTER TABLE generations ADD COLUMN IF NOT EXISTS "qualityTierUsed" VARCHAR(20);
ALTER TABLE generations ADD COLUMN IF NOT EXISTS "cacheHit" BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS generations_quality_tier_used_idx ON generations("qualityTierUsed");
CREATE INDEX IF NOT EXISTS generations_cache_hit_idx ON generations("cacheHit");
CREATE INDEX IF NOT EXISTS generations_cost_usd_idx ON generations("costUsd") WHERE "costUsd" IS NOT NULL;

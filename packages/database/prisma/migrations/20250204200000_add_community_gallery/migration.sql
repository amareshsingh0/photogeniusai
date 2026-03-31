-- CreateEnum
CREATE TYPE "GalleryModerationStatus" AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'FLAGGED');
CREATE TYPE "ChallengeStatus" AS ENUM ('DRAFT', 'ACTIVE', 'VOTING', 'ENDED');
CREATE TYPE "TemplatePriceType" AS ENUM ('FREE', 'PREMIUM');

-- AlterTable User: profile and relations
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "bio" VARCHAR(500);
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "displayName" VARCHAR(100);
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "allowTrainingExport" BOOLEAN NOT NULL DEFAULT false;

-- AlterTable Generation: public gallery
ALTER TABLE "generations" ADD COLUMN IF NOT EXISTS "isPublic" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "generations" ADD COLUMN IF NOT EXISTS "publishedAt" TIMESTAMPTZ;
ALTER TABLE "generations" ADD COLUMN IF NOT EXISTS "galleryCategory" VARCHAR(50);
ALTER TABLE "generations" ADD COLUMN IF NOT EXISTS "galleryStyle" VARCHAR(50);
ALTER TABLE "generations" ADD COLUMN IF NOT EXISTS "galleryModeration" "GalleryModerationStatus";
ALTER TABLE "generations" ADD COLUMN IF NOT EXISTS "galleryLikesCount" INTEGER NOT NULL DEFAULT 0;
ALTER TABLE "generations" ADD COLUMN IF NOT EXISTS "galleryCommentsCount" INTEGER NOT NULL DEFAULT 0;

-- CreateTable gallery_likes
CREATE TABLE IF NOT EXISTS "gallery_likes" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL,
    "generationId" UUID NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "gallery_likes_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "gallery_likes_userId_generationId_key" ON "gallery_likes"("userId", "generationId");
CREATE INDEX IF NOT EXISTS "gallery_likes_generationId_idx" ON "gallery_likes"("generationId");
CREATE INDEX IF NOT EXISTS "gallery_likes_userId_idx" ON "gallery_likes"("userId");
ALTER TABLE "gallery_likes" ADD CONSTRAINT "gallery_likes_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "gallery_likes" ADD CONSTRAINT "gallery_likes_generationId_fkey" FOREIGN KEY ("generationId") REFERENCES "generations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable gallery_comments
CREATE TABLE IF NOT EXISTS "gallery_comments" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL,
    "generationId" UUID NOT NULL,
    "body" TEXT NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "gallery_comments_pkey" PRIMARY KEY ("id")
);
CREATE INDEX IF NOT EXISTS "gallery_comments_generationId_idx" ON "gallery_comments"("generationId");
CREATE INDEX IF NOT EXISTS "gallery_comments_userId_idx" ON "gallery_comments"("userId");
ALTER TABLE "gallery_comments" ADD CONSTRAINT "gallery_comments_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "gallery_comments" ADD CONSTRAINT "gallery_comments_generationId_fkey" FOREIGN KEY ("generationId") REFERENCES "generations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable prompt_templates
CREATE TABLE IF NOT EXISTS "prompt_templates" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL,
    "name" VARCHAR(200) NOT NULL,
    "prompt" TEXT NOT NULL,
    "negativePrompt" TEXT,
    "suggestedSettings" JSONB,
    "priceType" "TemplatePriceType" NOT NULL DEFAULT 'FREE',
    "priceCredits" INTEGER NOT NULL DEFAULT 0,
    "usesCount" INTEGER NOT NULL DEFAULT 0,
    "successCount" INTEGER NOT NULL DEFAULT 0,
    "ratingSum" INTEGER NOT NULL DEFAULT 0,
    "ratingCount" INTEGER NOT NULL DEFAULT 0,
    "isPublic" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "prompt_templates_pkey" PRIMARY KEY ("id")
);
CREATE INDEX IF NOT EXISTS "prompt_templates_userId_idx" ON "prompt_templates"("userId");
CREATE INDEX IF NOT EXISTS "prompt_templates_priceType_idx" ON "prompt_templates"("priceType");
CREATE INDEX IF NOT EXISTS "prompt_templates_usesCount_idx" ON "prompt_templates"("usesCount");
CREATE INDEX IF NOT EXISTS "prompt_templates_createdAt_idx" ON "prompt_templates"("createdAt");
ALTER TABLE "prompt_templates" ADD CONSTRAINT "prompt_templates_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable template_ratings
CREATE TABLE IF NOT EXISTS "template_ratings" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL,
    "templateId" UUID NOT NULL,
    "rating" INTEGER NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "template_ratings_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "template_ratings_userId_templateId_key" ON "template_ratings"("userId", "templateId");
CREATE INDEX IF NOT EXISTS "template_ratings_templateId_idx" ON "template_ratings"("templateId");
ALTER TABLE "template_ratings" ADD CONSTRAINT "template_ratings_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "template_ratings" ADD CONSTRAINT "template_ratings_templateId_fkey" FOREIGN KEY ("templateId") REFERENCES "prompt_templates"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable template_purchases
CREATE TABLE IF NOT EXISTS "template_purchases" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL,
    "templateId" UUID NOT NULL,
    "creditsPaid" INTEGER NOT NULL,
    "creatorEarned" INTEGER NOT NULL,
    "platformEarned" INTEGER NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "template_purchases_pkey" PRIMARY KEY ("id")
);
CREATE INDEX IF NOT EXISTS "template_purchases_userId_idx" ON "template_purchases"("userId");
CREATE INDEX IF NOT EXISTS "template_purchases_templateId_idx" ON "template_purchases"("templateId");
ALTER TABLE "template_purchases" ADD CONSTRAINT "template_purchases_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "template_purchases" ADD CONSTRAINT "template_purchases_templateId_fkey" FOREIGN KEY ("templateId") REFERENCES "prompt_templates"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable challenges
CREATE TABLE IF NOT EXISTS "challenges" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "title" VARCHAR(200) NOT NULL,
    "description" TEXT NOT NULL,
    "theme" VARCHAR(100) NOT NULL,
    "startAt" TIMESTAMPTZ NOT NULL,
    "endAt" TIMESTAMPTZ NOT NULL,
    "status" "ChallengeStatus" NOT NULL DEFAULT 'DRAFT',
    "prizeCredits" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "challenges_pkey" PRIMARY KEY ("id")
);
CREATE INDEX IF NOT EXISTS "challenges_status_idx" ON "challenges"("status");
CREATE INDEX IF NOT EXISTS "challenges_startAt_idx" ON "challenges"("startAt");
CREATE INDEX IF NOT EXISTS "challenges_endAt_idx" ON "challenges"("endAt");

-- CreateTable challenge_submissions
CREATE TABLE IF NOT EXISTS "challenge_submissions" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "challengeId" UUID NOT NULL,
    "generationId" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "voteCount" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "challenge_submissions_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "challenge_submissions_challengeId_generationId_key" ON "challenge_submissions"("challengeId", "generationId");
CREATE INDEX IF NOT EXISTS "challenge_submissions_challengeId_idx" ON "challenge_submissions"("challengeId");
CREATE INDEX IF NOT EXISTS "challenge_submissions_userId_idx" ON "challenge_submissions"("userId");
ALTER TABLE "challenge_submissions" ADD CONSTRAINT "challenge_submissions_challengeId_fkey" FOREIGN KEY ("challengeId") REFERENCES "challenges"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "challenge_submissions" ADD CONSTRAINT "challenge_submissions_generationId_fkey" FOREIGN KEY ("generationId") REFERENCES "generations"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "challenge_submissions" ADD CONSTRAINT "challenge_submissions_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable challenge_votes
CREATE TABLE IF NOT EXISTS "challenge_votes" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "challengeId" UUID NOT NULL,
    "submissionId" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "challenge_votes_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "challenge_votes_challengeId_userId_key" ON "challenge_votes"("challengeId", "userId");
CREATE INDEX IF NOT EXISTS "challenge_votes_submissionId_idx" ON "challenge_votes"("submissionId");
CREATE INDEX IF NOT EXISTS "challenge_votes_userId_idx" ON "challenge_votes"("userId");
ALTER TABLE "challenge_votes" ADD CONSTRAINT "challenge_votes_challengeId_fkey" FOREIGN KEY ("challengeId") REFERENCES "challenges"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "challenge_votes" ADD CONSTRAINT "challenge_votes_submissionId_fkey" FOREIGN KEY ("submissionId") REFERENCES "challenge_submissions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "challenge_votes" ADD CONSTRAINT "challenge_votes_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable data_contributions
CREATE TABLE IF NOT EXISTS "data_contributions" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL,
    "generationId" UUID NOT NULL,
    "creditsEarned" INTEGER NOT NULL,
    "qualityBonus" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "data_contributions_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "data_contributions_generationId_key" ON "data_contributions"("generationId");
CREATE INDEX IF NOT EXISTS "data_contributions_userId_idx" ON "data_contributions"("userId");
CREATE INDEX IF NOT EXISTS "data_contributions_createdAt_idx" ON "data_contributions"("createdAt");
ALTER TABLE "data_contributions" ADD CONSTRAINT "data_contributions_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "data_contributions" ADD CONSTRAINT "data_contributions_generationId_fkey" FOREIGN KEY ("generationId") REFERENCES "generations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable follows
CREATE TABLE IF NOT EXISTS "follows" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "followerId" UUID NOT NULL,
    "followingId" UUID NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "follows_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "follows_followerId_followingId_key" ON "follows"("followerId", "followingId");
CREATE INDEX IF NOT EXISTS "follows_followerId_idx" ON "follows"("followerId");
CREATE INDEX IF NOT EXISTS "follows_followingId_idx" ON "follows"("followingId");
ALTER TABLE "follows" ADD CONSTRAINT "follows_followerId_fkey" FOREIGN KEY ("followerId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "follows" ADD CONSTRAINT "follows_followingId_fkey" FOREIGN KEY ("followingId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable activities
CREATE TABLE IF NOT EXISTS "activities" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL,
    "type" VARCHAR(50) NOT NULL,
    "targetType" VARCHAR(50) NOT NULL,
    "targetId" UUID,
    "metadata" JSONB,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "activities_pkey" PRIMARY KEY ("id")
);
CREATE INDEX IF NOT EXISTS "activities_userId_idx" ON "activities"("userId");
CREATE INDEX IF NOT EXISTS "activities_targetType_idx" ON "activities"("targetType");
CREATE INDEX IF NOT EXISTS "activities_createdAt_idx" ON "activities"("createdAt");
ALTER TABLE "activities" ADD CONSTRAINT "activities_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Indexes for generations (public gallery)
CREATE INDEX IF NOT EXISTS "generations_isPublic_idx" ON "generations"("isPublic");
CREATE INDEX IF NOT EXISTS "generations_publishedAt_idx" ON "generations"("publishedAt");
CREATE INDEX IF NOT EXISTS "generations_galleryModeration_idx" ON "generations"("galleryModeration");
CREATE INDEX IF NOT EXISTS "generations_galleryCategory_idx" ON "generations"("galleryCategory");
CREATE INDEX IF NOT EXISTS "generations_galleryStyle_idx" ON "generations"("galleryStyle");

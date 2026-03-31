# Community & Data Flywheel

This document describes the community features implemented for PhotoGenius AI: public gallery, prompt templates, challenges, data contribution, and social APIs.

## 1. Public Gallery

- **Publish**: Users opt-in to publish generations from **My Gallery** via "Publish to Explore". Only safe (postGenSafetyPassed, not quarantined) generations can be published.
- **Public URL**: `/explore` (Explore in nav; can be aliased to `/gallery` for public).
- **Filters**: `GET /api/gallery?category=&style=&sort=recent|trending|top_rated&limit=&cursor=`
- **Social**: Like (`POST /api/gallery/[id]/like`), comments (`GET/POST /api/gallery/[id]/comments`), share (Web Share API / copy link), report (`POST /api/gallery/report` with `generationId`, `reason`, `description`).
- **Moderation**: New publishes start as `galleryModeration: PENDING`. Admin review: `GET /api/admin/gallery?status=PENDING`, `PATCH /api/admin/gallery/[id]` with `{ status: "APPROVED"|"REJECTED"|"FLAGGED" }`. Reports create `AbuseReport` rows for review.
- **SEO**: Explore page is server-rendered with Open Graph metadata; `app/sitemap.ts` includes `/explore` and gallery item URLs.

## 2. Prompt Templates

- **Library**: `GET /api/templates?search=&priceType=FREE|PREMIUM&sort=recent|popular|rating&limit=&cursor=`
- **Create**: `POST /api/templates` (auth) with `name`, `prompt`, `negativePrompt?`, `suggestedSettings?`, `priceType?`, `priceCredits?`.
- **Get one**: `GET /api/templates/[id]`
- **Use**: `POST /api/templates/[id]` with `{ success?: boolean }`. FREE: increments uses/successCount. PREMIUM: deducts credits from caller, 70% to creator and 30% to platform (TemplatePurchase + user credits).
- **Rate**: `POST /api/templates/[id]/rate` with `{ rating: 1-5 }` (auth).
- **Metrics**: usesCount, successCount, successRate, ratingSum/ratingCount (and rating average).

## 3. Challenges & Contests

- **List**: `GET /api/challenges?status=ACTIVE|VOTING|ENDED|DRAFT&limit=`
- **Vote**: `POST /api/challenges/[id]/vote` with `{ submissionId }` (auth). Only when challenge `status === "VOTING"`. One vote per user per challenge (can change submission).
- **Leaderboard**: `GET /api/leaderboard?type=creators|templates&limit=` returns top by likes (creators) or by usesCount (templates).
- **Challenges** are created/updated via DB or future admin API. Submissions link a generation to a challenge (create `ChallengeSubmission` when user submits).

## 4. Data Contribution Incentives

- **Opt-in**: User flag `allowTrainingExport` (profile/settings). Toggle: `GET /api/contribute` (stats), `POST /api/contribute` with `{ optIn: true|false }`.
- **Credits**: When a generation is saved and the user has both consent (`allowTraining` in ConsentRecord) and `allowTrainingExport`, a `DataContribution` is created and user receives credits: base 5 per generation; 2× (10) if quality score ≥ 0.8 (using aestheticScore/faceMatchScore from request when available). User `creditsBalance` is incremented.
- **Tiers**: 100 contributions → 500 bonus credits; 1000 → 10,000 bonus + badge (logic in `/api/contribute` GET; actual bonus payout can be a cron or manual step).
- **Feedback**: Placeholder for "Your data helped improve X" (future: link contribution counts to model release notes).

## 5. Social Features

- **Follow**: `POST /api/users/[id]/follow` toggles follow; `GET /api/users/[id]/follow` returns `{ following: boolean }`. Creates `Follow` and optionally `Activity` (NEW_FOLLOWER).
- **Activity**: `Activity` model stores events (PUBLISHED_GALLERY, NEW_FOLLOWER, etc.). Activity feed API can be added as `GET /api/me/activity` or `GET /api/users/[id]/activity`.
- **Profiles**: User has `bio`, `displayName`; public portfolio = generations where `isPublic` and `galleryModeration === "APPROVED"` (filter by userId).
- **Embed**: For blogs, use `/explore` URL or a future `/embed?generationId=` route that renders a minimal card with image and link. API for developers: public `GET /api/gallery` and `GET /api/templates` are unauthenticated.

## Database (Prisma)

New/enhanced models and fields:

- **Generation**: `isPublic`, `publishedAt`, `galleryCategory`, `galleryStyle`, `galleryModeration`, `galleryLikesCount`, `galleryCommentsCount`.
- **User**: `bio`, `displayName`, `allowTrainingExport`.
- **GalleryLike**, **GalleryComment**, **PromptTemplate**, **TemplateRating**, **TemplatePurchase**, **Challenge**, **ChallengeSubmission**, **ChallengeVote**, **DataContribution**, **Follow**, **Activity**.

Migration: `packages/database/prisma/migrations/20250204200000_add_community_gallery/migration.sql`. Run `npx prisma migrate deploy` (or `prisma migrate dev`) when the DB is available.

## Success Metrics (reference)

- 10% of users publish to gallery (Month 1), 25% (Month 6).
- 1000+ prompt templates created.
- 50,000+ community-contributed training images (DataContribution rows).
- 20% monthly active users return weekly.

Track: share rate, template uses, contribution count, follow count, and return visits.

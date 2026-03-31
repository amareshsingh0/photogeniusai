# Consent & Training Data Collection

This document describes the **opt-in data collection and consent system** used to build a training data flywheel while staying GDPR/CCPA/EU AI Act compliant.

## 1. Consent flow

- **When:** A modal is shown after the user’s **first successful generation** on the generate page (“Help improve PhotoGenius?”).
- **Explanation:** Clear copy that we learn from their generations (anonymized) to improve models.
- **Incentive:** +100 free credits for opting in to “Allow training.”
- **Granular controls:**
  - **Allow training:** Use my prompts and results (anonymized) for model improvement.
  - **Allow showcase:** May feature my generations in marketing/gallery (with permission).
  - User can check neither, one, or both.

Consent is stored in `consent_records` with `allowTraining`, `allowShowcase`, and optional one-time `creditsGranted`. Users can **withdraw consent** anytime (Settings or `POST /api/consent/withdraw`).

## 2. Implementation

### Schema (Prisma)

- **ConsentRecord:** `allowTraining`, `allowShowcase`, `creditsGranted`, `withdrawnAt`.
- **Generation:** `allowTrainingDataExport` (set at creation from user’s current consent), `userRating` (optional 1–5).

When a generation is saved, we set `allowTrainingDataExport = true` only if the user has an active (non-withdrawn) consent record with `allowTraining = true`.

### API

| Endpoint | Description |
|----------|-------------|
| `GET /api/consent/status` | Returns `hasRecord`, `allowTraining`, `allowShowcase`, `showModal` (for modal logic). |
| `POST /api/consent/record` | Body: `allowTraining`, `allowShowcase`, optional `version`, `text`. Grants +100 credits once per user if `allowTraining` is true. |
| `POST /api/consent/withdraw` | Marks consent as withdrawn (GDPR). |

### UI

- **Component:** `@/components/consent/training-data-consent-modal.tsx`
- **Usage:** Rendered on the generate page; opened when `GET /api/consent/status` returns `showModal: true` after the first successful generation.

## 3. Data export pipeline

**Script:** `scripts/export-training-data.mjs`

- **Query:** Generations where `allowTrainingDataExport = true`, `overallScore >= 70`, `isDeleted = false`, `isQuarantined = false`, user not in (users with any `consent_records.withdrawnAt` set), and generation not in abuse reports.
- **Format:** JSONL with `prompt`, `image_url`, `quality_score`, `user_rating`, `mode`, `anonymized_user_id` (hashed).
- **Optional:** `BALANCE_CATEGORIES=1` to balance by `mode`.
- **Upload:** If AWS credentials are set, uploads to `photogenius-training-data/YYYY-MM-DD/export.jsonl`.

**Run (from repo root):**

```bash
DATABASE_URL="postgresql://..." node scripts/export-training-data.mjs
# Optional: BUCKET=photogenius-training-data MIN_QUALITY=70 BALANCE_CATEGORIES=1 AWS_REGION=us-east-1
```

Requires `@prisma/client` and `@aws-sdk/client-s3` (install in the workspace that has Prisma, e.g. root or `packages/database`).

## 4. Data quality filters (export)

- **Quality:** `overallScore >= 70` (configurable via `MIN_QUALITY`).
- **Exclude flagged/reported:** Exclude generations that appear in `abuse_reports`.
- **Exclude withdrawn:** Exclude users who have any consent record with `withdrawnAt` set.
- **Balance:** Optional per-category cap via `BALANCE_CATEGORIES=1`.

## 5. Legal documentation

Templates and process docs live in **`docs/legal/`**:

- **[DATA_USAGE_POLICY.md](legal/DATA_USAGE_POLICY.md)** – What we collect, how we use it, legal bases, rights (GDPR/CCPA).
- **[TRAINING_DATA_MANIFEST.md](legal/TRAINING_DATA_MANIFEST.md)** – EU AI Act–style transparency: source, schema, filters, storage.
- **[TAKEDOWN_PROCESS.md](legal/TAKEDOWN_PROCESS.md)** – Withdrawal of consent, erasure, takedown of content.

Serve these as your public Data Usage Policy, Training Data Manifest, and Takedown Process (e.g. at `/legal/data-usage`, `/legal/manifest`, `/legal/takedown` or equivalent).

## 6. Compliance checklist

- **GDPR:** Consent as basis; right to withdraw and to erasure; data minimization and anonymization in exports.
- **CCPA:** Opt-out and data disclosure; no sale of personal information.
- **EU AI Act:** Dataset transparency and documentation (manifest); human oversight and risk management as you scale.

## 7. Database migration

After pulling schema changes, run:

```bash
cd packages/database && pnpm prisma generate
# If using migrations: pnpm prisma migrate dev --name consent_training_fields
# Or: pnpm prisma db push
```

This adds `allowTraining`, `allowShowcase`, `creditsGranted`, `withdrawnAt` on `ConsentRecord` and `userRating`, `allowTrainingDataExport` on `Generation`.

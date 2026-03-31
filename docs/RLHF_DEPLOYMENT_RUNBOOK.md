# RLHF Pilot – Deployment Runbook

This runbook covers the minimal RLHF pipeline: data collection → reward model training → offline policy update → monitoring and rollout.

## 1. Data Collection

### 1.1 Preference capture

- **Explicit:** Thumbs up/down in gallery (Image Detail modal). Calls `POST /api/preferences/thumbs` with `generationId`, `imageUrl`, `thumbs: "up" | "down"`.
- **Implicit:**
  - **Save to gallery / Select output:** When user sets `selectedUrl` or favorite, `PATCH /api/generations/[id]` creates pairs (selected image preferred over other outputs). Source: `SAVE_GALLERY` or `EXPLICIT_THUMBS`.
  - **Download:** `POST /api/generations/[id]/download` records strong positive pairs. Source: `DOWNLOAD`.
  - **Delete:** Optional: record negative (deleted image vs kept); can be added in DELETE handler.

All pairs are stored in **`preference_pairs`** (Postgres): `prompt`, `imageAUrl`, `imageBUrl`, `preferred` (A/B/EQUAL), `source`, optional `strength`, `generationIdA/B`.

### 1.2 Target volume

- **Minimum:** 1,000+ preference pairs to train a useful reward model.
- **Goal:** 5,000+ for production RLHF.

Check count:

```sql
SELECT COUNT(*) FROM preference_pairs;
SELECT source, COUNT(*) FROM preference_pairs GROUP BY source;
```

## 2. Export preference data for training

From repo root (with `DATABASE_URL` set):

```bash
node scripts/export-preference-pairs.mjs --limit 5000 --out preference_pairs.jsonl
```

Requires Prisma and DB access. Output: one JSON object per line (`prompt`, `image_a_url`, `image_b_url`, `preferred`, `source`, `strength`).

## 3. Reward model training

### 3.1 Bradley-Terry preference model

- **Input:** Image A, Image B (and optional prompt).
- **Output:** Reward scores r(A), r(B). Preference P(A > B) = σ(r(A) - r(B)).
- **Loss:** Bradley-Terry pairwise ranking (see `reward_model_preference.py`).

### 3.2 Dataset mix

- **80%** user preference pairs (from `preference_pairs.jsonl`).
- **20%** AVA or other baseline (optional; script supports `--ava-dir` for mixed training).

### 3.3 Train

```bash
cd ai-pipeline
python training/reward_model_preference.py \
  --pairs /path/to/preference_pairs.jsonl \
  --epochs 5 --batch-size 32 --lr 1e-4 \
  --output-dir models/reward_preference
```

- **Evaluation:** Script reports validation accuracy (agreement with preferred). Target: Pearson r > 0.70 with human judgments when evaluated on a held-out set with human labels.
- **Export:** `models/reward_preference/reward_model_preference.pth` (same interface as aesthetic predictor for SageMaker).

## 4. Offline policy update

1. **Generate** 1000 images from recent prompts (from DB or a fixed prompt list).
2. **Score** each image with the reward model.
3. **Select** top 10% (rejection sampling).
4. **Fine-tune** base diffusion model on top 10% (supervised fine-tuning; no PPO in pilot).
5. **Export** new checkpoint for A/B test.

Script placeholder:

```bash
python ai-pipeline/scripts/offline_policy_update.py \
  --reward-checkpoint models/reward_model_preference.pth \
  --output-dir models/policy_canary \
  --top-fraction 0.1 --num-samples 1000
```

Implement generation + scoring + SFT in your pipeline (SageMaker training job or local GPU).

### 4.1 Safety constraint

- Before rollout: run safety eval on new checkpoint (same safety metrics as production).
- **No rollout** if safety metrics degrade (e.g. more violations on test set).

## 5. Rollout (canary → full)

- **Canary:** Deploy new checkpoint to 1–5% of traffic; compare acceptance rate and quality distribution.
- **10% → 50% → 100%:** Increase traffic if acceptance rate and safety hold.

## 6. Monitoring

### 6.1 Metrics to track

- **Reward model agreement with users:** % of pairs where model prefers same as user (e.g. on held-out set).
- **Acceptance rate:** Thumbs up / (thumbs up + thumbs down) or positive implicit signals vs negative.
- **Quality score distribution:** Mean/percentiles of reward score over time; detect shift after policy update.

### 6.2 Metrics script

```bash
DATABASE_URL=postgresql://... python ai-pipeline/scripts/rlhf_metrics.py
```

Outputs JSON: `total_pairs`, `by_source`, `acceptance_rate` (if derivable), `target_pairs`.

### 6.3 Automated rollback

- If acceptance rate drops below a threshold (e.g. 5% relative) after a policy rollout, revert to previous checkpoint and alert.
- Implement in your deployment pipeline (e.g. CloudWatch alarm + Lambda to switch model version).

## 7. Database migration

Ensure `preference_pairs` table exists (Prisma):

```bash
cd packages/database && npx prisma db push
# or: npx prisma migrate dev --name add_preference_pairs
```

## 8. Monthly cadence (pilot)

- **Week 1:** Collect preferences; export pairs.
- **Week 2:** Train reward model; evaluate Pearson r / accuracy.
- **Week 3:** Run offline policy update; safety check; canary deploy.
- **Week 4:** Monitor; expand to 10% → 50% → 100% if metrics good.

## 9. Files reference

| Item | Path |
|------|------|
| Preference API | `apps/web/app/api/preferences/route.ts`, `apps/web/app/api/preferences/thumbs/route.ts` |
| Download hook | `apps/web/app/api/generations/[id]/download/route.ts` |
| PATCH generations (implicit pairs) | `apps/web/app/api/generations/[id]/route.ts` |
| Thumbs UI | `apps/web/components/gallery/image-detail-modal.tsx` |
| Export pairs | `scripts/export-preference-pairs.mjs` |
| Reward model training | `ai-pipeline/training/reward_model_preference.py` |
| Offline policy script | `ai-pipeline/scripts/offline_policy_update.py` |
| Metrics | `ai-pipeline/scripts/rlhf_metrics.py` |

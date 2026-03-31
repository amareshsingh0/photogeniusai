# Base Model Strategy – 12-Month Roadmap

## Overview

- **Months 1–2:** Fine-tuning pilot (Option A): curate 20K dataset, train LoRA, run benchmark, A/B test 10%.
- **Months 3–4:** Scale dataset to 50K; re-run curation and fine-tuning; evaluate again.
- **Months 5–6:** Decide: continue fine-tuning vs train-from-scratch vs distill (Options B/C) based on pilot and scale results.
- **Months 7–12:** Execute chosen path (scale fine-tuning, start from-scratch, or distillation) and integrate into production.

---

## Month 1–2: Pilot (Option A – Fine-tuning)

| Week | Activity |
|------|----------|
| 1–2 | Dataset curation: aggregate user opt-in (5K), licensed stock (10K), public domain (5K). Run quality filter, BLIP-2 captions, dedup, license manifest. |
| 2–3 | Human review of captions (sample); fix and finalize manifest. Version as v1.0 (DVC or Hugging Face). |
| 3–4 | Fine-tuning: SDXL base + LoRA rank 128, 10K steps, 8× A100 (~40h). Save checkpoints every 500 steps. |
| 4–5 | Evaluation: run 1,000-prompt benchmark (base vs fine-tuned). Measure anatomy, composition, style. Target +15%. |
| 5–6 | Deployment: deploy fine-tuned LoRA as new endpoint; A/B test 10% traffic. Monitor acceptance rate, preference, latency. |

**Decision gate (end of Month 2):** If benchmark ≥ +15% and user preference ≥ neutral → proceed to scale (50K). If < +10% → revisit strategy (data, objectives, or Option C). If no improvement → consider Option B later.

---

## Month 3–4: Scale to 50K dataset

| Week | Activity |
|------|----------|
| 1–2 | Add more sources to reach 50K (e.g. more licensed stock, more public domain, additional user opt-in). |
| 2–3 | Run full curation pipeline (quality, caption, dedup, license). Version as v2.0. |
| 3–4 | Fine-tune again on 50K (or continue from v1 LoRA). 15K–20K steps. |
| 4–6 | Re-run benchmark; A/B test 25% then 50% if metrics hold. |

**Decision gate (end of Month 4):** If 50K model clearly beats 20K and base → full rollout. If marginal → iterate on data quality or try distillation (Option C).

---

## Month 5–6: Strategy decision

- **If fine-tuning ceiling is high enough:** Plan ongoing iterations (v3.0 dataset, new LoRAs for specific failure categories).
- **If ceiling is hit:** Evaluate Option B (train from scratch) cost and timeline; or Option C (distill ensemble). Document decision and next 6-month plan.

---

## Month 7–12: Execution

- **Path 1 (continue fine-tuning):** Quarterly dataset updates (v3.0, v4.0); train and deploy; monitor metrics.
- **Path 2 (train from scratch):** If approved, start data and infrastructure for SDXL-scale training; aim for first model in 6–12 months.
- **Path 3 (distillation):** If chosen, select teachers (e.g. SDXL + Flux + specialist), run distillation pipeline, deploy single model.

---

## Decision criteria (recap)

| Outcome | Action |
|---------|--------|
| Pilot ≥ +15%, user preference up | Scale to 50K; full rollout |
| Pilot < +10% | Revisit strategy; improve data or try Option C |
| No improvement | Consider Option B (from scratch) in 6–12 months |
| 50K better than 20K | Full rollout; plan v3.0 |

---

## Dependencies

- **Dataset curation pipeline:** `ai-pipeline/training/base_model/` (quality_filter, caption_blip2, dedup, license_tracking, run_curation_pipeline).
- **Training:** `finetune_sdxl_lora.py`, `train_sdxl_lora_impl.py` (config and LoRA training).
- **Evaluation:** `evaluate_benchmark.py` (1K benchmark, anatomy/composition/style).
- **Strategy and deployment:** `docs/BASE_MODEL_STRATEGY_ANALYSIS.md`, `docs/BASE_MODEL_DEPLOYMENT_PLAN.md`.

# Base Model Strategy Analysis

**Context:** Tier 1 drawback #1 — we do not own the base model. This limits our ability to shift creative priors and fix systematic biases. This document analyses current limitations, evaluates options, and defines decision criteria.

---

## 1. Current limitations (SDXL)

### 1.1 Twenty representative prompts where SDXL often fails

| # | Prompt (short) | Failure mode | Category |
|---|-----------------|--------------|----------|
| 1 | "person holding a cup, hand visible" | Wrong hand count, fused fingers | Anatomy |
| 2 | "two people facing each other, full body" | Extra limbs, bad proportions | Anatomy |
| 3 | "woman in red dress, standing, 3/4 view" | Dress merges with background, wrong composition | Composition |
| 4 | "portrait, rim light, dark background" | Flat lighting, no rim | Style / Lighting |
| 5 | "cinematic still, anamorphic 2.39:1" | Wrong aspect, not cinematic look | Style |
| 6 | "product shot, perfume bottle on marble" | Reflections wrong, bottle distorted | Composition / Objects |
| 7 | "horse galloping, motion blur" | Legs wrong, no motion blur | Motion / Anatomy |
| 8 | "elderly person, wrinkles, natural skin" | Plastic skin, no wrinkles | Style / Realism |
| 9 | "child playing, 8 years old" | Face too adult or distorted | Anatomy / Safety |
| 10 | "text overlay: HELLO in bold" | Garbled or wrong text | Typography |
| 11 | "symmetrical face, front view" | Asymmetric eyes/nose | Anatomy |
| 12 | "rainy street, neon signs, reflections" | No reflections, flat | Style / Lighting |
| 13 | "food photography, steam rising" | No steam, flat | Style |
| 14 | "architectural interior, wide angle" | Perspective wrong, bent lines | Composition |
| 15 | "person with umbrella, handle visible" | Umbrella-handle disconnect | Coherence |
| 16 | "golden hour, backlit portrait" | Overexposed or no glow | Lighting |
| 17 | "multiple objects on table, top-down" | Wrong relative scale, floating | Composition |
| 18 | "art deco poster style, 1920s" | Generic, not period-accurate | Style |
| 19 | "person with glasses, reflection in lens" | No reflection or wrong | Detail |
| 20 | "water splash, droplet detail" | Blurry, no droplet detail | Detail / Physics |

### 1.2 Failure rate by category (target metrics to measure)

| Category | Example prompts | Target measurement |
|----------|------------------|--------------------|
| Anatomy (hands, limbs, face) | 1, 2, 7, 9, 11 | % with correct anatomy (e.g. hand validator) |
| Composition (layout, perspective) | 3, 6, 14, 17 | % with correct composition (human or model score) |
| Style / lighting | 4, 5, 8, 12, 13, 16, 18 | % matching requested style (CLIP or human) |
| Typography | 10 | % readable/correct text |
| Coherence / objects | 15, 19, 20 | % with coherent objects and details |

**Aesthetic ceiling:** Define as the 95th percentile of human-rated aesthetic score on a fixed benchmark. Measure base SDXL today (e.g. 0.72) and track after fine-tuning (target +15% → ~0.83).

---

## 2. Options evaluation

### Option A — Fine-tune SDXL

| | |
|---|---|
| **Pro** | Faster, cheaper, leverages pretrained knowledge; can improve composition, anatomy, style with LoRA + DreamBooth. |
| **Con** | Cannot fix fundamental architectural issues (e.g. text decoder, attention). |
| **Cost** | ~$10K (GPU + data curation, 8× A100 ~40h). |
| **Time** | 4–6 weeks. |
| **Best for** | Pilot to prove +15% improvement; then scale dataset and iterate. |

### Option B — Train SDXL-scale model from scratch

| | |
|---|---|
| **Pro** | Full control; can fix architecture (e.g. better text, attention). |
| **Con** | Very expensive; requires large, high-quality dataset (e.g. 100M+ captioned images for competitive quality). |
| **Cost** | ~$100K–500K (compute + data). |
| **Time** | 3–6 months. |
| **Best for** | Long-term if fine-tuning ceiling is hit. |

### Option C — Distill ensemble

| | |
|---|---|
| **Pro** | Combine strengths of multiple models (e.g. SDXL + Flux + specialist). |
| **Con** | Limited to teacher knowledge; distillation loss can cap quality. |
| **Cost** | ~$50K. |
| **Time** | 2–3 months. |
| **Best for** | If we have several strong teachers and want one deployable model. |

---

## 3. Recommended path: Pilot Option A, then decide

1. **Pilot (Option A):** Fine-tune SDXL with LoRA (rank 128) + DreamBooth on 20K curated images. Target +15% on anatomy, composition, style, user preference.
2. **Evaluate:** Run 1,000-image benchmark; A/B test 10% traffic.
3. **Decision:**
   - Pilot ≥ +15% and user preference up → **Scale to 50K dataset**, continue fine-tuning.
   - Pilot &lt; +10% → **Revisit strategy** (data quality, objectives, or try Option C).
   - No improvement → **Consider Option B** (train from scratch) in 6–12 months.

---

## 4. Decision criteria summary

| Criterion | Proceed to scale (50K) | Revisit strategy | Consider from-scratch |
|-----------|------------------------|-------------------|------------------------|
| Benchmark improvement | ≥ +15% | &lt; +10% | No improvement |
| User preference (A/B) | Improved | Neutral | Worse |
| Anatomy / composition | Clear gain | Marginal | No gain |
| Cost/benefit | Positive | Unclear | N/A |

---

## 5. Data and infrastructure dependencies

- **Dataset:** 20K v1 (user opt-in 5K + licensed stock 10K + public domain 5K); annotations via BLIP-2 + human review.
- **Infrastructure:** Dataset curation pipeline (quality filter, captions, dedup, license tracking); versioning (e.g. DVC or Hugging Face datasets).
- **Evaluation:** 1,000-prompt benchmark with anatomy, composition, style, and preference metrics.

See:
- **Roadmap:** `BASE_MODEL_12MONTH_ROADMAP.md`
- **Deployment:** `BASE_MODEL_DEPLOYMENT_PLAN.md`
- **Implementation:** `ai-pipeline/training/base_model/` (curation pipeline, `finetune_sdxl_lora.py`, `train_sdxl_lora_impl.py`, `evaluate_benchmark.py`)
- **Sample benchmark prompts:** `ai-pipeline/training/base_model/benchmark_prompts_sample.jsonl` (expand to 1000 for full benchmark)

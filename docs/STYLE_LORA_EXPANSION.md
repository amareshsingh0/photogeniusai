# Style LoRA Expansion (P1)

20 diverse style LoRAs for Midjourney-level variety. Training, inference, and frontend are wired for AWS (SageMaker + Lambda + web).

---

## 1. Overview

| Item | Details |
|------|--------|
| **Goal** | 20 style LoRAs (cinematic, anime, photorealistic, oil painting, watercolor, digital art, concept art, pixel art, 3D render, sketch/pencil, comic book, ukiyo-e, Art Nouveau, cyberpunk, fantasy art, minimalist, surrealism, vintage photo, gothic, pop art) |
| **Base model** | SDXL 1.0 |
| **LoRA** | Rank 64, alpha 64, target `to_q`, `to_k`, `to_v`, `to_out.0`, dropout 0.1 |
| **Training** | 2000–3000 steps per style, lr 1e-4, batch 4 |
| **Infrastructure** | SageMaker Training Jobs (ml.g5.2xlarge), 4 styles in parallel; ~2–3 days for all 20 |

---

## 2. Implementation

### 2.1 Training (ai-pipeline)

- **`ai-pipeline/training/train_style_loras.py`**
  - **STYLE_DATASETS**: 20 styles with `dataset`, `trigger`, `examples` (e.g. cinematic_stills_4k, danbooru_quality_filtered, laion_aesthetic_7plus).
  - **StyleLoRATrainer**: `train_style_lora(style_name, dataset_path, trigger_phrase, output_dir, steps=2500, ...)` using diffusers + PEFT; latent-space training for SDXL.
  - **train_all_styles_local()**: Iterates STYLE_DATASETS and trains each style (local or SageMaker).
  - Existing Modal `train_style` / `train_all_styles` remain for reference.

### 2.2 SageMaker training

- **`aws/sagemaker/training/train_lora.py`**
  - SageMaker entrypoint: reads hyperparameters `style_name`, `steps`, `batch_size`, `learning_rate`, `output_s3`.
  - Uses STYLE_DATASETS (embedded) and inline trainer (or optional `train_style_loras_sagemaker`).
  - Output: `/opt/ml/model/{style_name}/` (lora.safetensors + config.json); optional upload to `s3://photogenius-models-{env}/loras/styles/`.
- **`aws/sagemaker/training/launch_style_jobs.py`**
  - Launches SageMaker PyTorch training jobs: `--role`, `--bucket`, `--prefix loras/styles`, `--parallel 4`, optional `--styles cinematic anime ...`.

### 2.3 Inference

- **`ai-pipeline/services/two_pass_generation.py`**
  - `generate_two_pass(..., style_lora=None)`. Pass 2: loads identity LoRA (if any), then style LoRA from `LORA_DIR/styles/{style_lora}/` (lora.safetensors or directory).
- **`aws/sagemaker/model/code/inference_two_pass.py`**
  - `input_fn`: accepts `style_lora`. `predict_fn`: loads style LoRA from `lora_dir/styles/{style_lora}/` before base generation (identity + style supported).
- **Lambda orchestrator** (`aws/lambda/orchestrator/handler.py`): Forwards `style_lora` in payload to two-pass (and single-pass when applicable). If client does not send `style_lora`, semantic enhancer can auto-apply via `suggest_style_lora(enhanced_prompt)`.

### 2.4 Semantic enhancer → auto-apply style LoRA

- **`ai-pipeline/services/semantic_prompt_enhancer.py`**
  - **STYLE_KEYWORDS_TO_LORA**: Maps prompt keywords to style names (e.g. "cinematic" → cinematic, "anime" → anime).
  - **suggest_style_lora(prompt)**: Returns suggested style name or None; longest matching keyword wins.
- **`aws/lambda/orchestrator/semantic_prompt_enhancer.py`**
  - Same STYLE_KEYWORDS_TO_LORA and `suggest_style_lora()` for Lambda; orchestrator calls it when `style_lora` is not in the request body and sets `style_lora` for the downstream payload.

### 2.5 Frontend

- **`apps/web/components/generate/style-selector.tsx`**
  - **STYLE_OPTIONS**: 20 styles with id, name, description, icon (matches STYLE_DATASETS keys).
  - **StyleSelector**: Grid of style buttons; optional “Clear style”.
- **Generate page**: Form and Two-Pass tabs show StyleSelector; selected style is sent as `style_lora` in API body.
- **Store & API**: `TwoPassParams.style_lora`, `GenerationData.style_lora`; `/api/generate` and orchestrator receive and forward `style_lora`.

---

## 3. Dataset sources (reference)

| Style | Dataset (reference) |
|-------|----------------------|
| Cinematic | MovieStills / cinematic_stills_4k |
| Anime | Danbooru (score > 100) / danbooru_quality_filtered |
| Photorealistic | LAION Aesthetics v2 (score > 7) / laion_aesthetic_7plus |
| Art styles | WikiArt, DeviantArt filtered |
| Concept art | ArtStation scraped / artstation_concept_art |

Training script supports synthetic data when no dataset path is provided (generate with trigger phrase then train on that).

---

## 4. S3 and endpoints

- **Upload trained LoRAs**: `s3://photogenius-models-{env}/loras/styles/{style_name}/` (lora.safetensors + config.json).
- **Inference**: Set `LORA_DIR` on SageMaker to include an S3 mount or copy of `loras/` so that `loras/styles/{style_name}/` is available.

---

## 5. Testing checklist

- [ ] Train one style locally or on SageMaker: `style_name=cinematic`, confirm lora.safetensors and config.json under output dir.
- [ ] Upload to S3; deploy or update two-pass endpoint so LORA_DIR includes `styles/cinematic/`.
- [ ] Call two-pass with `style_lora: "cinematic"`; confirm Pass 2 uses style LoRA and output reflects style.
- [ ] Frontend: select “Cinematic” in StyleSelector, run Two-Pass PREMIUM; confirm request includes `style_lora` and result matches.
- [ ] Orchestrator: send prompt “a cinematic film still” without `style_lora`; confirm Lambda logs “Style LoRA auto-applied from prompt: cinematic” and response uses that style.

---

## 6. Related docs

- [AWS_TWO_PASS.md](AWS_TWO_PASS.md) – Two-pass SageMaker pipeline.
- [ORCHESTRATOR_AWS_INTEGRATION.md](ORCHESTRATOR_AWS_INTEGRATION.md) – Lambda orchestrator and quality tiers.
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) – Phase 2 and Style LoRA status.

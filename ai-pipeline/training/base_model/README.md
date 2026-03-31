# Base Model Pilot – Dataset Curation Pipeline

## Overview

Pipeline to curate the v1.0 (20K) and v2.0 (50K) training datasets for SDXL fine-tuning:

1. **Quality filter** – resolution, aspect ratio, file size, blur (Laplacian variance)
2. **Caption generation** – BLIP-2 for detailed captions (optional; human review recommended)
3. **Deduplication** – file hash + perceptual hash (pHash)
4. **License tracking** – manifest of license per source (user_consent, commercial_license, public_domain)

## Setup

```bash
# From repo root or ai-pipeline
pip install pillow numpy
# For BLIP-2 captions:
pip install transformers torch accelerate
# For perceptual dedup:
pip install imagehash
```

## Usage

### 1. Quality filter only

```bash
python ai-pipeline/training/base_model/quality_filter.py data/base_model/sources/user_optin --output data/base_model/curated/quality_passed.jsonl
```

### 2. BLIP-2 captions (on existing manifest)

```bash
python ai-pipeline/training/base_model/caption_blip2.py data/base_model/curated/quality_passed.jsonl -o data/base_model/curated/captions.jsonl
```

### 3. Deduplication

```bash
python ai-pipeline/training/base_model/dedup.py data/base_model/curated/captions.jsonl -o data/base_model/curated/v1.0/manifest.jsonl
```

### 4. License manifest

```bash
python ai-pipeline/training/base_model/license_tracking.py data/base_model/curated/v1.0/manifest.jsonl -o data/base_model/curated/v1.0/license_manifest.json
```

### 5. Full pipeline (quality → dedup → license; captions optional)

```bash
python ai-pipeline/training/base_model/run_curation_pipeline.py --input data/base_model/sources --output data/base_model/curated/v1.0 [--captions]
```

## Human-in-the-loop review

- After BLIP-2, review a sample of captions and fix errors.
- Use a simple review UI (e.g. CSV/JSON + internal tool, or Label Studio) to mark bad captions and optionally edit them.
- Exclude NSFW or off-brand images in the quality step or via a separate safety classifier.

## Versioning

- **v1.0**: 20K images (5K user opt-in + 10K licensed stock + 5K public domain)
- **v2.0**: 50K images (after 3 months)
- Use DVC or Hugging Face Datasets to version `data/base_model/curated/` and push to remote storage.

## Config

See `dataset_config.yaml` for paths, targets, and quality thresholds.

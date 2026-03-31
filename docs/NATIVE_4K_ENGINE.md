# Native 4K Engine (P2)

Generate true 4K images (3840×2160 or 3840×3840) without upscaling. Two methods: MultiDiffusion (latent upscale + tiled VAE decode) and iterative refinement.

---

## 1. Overview

| Item | Details |
|------|--------|
| **Resolutions** | 3840×2160 (16:9), 3840×3840 (1:1) |
| **Methods** | `latent`: 1024 latent → upscale latents → tiled VAE decode; `iterative`: 1024 → 2048 img2img → 4K img2img |
| **Target time** | 120–180 seconds on ml.g5.4xlarge |
| **GPU** | 20–24GB (ml.g5.4xlarge) or 48GB (ml.g5.8xlarge) |
| **Quality** | No visible tiling artifacts; vae_tiling + vae_slicing enabled |

---

## 2. Implementation

### 2.1 ai-pipeline (`ultra_high_res_engine.py`)

- **Constants:** `WIDTH_4K_UHD`, `HEIGHT_4K_UHD` = 3840, 2160; `WIDTH_4K_SQ`, `HEIGHT_4K_SQ` = 3840, 3840.
- **`_upscale_latents(latents, target_size)`:** Bicubic upscale to (H/8, W/8) for SDXL VAE.
- **`generate_4k_native_latent(...)`:** First pass 1024×1024 latent; upscale latents to 4K latent size; tiled VAE decode; return PIL.
- **`generate_4k_iterative(...)`:** Base 1024 → resize 2048 → img2img strength 0.3 → resize to 3840×2160/3840×3840 → img2img strength 0.2.
- **`generate_4k_native(...)` (Modal):** Wrapper with `method="latent"` or `"iterative"`; returns dict with `image_base64`, `width`, `height`, `pipeline`.
- **`enable_vae_slicing`** added in `load_models` alongside `enable_vae_tiling`.

### 2.2 SageMaker

- **`aws/sagemaker/model/code/inference_4k.py`:** `model_fn` loads SDXL Base + img2img, enables vae_tiling/slicing and attention_slicing. `input_fn`: prompt, negative_prompt, width (3840), height (2160|3840), steps, guidance_scale, seed, method (latent|iterative). `predict_fn` runs latent or iterative path; `output_fn` returns image_base64, width, height, inference_time, error.
- **`aws/sagemaker/deploy_4k.py`:** Packages code dir, uploads to S3, deploys PyTorch model to endpoint (default `photogenius-4k-dev`, instance `ml.g5.4xlarge`).

### 2.3 Lambda orchestrator

- **`SAGEMAKER_4K_ENDPOINT`:** When set, PREMIUM tier with `resolution=4k` or `width=3840` / `height` in (2160, 3840) routes to the 4K endpoint instead of two-pass.
- **Request:** `quality_tier=PREMIUM`, `resolution=4k` (or `width=3840`, `height=2160`/`3840`); optional `4k_method=latent`|`iterative`.
- **Response:** Same shape as PREMIUM (images.preview, images.final, metadata) with `metadata.resolution=4k`, `metadata.width`, `metadata.height`, `metadata.final_time` (inference_time).

### 2.4 SAM template

- **Parameter:** `SageMaker4KEndpoint` (default `""`).
- **OrchestratorFunction env:** `SAGEMAKER_4K_ENDPOINT: !Ref SageMaker4KEndpoint`.

---

## 3. Deployment

1. Package: `tar -czf model_4k.tar.gz -C aws/sagemaker/model/code .` (or use `deploy_4k.py` which packages the code dir).
2. Upload to S3 (or set `MODEL_S3_URI`).
3. Run `python aws/sagemaker/deploy_4k.py` (set `SAGEMAKER_ROLE`, optional `SAGEMAKER_BUCKET`, `SAGEMAKER_INSTANCE_4K=ml.g5.4xlarge`, `SAGEMAKER_ENDPOINT_4K=photogenius-4k-dev`).
4. Set Lambda env `SAGEMAKER_4K_ENDPOINT=photogenius-4k-dev` (or pass parameter in SAM).

---

## 4. Testing

- Call PREMIUM with `resolution=4k` (or `width=3840`, `height=2160`); confirm response has `metadata.resolution=4k` and a 3840×2160 image.
- Call 4K endpoint directly: POST `{"prompt": "a landscape", "width": 3840, "height": 2160, "method": "latent"}`; confirm image_base64 and inference_time ~120–180s.

---

## 5. Related docs

- [AWS_TWO_PASS.md](AWS_TWO_PASS.md) – Two-pass pipeline (preview + final).
- [ORCHESTRATOR_AWS_INTEGRATION.md](ORCHESTRATOR_AWS_INTEGRATION.md) – Lambda quality tiers and routing.
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) – Phase 2 and 4K status.

# Two-Pass Generation on AWS (SageMaker)

Two-pass pipeline: **fast preview** (SDXL Turbo, ~5s) then **full quality** (SDXL Base + Refiner, ~45s). Designed for **AWS only** (no Modal).

## Pipeline

| Pass | Model                       | Steps | Size      | Time |
| ---- | --------------------------- | ----- | --------- | ---- |
| 1    | SDXL Turbo                  | 4     | 512×512   | < 5s |
| 2    | SDXL Base (+ optional LoRA) | 50    | 1024×1024 | ~40s |
| 3    | SDXL Refiner (img2img)      | 25    | 1024×1024 | ~5s  |

- **Preview**: recognizable composition in seconds.
- **Final**: refined 1024×1024 image.
- **Memory**: `torch.cuda.empty_cache()` between passes; attention/VAE slicing; fp16.

## Files

- **`ai-pipeline/services/two_pass_generation.py`** – Canonical implementation (no Modal).
- **`aws/sagemaker/model/code/inference_two_pass.py`** – SageMaker entrypoint: **model_fn** (loads Turbo, Base, Refiner at startup; fp16 + attention slicing; graceful degrade if Turbo/Refiner missing), **input_fn**, **predict_fn**, **output_fn**. Self-contained; optional copy of `two_pass_generation.py` in package.
- **`aws/sagemaker/model/code/requirements.txt`** – diffusers, torch, Pillow, etc.
- **`aws/sagemaker/package_two_pass.sh`** – Script to create `model_two_pass.tar.gz` (syncs from ai-pipeline, then tars `model/code`).
- **`aws/sagemaker/deploy_two_pass.py`** – Deploy script: package (or use `MODEL_S3_URI`), upload, create PyTorchModel, deploy to `ml.g5.2xlarge` (A10G 24GB).
- **`aws/sagemaker/.env.local`** – Model paths, `HUGGINGFACE_TOKEN`, `REGULARIZATION_*`, `SAGEMAKER_*`. Used when running deploy scripts from `aws/sagemaker/`. Create from template if missing; fill values for your account.

## Environment

- **In container:** `MODEL_DIR` (e.g. `/opt/ml/model`), `LORA_DIR`, `SDXL_TURBO_PATH`, `SDXL_BASE_PATH`, `SDXL_REFINER_PATH` – local paths or HuggingFace IDs (auto-fallback to stabilityai/sdxl-turbo etc. if path missing).
- **`HUGGINGFACE_TOKEN` / `HF_TOKEN`** – optional, for gated models.
- **Deploy:** `SAGEMAKER_ROLE`, `SAGEMAKER_BUCKET`, `AWS_REGION`, `SAGEMAKER_ENDPOINT_TWO_PASS`, `SAGEMAKER_INSTANCE_TWO_PASS` (default `ml.g5.2xlarge`), optional `MODEL_S3_URI`.

## Deploying Two-Pass on SageMaker

1. **Package model code**:

   ```bash
   bash aws/sagemaker/package_two_pass.sh
   ```

   Creates `aws/sagemaker/model_two_pass.tar.gz`. Optionally syncs `two_pass_generation.py` from ai-pipeline.

2. **Upload to S3** (or let deploy script do it):

   ```bash
   aws s3 cp aws/sagemaker/model_two_pass.tar.gz s3://YOUR_BUCKET/models/two-pass/model.tar.gz
   ```

3. **Deploy** (set `SAGEMAKER_ROLE`; optional `SAGEMAKER_BUCKET`, `MODEL_S3_URI`):

   ```bash
   python aws/sagemaker/deploy_two_pass.py
   ```

   Uses PyTorch DLC, entry `inference_two_pass.py`, instance `ml.g5.2xlarge`, timeout 600s.

4. **Invoke**:

   ```json
   {
     "prompt": "professional headshot of a person",
     "identity_id": "optional-lora-id",
     "user_id": "user-123",
     "negative_prompt": "blurry, low quality",
     "return_preview": true,
     "seed": 42
   }
   ```

5. **Response**:
   ```json
   {
     "preview_base64": "...",
     "final_base64": "...",
     "preview_time": 4.2,
     "final_time": 41.5
   }
   ```

## Error Handling

- **SDXL Turbo missing** → preview skipped (`preview_base64`: null, `preview_time`: 0).
- **Refiner missing** → final = Pass 2 output (no img2img refinement).
- **Pass 2 failure** → response includes `error`; `final_base64` may be empty.

## Performance Targets

- Preview: < 5 seconds
- Final: < 45 seconds total
- GPU memory: < 12GB peak (fp16 + slicing + cache clear)

## Testing Checklist

- [ ] Model packaging creates valid `model_two_pass.tar.gz` (run `package_two_pass.sh` or `package_two_pass.ps1`)
- [ ] S3 upload successful: `aws s3 cp model_two_pass.tar.gz s3://YOUR_BUCKET/models/two-pass/model.tar.gz`
- [ ] SageMaker endpoint deploys without errors (`python aws/sagemaker/deploy_two_pass.py`)
- [ ] Endpoint status = InService (check AWS Console or `describe_endpoint`)
- [ ] Preview generates in < 5 seconds (invoke with `return_preview: true`)
- [ ] Final generates in < 45 seconds total
- [ ] GPU memory usage < 12GB peak (fp16 + attention/VAE slicing + cache clear)
- [ ] Error handling: missing Turbo → preview skipped; missing Refiner → final = Pass 2 output
- [ ] LoRA loading works when `identity_id` and `user_id` provided and LoRA file exists under `LORA_DIR`
- [ ] Base64 encoding: response has `preview_base64` and `final_base64` (or null for preview if skipped)

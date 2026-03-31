# Finish Engine – Post-processing

4× upscale (RealESRGAN), face restoration (**CodeFormer**, GFPGAN fallback), color grading (**.cube** LUTs + programmatic), film grain, sharpening. Batch processing; preserves original on failure.

## Features

- **4× upscale:** RealESRGAN x4plus (tiled for large images).
- **Face restoration:** **CodeFormer** first; **GFPGAN** fallback if CodeFormer fails.
- **Color grading:** **.cube** LUTs from `/luts` volume (`cinematic.cube`, `vibrant.cube`, etc.); programmatic LUTs as fallback.
- **Film grain / sharpen:** Optional; configurable intensity.

## API

### `finish` (base64 in/out, orchestrator-friendly)

```python
finish(images, upscale=True, face_fix=True, color_grade=None, film_grain=0.0, sharpen=0.0, output_format="png")
```

- **`images`:** List of dicts with `image_base64` (or `image_bytes`). Other keys preserved.
- **Returns:** List of dicts with `image_base64`, `processed`, `applied` (upscale, face_fix, color_grade, etc.). On failure, `processed=False`, `error` set, original `image_base64` kept.

### `finish_from_paths` (paths in, file or S3 out)

```python
finish_from_paths(
    image_paths,
    upscale=True, face_fix=True, color_grade=None,
    film_grain=0.0, sharpen=0.0, output_format="png",
    upload_s3=False, s3_bucket="photogenius-results",
)
```

- **`image_paths`:** List of image paths to process.
- **`upload_s3`:** If true, upload finished images to S3 (requires `aws-secret`).
- **Returns:** List of dicts with `image_path` (local or `s3://...`), `processed`, `applied`, etc. Preserves original on failure.

## LUTs

- Place **.cube** files in the `color-luts` volume at `/luts` (e.g. `cinematic.cube`, `vibrant.cube`, `vintage.cube`, `cool.cube`, `warm.cube`, `neutral.cube`). These override programmatic LUTs for the same names.
- If no .cube files exist, built-in programmatic LUTs are used.

## Orchestrator integration

When the plan includes a **finish** engine, the orchestrator calls `finish` after rerank. Finish params come from the plan (`upscale`, `face_fix`, `color_grade`, `enhance_details`). `color_grade` LUT is chosen by mode (e.g. REALISM→neutral, CINEMATIC→cinematic). `enhance_details` enables sharpening.

## Deploy

```bash
modal deploy ai-pipeline/services/finish_engine.py
```

- **Models:** RealESRGAN, CodeFormer (and optionally GFPGAN) under `photogenius-models`. First run downloads them.
- **LUTs:** Optional `color-luts` volume with .cube files.
- **S3:** For `finish_from_paths(..., upload_s3=True)`, create `aws-secret` with AWS credentials.

## Validation

- Test 4× upscale vs original.
- Verify face restoration (CodeFormer) on damaged faces.
- Check color grading with .cube and programmatic LUTs.
- Measure processing time (<10s per image target) and ensure fallback preserves original on failure.

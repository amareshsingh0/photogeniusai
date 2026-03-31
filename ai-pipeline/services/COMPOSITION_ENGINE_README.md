# Composition Engine – Multi-ControlNet (Pose, Depth, Canny)

Pose (OpenPose), depth (MiDaS), and Canny edge detection from a reference image, then generation via `StableDiffusionXLControlNetPipeline` with all three controls. Used for composition-preserving and action/pose-guided generation.

## Features

- **Pose:** OpenPose-style skeleton from reference (controlnet_aux).
- **Depth:** MiDaS depth map from reference (controlnet_aux / Intel DPT).
- **Canny:** Edge map from reference (controlnet_aux CannyDetector or cv2 fallback), `low_threshold=100`, `high_threshold=200`.
- **Multi-ControlNet:** SDXL pipeline with pose + depth + canny; conditioning scales `[1.0, 0.8, 0.5]` by default.
- **Optional S3 upload:** `upload_s3=True` saves outputs to S3 and adds `image_path` (e.g. `s3://photogenius-results/composed/...`) to each result.
- **Multi-identity:** `compose_multi_identity` accepts `identity_ids` and `identity_positions`; currently falls back to single-reference `compose` (inpainting TBD). `_create_position_mask` available for future use.

## API

### `compose`

```python
compose(
    prompt: str,
    reference_images: List[Union[str, bytes]],  # base64, path, or bytes
    identities: Optional[List[str]] = None,     # reserved for multi-identity; no-op here
    negative_prompt: str = DEFAULT_NEGATIVE,
    num_images: int = 4,
    width: int = 1024,
    height: int = 1024,
    guidance_scale: float = 7.5,
    controlnet_conditioning_scale: Optional[List[float]] = None,  # [pose, depth, canny]
    num_inference_steps: int = 50,
    seed: Optional[int] = None,
    return_base64: bool = True,
    upload_s3: bool = False,
    s3_bucket: str = "photogenius-results",
) -> List[Dict]
```

Returns a list of dicts with `image_base64`, `seed`, `controls_used`, `controlnet_scales`; optionally `image_path` when `upload_s3=True`. Uses the first reference for pose/depth/canny.

### `compose_multi_identity`

```python
compose_multi_identity(
    prompt: str,
    reference_image: Union[str, bytes],
    identity_ids: List[str],
    identity_positions: List[Dict],  # [{"x": 0.2, "y": 0.3, "scale": 0.5}, ...]
    **kwargs,
) -> List[Dict]
```

Falls back to single-reference `compose`; adds `identities_used` and `positions` to each result. Full inpainting-based multi-identity is not yet implemented.

## Orchestrator integration

- When **`requires_composition`** (action words like “jumping”, “dancing”, “yoga”) and **`reference_images`** are provided, the orchestrator calls the composition engine before identity/generation.
- **`composition_params`** optional: `{"identity_ids": ["id1", "id2", ...], "identity_positions": [{"x": 0.2, "y": 0.3, "scale": 0.5}, ...]}`. When `identity_ids` has **>1** ids (and `identity_positions` match), the orchestrator calls **`compose_multi_identity`**; otherwise **`compose`**.
- **`reference_images`** / **`composition_params`** can be passed via `orchestrate`, `orchestrate_with_cache`, `orchestrate_multimodal`, or web endpoints.
- Composition results are turned into candidates with placeholder scores and then reranked/finish as usual.

## Deploy

```bash
modal deploy ai-pipeline/services/composition_engine.py
```

- **Models:** SDXL base, ControlNet pose/depth/canny (Hugging Face). Preprocessors (OpenPose, MiDaS, Canny) from controlnet_aux.
- **Secrets:** `huggingface` (optional) for gated models; `aws-secret` (optional) for S3 upload.

## Validation

- Check pose preservation with reference images.
- Confirm depth guidance keeps spatial layout.
- Test Canny edge influence.
- Multi-identity: use `composition_params` with &gt;1 `identity_ids` and matching `identity_positions`; verify `compose_multi_identity` path.
- Measure time (target &lt;2 min for typical compositions).

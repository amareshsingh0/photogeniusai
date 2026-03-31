# Orchestrator: Identity V2 Routing & Validation

**Goal:** Default flow (FAST / STANDARD / PREMIUM) keeps working; Identity V2 runs **only when explicitly requested**; automatic fallback if Identity V2 isn’t available.

---

## Final architecture

```
Client
  ├── No identity request → Two-pass / Single-pass SageMaker (FAST | STANDARD | PREMIUM)
  └── identity_engine_version = "v2" + face_image_base64
        └── Identity V2 SageMaker (InstantID now, FaceAdapter/PhotoMaker later)
              └── on failure → fallback to normal pipeline
```

- **No breaking changes:** Existing requests without `identity_engine_version: "v2"` use the same pipeline as before.
- **Feature-flagged:** Identity V2 is used only when the client sends `identity_engine_version: "v2"` and `face_image_base64`.
- **Cost-controlled:** Identity V2 endpoint is invoked only for those requests; set `SAGEMAKER_IDENTITY_V2_ENDPOINT` only when the endpoint is deployed.

---

## Routing logic (Lambda)

**Do not hardcode endpoint names.** Use environment variables only.

```python
# When to use Identity V2 (all must be true)
use_identity_v2 = (
    body.get("identity_engine_version") == "v2"
    and face_image_base64
    and os.getenv("SAGEMAKER_IDENTITY_V2_ENDPOINT")
)

if use_identity_v2:
    result = invoke_identity_v2(body)
    if result.get("error") or not result.get("images", {}).get("final"):
        result = invoke_standard_pipeline(body)  # fallback
else:
    result = invoke_standard_pipeline(body)
```

- **No identity request** → `invoke_standard_pipeline` (FAST / STANDARD / PREMIUM).
- **Identity V2 requested** → call Identity V2 endpoint; on error or no image, fallback to standard pipeline.

---

## Environment variable (critical)

In Lambda / Orchestrator configuration:

```bash
SAGEMAKER_IDENTITY_V2_ENDPOINT=photogenius-identity-v2
```

- Set only when the Identity V2 SageMaker endpoint is deployed.
- If unset, Identity V2 is never used (even if the client sends `identity_engine_version: "v2"`); request is handled by the standard pipeline.

---

## Client request rules

### Normal image (default)

```json
{
  "prompt": "studio portrait, soft light",
  "quality_tier": "STANDARD"
}
```

→ Uses existing pipeline (two-pass or single-pass by tier). No Identity V2.

### Identity V2 image

```json
{
  "prompt": "cinematic portrait, ultra realistic",
  "identity_engine_version": "v2",
  "identity_method": "ensemble",
  "face_image_base64": "BASE64_IMAGE"
}
```

→ Uses Identity V2 when `SAGEMAKER_IDENTITY_V2_ENDPOINT` is set and `face_image_base64` is present.  
→ InstantID path runs if the model is present; FaceAdapter/PhotoMaker are stubbed and skipped safely.

Optional: `identity_embedding`, `reference_face_base64` (alias for face image), `negative_prompt`, `width`, `height`, `seed`.

---

## Identity V2 container behavior

| Component    | Present | Result |
|-------------|--------|--------|
| InstantID   | ✔️      | Path 1 runs |
| IP-Adapter  | ✔️      | Ensemble improves |
| InstantID   | ❌      | Skipped silently |
| FaceAdapter | ❌      | Stubbed |
| PhotoMaker  | ❌      | Stubbed |

No crashes by design: missing or stubbed paths are skipped.

---

## Deploy Identity V2 endpoint (once)

1. **Package**
   - Linux/WSL: `bash aws/sagemaker/package_identity_v2.sh`
   - Windows: `.\aws\sagemaker\package_identity_v2.ps1`

2. **Upload**
   ```bash
   aws s3 cp model_identity_v2.tar.gz s3://<bucket>/identity-v2/
   ```

3. **Deploy** (same pattern as two-pass)
   - GPU instance, same handler lifecycle.
   - Endpoint name example: `photogenius-identity-v2` (or any name; set in env only).

4. **Set env in Lambda**
   ```bash
   SAGEMAKER_IDENTITY_V2_ENDPOINT=photogenius-identity-v2
   ```

---

## Validation checklist

### Test 1 — No identity (default flow)

- [ ] **FAST** – Request with `quality_tier: "FAST"`, no `identity_engine_version`. Expect preview/fast image from two-pass or realtime.
- [ ] **STANDARD** – Request with `quality_tier: "STANDARD"`, no identity. Expect single-pass or two-pass final image.
- [ ] **PREMIUM** – Request with `quality_tier: "PREMIUM"`, no identity. Expect preview + final from two-pass.

### Test 2 — Identity V2

- [ ] **With face image** – `identity_engine_version: "v2"`, `face_image_base64` set, endpoint configured. Expect image from Identity V2 (or fallback with clear behavior).
- [ ] **With wrong / invalid face image** – Same as above but invalid base64 or no face. Expect Identity V2 error then fallback to standard pipeline.
- [ ] **Without face image** – `identity_engine_version: "v2"` but no `face_image_base64`. Expect **no** Identity V2 call; request handled by standard pipeline (FAST/STANDARD/PREMIUM).

### Test 3 — Fallback

- [ ] Identity V2 endpoint not set – Client sends v2 + face_image_base64. Expect standard pipeline only (no Identity V2 call).
- [ ] Identity V2 endpoint fails or returns error – Expect fallback to standard pipeline and a valid response.

---

## Summary

- Default flow (FAST / STANDARD / PREMIUM) is unchanged.
- Identity V2 is opt-in via `identity_engine_version: "v2"` and `face_image_base64`.
- Endpoint name comes only from `SAGEMAKER_IDENTITY_V2_ENDPOINT` (no hardcoding).
- Automatic fallback to the standard pipeline on Identity V2 unavailability or failure.
- Production-safe, feature-flagged, cost-controlled.

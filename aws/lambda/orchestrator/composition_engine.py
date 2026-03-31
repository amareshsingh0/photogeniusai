"""
Composition Engine - Multi-ControlNet for pose, depth, and canny.

Pose (OpenPose), depth (MiDaS), Canny edge detection, then
StableDiffusionXLControlNetPipeline with all three controls.
Reference-image matching for composition; optional multi-identity (stub).
"""

from __future__ import annotations

import base64
import io
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import cv2  # type: ignore[reportMissingImports]
import modal  # type: ignore[import-untyped, reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from PIL import Image  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

app = modal.App("photogenius-composition-engine")
MODEL_DIR = "/models"
models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)

DEFAULT_NEGATIVE = (
    "blurry, low quality, worst quality, jpeg artifacts, "
    "watermark, text, deformed, bad anatomy, ugly, disfigured, "
    "misaligned parts, disconnected handle, wrong perspective, impossible geometry, "
    "floating parts, broken structure, handle canopy mismatch, inconsistent angles, "
    "structurally impossible, ai generated look, fake looking, disjointed object, "
    "missing head, headless, head cut off, no face, extra head, two heads, merged bodies, "
    "extra limbs, extra arm, arm from back, third arm, missing hands, phantom limb, "
    "merged figures, wrong number of people, six fingers, seven fingers, claw hands, "
    "impossible pose, impossible physics, body merging, jumbled figures, "
    "head absorbed by umbrella, face cut off by object"
)

comp_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1-mesa-glx", "libglib2.0-0")
    .pip_install(
        [
            "torch==2.1.0",
            "torchvision==0.16.0",
            "diffusers>=0.25.0,<0.31",
            "transformers>=4.30.0",
            "accelerate>=0.20.0",
            "opencv-python-headless>=4.8.0",
            "controlnet-aux>=0.0.6",
            "timm>=0.9.0",
            "pillow>=10.0.0",
            "numpy>=1.24.0",
        ]
    )
)


def _decode_reference(ref: Union[str, bytes]) -> Image.Image:
    """Decode reference from base64 string or path or bytes -> PIL RGB."""
    if isinstance(ref, bytes):
        return Image.open(io.BytesIO(ref)).convert("RGB")
    if isinstance(ref, str):
        path_like = (ref.startswith("/") or "\\" in ref) and len(ref) < 512
        if path_like:
            return Image.open(ref).convert("RGB")
        return Image.open(io.BytesIO(base64.b64decode(ref))).convert("RGB")
    raise TypeError("ref must be str (base64 or path) or bytes")


def _create_position_mask(
    x: float, y: float, scale: float, width: int, height: int
) -> Image.Image:
    """Create circular mask at (x, y) 0–1 normalized, with given scale. Gaussian blur for smooth edges."""
    mask = np.zeros((height, width), dtype=np.uint8)
    center_x = int(x * width)
    center_y = int(y * height)
    radius = int(scale * min(width, height) / 2)
    cv2.circle(mask, (center_x, center_y), radius, 255, -1)
    mask = cv2.GaussianBlur(mask, (51, 51), 0)
    return Image.fromarray(mask)


def _save_image(
    image: Image.Image,
    prefix: str,
    index: int = 0,
    upload_s3: bool = False,
    s3_bucket: str = "photogenius-results",
) -> str:
    """Save PIL image to /tmp; optionally upload to S3. Returns local path or s3:// URL."""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}_{index}.png"
    local = Path(tempfile.gettempdir()) / filename
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    local.write_bytes(buf.getvalue())
    if upload_s3:
        try:
            import boto3  # type: ignore[import-untyped]

            s3 = boto3.client("s3")
            key = f"composed/{filename}"
            s3.upload_file(str(local), s3_bucket, key)
            return f"s3://{s3_bucket}/{key}"
        except Exception as e:
            logger.warning("S3 upload failed, returning local path: %s", e)
    return str(local)


@app.cls(
    image=comp_image,
    gpu="A10G",
    timeout=600,
    volumes={MODEL_DIR: models_volume},
    keep_warm=0,
    secrets=[
        modal.Secret.from_name("huggingface", required=False),
        modal.Secret.from_name("aws-secret", required=False),
    ],
)
class CompositionEngine:
    """
    Multi-ControlNet composition: pose + depth + canny from reference image.
    """

    @modal.enter()
    def load_models(self) -> None:
        import torch  # type: ignore[reportMissingImports]
        from diffusers import (  # type: ignore[attr-defined, reportMissingImports]
            ControlNetModel,
            StableDiffusionXLControlNetPipeline,
            UniPCMultistepScheduler,
        )

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16

        logger.info("Loading ControlNet models...")
        self.controlnet_pose = ControlNetModel.from_pretrained(
            "thibaud/controlnet-openpose-sdxl-1.0",
            torch_dtype=dtype,
        )
        self.controlnet_depth = ControlNetModel.from_pretrained(
            "diffusers/controlnet-depth-sdxl-1.0",
            torch_dtype=dtype,
        )
        self.controlnet_canny = ControlNetModel.from_pretrained(
            "diffusers/controlnet-canny-sdxl-1.0",
            torch_dtype=dtype,
        )

        self.pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            controlnet=[
                self.controlnet_pose,
                self.controlnet_depth,
                self.controlnet_canny,
            ],
            torch_dtype=dtype,
            variant="fp16",
        )
        self.pipe.scheduler = UniPCMultistepScheduler.from_config(
            self.pipe.scheduler.config
        )
        self.pipe.enable_model_cpu_offload()
        self.pipe.enable_vae_slicing()

        self._openpose = None
        self._midas = None
        self._canny = None
        try:
            from controlnet_aux import CannyDetector, MidasDetector, OpenposeDetector  # type: ignore[import-untyped]

            self._openpose = OpenposeDetector.from_pretrained("lllyasviel/ControlNet")
            self._midas = MidasDetector.from_pretrained("Intel/dpt-hybrid-midas")
            self._canny = CannyDetector()
            logger.info("Preprocessors (OpenPose, MiDaS, Canny) loaded")
        except Exception as e:
            logger.warning("controlnet_aux preprocessors failed: %s", e)

        logger.info("Composition engine ready")

    def _prepare_control_images(
        self,
        reference: Image.Image,
        width: int,
        height: int,
    ) -> List[Image.Image]:
        """Extract pose, depth, canny from reference. Return [pose, depth, canny] PIL."""
        ref = reference.resize((width, height), Image.Resampling.LANCZOS)
        arr = np.array(ref)

        # Pose
        if self._openpose is not None:
            try:
                pose_img = self._openpose(ref)
                if isinstance(pose_img, np.ndarray):
                    pose_img = Image.fromarray(pose_img)
                pose_img = pose_img.resize((width, height), Image.Resampling.LANCZOS)
            except Exception as e:
                logger.warning("OpenPose failed: %s", e)
                pose_img = Image.fromarray(np.zeros((height, width, 3), dtype=np.uint8))
        else:
            pose_img = Image.fromarray(np.zeros((height, width, 3), dtype=np.uint8))

        # Depth
        if self._midas is not None:
            try:
                depth_img = self._midas(ref)
                if isinstance(depth_img, np.ndarray):
                    depth_img = Image.fromarray(depth_img)
                depth_img = depth_img.resize((width, height), Image.Resampling.LANCZOS)
            except Exception as e:
                logger.warning("MiDaS failed: %s", e)
                depth_img = Image.fromarray(
                    np.zeros((height, width, 3), dtype=np.uint8)
                )
        else:
            depth_img = Image.fromarray(np.zeros((height, width, 3), dtype=np.uint8))

        # Canny (controlnet_aux CannyDetector or cv2 fallback)
        if self._canny is not None:
            try:
                canny_img = self._canny(ref, low_threshold=100, high_threshold=200)
                if isinstance(canny_img, np.ndarray):
                    canny_img = Image.fromarray(canny_img)
                canny_img = canny_img.resize((width, height), Image.Resampling.LANCZOS)
            except Exception as e:
                logger.warning("CannyDetector failed: %s", e)
                gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
                canny = cv2.Canny(gray, 100, 200)
                canny = np.stack([canny] * 3, axis=-1)
                canny_img = Image.fromarray(canny)
        else:
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            canny = cv2.Canny(gray, 100, 200)
            canny = np.stack([canny] * 3, axis=-1)
            canny_img = Image.fromarray(canny)

        return [pose_img, depth_img, canny_img]

    @modal.method()
    def compose(
        self,
        prompt: str,
        reference_images: List[Union[str, bytes]],
        identities: Optional[List[str]] = None,
        negative_prompt: str = DEFAULT_NEGATIVE,
        num_images: int = 4,
        width: int = 1024,
        height: int = 1024,
        guidance_scale: float = 7.5,
        controlnet_conditioning_scale: Optional[List[float]] = None,
        num_inference_steps: int = 50,
        seed: Optional[int] = None,
        return_base64: bool = True,
        upload_s3: bool = False,
        s3_bucket: str = "photogenius-results",
    ) -> List[Dict[str, Any]]:
        """
        Generate composed scene from reference(s). Uses first reference for pose/depth/canny.

        reference_images: list of base64 strings, paths, or bytes.
        identities: optional identity IDs (reserved for multi-identity; no-op in single-reference compose).
        controlnet_conditioning_scale: [pose, depth, canny] strengths; default [1.0, 0.8, 0.5].
        upload_s3: if True, save each image to S3 and add image_path (s3://...) to each result.
        """
        import torch  # type: ignore[reportMissingImports]

        if not reference_images:
            raise ValueError("reference_images required for composition")
        scales = controlnet_conditioning_scale or [1.0, 0.8, 0.5]
        ref = _decode_reference(reference_images[0])
        control_images = self._prepare_control_images(ref, width, height)

        gen = torch.Generator(device="cpu")
        if seed is not None:
            gen.manual_seed(int(seed))
        else:
            gen.manual_seed(torch.randint(0, 2**32, (1,)).item())

        results = []
        for i in range(num_images):
            if num_images > 1:
                if seed is not None:
                    gen.manual_seed(int(seed) + i)
                else:
                    gen.manual_seed(torch.randint(0, 2**32, (1,)).item())
            out = self.pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=control_images,
                controlnet_conditioning_scale=scales,
                width=width,
                height=height,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                generator=gen,
            )
            img = out.images[0]  # type: ignore[union-attr]
            entry = {
                "seed": (
                    seed
                    if num_images == 1
                    else (seed + i) if seed is not None else None
                ),
                "controls_used": ["pose", "depth", "canny"],
                "controlnet_scales": scales,
            }
            if return_base64:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                entry["image_base64"] = base64.b64encode(buf.getvalue()).decode("utf-8")
            if upload_s3:
                entry["image_path"] = _save_image(
                    img, "composed", index=i, upload_s3=upload_s3, s3_bucket=s3_bucket
                )
            results.append(entry)
        return results

    @modal.method()
    def compose_multi_identity(
        self,
        prompt: str,
        reference_image: Union[str, bytes],
        identity_ids: List[str],
        identity_positions: List[Dict[str, float]],
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Multi-identity composition. Uses identity_positions for mask layout.

        Full implementation would use Identity Engine inpainting per position;
        for now falls back to single-reference compose. _create_position_mask
        is available for future per-identity masking.
        """
        logger.info(
            "compose_multi_identity: %d identities at %d positions; using single-reference compose (inpainting not implemented)",
            len(identity_ids),
            len(identity_positions),
        )
        allowed = {
            "negative_prompt",
            "num_images",
            "width",
            "height",
            "guidance_scale",
            "controlnet_conditioning_scale",
            "num_inference_steps",
            "seed",
            "return_base64",
            "upload_s3",
            "s3_bucket",
        }
        compose_kw = {k: v for k, v in kwargs.items() if k in allowed}
        out = self.compose(
            prompt=prompt, reference_images=[reference_image], **compose_kw
        )
        for r in out:
            r["identities_used"] = identity_ids
            r["positions"] = identity_positions
        return out


@app.local_entrypoint()
def main() -> None:
    print("Composition engine: pose + depth + canny multi-ControlNet.")
    print("  compose(prompt, reference_images=[base64|path|bytes], ...)")
    print(
        "  compose_multi_identity(prompt, reference_image, identity_ids, identity_positions, ...)"
    )
    print("  modal deploy ai-pipeline/services/composition_engine.py")


@app.local_entrypoint()
def test_composition() -> None:
    """Test composition engine. Use a local reference image path (e.g. reference_pose.jpg)."""
    from pathlib import Path

    ref = Path("reference_pose.jpg")
    if not ref.exists():
        print("Skip: reference_pose.jpg not found. Create it or pass another path.")
        return
    engine = CompositionEngine()
    result = engine.compose.remote(  # type: ignore[reportAttributeAccessIssue]
        prompt="Two friends having coffee at a cafe, photorealistic",
        reference_images=[str(ref)],
        controlnet_conditioning_scale=[1.0, 0.7, 0.4],
        num_images=1,
    )
    print("Composition result:", [r.get("seed") for r in result])

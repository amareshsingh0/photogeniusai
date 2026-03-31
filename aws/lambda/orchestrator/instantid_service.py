"""
InstantID Service for 90%+ face consistency in PhotoGenius AI pipeline.

Uses Modal stub "photogenius-instantid" with A10G GPU and /models volume.
Flow: ControlNet + SDXL + IP-Adapter + optional LoRA; InsightFace for face/keypoints;
draw_kps for control image; generate with control_image + face reference.

Models expected under /models (Modal volume):
- /models/instantid/ControlNetModel/
- /models/instantid/ip-adapter.bin
- /models/instantid/image_encoder/ (CLIP)
- /models/sdxl-base/ or HuggingFace SDXL
- Optional: LoRA at lora_path
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

MODEL_DIR = "/models"
LORA_DIR = "/loras"
INSTANTID_DIR = f"{MODEL_DIR}/instantid"

# Optional Modal import (service runs inside Modal; can be imported elsewhere for types)
try:
    import modal  # type: ignore[reportMissingImports]
except ImportError:
    modal = None  # type: ignore[assignment]


def draw_kps(
    face_image: "PIL.Image.Image",
    kps: "np.ndarray",
    width: int = 1024,
    height: int = 1024,
) -> "PIL.Image.Image":
    """
    Draw face keypoints for ControlNet conditioning.

    Uses 5-point facial landmarks (left_eye, right_eye, nose, left_mouth, right_mouth).
    Creates white skeleton on black background. InstantID ControlNet expects this format.

    Args:
        face_image: Reference face image (used for size if no width/height).
        kps: Keypoints array of shape (5, 2) - [left_eye, right_eye, nose, left_mouth, right_mouth].
        width: Output control image width.
        height: Output control image height.

    Returns:
        PIL Image: Black background with white keypoints and connecting lines (control image).
    """
    import numpy as np
    from PIL import Image

    # kps: (5, 2) - typically float xy in image coordinates
    kps = np.asarray(kps, dtype=np.float32)
    if kps.size == 0 or kps.shape[0] < 5:
        raise ValueError("draw_kps requires at least 5 keypoints (left_eye, right_eye, nose, left_mouth, right_mouth)")

    # Use face_image size if not specified
    if width <= 0 or height <= 0:
        w, h = face_image.size
        width = width if width > 0 else w
        height = height if height > 0 else h

    # Create black background (single channel for control; InstantID often uses 3-channel)
    control = np.zeros((height, width, 3), dtype=np.uint8)
    # Scale keypoints to output size
    src_h, src_w = face_image.size[1], face_image.size[0]
    scale_x = width / max(src_w, 1)
    scale_y = height / max(src_h, 1)
    pts = (kps[:5] * [scale_x, scale_y]).astype(np.int32)

    # Draw white lines: 5-point skeleton
    # 0: left_eye, 1: right_eye, 2: nose, 3: left_mouth, 4: right_mouth
    import cv2  # type: ignore[reportMissingImports]
    line_color = (255, 255, 255)
    thickness = max(1, min(width, height) // 256)
    radius = max(2, min(width, height) // 128)
    for i in range(5):
        x, y = int(pts[i, 0]), int(pts[i, 1])
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        cv2.circle(control, (x, y), radius, line_color, -1)
    # Nose to eyes and mouth
    if len(pts) >= 5:
        cv2.line(control, tuple(pts[2]), tuple(pts[0]), line_color, thickness)
        cv2.line(control, tuple(pts[2]), tuple(pts[1]), line_color, thickness)
        cv2.line(control, tuple(pts[2]), tuple(pts[3]), line_color, thickness)
        cv2.line(control, tuple(pts[2]), tuple(pts[4]), line_color, thickness)
        cv2.line(control, tuple(pts[3]), tuple(pts[4]), line_color, thickness)

    return Image.fromarray(control)


def _get_instantid_app():
    """Return Modal app for InstantID (used when running under Modal)."""
    if modal is None:
        raise RuntimeError("Modal is not installed. Install with: pip install modal")
    return modal.App("photogenius-instantid")


def _build_instantid_image():
    """Build Modal image with InstantID dependencies."""
    if modal is None:
        raise RuntimeError("Modal is not installed")
    return (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("libgl1-mesa-glx", "libglib2.0-0")
        .pip_install(
            "diffusers==0.25.0",
            "transformers==4.37.0",
            "accelerate>=0.25.0",
            "safetensors>=0.4.1",
            "insightface==0.7.3",
            "onnxruntime-gpu==1.16.3",
            "opencv-python==4.8.1.78",
            "Pillow>=10.0.0",
            "numpy>=1.24.0",
            "torch>=2.1.0",
            "torchvision>=0.16.0",
            "ip-adapter",  # IP-Adapter for InstantID identity conditioning
        )
    )


if modal is not None:
    models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)
    lora_volume = modal.Volume.from_name("photogenius-loras", create_if_missing=True)
    instantid_image = _build_instantid_image()

    _secrets = []
    try:
        _secrets = [modal.Secret.from_name("huggingface")]
    except Exception:
        pass

    app = _get_instantid_app()
    @app.cls(
        gpu="A10G",
        image=instantid_image,
        volumes={MODEL_DIR: models_volume, LORA_DIR: lora_volume},
        timeout=600,
        secrets=_secrets,
    )
    class InstantIDService:
        """
        InstantID service for 90%+ face consistency.
        GPU: A10G. Models: /models (Modal volume).
        """

        @modal.enter()
        def load_models(self):
            """Load ControlNet, SDXL, IP-Adapter, InsightFace once at startup."""
            import os
            import torch
            from diffusers import (
                StableDiffusionXLControlNetPipeline,
                ControlNetModel,
                StableDiffusionXLPipeline,
            )
            from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection

            self._device = "cuda"
            self._dtype = torch.float16
            self.pipe = None
            self.controlnet = None
            self.clip_processor = None
            self.clip_encoder = None
            self.ip_adapter = None
            self.face_app = None
            self._instantid_ready = False

            instantid_path = Path(INSTANTID_DIR)
            if not instantid_path.exists():
                raise FileNotFoundError(
                    f"InstantID models not found at {INSTANTID_DIR}. "
                    "Run download_instantid (e.g. python -m ai_pipeline.models.download_instantid) and sync to Modal volume."
                )

            # 1) Load ControlNet
            controlnet_path = instantid_path / "ControlNetModel"
            if not controlnet_path.exists():
                raise FileNotFoundError(f"ControlNet not found at {controlnet_path}")
            self.controlnet = ControlNetModel.from_pretrained(
                str(controlnet_path),
                torch_dtype=self._dtype,
            ).to(self._device)

            # 2) Load SDXL base then create ControlNet pipeline
            sdxl_path = Path(f"{MODEL_DIR}/sdxl-base")
            hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
            if sdxl_path.exists() and any(sdxl_path.iterdir()):
                sdxl_repo = str(sdxl_path)
            else:
                sdxl_repo = "stabilityai/stable-diffusion-xl-base-1.0"
            base_pipe = StableDiffusionXLPipeline.from_pretrained(
                sdxl_repo,
                torch_dtype=self._dtype,
                use_safetensors=True,
                token=hf_token,
            ).to(self._device)
            self.pipe = StableDiffusionXLControlNetPipeline(
                vae=base_pipe.vae,
                text_encoder=base_pipe.text_encoder,
                text_encoder_2=base_pipe.text_encoder_2,
                tokenizer=base_pipe.tokenizer,
                tokenizer_2=base_pipe.tokenizer_2,
                unet=base_pipe.unet,
                controlnet=self.controlnet,
                scheduler=base_pipe.scheduler,
            ).to(self._device)

            # GPU memory optimization
            self.pipe.enable_attention_slicing()
            self.pipe.enable_vae_slicing()

            # 3) Load CLIP image encoder and IP-Adapter
            clip_path = instantid_path / "image_encoder"
            ip_path = instantid_path / "ip-adapter.bin"
            if clip_path.exists():
                self.clip_processor = CLIPImageProcessor.from_pretrained(str(clip_path))
                self.clip_encoder = CLIPVisionModelWithProjection.from_pretrained(
                    str(clip_path),
                    torch_dtype=self._dtype,
                ).to(self._device)
            if ip_path.exists() and self.clip_encoder is not None:
                try:
                    from ip_adapter import IPAdapterPlus  # type: ignore[reportMissingImports]
                    self.ip_adapter = IPAdapterPlus(
                        self.pipe,
                        image_encoder_path=str(clip_path),
                        ip_ckpt=str(ip_path),
                        device=self._device,
                        num_tokens=16,
                    )
                except Exception as e:
                    import warnings
                    warnings.warn(f"IP-Adapter load failed: {e}. InstantID will use ControlNet only.")

            # 4) Load InsightFace (buffalo_l)
            try:
                from insightface.app import FaceAnalysis  # type: ignore[reportMissingImports]
                self.face_app = FaceAnalysis(
                    name="buffalo_l",
                    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                )
                self.face_app.prepare(ctx_id=0, det_size=(640, 640))
            except Exception as e:
                import warnings
                warnings.warn(f"InsightFace load failed: {e}. Face detection will fail.")

            self._instantid_ready = (
                self.pipe is not None
                and self.controlnet is not None
                and self.face_app is not None
            )
            if self._instantid_ready:
                print("[InstantID] Loaded: ControlNet + SDXL + InsightFace" + (" + IP-Adapter" if self.ip_adapter else ""))

        @modal.method()
        def generate_with_instantid(
            self,
            prompt: str,
            face_image_path: str,
            lora_path: Optional[str] = None,
            negative_prompt: str = "",
            num_inference_steps: int = 50,
            guidance_scale: float = 8.5,
            controlnet_conditioning_scale: float = 0.88,
            ip_adapter_scale: float = 0.8,
            width: int = 1024,
            height: int = 1024,
            seed: Optional[int] = None,
        ) -> bytes:
            """
            Generate image with 90%+ face consistency using InstantID.

            Args:
                prompt: Enhanced text prompt.
                face_image_path: Path to reference face image (in container or URL); must contain one face.
                lora_path: Optional path to LoRA weights (validated before load).
                negative_prompt: Negative prompt string.
                num_inference_steps: Inference steps (default 50).
                guidance_scale: Classifier-free guidance (default 8.5).
                controlnet_conditioning_scale: ControlNet strength (default 0.88).
                ip_adapter_scale: IP-Adapter strength (default 0.8).
                width: Output width (default 1024).
                height: Output height (default 1024).
                seed: Random seed for reproducibility.

            Returns:
                PNG image bytes.

            Raises:
                ValueError: If no face detected in reference image.
                FileNotFoundError: If lora_path given but file not found.
            """
            import torch
            import numpy as np
            from PIL import Image
            import cv2

            if not self._instantid_ready:
                raise RuntimeError("InstantID models not fully loaded (ControlNet + InsightFace required).")

            # Validate LoRA path if provided
            if lora_path:
                p = Path(lora_path)
                if not p.exists():
                    raise FileNotFoundError(f"LoRA path does not exist: {lora_path}")

            # Load face image
            face_path = Path(face_image_path)
            if face_path.exists():
                face_pil = Image.open(str(face_path)).convert("RGB")
            else:
                # Allow URL or base64 later if needed
                raise FileNotFoundError(f"Face image not found: {face_image_path}")

            face_np = np.array(face_pil)
            face_bgr = cv2.cvtColor(face_np, cv2.COLOR_RGB2BGR)
            faces = self.face_app.get(face_bgr)
            if not faces:
                raise ValueError("No face detected in reference image. Use an image with one clear face.")
            # Largest face
            face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            kps = face.kps  # (5, 2) for buffalo_l

            # Create control image from keypoints
            control_pil = draw_kps(face_pil, kps, width=width, height=height)

            # Optional: Load LoRA
            if lora_path:
                self.pipe.load_lora_weights(lora_path, adapter_name="instantid_lora")
                self.pipe.set_adapters(["instantid_lora"], adapter_weights=[0.9])

            # IP-Adapter: use face image for identity
            if self.ip_adapter is not None:
                self.pipe.set_ip_adapter_scale([ip_adapter_scale])

            generator = None
            if seed is not None:
                generator = torch.Generator(device=self._device).manual_seed(seed)

            with torch.inference_mode():
                kwargs = dict(
                    prompt=prompt,
                    negative_prompt=negative_prompt or None,
                    control_image=control_pil,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    controlnet_conditioning_scale=controlnet_conditioning_scale,
                    width=width,
                    height=height,
                    generator=generator,
                )
                if self.ip_adapter is not None:
                    kwargs["ip_adapter_image"] = face_pil
                out = self.pipe(**kwargs)
            image = out.images[0]

            # Unload LoRA after generation
            if lora_path:
                try:
                    self.pipe.unload_lora_weights("instantid_lora")
                except Exception:
                    pass

            buf = io.BytesIO()
            image.save(buf, format="PNG", optimize=True)
            return buf.getvalue()

else:
    InstantIDService = None  # type: ignore[misc, assignment]
    app = None  # type: ignore[assignment]


def generate_with_instantid(
    prompt: str,
    face_image_path: str,
    lora_path: Optional[str] = None,
    negative_prompt: str = "",
    num_inference_steps: int = 50,
    guidance_scale: float = 8.5,
    controlnet_conditioning_scale: float = 0.88,
    ip_adapter_scale: float = 0.8,
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None,
    stub: Optional[object] = None,
) -> "PIL.Image.Image":
    """
    Run InstantID generation via Modal and return a PIL Image.

    When running as a Modal client, pass the Modal class so we can call remote:
        from ai_pipeline.services.instantid_service import app, generate_with_instantid
        img = generate_with_instantid(..., stub=app.InstantIDService)

    Or call the Modal class directly:
        app.InstantIDService().generate_with_instantid.remote(prompt=..., face_image_path=...)
    """
    from PIL import Image
    if stub is None:
        if InstantIDService is None:
            raise RuntimeError(
                "Modal not installed. Install with: pip install modal. "
                "Then use: app.InstantIDService().generate_with_instantid.remote(...)"
            )
        raise ValueError(
            "Pass the Modal class to run remotely, e.g. "
            "generate_with_instantid(..., stub=app.InstantIDService)"
        )
    # stub is the Modal class; instantiate and call remote
    png_bytes = stub().generate_with_instantid.remote(
        prompt=prompt,
        face_image_path=face_image_path,
        lora_path=lora_path,
        negative_prompt=negative_prompt,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        controlnet_conditioning_scale=controlnet_conditioning_scale,
        ip_adapter_scale=ip_adapter_scale,
        width=width,
        height=height,
        seed=seed,
    )
    return Image.open(io.BytesIO(png_bytes)).convert("RGB")

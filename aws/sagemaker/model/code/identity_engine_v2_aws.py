"""
Identity Engine V2 - AWS/SageMaker compatible (no Modal).
Copy of ai-pipeline/services/identity_engine_v2_aws.py for SageMaker container.
Multi-path face consistency with ensemble verification; target 99%+ (ArcFace >0.85).
"""

from __future__ import annotations

import io
import base64
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image


@dataclass
class GenerationResult:
    image: Optional[Image.Image] = None
    image_base64: Optional[str] = None
    similarity: float = 0.0
    path: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    guaranteed: bool = False
    error: Optional[str] = None


class FaceConsistencyScorer:
    """ArcFace similarity; target > 0.85."""

    def __init__(self, det_size: Tuple[int, int] = (640, 640)):
        self._app = None
        self._det_size = det_size

    def _ensure_loaded(self) -> bool:
        if self._app is not None:
            return True
        try:
            from insightface.app import FaceAnalysis
            self._app = FaceAnalysis(
                name="buffalo_l",
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            self._app.prepare(ctx_id=0, det_size=self._det_size)
            return True
        except Exception:
            return False

    def score(self, original: Image.Image, generated: Image.Image) -> float:
        if not self._ensure_loaded():
            return 0.0
        try:
            arr_orig = np.array(original.convert("RGB"))
            arr_gen = np.array(generated.convert("RGB"))
            faces_orig = self._app.get(arr_orig)
            faces_gen = self._app.get(arr_gen)
            if not faces_orig or not faces_gen:
                return 0.0
            e1 = faces_orig[0].embedding
            e2 = faces_gen[0].embedding
            e1_n = e1 / (np.linalg.norm(e1) + 1e-8)
            e2_n = e2 / (np.linalg.norm(e2) + 1e-8)
            sim = float(np.dot(e1_n, e2_n))
            return max(0.0, min(1.0, sim))
        except Exception:
            return 0.0

    def get_embedding(self, image: Image.Image) -> Optional[np.ndarray]:
        if not self._ensure_loaded():
            return None
        try:
            arr = np.array(image.convert("RGB"))
            faces = self._app.get(arr)
            if not faces:
                return None
            return faces[0].embedding
        except Exception:
            return None


def _compute_face_similarity(
    original: Image.Image,
    generated: Image.Image,
    scorer: Optional[FaceConsistencyScorer] = None,
) -> float:
    if scorer is None:
        scorer = FaceConsistencyScorer()
    return scorer.score(original, generated)


class InstantIDEngine:
    def __init__(self, model_dir: str = "", device: str = "cuda"):
        self.model_dir = model_dir or os.environ.get("MODEL_DIR", "/opt/ml/model")
        self.device = device
        self._pipe = None
        self._ip_adapter = None
        self._controlnet = None

    def is_available(self) -> bool:
        return self._pipe is not None

    def load(self) -> None:
        import torch
        from diffusers import StableDiffusionXLPipeline, ControlNetModel
        if not torch.cuda.is_available():
            return
        dtype = torch.float16
        instantid_path = Path(f"{self.model_dir}/instantid")
        controlnet_path = instantid_path / "ControlNetModel" if instantid_path.exists() else None
        if controlnet_path and controlnet_path.exists():
            self._controlnet = ControlNetModel.from_pretrained(
                str(controlnet_path), torch_dtype=dtype
            ).to(self.device)
        base_path = Path(f"{self.model_dir}/sdxl-base")
        hf_id = "stabilityai/stable-diffusion-xl-base-1.0"
        repo = str(base_path) if base_path.exists() and any(base_path.iterdir()) else hf_id
        kwargs = {"torch_dtype": dtype, "variant": "fp16", "use_safetensors": True}
        token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        if token:
            kwargs["token"] = token
        if self._controlnet is not None:
            self._pipe = StableDiffusionXLPipeline.from_pretrained(
                repo, controlnet=self._controlnet, **kwargs
            ).to(self.device)
        else:
            self._pipe = StableDiffusionXLPipeline.from_pretrained(repo, **kwargs).to(self.device)
        try:
            self._pipe.enable_attention_slicing()
            self._pipe.enable_vae_slicing()
        except Exception:
            pass
        ip_path = instantid_path / "ip-adapter.bin" if instantid_path else None
        enc_path = instantid_path / "image_encoder" if instantid_path else None
        if ip_path and ip_path.exists() and enc_path and enc_path.exists():
            try:
                from ip_adapter import IPAdapterPlus
                self._ip_adapter = IPAdapterPlus(
                    self._pipe,
                    image_encoder_path=str(enc_path),
                    ip_ckpt=str(ip_path),
                    device=self.device,
                    num_tokens=16,
                )
            except Exception:
                pass

    def generate(
        self,
        prompt: str,
        face_image: Image.Image,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 45,
        guidance: float = 7.5,
        seed: Optional[int] = None,
    ) -> Optional[Image.Image]:
        if self._pipe is None:
            return None
        import torch
        gen = torch.Generator(device=self.device)
        if seed is not None:
            gen.manual_seed(int(seed))
        else:
            gen.manual_seed(torch.randint(0, 2**32, (1,)).item())
        if self._ip_adapter is not None:
            try:
                out = self._ip_adapter.generate(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    ip_adapter_image=face_image,
                    num_samples=1,
                    num_inference_steps=steps,
                    guidance_scale=guidance,
                    generator=gen,
                    width=width,
                    height=height,
                )
                return out.images[0] if out.images else None
            except Exception:
                pass
        out = self._pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=steps,
            guidance_scale=guidance,
            generator=gen,
            width=width,
            height=height,
        )
        return out.images[0] if out.images else None


class FaceAdapterEngine:
    def __init__(self, model_dir: str = ""):
        self.model_dir = model_dir
        self._available = False

    def is_available(self) -> bool:
        return self._available

    def load(self) -> None:
        pass

    def generate(self, prompt: str, face_image: Image.Image, negative_prompt: str = "",
                 width: int = 1024, height: int = 1024, steps: int = 45, guidance: float = 7.5,
                 seed: Optional[int] = None) -> Optional[Image.Image]:
        return None


class PhotoMakerEngine:
    def __init__(self, model_dir: str = ""):
        self.model_dir = model_dir
        self._available = False

    def is_available(self) -> bool:
        return self._available

    def load(self) -> None:
        pass

    def generate(self, prompt: str, face_image: Image.Image, negative_prompt: str = "",
                 width: int = 1024, height: int = 1024, steps: int = 45, guidance: float = 7.5,
                 seed: Optional[int] = None) -> Optional[Image.Image]:
        return None


class IdentityEngineV2:
    def __init__(self, model_dir: str = ""):
        self.model_dir = model_dir or os.environ.get("MODEL_DIR", "/opt/ml/model")
        self.instantid_engine = InstantIDEngine(model_dir=self.model_dir)
        self.face_adapter = FaceAdapterEngine(model_dir=self.model_dir)
        self.photomaker = PhotoMakerEngine(model_dir=self.model_dir)
        self.face_scorer = FaceConsistencyScorer()

    def load_all(self) -> None:
        self.instantid_engine.load()
        self.face_adapter.load()
        self.photomaker.load()

    def _compute_face_similarity(self, original: Image.Image, generated: Image.Image) -> float:
        return _compute_face_similarity(original, generated, self.face_scorer)

    def generate_with_identity(
        self,
        prompt: str,
        identity_embedding: np.ndarray,
        face_image: Image.Image,
        method: str = "ensemble",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 45,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
    ) -> GenerationResult:
        if method == "ensemble":
            return self._ensemble_generate(
                prompt=prompt, face_image=face_image, negative_prompt=negative_prompt,
                width=width, height=height, num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale, seed=seed,
            )
        if method == "instantid":
            img = self._run_path("instantid", prompt, face_image, negative_prompt,
                width, height, num_inference_steps, guidance_scale, seed)
        elif method == "faceadapter":
            img = self._run_path("faceadapter", prompt, face_image, negative_prompt,
                width, height, num_inference_steps, guidance_scale, seed)
        elif method == "photomaker":
            img = self._run_path("photomaker", prompt, face_image, negative_prompt,
                width, height, num_inference_steps, guidance_scale, seed)
        else:
            return GenerationResult(error=f"Unknown method: {method}")
        if img is None:
            return GenerationResult(path=method, error=f"{method} returned no image")
        sim = self._compute_face_similarity(face_image, img)
        return GenerationResult(
            image=img, similarity=sim, path=method,
            scores={"arcface": sim}, guaranteed=(sim >= 0.85),
        )

    def _run_path(
        self, path_name: str, prompt: str, face_image: Image.Image, negative_prompt: str,
        width: int, height: int, steps: int, guidance: float, seed: Optional[int],
    ) -> Optional[Image.Image]:
        if path_name == "instantid" and self.instantid_engine.is_available():
            return self.instantid_engine.generate(
                prompt, face_image, negative_prompt, width, height, steps, guidance, seed
            )
        if path_name == "faceadapter" and self.face_adapter.is_available():
            return self.face_adapter.generate(
                prompt, face_image, negative_prompt, width, height, steps, guidance, seed
            )
        if path_name == "photomaker" and self.photomaker.is_available():
            return self.photomaker.generate(
                prompt, face_image, negative_prompt, width, height, steps, guidance, seed
            )
        return None

    def _ensemble_generate(
        self,
        prompt: str,
        face_image: Image.Image,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 45,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
    ) -> GenerationResult:
        candidates: List[Tuple[str, Image.Image, float]] = []
        for path_name in ("instantid", "faceadapter", "photomaker"):
            img = self._run_path(
                path_name, prompt, face_image, negative_prompt,
                width, height, num_inference_steps, guidance_scale, seed,
            )
            if img is not None:
                sim = self._compute_face_similarity(face_image, img)
                candidates.append((path_name, img, sim))
        if not candidates:
            return GenerationResult(error="Ensemble: no path produced an image")
        best_path, best_img, best_sim = max(candidates, key=lambda x: x[2])
        return GenerationResult(
            image=best_img, similarity=best_sim, path=best_path,
            scores={"arcface": best_sim}, guaranteed=(best_sim >= 0.85),
        )


def result_to_base64(result: GenerationResult) -> Optional[str]:
    if result.image is None:
        return result.image_base64
    buf = io.BytesIO()
    result.image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

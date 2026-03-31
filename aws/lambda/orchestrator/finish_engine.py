"""
Finish Engine - Post-processing for generated images

4× upscale (RealESRGAN), face restoration (CodeFormer, GFPGAN fallback),
color grading (.cube LUTs + programmatic), film grain, sharpening.
Batch processing; preserve original on failure.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2  # type: ignore[reportMissingImports]
import modal  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from PIL import Image  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

app = modal.App("photogenius-finish-engine")
MODEL_DIR = "/models"
LUT_DIR = "/luts"
models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)
luts_volume = modal.Volume.from_name("color-luts", create_if_missing=True)

finish_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1-mesa-glx", "libglib2.0-0", "wget")
    .pip_install(
        [
            "torch==2.1.0",
            "torchvision==0.16.0",
            "opencv-python-headless>=4.8.0",
            "pillow>=10.0.0",
            "numpy>=1.24.0",
            "basicsr>=1.4.2",
            "realesrgan>=0.3.0",
            "gfpgan>=1.3.8",
            "facexlib>=0.3.0",
            "codeformer-pip>=0.0.4",
        ]
    )
)


def _download_model(url: str, path: Path) -> bool:
    """Download model if missing. Returns True if a download happened."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    import urllib.request

    urllib.request.urlretrieve(url, path)
    logger.info("Downloaded %s -> %s", url, path)
    return True


def _setup_codeformer_weights() -> None:
    """Prepare CodeFormer weights under /models for codeformer-pip (expects CodeFormer/weights/...)."""
    base = Path(MODEL_DIR) / "CodeFormer" / "weights"
    dirs = {
        "codeformer": base / "CodeFormer",
        "facelib": base / "facelib",
        "realesrgan": base / "realesrgan",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    urls = {
        dirs["codeformer"] / "codeformer.pth": "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth",
        dirs["facelib"] / "detection_Resnet50_Final.pth": "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/detection_Resnet50_Final.pth",
        dirs["facelib"] / "parsing_parsenet.pth": "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/parsing_parsenet.pth",
        dirs["realesrgan"] / "RealESRGAN_x2plus.pth": "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/RealESRGAN_x2plus.pth",
    }
    for p, u in urls.items():
        if not p.exists():
            _download_model(u, p)
    # codeformer-pip uses CWD for "CodeFormer/weights/..."
    os.chdir(MODEL_DIR)


def _parse_cube_lut(lut_path: Path) -> np.ndarray:
    """Parse .cube LUT file into (size, size, size, 3) float32 RGB."""
    with open(lut_path, encoding="utf-8") as f:
        lines = f.readlines()
    size = 33
    for line in lines:
        if line.strip().startswith("LUT_3D_SIZE"):
            size = int(line.split()[1])
            break
    lut_data: List[List[float]] = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("LUT"):
            continue
        parts = s.split()
        if len(parts) >= 3:
            try:
                r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
                lut_data.append([r, g, b])
            except ValueError:
                continue
    arr = np.array(lut_data, dtype=np.float32)
    n = size * size * size
    if len(arr) < n:
        arr = np.resize(arr, (n, 3))
    return arr.reshape(size, size, size, 3)


def _load_luts() -> Dict[str, np.ndarray]:
    """Load .cube LUTs from /luts volume; fall back to programmatic LUTs."""
    default_names = ["cinematic", "vibrant", "vintage", "cool", "warm", "neutral"]
    luts: Dict[str, np.ndarray] = {}
    lut_path = Path(LUT_DIR)
    for name in default_names:
        p = lut_path / f"{name}.cube"
        if p.exists():
            try:
                luts[name] = _parse_cube_lut(p)
                logger.info("Loaded LUT %s from %s", name, p)
            except Exception as e:
                logger.warning("Failed to parse LUT %s: %s", p, e)
    if not luts:
        luts = _build_programmatic_luts()
        logger.info("Using programmatic LUTs (no .cube files in /luts)")
    else:
        prog = _build_programmatic_luts()
        for k, v in prog.items():
            if k not in luts:
                luts[k] = v
    return luts


@app.cls(
    image=finish_image,
    gpu="T4",
    timeout=300,
    volumes={MODEL_DIR: models_volume, LUT_DIR: luts_volume},
    keep_warm=1,
    secrets=[modal.Secret.from_name("aws-secret", required=False)],
)
class FinishEngine:
    """
    Post-processing: 4× upscale, face restore (CodeFormer / GFPGAN), color grade, film grain, sharpening.
    """

    @modal.enter()
    def load_models(self) -> None:
        import torch  # type: ignore[reportMissingImports]

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self.upsampler = None
        self._codeformer_infer = None
        self.face_restorer = None

        # RealESRGAN 4×
        try:
            from basicsr.archs.rrdbnet_arch import RRDBNet  # type: ignore[reportMissingImports]
            from realesrgan import RealESRGANer  # type: ignore[reportMissingImports]

            pth = Path(f"{MODEL_DIR}/RealESRGAN_x4plus.pth")
            if not pth.exists():
                _download_model(
                    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
                    pth,
                )
            model = RRDBNet(
                num_in_ch=3,
                num_out_ch=3,
                num_feat=64,
                num_block=23,
                num_grow_ch=32,
                scale=4,
            )
            self.upsampler = RealESRGANer(
                scale=4,
                model_path=str(pth),
                model=model,
                tile=512,
                tile_pad=10,
                pre_pad=0,
                half=(self._device == "cuda"),
                device=self._device,
            )
            logger.info("RealESRGAN loaded")
        except Exception as e:
            logger.warning("RealESRGAN load failed: %s", e)

        # CodeFormer face restoration (primary)
        try:
            _setup_codeformer_weights()
            from codeformer.app import inference_app  # type: ignore[reportMissingImports]

            self._codeformer_infer = inference_app
            logger.info("CodeFormer loaded")
        except Exception as e:
            logger.warning("CodeFormer load failed: %s", e)

        # GFPGAN face restoration (fallback)
        if self._codeformer_infer is None:
            try:
                from gfpgan import GFPGANer  # type: ignore[reportMissingImports]

                gfp_path = Path(f"{MODEL_DIR}/GFPGANv1.4.pth")
                if not gfp_path.exists():
                    _download_model(
                        "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
                        gfp_path,
                    )
                self.face_restorer = GFPGANer(
                    model_path=str(gfp_path),
                    upscale=1,
                    arch="clean",
                    channel_multiplier=2,
                    device=self._device,
                )
                logger.info("GFPGAN loaded (fallback)")
            except Exception as e:
                logger.warning("GFPGAN load failed: %s", e)

        self._luts = _load_luts()
        try:
            models_volume.commit()
        except Exception as e:
            logger.debug("Volume commit skipped: %s", e)
        logger.info("Finish engine ready")

    @modal.method()
    def finish(
        self,
        images: List[Dict[str, Any]],
        upscale: bool = True,
        face_fix: bool = True,
        color_grade: Optional[str] = None,
        film_grain: float = 0.0,
        sharpen: float = 0.0,
        output_format: str = "png",
    ) -> List[Dict[str, Any]]:
        """
        Apply finishing to a list of image dicts.
        Each item must have 'image_base64' (or 'image_bytes'). Preserves other keys.
        """
        results: List[Dict[str, Any]] = []
        for item in images:
            try:
                out = self._process_one(
                    item,
                    upscale=upscale,
                    face_fix=face_fix,
                    color_grade=color_grade,
                    film_grain=film_grain,
                    sharpen=sharpen,
                    output_format=output_format,
                )
                results.append(out)
            except Exception as e:
                logger.exception("Finish failed for item: %s", e)
                orig_b64 = item.get("image_base64")
                if orig_b64 is None and item.get("image_bytes"):
                    orig_b64 = base64.b64encode(item["image_bytes"]).decode("utf-8")
                results.append({
                    **{k: v for k, v in item.items() if k not in ("image_base64", "image_bytes")},
                    "processed": False,
                    "error": str(e),
                    "image_base64": orig_b64,
                })
        return results

    @modal.method()
    def finish_from_paths(
        self,
        image_paths: List[str],
        upscale: bool = True,
        face_fix: bool = True,
        color_grade: Optional[str] = None,
        film_grain: float = 0.0,
        sharpen: float = 0.0,
        output_format: str = "png",
        upload_s3: bool = False,
        s3_bucket: str = "photogenius-results",
    ) -> List[Dict[str, Any]]:
        """
        Apply finishing to images on disk. Returns list of dicts with
        image_path (local or s3://), processed, applied, etc.
        Preserves original on failure.
        """
        results: List[Dict[str, Any]] = []
        for i, img_path in enumerate(image_paths):
            try:
                with open(img_path, "rb") as f:
                    raw = f.read()
                item = {"image_bytes": raw, "image_path": img_path}
                out = self._process_one(
                    item,
                    upscale=upscale,
                    face_fix=face_fix,
                    color_grade=color_grade,
                    film_grain=film_grain,
                    sharpen=sharpen,
                    output_format=output_format,
                )
                path_out = _save_processed(
                    out["image_base64"],
                    output_format,
                    img_path,
                    index=i,
                    upload_s3=upload_s3,
                    s3_bucket=s3_bucket,
                )
                out["image_path"] = path_out
                results.append(out)
            except Exception as e:
                logger.exception("Finish failed for %s: %s", img_path, e)
                results.append({
                    "image_path": img_path,
                    "processed": False,
                    "error": str(e),
                })
        return results

    def _process_one(
        self,
        item: Dict[str, Any],
        upscale: bool,
        face_fix: bool,
        color_grade: Optional[str],
        film_grain: float,
        sharpen: float,
        output_format: str,
    ) -> Dict[str, Any]:
        raw = item.get("image_bytes")
        if raw is None:
            b64 = item.get("image_base64")
            if not b64:
                raise ValueError("Item must have 'image_base64' or 'image_bytes'")
            raw = base64.b64decode(b64)
        img = np.array(Image.open(io.BytesIO(raw)).convert("RGB"))
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        original_size = (img.shape[1], img.shape[0])
        applied: Dict[str, Any] = {
            "upscale": False,
            "face_fix": False,
            "color_grade": None,
            "film_grain": False,
            "sharpen": False,
        }

        # 1. Upscale
        if upscale and self.upsampler is not None:
            try:
                img, _ = self.upsampler.enhance(img, outscale=4)
                applied["upscale"] = True
            except Exception as e:
                logger.warning("Upscale failed: %s", e)

        # 2. Face restoration (CodeFormer preferred, GFPGAN fallback)
        if face_fix:
            if self._codeformer_infer is not None:
                try:
                    out = self._codeformer_infer(
                        img,
                        background_enhance=False,
                        face_upsample=False,
                        upscale=1,
                        codeformer_fidelity=0.5,
                    )
                    if out is not None:
                        img = out
                        applied["face_fix"] = True
                except Exception as e:
                    logger.warning("CodeFormer face restore failed: %s", e)
            elif self.face_restorer is not None:
                try:
                    _, _, img = self.face_restorer.enhance(
                        img, has_aligned=False, only_center_face=False, paste_back=True
                    )
                    applied["face_fix"] = True
                except Exception as e:
                    logger.warning("GFPGAN face restore failed: %s", e)

        # 3. Color grading
        if color_grade and color_grade in self._luts:
            img = _apply_lut_numpy(img, self._luts[color_grade])
            applied["color_grade"] = color_grade

        # 4. Film grain
        if film_grain > 0:
            img = _add_film_grain(img, film_grain)
            applied["film_grain"] = True

        # 5. Sharpening
        if sharpen > 0:
            img = _sharpen(img, sharpen)
            applied["sharpen"] = True

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(img_rgb)
        buf = io.BytesIO()
        pil.save(buf, format=output_format.upper(), quality=95)
        b64_out = base64.b64encode(buf.getvalue()).decode("utf-8")

        result = {k: v for k, v in item.items() if k not in ("image_base64", "image_bytes")}
        result["image_base64"] = b64_out
        result["processed"] = True
        result["original_size"] = original_size
        result["final_size"] = (img.shape[1], img.shape[0])
        result["applied"] = applied
        return result


def _build_programmatic_luts() -> Dict[str, np.ndarray]:
    """Simple 33^3 LUTs (cinematic, vibrant, vintage, cool, warm, neutral)."""
    size = 33
    luts: Dict[str, np.ndarray] = {}
    # Identity
    id_lut = np.zeros((size, size, size, 3), dtype=np.float32)
    for r in range(size):
        for g in range(size):
            for b in range(size):
                id_lut[r, g, b] = [
                    r / (size - 1),
                    g / (size - 1),
                    b / (size - 1),
                ]

    def copy_lut() -> np.ndarray:
        return id_lut.copy()

    # Cinematic: crush blacks, slight teal shadows, warm highlights
    lut = copy_lut()
    lut[..., 0] = np.power(lut[..., 0], 1.1)
    lut[..., 1] = lut[..., 1] * 0.95 + lut[..., 0] * 0.05
    lut[..., 2] = lut[..., 2] * 1.05
    luts["cinematic"] = np.clip(lut, 0, 1).astype(np.float32)

    # Vibrant: boost saturation
    lut = copy_lut()
    mid = 0.5
    for c in range(3):
        lut[..., c] = mid + (lut[..., c] - mid) * 1.25
    luts["vibrant"] = np.clip(lut, 0, 1).astype(np.float32)

    # Vintage: warm, reduced blue
    lut = copy_lut()
    lut[..., 0] = lut[..., 0] * 1.05
    lut[..., 1] = lut[..., 1] * 1.02
    lut[..., 2] = lut[..., 2] * 0.88
    luts["vintage"] = np.clip(lut, 0, 1).astype(np.float32)

    # Cool: reduce red, boost blue
    lut = copy_lut()
    lut[..., 0] = lut[..., 0] * 0.92
    lut[..., 2] = lut[..., 2] * 1.08
    luts["cool"] = np.clip(lut, 0, 1).astype(np.float32)

    # Warm: boost red/orange
    lut = copy_lut()
    lut[..., 0] = lut[..., 0] * 1.1
    lut[..., 1] = lut[..., 1] * 1.03
    lut[..., 2] = lut[..., 2] * 0.95
    luts["warm"] = np.clip(lut, 0, 1).astype(np.float32)

    luts["neutral"] = id_lut.astype(np.float32)
    return luts


def _apply_lut_numpy(img_bgr: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Apply 3D LUT. img_bgr -> index LUT (RGB) -> output BGR."""
    size = lut.shape[0]
    img = img_bgr.astype(np.float32) / 255.0
    r = np.clip((img[:, :, 2] * (size - 1)).astype(np.int32), 0, size - 1)
    g = np.clip((img[:, :, 1] * (size - 1)).astype(np.int32), 0, size - 1)
    b = np.clip((img[:, :, 0] * (size - 1)).astype(np.int32), 0, size - 1)
    out = lut[r, g, b]  # (H,W,3) RGB
    out = (np.clip(out, 0, 1) * 255).astype(np.uint8)
    return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)


def _add_film_grain(img_bgr: np.ndarray, intensity: float = 0.3) -> np.ndarray:
    noise = np.random.normal(0, intensity * 32, img_bgr.shape).astype(np.float32)
    out = np.clip(img_bgr.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return out


def _sharpen(img_bgr: np.ndarray, amount: float = 0.5) -> np.ndarray:
    blurred = cv2.GaussianBlur(img_bgr, (0, 0), 3)
    out = cv2.addWeighted(img_bgr, 1.0 + amount, blurred, -amount, 0)
    return np.clip(out, 0, 255).astype(np.uint8)


def _save_processed(
    image_base64: str,
    output_format: str,
    original_path: str,
    index: int = 0,
    upload_s3: bool = False,
    s3_bucket: str = "photogenius-results",
) -> str:
    """Save processed image to /tmp or S3. Returns path (file:// or s3://)."""
    raw = base64.b64decode(image_base64)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ext = output_format.lower() if output_format else "png"
    filename = f"finished_{ts}_{index}.{ext}"
    local = Path(tempfile.gettempdir()) / filename
    local.write_bytes(raw)
    if upload_s3:
        try:
            import boto3  # type: ignore[reportMissingImports]

            s3 = boto3.client("s3")
            key = f"finished/{filename}"
            s3.upload_file(str(local), s3_bucket, key)
            return f"s3://{s3_bucket}/{key}"
        except Exception as e:
            logger.warning("S3 upload failed, returning local path: %s", e)
    return str(local)


@app.local_entrypoint()
def main() -> None:
    print("Finish engine: CodeFormer (GFPGAN fallback), RealESRGAN 4×, .cube LUTs.")
    print("  finish(images=[{image_base64|image_bytes}, ...], ...) -> base64 results")
    print("  finish_from_paths(image_paths=[...], ..., upload_s3=True) -> path results")
    print("  modal deploy ai-pipeline/services/finish_engine.py")

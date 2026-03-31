"""
PhotoGenius GPU2 Post-Processor — SageMaker Inference Handler
v3.2 — Asymmetric prompt routing + signal preservation + regional attention + seam/overlap fixes.

v3.0 philosophy: GPU2 is a TEXTURE GLAZER, not a re-architect.
GPU1 (PixArt T5-XXL) = composition brain  →  GPU2 (RealVisXL CLIP) = texture renderer.
NEVER send full user prompt to GPU2 — CLIP can't understand spatial relationships,
tries to redraw geometry → melts hands, genericizes jewelry, destroys cultural detail.

Key fixes v2.0 → v3.0:
  - Asymmetric prompting: GPU2 gets hardcoded photorealism prompt (no user prompt)
  - CFG 4.7→2.5 (human), 5.0→3.5 (scene) — preserves high-freq latent noise (pores, fabric)
  - Denoising 0.38-0.65 → 0.20-0.35 — texture injection only, no geometry redraw
  - ControlNet end scheduling: control_guidance_end=0.4 (geometry lock first 40%, free 60%)
  - Face latent lock: CONDITIONAL + dynamic sigma (4.5/6.0/skip based on det_score)
  - ADetailer: generic face prompt, max 5 faces, dynamic strength by det_score
  - Hand detailer: targeted hand region inpaint via OpenPose keypoints
  - ESRGAN loop REMOVED (upscale-downscale = low-pass filter destroying micro-contrast)
  - Camera sim GATED by jury_score (only applied to high-quality images)

Architecture:
- RealVisXL V5.0 (6.5GB): img2img base with MultiControlNet
- ControlNet-Depth (2.3GB): scene geometry (non-human scenes only)
- ControlNet-OpenPose (1.3GB): human anatomy + pose lock (human scenes only)
- InsightFace ONNX (0.5GB): human detection + face/eye landmarks + det_score
- RealESRGAN-x4 (0.1GB): loaded but NOT USED (kept for potential future use)
Total: ~11-13GB / 24GB VRAM (stable, never fragmented)

ONE PIPELINE. NEVER REBUILT.
ControlNet gating (weight-switch only, control_guidance_end=0.4):
  Human scene:   pose=0.65, depth=0.00 (end at 40% steps)
  No humans:     depth=0.70, pose=0.00 (end at 40% steps)

Pipeline (v3.1 — 9 steps):
  0. InsightFace detection — one call, faces + det_scores reused throughout
  1. RealVisXL refine (TEXTURE PROMPT, CFG 2.5/3.5, str 0.20-0.35, CN end=0.4)
 1b. Person regional refine (MULTI-PERSON ONLY, 2+ faces): per-person crop→refine→paste
      str=0.20, CFG=2.5, 25 steps, zero CN — 100% attention per person vs ~25% shared
  2. ADetailer — face inpaint (GENERIC face prompt, max 5, dynamic strength)
  3. Hand detailer — hand region inpaint via OpenPose wrist/elbow keypoints
  4. Face latent lock (CONDITIONAL: skip if det_score<0.5, dynamic sigma 4.5-6.0)
  5. Latent cohesion pass (str=0.10, steps=5, CFG=2.5 — blend seams)
  6. Camera simulation (GATED — only if jury_score>0.5)
  7. Output JPEG q=92

Key rule: ALL model loading in model_fn() only. NEVER inside request handler.

Hardware: ml.g5.2xlarge (24GB VRAM A10G, 32GB RAM, 450GB NVMe)
Container: pytorch-inference:2.4.0-gpu-py311-cu124-ubuntu22.04-sagemaker
"""

import base64
import gc
import io
import json
import logging
import os
import threading
import time
import traceback
from typing import Any, Dict, Optional

import torch
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("gpu2-postproc")

# ============================================================
# Global state
# ============================================================
S3_BUCKET    = os.environ.get("S3_BUCKET", "photogenius-models-dev")
MODELS_CACHE = "/tmp/models"

# ONE pipeline — never rebuilt
REALVIS_PIPE = None       # StableDiffusionXLControlNetImg2ImgPipeline (MultiControlNet)

# ControlNet models (loaded at startup, passed to MultiControlNet)
DEPTH_CN_MODEL   = None   # ControlNetModel
OPENPOSE_CN_MODEL= None   # ControlNetModel

# Blank neutral image (same size as input) — reused when CN weight=0
# Pre-created per-resolution at first use
_BLANK_CACHE: Dict[tuple, Any] = {}

# OpenPose detector — lightweight, lazy on first human request
# (CPU/GPU pose extraction utility; ~0.3GB; not a ControlNet model)
OPENPOSE_DETECTOR = None
_openpose_detector_lock = threading.Lock()
_openpose_detector_loaded = False

# InstantID (optional)
INSTANTID_LOADED = False
FACE_ANALYSER    = None   # InsightFace FaceAnalysis (also used for human detection)
INSTANTID_PIPE   = None   # IPAdapterFaceIDPlus

# Upscaler
REALESRGAN_NET = None

_models_ready = threading.Event()
_loaded_models: set = set()

# ============================================================
# S3 paths
# ============================================================
MODEL_S3_PATHS = {
    "realvisxl-v5":         "models/core/realvisxl-v5",
    "controlnet-depth":     "models/control/controlnet-depth",
    "controlnet-openpose":  "models/control/controlnet-openpose",
    "instantid":            "models/core/instantid",
    "realesrgan":           "models/enhancement/realesrgan",
}


# ============================================================
# RRDBNet (RealESRGAN) — self-contained, no extra dependency
# ============================================================
import torch.nn as nn
import torch.nn.functional as F


class ResidualDenseBlock(nn.Module):
    def __init__(self, num_feat=64, num_grow_ch=32):
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    def __init__(self, num_feat, num_grow_ch=32):
        super().__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x):
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class RRDBNet(nn.Module):
    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64,
                 num_block=23, num_grow_ch=32, scale=4):
        super().__init__()
        self.scale = scale
        if scale == 2:
            num_in_ch = num_in_ch * 4
        elif scale == 1:
            num_in_ch = num_in_ch * 16
        self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
        self.body       = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
        self.conv_body  = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1   = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2   = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr    = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last  = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        if self.scale == 2:
            feat = F.pixel_unshuffle(x, downscale_factor=2)
        elif self.scale == 1:
            feat = F.pixel_unshuffle(x, downscale_factor=4)
        else:
            feat = x
        feat = self.conv_first(feat)
        feat = feat + self.conv_body(self.body(feat))
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))


# ============================================================
# S3 helpers
# ============================================================

def _s3_client():
    import boto3
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _download_s3_dir(s3_prefix: str, local_dir: str) -> bool:
    try:
        s3 = _s3_client()
        paginator = s3.get_paginator("list_objects_v2")
        count = 0
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=s3_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel = key[len(s3_prefix):].lstrip("/")
                if not rel:
                    continue
                dest = os.path.join(local_dir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                s3.download_file(S3_BUCKET, key, dest)
                count += 1
        logger.info("Downloaded %d files: s3://%s/%s → %s", count, S3_BUCKET, s3_prefix, local_dir)
        return count > 0
    except Exception as e:
        logger.error("S3 download failed (%s/%s): %s", S3_BUCKET, s3_prefix, e)
        return False


# ============================================================
# Model loaders — ALL called from model_fn() only
# ============================================================

def _load_controlnet_models() -> bool:
    """
    Load ControlNet-Depth and ControlNet-OpenPose as separate models.
    Both loaded at startup — no lazy loading — stable VRAM, no fragmentation.
    Returns True if at least one loaded (depth fallback ok).
    """
    global DEPTH_CN_MODEL, OPENPOSE_CN_MODEL
    from diffusers import ControlNetModel
    success = False

    # Depth CN
    try:
        cn_dir = os.path.join(MODELS_CACHE, "controlnet-depth")
        if not os.path.exists(os.path.join(cn_dir, "config.json")):
            _download_s3_dir(MODEL_S3_PATHS["controlnet-depth"], cn_dir)
        DEPTH_CN_MODEL = ControlNetModel.from_pretrained(
            cn_dir, torch_dtype=torch.float16
        ).to("cuda")
        _loaded_models.add("controlnet-depth")
        logger.info("ControlNet-Depth loaded (2.3GB)")
        success = True
    except Exception as e:
        logger.warning("ControlNet-Depth load failed: %s", e)

    # OpenPose CN
    try:
        cn_dir = os.path.join(MODELS_CACHE, "controlnet-openpose")
        if not os.path.exists(os.path.join(cn_dir, "config.json")):
            _download_s3_dir(MODEL_S3_PATHS["controlnet-openpose"], cn_dir)
        # S3 stores weight as OpenPoseXL2.safetensors — rename to standard name for from_pretrained
        _std_weight = os.path.join(cn_dir, "diffusion_pytorch_model.safetensors")
        _alt_weight = os.path.join(cn_dir, "OpenPoseXL2.safetensors")
        if not os.path.exists(_std_weight) and os.path.exists(_alt_weight):
            os.rename(_alt_weight, _std_weight)
            logger.info("Renamed OpenPoseXL2.safetensors -> diffusion_pytorch_model.safetensors")
        OPENPOSE_CN_MODEL = ControlNetModel.from_pretrained(
            cn_dir, torch_dtype=torch.float16
        ).to("cuda")
        _loaded_models.add("controlnet-openpose")
        logger.info("ControlNet-OpenPose loaded (1.3GB)")
        success = True
    except Exception as e:
        logger.warning("ControlNet-OpenPose load failed: %s", e)

    return success


def _load_realvisxl() -> bool:
    """
    Load RealVisXL with MultiControlNet (depth + openpose).
    Requires both CN models to already be loaded.
    Falls back to single CN or plain img2img if models missing.
    ONE pipeline — never rebuilt per request.
    """
    global REALVIS_PIPE
    try:
        from diffusers import (
            ControlNetModel,
            MultiControlNetModel,
            StableDiffusionXLControlNetImg2ImgPipeline,
            StableDiffusionXLImg2ImgPipeline,
        )

        local_dir = os.path.join(MODELS_CACHE, "realvisxl-v5")
        if not os.path.exists(os.path.join(local_dir, "model_index.json")):
            if not _download_s3_dir(MODEL_S3_PATHS["realvisxl-v5"], local_dir):
                return False

        # Build pipeline based on what CN models are available
        if DEPTH_CN_MODEL is not None and OPENPOSE_CN_MODEL is not None:
            # Best case: MultiControlNet (depth + openpose simultaneously)
            multi_cn = MultiControlNetModel([DEPTH_CN_MODEL, OPENPOSE_CN_MODEL])
            REALVIS_PIPE = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
                local_dir,
                controlnet=multi_cn,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True,
            ).to("cuda")
            logger.info("RealVisXL + MultiControlNet(depth+pose) loaded — ONE pipeline, weight-switching only")

        elif DEPTH_CN_MODEL is not None:
            # Single depth CN fallback
            REALVIS_PIPE = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
                local_dir,
                controlnet=DEPTH_CN_MODEL,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True,
            ).to("cuda")
            logger.info("RealVisXL + ControlNet-Depth (single) loaded")

        else:
            # Plain img2img fallback (both CNs unavailable)
            REALVIS_PIPE = StableDiffusionXLImg2ImgPipeline.from_pretrained(
                local_dir,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True,
            ).to("cuda")
            logger.warning("RealVisXL loaded WITHOUT ControlNet (no CNs available)")

        REALVIS_PIPE.enable_attention_slicing()
        _loaded_models.add("realvisxl")
        return True

    except Exception as e:
        logger.error("RealVisXL load failed: %s", e)
        traceback.print_exc()
        return False


def _load_openpose_detector() -> None:
    """
    Load OpenposeDetector (controlnet_aux) in model_fn.
    Lightweight CPU/GPU pose extraction utility.
    Downloads pose estimation weights from HuggingFace on first call.
    """
    global OPENPOSE_DETECTOR, _openpose_detector_loaded
    try:
        from controlnet_aux import OpenposeDetector
        OPENPOSE_DETECTOR = OpenposeDetector.from_pretrained("lllyasviel/ControlNet")
        _openpose_detector_loaded = True
        _loaded_models.add("openpose-detector")
        logger.info("OpenposeDetector loaded")
    except Exception as e:
        logger.warning("OpenposeDetector load failed (%s) — pose maps will use edge fallback", e)


def _load_realesrgan() -> bool:
    global REALESRGAN_NET
    try:
        ckpt_path = os.path.join(MODELS_CACHE, "realesrgan", "RealESRGAN_x4plus.pth")
        if not os.path.exists(ckpt_path):
            if not _download_s3_dir(MODEL_S3_PATHS["realesrgan"],
                                    os.path.join(MODELS_CACHE, "realesrgan")):
                return False
        net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                      num_block=23, num_grow_ch=32, scale=4)
        sd = torch.load(ckpt_path, map_location="cpu")
        if "params_ema" in sd:   sd = sd["params_ema"]
        elif "params" in sd:     sd = sd["params"]
        net.load_state_dict(sd, strict=True)
        net.eval().to("cuda")
        REALESRGAN_NET = net
        _loaded_models.add("realesrgan")
        logger.info("RealESRGAN-x4 loaded")
        return True
    except Exception as e:
        logger.error("RealESRGAN load failed: %s", e)
        return False


def _load_instantid() -> bool:
    global INSTANTID_LOADED, FACE_ANALYSER, INSTANTID_PIPE
    try:
        from insightface.app import FaceAnalysis
        FACE_ANALYSER = FaceAnalysis(
            name="buffalo_l",
            root=os.path.join(MODELS_CACHE, "insightface"),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        FACE_ANALYSER.prepare(ctx_id=0, det_size=(640, 640))
        _loaded_models.add("insightface")
        logger.info("InsightFace loaded (human detection + InstantID)")

        instantid_dir = os.path.join(MODELS_CACHE, "instantid")
        if not os.path.exists(os.path.join(instantid_dir, "ip-adapter.bin")):
            if not _download_s3_dir(MODEL_S3_PATHS["instantid"], instantid_dir):
                logger.warning("InstantID weights not in S3")
                return False

        if REALVIS_PIPE is None:
            logger.warning("RealVisXL not ready — InstantID skipped")
            return False

        try:
            from ip_adapter.ip_adapter_faceid import IPAdapterFaceIDPlus
            INSTANTID_PIPE = IPAdapterFaceIDPlus(
                REALVIS_PIPE,
                image_encoder_path=os.path.join(instantid_dir, "image_encoder"),
                ip_ckpt=os.path.join(instantid_dir, "ip-adapter.bin"),
                device="cuda",
                num_tokens=16,
            )
        except ImportError:
            logger.warning("ip_adapter package not available — InstantID disabled")
            return False

        INSTANTID_LOADED = True
        _loaded_models.add("instantid")
        logger.info("InstantID IP-Adapter loaded")
        return True
    except Exception as e:
        logger.warning("InstantID load failed (non-fatal): %s", e)
        return False


# ============================================================
# Human detection + face helpers
# ============================================================

def _get_faces(image) -> list:
    """Run InsightFace on image. Returns list of face objects (empty on error/no humans)."""
    if FACE_ANALYSER is None:
        return []
    try:
        return FACE_ANALYSER.get(np.array(image.convert("RGB")))
    except Exception as e:
        logger.warning("[DETECT] InsightFace failed (%s)", e)
        return []


def _detect_humans(image) -> bool:
    """Detect humans via InsightFace face detection (already in VRAM, fast)."""
    faces = _get_faces(image)
    count = len(faces)
    logger.info("[DETECT] %d human(s) found", count)
    return count > 0


def _adetailer_refine(image, faces: list, prompt: str):
    """
    v3.0 ADetailer: face region crop-and-inpaint with GENERIC PROMPT OVERRIDE.

    KEY CHANGES from v2.0:
      - GENERIC face prompt (ignores user prompt) — fixes "micro-universe" bug where
        SDXL tried to render "group of friends" inside a 64px face crop → monsters
      - max_faces: 2→5 (group photos fully refined)
      - min_face: 80→40px (distant/small faces now caught)
      - Dynamic strength by InsightFace det_score:
          det_score > 0.75: str=0.30 (good face, light touch)
          det_score 0.50-0.75: str=0.38 (medium face, moderate rebuild)
          det_score < 0.50: str=0.45 (bad face, heavy rebuild)
      - CFG: 4.5→3.0 (lower CFG preserves skin texture in face crops too)
      - Steps: 20→15 (at lower strength, fewer steps prevent overbaking)

    Faces are re-detected on the refined 1024px image (original faces from draft
    are off-scale). Sorted largest-first for priority processing.
    """
    if REALVIS_PIPE is None or not faces:
        return image
    try:
        from PIL import Image as _PIL
        from diffusers import StableDiffusionXLImg2ImgPipeline
        import numpy as _np
        from scipy.ndimage import gaussian_filter as _gf

        # Re-detect on refined 1024px image — draft bboxes are off-scale
        refined_faces = _get_faces(image)
        if not refined_faces:
            logger.info("[ADETAIL] No faces on refined image — skip")
            return image

        # Sort by face area (largest first — most visible, highest priority)
        refined_faces = sorted(refined_faces,
            key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]), reverse=True)

        img_w, img_h = image.size
        result = image.copy()

        # v3.0: GENERIC prompts — prevent "micro-universe" contamination
        face_prompt = (
            "highly detailed face, natural skin texture, sharp eyes, "
            "realistic pores, photorealistic portrait, masterpiece"
        )
        face_neg = (
            "distorted, asymmetrical, mutated, ugly, poorly drawn, "
            "blurry, deformed, extra eyes, cartoon, anime"
        )

        is_plain_img2img = isinstance(REALVIS_PIPE, StableDiffusionXLImg2ImgPipeline)
        is_multi = (DEPTH_CN_MODEL is not None and OPENPOSE_CN_MODEL is not None)

        processed = 0
        for face in refined_faces[:5]:  # v3.0: max 5 faces (was 2)
            x1, y1, x2, y2 = [int(c) for c in face.bbox]
            fw, fh = x2 - x1, y2 - y1
            if fw < 40 or fh < 40:  # v3.0: min 40px (was 80)
                logger.info("[ADETAIL] Face %dpx too small — skip", min(fw, fh))
                continue

            # v3.0: Dynamic strength by det_score
            det_score = float(getattr(face, 'det_score', 0.5))
            if det_score > 0.75:
                face_strength = 0.30   # good face, light touch
            elif det_score >= 0.50:
                face_strength = 0.38   # medium face, moderate rebuild
            else:
                face_strength = 0.45   # bad face, heavy rebuild

            # Asymmetric padding: generous top/sides, LESS below to push seam away from shoulder.
            # Old: symmetric 40% all sides → seam ring visible at shoulder level.
            # New: 50% top (hair), 35% sides, 20% bottom (chin to upper neck only).
            pad_top  = int(fh * 0.50)
            pad_side = int(fw * 0.35)
            pad_bot  = int(fh * 0.20)   # keep seam at chin/neck, NOT shoulder
            cx1 = max(0,     x1 - pad_side)
            cy1 = max(0,     y1 - pad_top)
            cx2 = min(img_w, x2 + pad_side)
            cy2 = min(img_h, y2 + pad_bot)
            crop = result.crop((cx1, cy1, cx2, cy2))
            crop_w, crop_h = crop.size

            # img2img on face crop — ControlNet disabled, GENERIC prompt
            if is_plain_img2img:
                refined_crop = REALVIS_PIPE(
                    prompt=face_prompt, negative_prompt=face_neg, image=crop,
                    strength=face_strength, num_inference_steps=15,
                    guidance_scale=3.0, guidance_rescale=0.7, eta=0.0, output_type="pil",
                ).images[0]
            else:
                blank = _blank_image(crop.size)
                ctrl_imgs  = [blank, blank] if is_multi else blank
                cn_scales  = [0.0,  0.0]   if is_multi else 0.0
                refined_crop = REALVIS_PIPE(
                    prompt=face_prompt, negative_prompt=face_neg, image=crop,
                    control_image=ctrl_imgs,
                    controlnet_conditioning_scale=cn_scales,
                    strength=face_strength, num_inference_steps=15,
                    guidance_scale=3.0, guidance_rescale=0.7, eta=0.0, output_type="pil",
                ).images[0]

            # Feathered paste-back — sigma 1.5x larger than before (was 0.5x).
            # Old: sigma=feather*0.5 → sharp oval seam ring visible at crop boundary.
            # New: sigma=feather*1.5 → gradual 2.4x softer blend, no visible ring.
            feather = max(15, min(crop_w, crop_h) // 6)   # was max(10, //8)
            mask = _np.zeros((crop_h, crop_w), dtype=_np.float32)
            mask[feather:-feather, feather:-feather] = 1.0
            mask = _gf(mask, sigma=feather * 1.5)[:, :, _np.newaxis]  # was * 0.5

            orig_np = _np.array(result.crop((cx1, cy1, cx2, cy2))).astype(_np.float32)
            ref_np  = _np.array(refined_crop.resize((crop_w, crop_h), _PIL.LANCZOS)).astype(_np.float32)
            blended = _PIL.fromarray(_np.clip(ref_np * mask + orig_np * (1.0 - mask), 0, 255).astype(_np.uint8))
            result.paste(blended, (cx1, cy1))
            processed += 1
            logger.info("[ADETAIL] Face %d (%dx%d) det=%.2f str=%.2f cfg=3.0 steps=15 (asym-pad, soft-feather)",
                        processed, fw, fh, det_score, face_strength)

        logger.info("[ADETAIL] %d/%d face(s) processed (v3.0 generic prompt, dynamic strength)",
                    processed, min(len(refined_faces), 5))
        return result
    except Exception as e:
        logger.warning("[ADETAIL] Failed (%s) — returning unchanged", e)
        return image


def _face_latent_lock(refined, original_resized, faces: list):
    """
    v3.0 — CONDITIONAL frequency-separation face lock with DYNAMIC sigma.

    KEY CHANGE from v2.0: Lock is now CONDITIONAL on face quality.
    v2.0 always locked → permanently froze broken geometry from draft.
    v3.0 checks InsightFace det_score per face:
      - det_score > 0.75: LOCK with sigma=4.5 (good face, preserve identity)
      - det_score 0.50-0.75: LOCK with sigma=6.0 (medium face, let refiner correct more)
      - det_score < 0.50: SKIP lock (bad face, trust RealVisXL to regenerate)

    Sigma explanation:
      sigma=4.5 (mid-frequency): structures >4.5px from original, <4.5px from refined.
      This transfers pure epidermal texture (pores, fine wrinkles) from RealVisXL
      without importing draft's inferior tonal gradients. Wider than v2.0's 2.5 —
      gives refiner enough freedom to correct minor geometrical misalignments.

    Previous values and why they failed:
      sigma=2.5 (v2.0): too tight → locked draft defects, overrode RealVisXL texture → waxy
      sigma=8.0 (v1.5): too broad → too much draft low-freq bled through → also waxy
    """
    if not faces:
        return refined
    try:
        from PIL import Image as _PIL
        from scipy.ndimage import gaussian_filter as _gf
        result   = np.array(refined).astype(np.float32)
        orig_np  = np.array(original_resized.resize(refined.size, _PIL.LANCZOS)).astype(np.float32)
        h, w     = result.shape[:2]

        # Build per-face mask with dynamic sigma based on det_score
        mask = np.zeros((h, w), dtype=np.float32)
        faces_locked = 0
        faces_skipped = 0

        for face in faces:
            det_score = float(getattr(face, 'det_score', 0.5))

            if det_score < 0.50:
                # Bad face — skip lock entirely, trust RealVisXL regeneration
                logger.info("[FACE-LOCK] Face det_score=%.2f < 0.50 — SKIP (let refiner regenerate)", det_score)
                faces_skipped += 1
                continue

            # Dynamic sigma: higher det_score = tighter lock (more identity preservation)
            sigma = 4.5 if det_score > 0.75 else 6.0

            x1, y1, x2, y2 = [int(c) for c in face.bbox]
            pad_y = int((y2 - y1) * 0.20)
            pad_x = int((x2 - x1) * 0.15)
            x1 = max(0, x1 - pad_x); y1 = max(0, y1 - pad_y)
            x2 = min(w, x2 + pad_x); y2 = min(h, y2 + pad_y)
            if x2 <= x1 or y2 <= y1:
                continue

            # Per-face frequency separation with dynamic sigma
            face_mask = np.zeros((h, w), dtype=np.float32)
            face_mask[y1:y2, x1:x2] = 1.0
            face_mask = _gf(face_mask, sigma=12)

            orig_low     = _gf(orig_np,  sigma=[sigma, sigma, 0])
            refined_low  = _gf(result,   sigma=[sigma, sigma, 0])
            refined_high = result - refined_low
            face_reconstructed = np.clip(orig_low + refined_high, 0, 255)

            # Apply only in this face's region
            fm3 = face_mask[:, :, np.newaxis]
            result = face_reconstructed * fm3 + result * (1 - fm3)

            faces_locked += 1
            logger.info("[FACE-LOCK] Face det_score=%.2f → sigma=%.1f (locked)", det_score, sigma)

        logger.info("[FACE-LOCK] %d locked, %d skipped (conditional v3.0)", faces_locked, faces_skipped)
        return _PIL.fromarray(np.clip(result, 0, 255).astype(np.uint8))
    except Exception as e:
        logger.warning("[FACE-LOCK] Failed (%s) — returning refined unchanged", e)
        return refined


def _face_contrast_lift(image, faces: list):
    """
    +6% local contrast boost in face region only.

    After frequency separation, face geometry is locked but can feel slightly flat
    vs. the background. A targeted luminance contrast stretch (+6%) in the face
    zone makes faces naturally draw the eye — simulating how camera lenses
    prioritise the focal subject without applying global sharpening.
    """
    if not faces:
        return image
    try:
        from PIL import Image as _PIL
        from scipy.ndimage import gaussian_filter as _gf
        img   = np.array(image).astype(np.float32)
        h, w  = img.shape[:2]
        mask  = np.zeros((h, w), dtype=np.float32)
        for face in faces:
            x1, y1, x2, y2 = [int(c) for c in face.bbox]
            pad_y = int((y2 - y1) * 0.15); pad_x = int((x2 - x1) * 0.10)
            x1 = max(0, x1 - pad_x); y1 = max(0, y1 - pad_y)
            x2 = min(w, x2 + pad_x); y2 = min(h, y2 + pad_y)
            if x2 > x1 and y2 > y1:
                mask[y1:y2, x1:x2] = 1.0
        mask = _gf(mask, sigma=12)[:, :, np.newaxis]
        # Luminance contrast stretch: stretch values away from local mean by 6%
        lum      = 0.299 * img[:,:,0] + 0.587 * img[:,:,1] + 0.114 * img[:,:,2]
        mean_lum = np.mean(lum[mask[:,:,0] > 0.5]) if np.any(mask[:,:,0] > 0.5) else 128.0
        lifted   = (img - mean_lum) * 1.06 + mean_lum
        result   = lifted * mask + img * (1 - mask)
        logger.info("[FACE-CONTRAST] +6%% face contrast for %d face(s)", len(faces))
        return _PIL.fromarray(np.clip(result, 0, 255).astype(np.uint8))
    except Exception as e:
        logger.warning("[FACE-CONTRAST] Failed (%s) — skipping", e)
        return image


def _hand_stabilize_blend(image, original_resized, faces: list):
    """
    Blend 25% original draft in estimated hand/wrist region.

    OpenPose anchors major joints but doesn't stabilize fingers — high-frequency
    hand structure is lost during img2img denoising. Blending 25% of the original
    draft at the estimated hand zone (1.5x–3.5x face height below chin, wider than
    face width) preserves grip geometry and knuckle structure without a separate
    hand detection model.
    """
    if not faces:
        return image
    try:
        from PIL import Image as _PIL
        from scipy.ndimage import gaussian_filter
        result  = np.array(image).astype(np.float32)
        orig_np = np.array(original_resized.resize(image.size, _PIL.LANCZOS)).astype(np.float32)
        h, w    = result.shape[:2]
        mask    = np.zeros((h, w), dtype=np.float32)

        for face in faces:
            x1, y1, x2, y2 = [int(c) for c in face.bbox]
            fh = y2 - y1; fw = x2 - x1
            # Estimate hand zone: lower body region
            hy1 = min(h, int(y2 + fh * 1.5))
            hy2 = min(h, int(y2 + fh * 3.5))
            hx1 = max(0, x1 - int(fw * 0.8))
            hx2 = min(w, x2 + int(fw * 0.8))
            if hx2 > hx1 and hy2 > hy1:
                mask[hy1:hy2, hx1:hx2] = 1.0

        mask    = gaussian_filter(mask, sigma=20)
        mask    = np.clip(mask, 0, 1)[:, :, np.newaxis]
        blended = orig_np * 0.25 * mask + result * (1.0 - 0.25 * mask)
        logger.info("[HAND-BLEND] Applied for %d face(s)", len(faces))
        from PIL import Image as _PIL2
        return _PIL2.fromarray(np.clip(blended, 0, 255).astype(np.uint8))
    except Exception as e:
        logger.warning("[HAND-BLEND] Failed (%s) — skipping", e)
        return image


def _eye_micro_restore(image, faces: list):
    """
    Luminance-channel unsharp mask on iris regions — restores eye clarity.

    Sharpening on RGB directly causes color halos (R/G/B channels sharpened
    independently → color fringing). Working in LAB colorspace and sharpening
    only the L (luminance) channel gives crisp iris detail without color artifacts.

    InsightFace kps[0] = left eye center, kps[1] = right eye center.
    """
    if not faces:
        return image
    try:
        from PIL import Image as _PIL, ImageFilter as _IF
        result_np = np.array(image).astype(np.uint8)
        w, h = image.size

        for face in faces:
            if face.kps is None or len(face.kps) < 2:
                continue
            for kp in face.kps[:2]:  # left eye, right eye
                ex, ey = int(kp[0]), int(kp[1])
                r = 28
                x1, y1 = max(0, ex - r), max(0, ey - r)
                x2, y2 = min(w, ex + r), min(h, ey + r)
                if x2 <= x1 or y2 <= y1:
                    continue

                region_rgb = result_np[y1:y2, x1:x2]
                region_pil = _PIL.fromarray(region_rgb)

                # Convert to LAB — sharpen only L channel
                region_lab = region_pil.convert("LAB")
                l, a, b    = region_lab.split()
                l_sharp    = l.filter(_IF.UnsharpMask(radius=0.4, percent=25, threshold=2))
                sharpened  = _PIL.merge("LAB", (l_sharp, a, b)).convert("RGB")

                result_np[y1:y2, x1:x2] = np.array(sharpened)

        logger.info("[EYE-RESTORE] Luminance sharpen for %d face(s)", len(faces))
        from PIL import Image as _PIL2
        return _PIL2.fromarray(result_np)
    except Exception as e:
        logger.warning("[EYE-RESTORE] Failed (%s) — skipping", e)
        return image


def _eye_detailer_refine(image, faces: list):
    """
    v3.2 — Conditional eye region refinement for close-up portraits.

    Fixes molten irises, warped eyeballs, and asymmetric eyes that PixArt-Sigma
    frequently produces on close-up portraits.

    ONLY triggers when face occupies >15% of image area (close-up/portrait shot).
    Uses InsightFace eye keypoints (kps[0]=left eye, kps[1]=right eye) for precise
    crop regions. Runs RealVisXL img2img at very low strength (0.22-0.28) with
    generic eye prompt to preserve identity while fixing iris topology.

    Skipped for wide shots, group photos, and any face with det_score < 0.5
    (too damaged for eye-level fix — let ADetailer handle the whole face).
    """
    if REALVIS_PIPE is None or not faces:
        return image
    try:
        from PIL import Image as _PIL
        from diffusers import StableDiffusionXLImg2ImgPipeline
        import numpy as _np
        from scipy.ndimage import gaussian_filter as _gf

        img_w, img_h = image.size
        img_area = img_w * img_h
        result = image.copy()

        eye_prompt = (
            "detailed realistic human eye, clear round iris, distinct pupil, "
            "natural sclera, sharp eyelashes, photorealistic"
        )
        eye_neg = (
            "molten eye, cloudy iris, deformed pupil, asymmetric eyes, "
            "glowing eyes, blurry, distorted, cartoon"
        )

        is_plain_img2img = isinstance(REALVIS_PIPE, StableDiffusionXLImg2ImgPipeline)
        is_multi = (DEPTH_CN_MODEL is not None and OPENPOSE_CN_MODEL is not None)

        processed = 0
        for face in faces[:3]:  # max 3 faces for eye detail
            det_score = float(getattr(face, 'det_score', 0.5))

            # Skip low-quality faces — ADetailer handles those
            if det_score < 0.50:
                continue

            # Check face area — only process close-up portraits
            fx1, fy1, fx2, fy2 = [int(c) for c in face.bbox]
            face_area = (fx2 - fx1) * (fy2 - fy1)
            face_pct = face_area / img_area

            if face_pct < 0.15:
                # Not a close-up — skip eye detail
                continue

            # Get eye keypoints from InsightFace
            if face.kps is None or len(face.kps) < 2:
                continue

            # Dynamic strength: better face = lighter touch
            if det_score > 0.75:
                eye_str = 0.22
            elif det_score > 0.60:
                eye_str = 0.25
            else:
                eye_str = 0.28

            for eye_idx in range(2):  # left eye (0), right eye (1)
                ex, ey = int(face.kps[eye_idx][0]), int(face.kps[eye_idx][1])

                # Eye crop radius proportional to face size
                face_h = fy2 - fy1
                r = max(24, int(face_h * 0.15))  # ~15% of face height

                # Padded crop
                pad = int(r * 0.4)
                cx1 = max(0, ex - r - pad)
                cy1 = max(0, ey - r - pad)
                cx2 = min(img_w, ex + r + pad)
                cy2 = min(img_h, ey + r + pad)

                crop_w = cx2 - cx1
                crop_h = cy2 - cy1
                if crop_w < 32 or crop_h < 32:
                    continue

                eye_crop = result.crop((cx1, cy1, cx2, cy2))

                if is_plain_img2img:
                    refined = REALVIS_PIPE(
                        prompt=eye_prompt, negative_prompt=eye_neg, image=eye_crop,
                        strength=eye_str, num_inference_steps=12,
                        guidance_scale=2.5, guidance_rescale=0.7, eta=0.0, output_type="pil",
                    ).images[0]
                else:
                    blank = _blank_image(eye_crop.size)
                    ctrl_imgs = [blank, blank] if is_multi else blank
                    cn_scales = [0.0, 0.0] if is_multi else 0.0
                    refined = REALVIS_PIPE(
                        prompt=eye_prompt, negative_prompt=eye_neg, image=eye_crop,
                        control_image=ctrl_imgs,
                        controlnet_conditioning_scale=cn_scales,
                        strength=eye_str, num_inference_steps=12,
                        guidance_scale=2.5, guidance_rescale=0.7, eta=0.0, output_type="pil",
                    ).images[0]

                # Feathered paste-back (extra soft for eye region)
                feather = max(8, min(crop_w, crop_h) // 5)
                mask = _np.zeros((crop_h, crop_w), dtype=_np.float32)
                if feather < crop_h // 2 and feather < crop_w // 2:
                    mask[feather:-feather, feather:-feather] = 1.0
                else:
                    mask[:, :] = 1.0
                mask = _gf(mask, sigma=feather * 0.6)[:, :, _np.newaxis]

                orig_np = _np.array(result.crop((cx1, cy1, cx2, cy2))).astype(_np.float32)
                ref_np = _np.array(refined.resize((crop_w, crop_h), _PIL.LANCZOS)).astype(_np.float32)
                blended = _PIL.fromarray(
                    _np.clip(ref_np * mask + orig_np * (1.0 - mask), 0, 255).astype(_np.uint8)
                )
                result.paste(blended, (cx1, cy1))
                processed += 1

        if processed > 0:
            logger.info("[EYE-DETAIL] %d eye region(s) refined (close-up portrait)", processed)
        else:
            logger.info("[EYE-DETAIL] Skipped (no close-up faces detected)")
        return result
    except Exception as e:
        logger.warning("[EYE-DETAIL] Failed (%s) — returning unchanged", e)
        return image


def _detail_restore(image):
    """
    RealESRGAN detail injection: upscale 2x then resize back to original dimensions.

    Diffusion decoding always produces micro-blur. RealESRGAN reconstructs
    high-frequency texture (pores, strands, fabric fibers). Downscaling back
    keeps the reconstructed detail without the resolution increase.
    No output size change → TorchServe 8MB limit not hit.
    Latency: ~1-2s on A10G.
    """
    if REALESRGAN_NET is None:
        return image
    try:
        from PIL import Image as _PIL
        w, h      = image.size
        upscaled  = _upscale_image(image, scale=2)          # 1024 → 2048
        restored  = upscaled.resize((w, h), _PIL.LANCZOS)   # 2048 → 1024
        logger.info("[DETAIL-RESTORE] RealESRGAN inject: %dx%d → 2048 → %dx%d", w, h, w, h)
        return restored
    except Exception as e:
        logger.warning("[DETAIL-RESTORE] Failed (%s) — skipping", e)
        return image


# ============================================================
# Image helpers
# ============================================================

def _b64_to_pil(b64_str: str):
    from PIL import Image
    return Image.open(io.BytesIO(base64.b64decode(b64_str))).convert("RGB")


def _pil_to_b64(img) -> str:
    # JPEG q=92 → ~250-400KB vs PNG ~3-5MB after ESRGAN detail restore.
    # Keeps response well within SageMaker's 6MB real-time limit.
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _blank_image(size: tuple):
    """Mid-gray neutral image — used when a ControlNet weight is 0."""
    from PIL import Image
    if size not in _BLANK_CACHE:
        _BLANK_CACHE[size] = Image.new("RGB", size, (128, 128, 128))
    return _BLANK_CACHE[size]


def _extract_depth_map(image):
    """Edge-distance pseudo-depth (no model needed, ~0.1s)."""
    from PIL import Image, ImageFilter
    from scipy.ndimage import convolve, distance_transform_edt
    gray = np.array(image.convert("L")).astype(np.float32)
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    gx = convolve(gray, kx)
    gy = convolve(gray, kx.T)
    edges = np.hypot(gx, gy)
    edges = (edges / (edges.max() + 1e-8) * 255).astype(np.uint8)
    dist = distance_transform_edt(1 - (edges > 30).astype(np.uint8)).astype(np.float32)
    dist = (dist / (dist.max() + 1e-8) * 255).astype(np.uint8)
    return Image.fromarray(dist).filter(ImageFilter.GaussianBlur(3)).resize(image.size, Image.LANCZOS)


def _extract_pose_map(image):
    """Extract OpenPose skeleton. Falls back to depth map if detector unavailable."""
    if OPENPOSE_DETECTOR is not None:
        try:
            pose = OPENPOSE_DETECTOR(image, hand_and_face=True)
            logger.info("[POSE] OpenPose skeleton extracted")
            return pose
        except Exception as e:
            logger.warning("[POSE] Failed (%s) — depth fallback for pose slot", e)
    # Fallback: depth map in pose slot (still better than blank for anatomy hints)
    return _extract_depth_map(image)


# ============================================================
# Smart texture keyword extraction (v3.2)
# ============================================================

# Texture-safe keyword categories that CLIP handles well.
# NO spatial verbs, NO actions, NO composition directives — those melt geometry.
_TEXTURE_KEYWORDS = {
    # Materials & fabrics
    "silk", "satin", "velvet", "leather", "denim", "linen", "cotton", "wool",
    "lace", "chiffon", "tulle", "sequin", "embroidered", "beaded", "metallic",
    "gold", "golden", "silver", "bronze", "copper", "chrome", "glass", "crystal",
    "marble", "granite", "wood", "wooden", "stone", "brick", "concrete", "steel",
    # Lighting
    "golden hour", "blue hour", "neon", "candlelight", "firelight", "moonlight",
    "backlit", "rim light", "soft light", "harsh light", "dramatic lighting",
    "studio lighting", "natural light", "ambient", "moody",
    # Color tones
    "warm tones", "cool tones", "muted", "vibrant", "pastel", "earthy",
    "monochrome", "sepia", "desaturated",
    # Camera/film
    "bokeh", "shallow depth", "tilt shift", "macro", "telephoto", "wide angle",
    "film grain", "kodak", "fujifilm", "portra", "cinematic",
    # Surface qualities
    "glossy", "matte", "frosted", "polished", "rough", "textured", "smooth",
    "wet", "dewy", "dusty", "weathered", "rustic", "vintage", "antique",
}


def _extract_texture_keywords(user_prompt: str) -> str:
    """Extract texture-safe keywords from user prompt for CLIP conditioning.

    Returns comma-separated string of found keywords, or empty string.
    Only includes words/phrases CLIP can meaningfully condition on —
    materials, lighting, colors, camera terms. Spatial verbs excluded.
    """
    if not user_prompt:
        return ""
    prompt_lower = user_prompt.lower()
    found = []
    # Check multi-word phrases first (longest match wins)
    for kw in sorted(_TEXTURE_KEYWORDS, key=len, reverse=True):
        if kw in prompt_lower and kw not in found:
            found.append(kw)
    # Cap at 8 keywords to avoid prompt dilution
    return ", ".join(found[:8])


# ============================================================
# Core refinement — ONE pipeline, weight switching only
# ============================================================

def _realvisxl_refine(image, prompt: str, jury_score: float, has_humans: bool,
                      target_w: int = None, target_h: int = None):
    """
    RealVisXL + MultiControlNet refine — v3.0 ASYMMETRIC PROMPT.

    KEY CHANGE: GPU2 does NOT use user prompt. CLIP encoder can't understand
    spatial relationships (T5 can). Sending action verbs causes CLIP to try
    redrawing geometry → melts hands, genericizes jewelry, destroys detail.

    GPU2 prompt = hardcoded photorealism texture-only keywords.
    GPU2 job = inject texture + lighting, NOT redesign composition.

    v3.0 parameter changes:
      - CFG: human=2.5, scene=3.5 (was 4.7/5.0 — high CFG kills micro-texture)
      - Strength: 0.20-0.35 dynamic (was 0.38-0.65 — high strength redraws geometry)
      - ControlNet: control_guidance_end=0.4 (lock geometry first 40%, free render last 60%)
      - Steps: 25 (was 35 — fewer steps at low strength prevents overbaking)

    Strength from jury_score (texture injection only):
      > 0.75 → 0.20 (excellent draft, lightest touch)
      0.55-0.75 → 0.28 (good draft, moderate texture)
      < 0.55 → 0.35 (weak draft, heavier texture injection)
    """
    if REALVIS_PIPE is None:
        return image

    # Resize draft → target resolution before rendering
    from PIL import Image as _PILImage
    if target_w and target_h and (image.width != target_w or image.height != target_h):
        image = image.resize((target_w, target_h), _PILImage.LANCZOS)
        logger.info("[REFINE] Draft resized → %dx%d before render", target_w, target_h)

    # v3.0: Lower strength range — texture injection, NOT geometry redraw
    strength = 0.20 if jury_score > 0.75 else (0.28 if jury_score >= 0.55 else 0.35)

    # v3.0: Lower CFG — preserves high-frequency latent noise (pores, wrinkles, fabric weave)
    # RealVisXL V5.0 sweet spot for img2img is 1.5-3.5 (empirically verified)
    if has_humans:
        guidance = 2.5   # humans need lowest CFG for natural skin subsurface scattering
    else:
        guidance = 3.5   # scenes can handle slightly higher for structural sharpness

    # v3.2: SMART ASYMMETRIC PROMPT — base texture + user's material/lighting keywords
    # CLIP can't handle spatial verbs ("gripping", "standing beside") — those melt geometry.
    # But CLIP CAN condition on materials, lighting, colors, camera terms.
    # _extract_texture_keywords strips everything except texture-safe words.
    base_texture = (
        "masterpiece, photorealistic, ultra high resolution, natural skin texture, "
        "sharp focus, detailed pores, realistic lighting, cinematic color grading, "
        "professional photography, 8k, film grain, natural shadows, "
        "subsurface scattering, micro detail, razor sharp"
    )
    user_texture = _extract_texture_keywords(prompt)
    if user_texture:
        texture_prompt = f"{base_texture}, {user_texture}"
        logger.info("[REFINE] Smart texture prompt: +[%s]", user_texture)
    else:
        texture_prompt = base_texture
    neg = (
        "cartoon, anime, illustration, painting, low quality, blurry, "
        "distorted, deformed, oversaturated, overexposed, artificial, "
        "plastic skin, waxy, smooth skin, airbrushed"
    )

    # v3.0: 25 steps (was 35) — at low strength+CFG, fewer steps = crisper, no overbaking
    num_steps = 25

    try:
        from diffusers import StableDiffusionXLImg2ImgPipeline, StableDiffusionXLControlNetImg2ImgPipeline

        # Plain img2img fallback (no CNs available)
        if isinstance(REALVIS_PIPE, StableDiffusionXLImg2ImgPipeline):
            safe_strength = min(strength, 0.35)
            logger.info("[REFINE] Base img2img (no CN) | str=%.2f cfg=%.1f steps=%d",
                        safe_strength, guidance, num_steps)
            return REALVIS_PIPE(
                prompt=texture_prompt, negative_prompt=neg, image=image,
                strength=safe_strength, num_inference_steps=num_steps,
                guidance_scale=guidance, guidance_rescale=0.7, eta=0.0, output_type="pil",
            ).images[0]

        # ControlNet path (single or MultiControlNet)
        is_multi = (DEPTH_CN_MODEL is not None and OPENPOSE_CN_MODEL is not None)

        if is_multi:
            neutral = _blank_image(image.size)
            if has_humans:
                pose_map     = _extract_pose_map(image)
                control_imgs = [neutral, pose_map]
                cn_scales    = [0.00, 0.65]
                logger.info("[REFINE] MultiCN human | pose=0.65 str=%.2f cfg=%.1f steps=%d CN_end=0.4",
                            strength, guidance, num_steps)
            else:
                depth_map    = _extract_depth_map(image)
                control_imgs = [depth_map, neutral]
                cn_scales    = [0.70, 0.00]
                logger.info("[REFINE] MultiCN scene | depth=0.70 str=%.2f cfg=%.1f steps=%d CN_end=0.4",
                            strength, guidance, num_steps)

            result = REALVIS_PIPE(
                prompt=texture_prompt, negative_prompt=neg, image=image,
                control_image=control_imgs,
                controlnet_conditioning_scale=cn_scales,
                control_guidance_end=0.4,  # v3.0: geometry lock first 40%, free render last 60%
                strength=strength, num_inference_steps=num_steps,
                guidance_scale=guidance, guidance_rescale=0.7, eta=0.0, output_type="pil",
            ).images[0]

        else:
            # Single ControlNet (depth only)
            depth_map = _extract_depth_map(image)
            logger.info("[REFINE] Single DepthCN | str=%.2f cfg=%.1f steps=%d CN_end=0.4",
                        strength, guidance, num_steps)
            result = REALVIS_PIPE(
                prompt=texture_prompt, negative_prompt=neg, image=image,
                control_image=depth_map,
                controlnet_conditioning_scale=0.55,
                control_guidance_end=0.4,
                strength=strength, num_inference_steps=num_steps,
                guidance_scale=guidance, guidance_rescale=0.7, eta=0.0, output_type="pil",
            ).images[0]

        logger.info("[REFINE] Complete (v3.0 asymmetric prompt, low CFG, CN end=0.4)")
        return result

    except Exception as e:
        logger.warning("[REFINE] Failed (%s) — returning original image", e)
        return image


def _instantid_refine(image, prompt: str, reference_face_b64: str, jury_score: float,
                      target_w: int = None, target_h: int = None):
    """InstantID face identity conditioning (reference_face path)."""
    if not INSTANTID_LOADED or FACE_ANALYSER is None or INSTANTID_PIPE is None:
        return None  # caller falls back to _realvisxl_refine
    try:
        # Resize draft to target resolution before rendering
        from PIL import Image as _PILImage
        if target_w and target_h and (image.width != target_w or image.height != target_h):
            image = image.resize((target_w, target_h), _PILImage.LANCZOS)
            logger.info("[INSTANTID] Draft resized → %dx%d", target_w, target_h)

        ref_pil = _b64_to_pil(reference_face_b64)
        faces = FACE_ANALYSER.get(np.array(ref_pil))
        if not faces:
            logger.warning("[INSTANTID] No face in reference — fallback")
            return None
        face_emb = faces[0].normed_embedding
        strength = 0.45 if jury_score > 0.75 else (0.55 if jury_score >= 0.55 else 0.65)
        neg = "cartoon, anime, low quality, blurry, distorted, wrong face, different person"
        result = INSTANTID_PIPE.generate(
            prompt=prompt, negative_prompt=neg,
            face_image=ref_pil, face_emb=face_emb,
            image=image, strength=strength,
            num_inference_steps=35, guidance_scale=5.0, ip_adapter_scale=0.8,
        )
        if isinstance(result, list):    result = result[0]
        elif hasattr(result, "images"): result = result.images[0]
        logger.info("[INSTANTID] Applied successfully")
        return result
    except Exception as e:
        logger.warning("[INSTANTID] Failed (%s) — fallback to RealVisXL", e)
        return None


# ============================================================
# Post-processing steps
# ============================================================

def _upscale_image(image, scale: int = 2):
    """RealESRGAN 4x → crop to 2x. Lanczos fallback."""
    if REALESRGAN_NET is None:
        w, h = image.size
        return image.resize((w * scale, h * scale), resample=3)
    try:
        img_t = torch.from_numpy(
            np.array(image).astype(np.float32) / 255.0
        ).permute(2, 0, 1).unsqueeze(0).to("cuda")
        with torch.no_grad():
            out_t = REALESRGAN_NET(img_t)
        out_np = (out_t.squeeze(0).permute(1, 2, 0).cpu().numpy().clip(0, 1) * 255).astype(np.uint8)
        from PIL import Image
        h4, w4 = out_np.shape[:2]
        pil_2x = Image.fromarray(out_np).resize((w4 // 2, h4 // 2), Image.LANCZOS)
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        logger.info("[UPSCALE] 2x done")
        return pil_2x
    except Exception as e:
        logger.warning("[UPSCALE] Failed (%s) — Lanczos fallback", e)
        w, h = image.size
        return image.resize((w * scale, h * scale), resample=3)


def _micro_contrast_restore(image):
    """
    Restore local contrast lost during SDXL VAE decode.

    SDXL's 4-channel VAE smooths micro-contrast — skin, fabric, hair all look
    slightly flat. A local contrast pass (CLAHE-style via scipy) amplifies
    deviations from local mean by 1.15× before feeding to RealESRGAN, giving
    the SR model sharper high-frequency edges to reconstruct.

    Runs entirely on CPU. ~0.05s.
    """
    try:
        from scipy.ndimage import uniform_filter
        img = np.array(image).astype(np.float32) / 255.0
        lum = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]
        local_mean = uniform_filter(lum, size=64)
        local_dev  = lum - local_mean
        enhanced   = local_mean + local_dev * 1.15
        scale      = np.where(lum > 0.01, enhanced / (lum + 1e-6), 1.0)
        scale      = np.clip(scale, 0.85, 1.15)[:, :, np.newaxis]
        restored   = np.clip(img * scale, 0, 1)
        logger.info("[MICRO-CONTRAST] Local contrast restored")
        from PIL import Image as _PIL
        return _PIL.fromarray((restored * 255).astype(np.uint8))
    except Exception as e:
        logger.warning("[MICRO-CONTRAST] Failed (%s) — skipping", e)
        return image


def _camera_defect_pass(image):
    """Reality simulation: grain + CA + bloom + rolloff + gradient + tone + vignette."""
    from PIL import Image
    from scipy.ndimage import gaussian_filter, shift as nd_shift
    img = np.array(image).astype(np.float32) / 255.0
    h, w = img.shape[:2]
    lum  = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]
    shadow = np.clip(1.0 - lum * 2.0, 0, 1)
    img[:, :, 0] += np.random.normal(0, 0.022, (h, w)).astype(np.float32) * shadow
    img[:, :, 1] += np.random.normal(0, 0.019, (h, w)).astype(np.float32) * shadow * 0.85
    img[:, :, 2] += np.random.normal(0, 0.022, (h, w)).astype(np.float32) * shadow
    img[:, :, 0] = nd_shift(img[:, :, 0], shift=(0, 1),  mode="reflect")
    img[:, :, 2] = nd_shift(img[:, :, 2], shift=(0, -1), mode="reflect")
    bloom = gaussian_filter(img * np.clip((lum - 0.75) * 4.0, 0, 1)[:, :, np.newaxis], sigma=8)
    img  += bloom * 0.08
    img   = np.where(img > 0.85, 0.85 + (img - 0.85) * 0.5, img)
    img  *= np.linspace(1.03, 0.97, h, dtype=np.float32)[:, np.newaxis, np.newaxis]
    img   = np.clip(img, 0, 1) ** (1.0 / 1.03)
    cy, cx = h / 2, w / 2
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    vig = np.clip(1.0 - np.sqrt(((yy - cy) / cy) ** 2 + ((xx - cx) / cx) ** 2) * 0.045, 0.6, 1.0)
    img = np.clip(img * vig[:, :, np.newaxis], 0, 1)
    return Image.fromarray((img * 255).astype(np.uint8))


def _camera_defect_pass_light(image):
    """v3.0 — Light camera sim: grain + vignette only (no bloom/CA that amplify softness)."""
    from PIL import Image
    img = np.array(image).astype(np.float32) / 255.0
    h, w = img.shape[:2]
    lum  = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]
    # Light grain only
    shadow = np.clip(1.0 - lum * 2.0, 0, 1)
    img[:, :, 0] += np.random.normal(0, 0.015, (h, w)).astype(np.float32) * shadow
    img[:, :, 1] += np.random.normal(0, 0.013, (h, w)).astype(np.float32) * shadow * 0.85
    img[:, :, 2] += np.random.normal(0, 0.015, (h, w)).astype(np.float32) * shadow
    # Light vignette only
    cy, cx = h / 2, w / 2
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    vig = np.clip(1.0 - np.sqrt(((yy - cy) / cy) ** 2 + ((xx - cx) / cx) ** 2) * 0.03, 0.75, 1.0)
    img = np.clip(img * vig[:, :, np.newaxis], 0, 1)
    logger.info("[CAMERA-LIGHT] Grain + vignette only (no bloom/CA)")
    return Image.fromarray((img * 255).astype(np.uint8))


def _micro_polish(image):
    """Sharpen + contrast + saturation + vignette."""
    from PIL import Image, ImageEnhance, ImageFilter
    out = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=20, threshold=3))
    out = ImageEnhance.Contrast(out).enhance(1.04)
    out = ImageEnhance.Color(out).enhance(1.02)
    img_np = np.array(out).astype(np.float32)
    h, w   = img_np.shape[:2]
    cy, cx = h / 2.0, w / 2.0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    vig = np.clip(1.0 - np.sqrt(((yy - cy) / cy) ** 2 + ((xx - cx) / cx) ** 2) * 0.07, 0.75, 1.0)
    img_np *= vig[:, :, np.newaxis]
    return Image.fromarray(np.clip(img_np, 0, 255).astype(np.uint8))


# ============================================================
# Perceptual attention layer
# ============================================================

def _background_desaturate(image, faces: list):
    """
    Gently reduce saturation outside human regions.

    AI images give equal visual weight to background and subjects.
    Reducing background saturation by 6% makes humans naturally pop
    without any visible manipulation — mimics how camera lenses deprioritize
    out-of-focus color rendering. No segmentation model needed.
    """
    if not faces:
        return image
    try:
        from PIL import Image as _PIL
        from scipy.ndimage import gaussian_filter
        img_np = np.array(image).astype(np.float32)
        h, w   = img_np.shape[:2]

        # Build human region mask from face bboxes — extend downward for body
        human_mask = np.zeros((h, w), dtype=np.float32)
        for face in faces:
            x1, y1, x2, y2 = [int(c) for c in face.bbox]
            face_h = y2 - y1
            # Extend bbox to approximate body (3× face height below)
            y2_body = min(h, y2 + face_h * 3)
            pad_x   = int((x2 - x1) * 0.35)
            x1 = max(0, x1 - pad_x); x2 = min(w, x2 + pad_x)
            if x2 > x1 and y2_body > y1:
                human_mask[y1:y2_body, x1:x2] = 1.0

        human_mask = gaussian_filter(human_mask, sigma=30)
        human_mask = np.clip(human_mask, 0, 1)[:, :, np.newaxis]

        # Grayscale version (neutral desaturation target)
        gray = (0.299 * img_np[:,:,0] + 0.587 * img_np[:,:,1] + 0.114 * img_np[:,:,2])
        gray_3ch = gray[:, :, np.newaxis]

        # Blend: subject unchanged, background 6% desaturated
        desat = img_np * 0.94 + gray_3ch * 0.06
        result = img_np * human_mask + desat * (1 - human_mask)

        logger.info("[BG-DESAT] Applied for %d face(s)", len(faces))
        return _PIL.fromarray(np.clip(result, 0, 255).astype(np.uint8))
    except Exception as e:
        logger.warning("[BG-DESAT] Failed (%s) — skipping", e)
        return image


def _depth_dof(image):
    """
    Depth-based depth-of-field: gently blur background using pseudo-depth map.

    Subject (near edges) stays sharp; open background areas receive
    up to 1.5px Gaussian blur weighted by depth. Very subtle — enough
    to remove the AI "equally sharp everywhere" look without obvious
    blur artifacts. Uses the same edge-distance depth as ControlNet.
    """
    try:
        from PIL import Image as _PIL
        from scipy.ndimage import gaussian_filter
        depth_np = np.array(_extract_depth_map(image).convert("L")).astype(np.float32) / 255.0
        img_np   = np.array(image).astype(np.float32)
        # Max blur = 1.5px — enough for perceptual separation, not obvious
        blurred  = gaussian_filter(img_np, sigma=[1.5, 1.5, 0])
        # depth_np high = far background → more blur weight (max 0.35 blend)
        w_map    = (depth_np * 0.35)[:, :, np.newaxis]
        result   = img_np * (1 - w_map) + blurred * w_map
        logger.info("[DOF] Depth-based background blur applied")
        return _PIL.fromarray(np.clip(result, 0, 255).astype(np.uint8))
    except Exception as e:
        logger.warning("[DOF] Failed (%s) — skipping", e)
        return image


# ============================================================
# Person-level regional refinement (v3.1 — attention routing)
# ============================================================

def _person_regional_refine(image, faces: list):
    """
    v3.1 — Per-person regional attention routing.

    ROOT CAUSE: In multi-subject diffusion (SDXL/RealVisXL), cross-attention
    energy is shared across ALL subjects. With 4 people each gets ~25% attention
    → peripheral faces melt, bodies genericize, clothing blurs.

    FIX: For each detected person, isolate their body crop and run img2img at
    100% local attention. Global pass sets shared lighting/environment first,
    then this pass gives each person a private attention budget for texture.

    Implementation:
    - InsightFace face bbox → expanded to full upper-body person region
    - Per-person: RealVisXL img2img (SAME asymmetric texture prompt, no user prompt)
    - Feathered Gaussian paste-back (avoids hard seams)
    - Only triggers for 2+ detected persons (single person: global pass already 100%)
    - Skips if person region is too small (<200×200) or too large (>65% of image)

    Parameters chosen for zero-geometry-change texture injection:
    - strength=0.20 (ceil(25×0.20)=5 actual denoising steps, ~4-6s per person)
    - CFG=2.5 (same as global — preserves natural noise spectrum)
    - steps=25 (same as global — consistent noise schedule)
    - NO ControlNet (zero-weight, blank CN — crops are single-subject, no pose lock needed)
    """
    if REALVIS_PIPE is None or not faces or len(faces) < 2:
        return image  # single person or no faces: global pass already gave 100% attention

    try:
        from PIL import Image as _PIL
        from diffusers import StableDiffusionXLImg2ImgPipeline
        import numpy as _np
        from scipy.ndimage import gaussian_filter as _gf

        img_w, img_h = image.size
        img_area = img_w * img_h
        result = image.copy()

        # Asymmetric texture prompt — same as global pass (no user prompt, no spatial language)
        texture_prompt = (
            "masterpiece, photorealistic, ultra high resolution, natural skin texture, "
            "sharp focus, detailed pores, realistic lighting, cinematic color grading, "
            "professional photography, 8k, film grain, natural shadows, "
            "subsurface scattering, micro detail, razor sharp"
        )
        neg = (
            "cartoon, anime, illustration, painting, low quality, blurry, "
            "distorted, deformed, oversaturated, overexposed, artificial, "
            "plastic skin, waxy, smooth skin, airbrushed"
        )

        is_plain_img2img = isinstance(REALVIS_PIPE, StableDiffusionXLImg2ImgPipeline)
        is_multi = (DEPTH_CN_MODEL is not None and OPENPOSE_CN_MODEL is not None)

        # Sort faces by area descending — process most prominent people first
        sorted_faces = sorted(faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)

        processed = 0
        refined_bboxes = []  # track already-refined person crops to skip heavy overlaps

        for face in sorted_faces[:4]:  # max 4 persons (diminishing returns beyond)
            x1, y1, x2, y2 = [int(c) for c in face.bbox]
            fw = x2 - x1
            fh = y2 - y1

            # Expand face bbox to full-body person region
            # Head room above face (hair), chest + torso + arms below
            px1 = max(0,     int(x1 - fw * 1.2))   # shoulders width left
            py1 = max(0,     int(y1 - fh * 0.5))   # head room for hair
            px2 = min(img_w, int(x2 + fw * 1.2))   # shoulders width right
            py2 = min(img_h, int(y2 + fh * 3.5))   # torso + hands below chin

            pw = px2 - px1
            ph = py2 - py1

            # Skip trivially small crops
            if pw < 200 or ph < 200:
                logger.info("[PERSON-REFINE] Person %d skipped: crop too small (%dx%d)", processed+1, pw, ph)
                continue

            # Skip crops that cover most of the image (global pass already handled it well)
            crop_area = pw * ph
            if crop_area > img_area * 0.65:
                logger.info("[PERSON-REFINE] Person %d skipped: crop too large (%.0f%% of image)", processed+1, crop_area/img_area*100)
                continue

            # Skip if this crop heavily overlaps an already-refined person crop.
            # Closely packed subjects produce overlapping crops → double-refinement
            # at the overlap zone creates inconsistency. Skip if overlap > 50% of this crop.
            skip_this = False
            for rx1, ry1, rx2, ry2 in refined_bboxes:
                ix1 = max(px1, rx1); iy1 = max(py1, ry1)
                ix2 = min(px2, rx2); iy2 = min(py2, ry2)
                if ix2 > ix1 and iy2 > iy1:
                    inter = (ix2 - ix1) * (iy2 - iy1)
                    if crop_area > 0 and inter / crop_area > 0.50:
                        logger.info("[PERSON-REFINE] Person %d skipped: >50%% overlap with already-refined crop", processed+1)
                        skip_this = True
                        break
            if skip_this:
                continue

            crop = result.crop((px1, py1, px2, py2))

            # img2img — NO ControlNet (zero weight), asymmetric texture prompt
            # strength=0.20 → ceil(25×0.20)=5 actual steps — texture only, no geometry change
            if is_plain_img2img:
                refined_crop = REALVIS_PIPE(
                    prompt=texture_prompt, negative_prompt=neg, image=crop,
                    strength=0.20, num_inference_steps=25,
                    guidance_scale=2.5, guidance_rescale=0.7, eta=0.0, output_type="pil",
                ).images[0]
            else:
                blank = _blank_image(crop.size)
                ctrl_imgs = [blank, blank] if is_multi else blank
                cn_scales = [0.0, 0.0]    if is_multi else 0.0
                refined_crop = REALVIS_PIPE(
                    prompt=texture_prompt, negative_prompt=neg, image=crop,
                    control_image=ctrl_imgs,
                    controlnet_conditioning_scale=cn_scales,
                    strength=0.20, num_inference_steps=25,
                    guidance_scale=2.5, guidance_rescale=0.7, eta=0.0, output_type="pil",
                ).images[0]

            # Feathered paste-back — soft Gaussian blend (sigma=1.2x) to prevent seam rings
            feather = max(25, min(pw, ph) // 6)   # was max(20, //8)
            mask = _np.zeros((ph, pw), dtype=_np.float32)
            mask[feather:-feather, feather:-feather] = 1.0
            mask = _gf(mask, sigma=feather * 1.2)[:, :, _np.newaxis]  # was * 0.6

            orig_np = _np.array(result.crop((px1, py1, px2, py2))).astype(_np.float32)
            ref_np  = _np.array(refined_crop.resize((pw, ph), _PIL.LANCZOS)).astype(_np.float32)
            blended = _PIL.fromarray(_np.clip(ref_np * mask + orig_np * (1.0 - mask), 0, 255).astype(_np.uint8))
            result.paste(blended, (px1, py1))
            refined_bboxes.append((px1, py1, px2, py2))

            processed += 1
            logger.info("[PERSON-REFINE] Person %d/%d (%dx%d crop, face=%.0f%% → person=%.0f%% of img) | str=0.20 cfg=2.5",
                        processed, min(len(faces), 4), pw, ph,
                        (fw*fh)/img_area*100, crop_area/img_area*100)

        logger.info("[PERSON-REFINE] %d/%d person(s) regionally refined", processed, min(len(faces), 4))
        return result

    except Exception as e:
        logger.warning("[PERSON-REFINE] Failed (%s) — returning unchanged", e)
        return image


# ============================================================
# Main handler
# ============================================================

def _hand_detailer_refine(image, faces: list, jury_score: float = 0.5):
    """
    v3.2 — Hand region targeted inpaint with dynamic strength.

    Hands are the highest failure rate in all diffusion models.
    Face detailer exists but hand detailer was missing → watchmaker fingers melt,
    bride's hand on jewelry breaks, fashion model hands distort.

    Uses face-relative body zone estimation to find hand regions.
    Applies targeted img2img with generic hand prompt (same philosophy as face ADetailer).

    v3.2: Dynamic strength based on jury_score (mirrors ADetailer's dynamic approach):
      jury > 0.70:  str=0.35 (good draft, hands likely okay, light touch)
      jury 0.50-0.70: str=0.40 (medium draft, standard correction)
      jury < 0.50:  str=0.45 (weak draft, heavier hand rebuild)

    steps=15, CFG=3.0, no ControlNet
    """
    if REALVIS_PIPE is None or not faces:
        return image
    try:
        from PIL import Image as _PIL
        from diffusers import StableDiffusionXLImg2ImgPipeline
        import numpy as _np
        from scipy.ndimage import gaussian_filter as _gf

        img_w, img_h = image.size
        result = image.copy()

        # Dynamic strength based on draft quality (v3.2)
        if jury_score > 0.70:
            hand_str = 0.35   # good draft, hands likely decent, light touch
        elif jury_score > 0.50:
            hand_str = 0.40   # medium draft, standard correction
        else:
            hand_str = 0.45   # weak draft, heavier hand rebuild

        hand_prompt = (
            "highly detailed hands, correct finger count, natural skin texture, "
            "realistic hand anatomy, sharp knuckles, photorealistic, masterpiece"
        )
        hand_neg = (
            "extra fingers, missing fingers, fused fingers, deformed hands, "
            "blurry, distorted, mutated, ugly, cartoon"
        )

        is_plain_img2img = isinstance(REALVIS_PIPE, StableDiffusionXLImg2ImgPipeline)
        is_multi = (DEPTH_CN_MODEL is not None and OPENPOSE_CN_MODEL is not None)

        hand_regions = []

        # Strategy: estimate hand zone from face bbox (1.5x-4x face height below chin)
        # More reliable than OpenPose hand keypoints which are often missing/wrong
        for face in faces[:3]:  # max 3 hand zones (more = diminishing returns)
            x1, y1, x2, y2 = [int(c) for c in face.bbox]
            fh = y2 - y1
            fw = x2 - x1

            # Hand zone: below face, wider than face, extending down body
            hy1 = min(img_h, int(y2 + fh * 1.2))
            hy2 = min(img_h, int(y2 + fh * 4.0))
            hx1 = max(0, int(x1 - fw * 1.0))
            hx2 = min(img_w, int(x2 + fw * 1.0))

            hw = hx2 - hx1
            hh = hy2 - hy1
            if hw < 60 or hh < 60:
                continue
            hand_regions.append((hx1, hy1, hx2, hy2))

        # Merge heavily overlapping hand zones before processing.
        # Problem: closely packed faces (same y level) generate overlapping zones → triple-processing
        # at str=0.40 in the overlap area → creates new deformations instead of fixing hands.
        # Fix: merge any zones where intersection > 35% of the smaller zone's area into a union bbox.
        if len(hand_regions) > 1:
            merged = True
            while merged:
                merged = False
                new_regions = []
                skip = set()
                for i in range(len(hand_regions)):
                    if i in skip:
                        continue
                    ax1, ay1, ax2, ay2 = hand_regions[i]
                    for j in range(i + 1, len(hand_regions)):
                        if j in skip:
                            continue
                        bx1, by1, bx2, by2 = hand_regions[j]
                        ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
                        ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
                        if ix2 > ix1 and iy2 > iy1:
                            inter_area = (ix2 - ix1) * (iy2 - iy1)
                            min_area = min((ax2-ax1)*(ay2-ay1), (bx2-bx1)*(by2-by1))
                            if min_area > 0 and inter_area / min_area > 0.35:
                                ax1 = min(ax1, bx1); ay1 = min(ay1, by1)
                                ax2 = max(ax2, bx2); ay2 = max(ay2, by2)
                                skip.add(j)
                                merged = True
                    new_regions.append((ax1, ay1, ax2, ay2))
                hand_regions = new_regions
            logger.info("[HAND-DETAIL] After zone merge: %d zone(s)", len(hand_regions))

        processed = 0
        for hx1, hy1, hx2, hy2 in hand_regions:
            crop = result.crop((hx1, hy1, hx2, hy2))
            crop_w, crop_h = crop.size

            if is_plain_img2img:
                refined_crop = REALVIS_PIPE(
                    prompt=hand_prompt, negative_prompt=hand_neg, image=crop,
                    strength=hand_str, num_inference_steps=15,
                    guidance_scale=3.0, guidance_rescale=0.7, eta=0.0, output_type="pil",
                ).images[0]
            else:
                blank = _blank_image(crop.size)
                ctrl_imgs = [blank, blank] if is_multi else blank
                cn_scales = [0.0, 0.0] if is_multi else 0.0
                refined_crop = REALVIS_PIPE(
                    prompt=hand_prompt, negative_prompt=hand_neg, image=crop,
                    control_image=ctrl_imgs,
                    controlnet_conditioning_scale=cn_scales,
                    strength=hand_str, num_inference_steps=15,
                    guidance_scale=3.0, guidance_rescale=0.7, eta=0.0, output_type="pil",
                ).images[0]

            # Feathered paste-back
            feather = max(12, min(crop_w, crop_h) // 6)
            mask = _np.zeros((crop_h, crop_w), dtype=_np.float32)
            mask[feather:-feather, feather:-feather] = 1.0
            mask = _gf(mask, sigma=feather * 0.5)[:, :, _np.newaxis]

            orig_np = _np.array(result.crop((hx1, hy1, hx2, hy2))).astype(_np.float32)
            ref_np  = _np.array(refined_crop.resize((crop_w, crop_h), _PIL.LANCZOS)).astype(_np.float32)
            blended = _PIL.fromarray(_np.clip(ref_np * mask + orig_np * (1.0 - mask), 0, 255).astype(_np.uint8))
            result.paste(blended, (hx1, hy1))
            processed += 1
            logger.info("[HAND-DETAIL] Region %d (%dx%d) refined (str=%.2f steps=15 cfg=3.0 jury=%.2f)",
                        processed, crop_w, crop_h, hand_str, jury_score)

        logger.info("[HAND-DETAIL] %d hand region(s) processed", processed)
        return result
    except Exception as e:
        logger.warning("[HAND-DETAIL] Failed (%s) — returning unchanged", e)
        return image


def _latent_cohesion_pass(image):
    """
    v3.0 — Lightweight latent cohesion bake with TEXTURE PROMPT.

    Homogenizes noise floor after ADetailer + hand detailer paste-backs.
    Uses same asymmetric texture-only prompt as main refine (no user prompt).

    v3.0 changes from v2.0:
      - strength: 0.12→0.10 (even lighter — main refine already low-strength)
      - steps: 6→5 (prevents overbaking at low strength)
      - CFG: 3.2→2.5 (consistent with v3.0 low-CFG philosophy)
      - prompt: user prompt → hardcoded texture prompt (asymmetric routing)
    """
    if REALVIS_PIPE is None:
        return image
    try:
        from diffusers import StableDiffusionXLImg2ImgPipeline
        texture_prompt = (
            "photorealistic, natural lighting, seamless texture, "
            "unified color grading, professional photography"
        )
        neg = (
            "cartoon, anime, illustration, painting, low quality, blurry, "
            "distorted, deformed, artificial"
        )
        is_plain_img2img = isinstance(REALVIS_PIPE, StableDiffusionXLImg2ImgPipeline)
        is_multi = (DEPTH_CN_MODEL is not None and OPENPOSE_CN_MODEL is not None)

        if is_plain_img2img:
            result = REALVIS_PIPE(
                prompt=texture_prompt, negative_prompt=neg, image=image,
                strength=0.10, num_inference_steps=5,
                guidance_scale=2.5, guidance_rescale=0.7, eta=0.0, output_type="pil",
            ).images[0]
        else:
            blank = _blank_image(image.size)
            ctrl_imgs = [blank, blank] if is_multi else blank
            cn_scales = [0.0, 0.0] if is_multi else 0.0
            result = REALVIS_PIPE(
                prompt=texture_prompt, negative_prompt=neg, image=image,
                control_image=ctrl_imgs,
                controlnet_conditioning_scale=cn_scales,
                strength=0.10, num_inference_steps=5,
                guidance_scale=2.5, guidance_rescale=0.7, eta=0.0, output_type="pil",
            ).images[0]

        logger.info("[COHESION] Latent bake complete (v3.0: str=0.10 steps=5 cfg=2.5 texture prompt)")
        return result
    except Exception as e:
        logger.warning("[COHESION] Failed (%s) — skipping", e)
        return image


def _handle_post_process(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    GPU2 PREMIUM pipeline v3.2 — Asymmetric prompt + signal preservation.

    v3.2 philosophy: GPU2 is a TEXTURE GLAZER, not a re-architect.
    Never send user prompt to RealVisXL — CLIP can't understand spatial relations,
    tries to redraw → melts hands, genericizes jewelry, destroys cultural detail.

    Pipeline order (critical — do not reorder):
      0. InsightFace: one call, faces + det_scores reused throughout
      1. RealVisXL refine (TEXTURE prompt, CFG 2.5/3.5, str 0.20-0.35, CN end=0.4)
      2. ADetailer — face inpaint (GENERIC face prompt, max 5, dynamic strength)
     2b. Eye detailer — CONDITIONAL close-up portraits only (face>15%), str 0.22-0.28 [NEW v3.2]
      3. Hand detailer — hand region inpaint (GENERIC hand prompt, dynamic str=0.35-0.45) [UPD v3.2]
      4. Face latent lock (CONDITIONAL: skip bad faces, dynamic sigma 4.5-6.0)
      5. Latent cohesion pass (str=0.10, steps=5, CFG=2.5 — blend seams)
      6. Camera simulation (GATED: full if jury>0.7, partial 0.5-0.7, skip <0.5)

    REMOVED in v3.0 (signal destruction):
      - ESRGAN upscale-downscale loop (Lanczos downscale = low-pass filter)
      - face_contrast_lift, hand_stabilize_blend, eye_micro_restore
      - micro_contrast_restore, depth_dof, background_desaturate, micro_polish
    """
    start = time.time()

    image_b64      = payload.get("image", "")
    prompt         = payload.get("prompt", "")
    jury_score     = float(payload.get("jury_score", 0.5))
    reference_face = payload.get("reference_face")
    target_w = int(payload["target_width"])  if payload.get("target_width")  else None
    target_h = int(payload["target_height"]) if payload.get("target_height") else None

    if not image_b64:
        return {"status": "error", "error": "No image provided"}
    if not _models_ready.is_set():
        return {"status": "error", "error": "Models not ready yet"}

    try:
        image = _b64_to_pil(image_b64)
        logger.info("[POST-v3.0] start — draft %dx%d → target %sx%s | jury=%.3f ref=%s",
                    image.width, image.height,
                    target_w or "same", target_h or "same",
                    jury_score, "yes" if reference_face else "no")

        # Step 0: Human detection — single InsightFace call, reused downstream
        faces      = _get_faces(image)
        has_humans = len(faces) > 0
        face_scores = [float(getattr(f, 'det_score', 0.5)) for f in faces]
        logger.info("[POST-v3.0] %d human(s) detected, det_scores=%s",
                    len(faces), [round(s, 2) for s in face_scores])

        # Save draft resized to target resolution — geometry reference for face lock
        from PIL import Image as _PIL
        if target_w and target_h:
            original_for_blend = image.resize((target_w, target_h), _PIL.LANCZOS)
        else:
            original_for_blend = image.copy()

        # Step 1: RealVisXL refine (ASYMMETRIC texture prompt, low CFG, CN end=0.4)
        used_instantid = False
        if reference_face and INSTANTID_LOADED:
            refined = _instantid_refine(image, prompt, reference_face, jury_score, target_w, target_h)
            if refined is not None:
                image = refined
                used_instantid = True
            else:
                image = _realvisxl_refine(image, prompt, jury_score, has_humans, target_w, target_h)
        else:
            image = _realvisxl_refine(image, prompt, jury_score, has_humans, target_w, target_h)

        # Step 1b: Person regional refinement — ONLY for multi-person scenes (2+ people)
        # Each person gets a private attention budget (100% vs ~25% shared in global pass)
        # Triggers after global refine (shared lighting established) but before ADetailer (faces fixed on top)
        if has_humans and len(faces) >= 2:
            # Re-detect faces on the post-refine image for accurate bboxes at 1024px
            post_refine_faces = _get_faces(image)
            if len(post_refine_faces) >= 2:
                image = _person_regional_refine(image, post_refine_faces)

        # Step 2: ADetailer — face inpaint (GENERIC prompt, max 5, dynamic strength)
        if has_humans and faces:
            image = _adetailer_refine(image, faces, prompt)

        # Step 2b: Eye detailer — CONDITIONAL, close-up portraits only (face > 15% of image)
        # Fixes molten irises, warped eyeballs from PixArt-Sigma. Very low strength (0.22-0.28).
        if has_humans and faces:
            image = _eye_detailer_refine(image, faces)

        # Step 3: Hand detailer — targeted hand region inpaint (dynamic strength by jury)
        if has_humans and faces:
            image = _hand_detailer_refine(image, faces, jury_score=jury_score)

        # Step 4: Face latent lock — CONDITIONAL (skip bad faces, dynamic sigma)
        if has_humans and faces:
            # Re-detect faces on post-ADetailer image for accurate bboxes
            post_faces = _get_faces(image)
            if post_faces:
                image = _face_latent_lock(image, original_for_blend, post_faces)

        # Step 5: Latent cohesion pass — blend seams from ADetailer + hand detailer
        image = _latent_cohesion_pass(image)

        # Step 6: Camera simulation — GATED by jury score
        if jury_score > 0.70:
            # High quality draft → full camera simulation
            image = _camera_defect_pass(image)
            logger.info("[POST-v3.0] Camera sim: FULL (jury=%.3f > 0.70)", jury_score)
        elif jury_score > 0.50:
            # Medium quality → grain + vignette only (no bloom/CA that amplify softness)
            image = _camera_defect_pass_light(image)
            logger.info("[POST-v3.0] Camera sim: LIGHT (jury=%.3f 0.50-0.70)", jury_score)
        else:
            # Low quality → skip entirely (don't add effects on weak images)
            logger.info("[POST-v3.0] Camera sim: SKIP (jury=%.3f < 0.50)", jury_score)

        process_time = time.time() - start
        logger.info("[POST-v3.0] done %.1fs | %dx%d | humans=%d faces=%d openpose=%s instantid=%s",
                    process_time, image.width, image.height,
                    len(faces), len(face_scores),
                    has_humans and OPENPOSE_CN_MODEL is not None, used_instantid)

        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        gc.collect()

        return {
            "status":         "success",
            "image_base64":   _pil_to_b64(image),
            "image_format":   "jpeg",
            "process_time":   round(process_time, 2),
            "output_size":    f"{image.width}x{image.height}",
            "has_humans":     has_humans,
            "face_count":     len(faces),
            "face_det_scores": [round(s, 2) for s in face_scores],
            "used_openpose":  has_humans and OPENPOSE_CN_MODEL is not None,
            "used_instantid": used_instantid,
            "pipeline_version": "v3.0",
        }

    except Exception as e:
        logger.error("[POST-v3.0] failed: %s", e)
        traceback.print_exc()
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


# ============================================================
# SageMaker interface
# ============================================================

def model_fn(model_dir: str) -> Dict:
    """
    ALL model loading happens here — NEVER inside request handlers.

    Load order:
      1. ControlNet-Depth + ControlNet-OpenPose (~3.6GB, ~25s)
      2. RealVisXL V5.0 with MultiControlNet (~6.5GB, ~45s)
      3. RealESRGAN-x4 (64MB, ~2s)
      4. InsightFace + InstantID (~4.4GB optional, ~30s)
      5. OpenposeDetector — lightweight pose extractor (~10s)

    Expected: ~90s warm | ~180s cold (S3 download)
    VRAM at rest: ~13GB / 24GB
    """
    logger.info("=" * 60)
    logger.info("GPU2 Post-Processor v3.0 — Asymmetric prompt + signal preservation")
    if torch.cuda.is_available():
        logger.info("GPU: %s | VRAM: %.1fGB",
                    torch.cuda.get_device_name(0),
                    torch.cuda.get_device_properties(0).total_memory / 1e9)
    logger.info("=" * 60)

    os.makedirs(MODELS_CACHE, exist_ok=True)

    # 1. ControlNet models (must load before RealVisXL — passed to MultiControlNet constructor)
    _load_controlnet_models()

    # 2. RealVisXL with MultiControlNet (one pipeline, never rebuilt)
    rv_ok = _load_realvisxl()
    if not rv_ok:
        logger.error("RealVisXL FAILED — GPU2 severely degraded")

    # 3. Upscaler
    _load_realesrgan()

    # 4. InstantID + InsightFace (requires RealVisXL to be ready)
    _load_instantid()

    # 5. OpenPose detector (lightweight, for pose map extraction)
    _load_openpose_detector()

    _models_ready.set()

    vram_gb = torch.cuda.memory_allocated(0) / 1e9 if torch.cuda.is_available() else 0
    logger.info(
        "GPU2 MODEL_READY: True | loaded=%s | VRAM=%.1fGB",
        sorted(_loaded_models), vram_gb,
    )
    logger.info(
        "Pipeline mode: %s",
        "MultiControlNet(depth+pose)" if (DEPTH_CN_MODEL and OPENPOSE_CN_MODEL) else
        "SingleCN(depth)" if DEPTH_CN_MODEL else "Base img2img"
    )
    return {"loaded_models": list(_loaded_models)}


def input_fn(request_body, request_content_type: str = "application/json") -> Dict:
    if isinstance(request_body, (bytes, bytearray)):
        request_body = request_body.decode("utf-8")
    if isinstance(request_body, str):
        return json.loads(request_body)
    return request_body


def predict_fn(data: Dict, model_artifacts: Dict) -> Dict:
    action = data.get("action", "post_process")
    if action == "post_process":
        return _handle_post_process(data)
    elif action == "health":
        vram = torch.cuda.memory_allocated(0) / 1e9 if torch.cuda.is_available() else 0
        is_multi = DEPTH_CN_MODEL is not None and OPENPOSE_CN_MODEL is not None
        return {
            "status":           "healthy",
            "gpu2_ready":       _models_ready.is_set(),
            "loaded_models":    sorted(_loaded_models),
            "pipeline_mode":    "multi_cn" if is_multi else ("single_depth_cn" if DEPTH_CN_MODEL else "base"),
            "has_realvisxl":    REALVIS_PIPE is not None,
            "has_depth_cn":     DEPTH_CN_MODEL is not None,
            "has_openpose_cn":  OPENPOSE_CN_MODEL is not None,
            "has_openpose_det": OPENPOSE_DETECTOR is not None,
            "has_instantid":    INSTANTID_LOADED,
            "has_realesrgan":   REALESRGAN_NET is not None,
            "vram_used_gb":     round(vram, 2),
        }
    else:
        return {"status": "error", "error": f"Unknown action: {action!r}"}


def output_fn(prediction: Dict, accept: str = "application/json") -> str:
    return json.dumps(prediction)

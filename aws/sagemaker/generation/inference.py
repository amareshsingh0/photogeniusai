"""
PhotoGenius Generation GPU - SageMaker Inference Handler (v31)
GPU 1 of 2-GPU architecture.

Generation Models (hot-swap, ONE at a time):
- PixArt-Sigma (default) + FLUX.1-Schnell

Post-Processing Models (always loaded, ~1.6GB):
- CLIP-ViT-Large (~800MB) - quality scoring + jury
- RealESRGAN-x4 (~64MB) - 2x upscaling (FAST/STANDARD only)
- AestheticMLP (~4MB, CPU) - LAION v2.5 jury score
- MediaPipe Hands (~5MB, CPU) - 21-landmark hand validation [v31]

NudeNet: disabled (NUDENET_ENABLED=false). Set env var to "true" to re-enable.
RealVisXL: moved to GPU2 (photogenius-orchestrator post-processor).

Actions:
- generate_best: Best-of-N + CLIP jury + reality sim (FAST/STANDARD full; PREMIUM raw winner)
- health: Health check

Hardware: ml.g5.2xlarge (24GB VRAM A10G, 32GB RAM, 450GB NVMe)
GPU1 VRAM peak: ~14GB (PixArt 13 + CLIP 0.8) — down from ~21.5GB
"""

import json
import io
import base64
import os
import gc
import time
import logging
import random
import threading
from typing import Dict, Any, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("photogenius-generation")

# ============================================================
# Global state
# ============================================================
MODEL_DIR = None
S3_BUCKET = os.environ.get("S3_BUCKET", "photogenius-models-dev")
MODELS_CACHE = "/tmp/models"

# Generation models (hot-swap)
CURRENT_MODEL = None
PIPE = None
LAST_ACTIVITY_TIME = None

# Post-processing models (always loaded)
CLIP_MODEL = None
CLIP_PROCESSOR = None
REALESRGAN_NET = None
AESTHETIC_PREDICTOR = None  # LAION v2.5 MLP, CPU-only (~4MB), uses CLIP embeddings
YOLO_FACE_MODEL = None      # YOLOv8n face detector, CPU-only (~6MB)
YOLO_HAND_MODEL = None      # YOLOv8n hand detector, CPU-only (~6MB)
MEDIAPIPE_HANDS = None       # MediaPipe hand landmark validator, CPU-only (~5MB)

# NudeNet: disabled by default — set NUDENET_ENABLED=true in endpoint env to re-enable.
NUDENET_PIPELINE = None
NUDENET_ENABLED = os.environ.get("NUDENET_ENABLED", "false").lower() == "true"

# RealVisXL + ControlNet + depth estimation moved to GPU2 (photogenius-orchestrator).
# Variables kept as None so any stale call-sites fail gracefully instead of NameError.

GPU_LOCK = threading.Lock()

_init_complete = threading.Event()
_init_error = None
_loaded_models = set()

# S3 paths for all models (GPU1 only — RealVisXL/ControlNet/depth moved to GPU2)
MODEL_S3_PATHS = {
    # Generation
    "pixart-sigma": "models/core/pixart-sigma",
    "flux-schnell": "models/core/flux-schnell",
    # Post-processing (always loaded, ~1.6GB)
    "clip": "models/ranking/clip-vit-large",
    "realesrgan": "models/enhancement/realesrgan",
    "nudenet": "models/safety/nudenet",  # only downloaded when NUDENET_ENABLED=true
}

DEFAULT_MODEL = "pixart-sigma"


# ============================================================
# RRDBNet Architecture (for RealESRGAN-x4)
# ============================================================
import torch
import torch.nn as nn
import torch.nn.functional as F


class _ResidualDenseBlock(nn.Module):
    def __init__(self, nf=64, gc=32):
        super().__init__()
        self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
        self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
        self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
        self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
        self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(0.2, inplace=True)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class _RRDB(nn.Module):
    def __init__(self, nf, gc=32):
        super().__init__()
        self.rdb1 = _ResidualDenseBlock(nf, gc)
        self.rdb2 = _ResidualDenseBlock(nf, gc)
        self.rdb3 = _ResidualDenseBlock(nf, gc)

    def forward(self, x):
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class RRDBNet(nn.Module):
    """RealESRGAN x4 upscaler architecture."""

    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64,
                 num_block=23, num_grow_ch=32, scale=4):
        super().__init__()
        self.scale = scale
        self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
        self.body = nn.Sequential(
            *[_RRDB(num_feat, num_grow_ch) for _ in range(num_block)]
        )
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(0.2, inplace=True)

    def forward(self, x):
        feat = self.conv_first(x)
        body_feat = self.conv_body(self.body(feat))
        feat = feat + body_feat
        feat = self.lrelu(self.conv_up1(
            F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(
            F.interpolate(feat, scale_factor=2, mode="nearest")))
        out = self.conv_last(self.lrelu(self.conv_hr(feat)))
        return out


# ============================================================
# Aesthetic Predictor (LAION v2.5 MLP on CLIP ViT-L/14 embeddings)
# ============================================================
class AestheticMLP(nn.Module):
    """LAION Aesthetic Predictor v2.5.

    MLP trained on SAC+Logos+AVA1 human aesthetic ratings, using
    CLIP ViT-L/14 image embeddings (768-dim) as input.
    Output: scalar score (~1-10, higher = more aesthetically pleasing).

    Weights: christophschuhmann/improved-aesthetic-predictor
             sac+logos+ava1-l14-linearMSE.pth (~4MB)

    Runs on CPU only — no VRAM impact.
    """
    def __init__(self):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(768, 1024),
            nn.Dropout(0.2),
            nn.Linear(1024, 128),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.Dropout(0.1),
            nn.Linear(64, 16),
            nn.Linear(16, 1),
        )

    def forward(self, x):
        return self.layers(x)


# ============================================================
# Smart routing keywords
# ============================================================
HUMAN_KEYWORDS = [
    "person", "people", "human", "man", "woman", "child", "family", "group",
    "face", "portrait", "selfie", "headshot", "profile",
    "wedding", "bride", "groom", "couple",
    "crowd", "audience", "team", "friends",
    "girl", "boy", "lady", "guy", "kid", "baby", "teen",
    "model", "dancer", "actor", "actress", "singer",
    "indian", "chinese", "japanese", "african", "european",
    "ladki", "ladka", "aurat", "aadmi",
]

TEXT_TRIGGER_WORDS = [
    "text", "letters", "words", "sign", "typography", "font",
    "writing", "caption", "title", "logo", "label", "banner",
    "card", "poster", "headline", "quote",
]


# ============================================================
# Tier configuration
# ============================================================
TIER_CONFIG = {
    # Async inference → no 60s wall-clock limit.
    # Steps restored to full quality targets.
    # GPU1 timing (warm, 1024×1024, PixArt):
    #   FAST    ~55-70s  (8 steps,  1 candidate)
    #   STANDARD ~120-150s (22 steps, 1 candidate)
    #   PREMIUM ~570-630s (20 steps, 6 candidates + dedup + jury(4-component) + top-2 RealVisXL(adaptive strength,30) + upscale)
    "FAST": {
        "pixart-sigma":  {"steps": 8,  "guidance": 4.5},
        "flux-schnell":  {"steps": 4,  "guidance": 0.0},
    },
    "STANDARD": {
        # 16 steps: DPM++ handles it well, ~25% faster than 22 steps, near-identical quality.
        "pixart-sigma":  {"steps": 16, "guidance": 4.5},
        "flux-schnell":  {"steps": 4,  "guidance": 0.0},
    },
    "PREMIUM": {
        # 12 steps (DRAFT): jury only needs composition/layout, not final texture.
        # GPU2 does the true render at 30-35 steps with RealVisXL strength 0.45-0.65.
        # Draft at 768px: saves ~50% compute on GPU1.
        # Two-pass: fast composition discovery (GPU1) + cinematic render (GPU2).
        "pixart-sigma":  {"steps": 12, "guidance": 4.5},
        "flux-schnell":  {"steps": 4,  "guidance": 0.0},
    },
}


def get_tier_defaults(tier: str, model_name: str) -> Tuple[int, float]:
    tier_config = TIER_CONFIG.get(tier, TIER_CONFIG["STANDARD"])
    model_config = tier_config.get(
        model_name,
        tier_config.get(DEFAULT_MODEL, {"steps": 20, "guidance": 4.5}),
    )
    return model_config["steps"], model_config["guidance"]


# ============================================================
# S3 Download + NVMe Cache
# ============================================================
def get_local_model_path(model_name: str) -> str:
    s3_prefix = MODEL_S3_PATHS[model_name]
    return os.path.join(MODELS_CACHE, s3_prefix.replace("/", "_"))


def is_model_cached(model_name: str) -> bool:
    local_path = get_local_model_path(model_name)
    if not os.path.exists(local_path):
        return False
    # Only trust the completion marker (written after full download)
    marker = os.path.join(local_path, ".download_complete")
    return os.path.exists(marker)


def download_model_from_s3(model_name: str) -> str:
    import boto3
    from boto3.s3.transfer import TransferConfig

    s3_prefix = MODEL_S3_PATHS.get(model_name)
    if not s3_prefix:
        raise ValueError(f"Unknown model: {model_name}")

    local_path = get_local_model_path(model_name)

    if is_model_cached(model_name):
        logger.info(f"[S3 CACHE] {model_name} cached at {local_path}")
        return local_path

    logger.info(f"[S3] Downloading {model_name} from s3://{S3_BUCKET}/{s3_prefix}/")
    dl_start = time.time()

    # Multipart for large files
    transfer_config = TransferConfig(
        multipart_threshold=64 * 1024 * 1024,
        max_concurrency=10,
        multipart_chunksize=256 * 1024 * 1024,
    )

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    total_bytes = 0
    file_count = 0

    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=s3_prefix + "/"):
        for obj in page.get("Contents", []):
            s3_key = obj["Key"]
            rel_path = s3_key[len(s3_prefix) + 1:]
            if not rel_path:
                continue

            local_file = os.path.join(local_path, rel_path)
            os.makedirs(os.path.dirname(local_file), exist_ok=True)

            if os.path.exists(local_file) and os.path.getsize(local_file) == obj["Size"]:
                total_bytes += obj["Size"]
                file_count += 1
                continue

            file_gb = obj["Size"] / 1e9
            if file_gb > 1:
                logger.info(f"  [{model_name}] Downloading {rel_path} ({file_gb:.1f}GB)...")

            s3.download_file(S3_BUCKET, s3_key, local_file, Config=transfer_config)
            total_bytes += obj["Size"]
            file_count += 1

            if file_count % 10 == 0 or file_gb > 0.5:
                elapsed = time.time() - dl_start
                speed = (total_bytes / 1e6) / max(elapsed, 0.1)
                logger.info(f"  [{model_name}] {file_count} files, "
                            f"{total_bytes/1e9:.1f}GB, {elapsed:.0f}s ({speed:.0f} MB/s)")

    dl_time = time.time() - dl_start
    logger.info(f"[S3] {model_name}: {file_count} files, "
                f"{total_bytes/1e9:.1f}GB in {dl_time:.0f}s")

    # Write completion marker so partial downloads are detected
    marker = os.path.join(local_path, ".download_complete")
    with open(marker, "w") as f:
        f.write(f"{file_count} files, {total_bytes} bytes\n")

    return local_path


# ============================================================
# Model selection (smart routing)
# ============================================================
def select_model(
    tier: str, prompt: str, requested_model: Optional[str] = None,
    recommended_model: Optional[str] = None,
) -> Tuple[str, int, float]:
    # Priority 1: Explicit model request (for testing/debugging)
    if requested_model and requested_model in MODEL_S3_PATHS:
        model_name = requested_model
        logger.info(f"[SMART ROUTE] Explicit request -> {model_name}")

    # Priority 2: AI recommendation from GPU2 (Qwen2 scene analysis)
    # FLUX is hardware-gated: transformer alone is ~23GB bf16 — requires 40GB+ GPU.
    # On A10G (24GB) can_run_flux() returns False, so FLUX is never routed here.
    # When GPU is upgraded to 40GB+, FLUX auto-enables without any code change.
    elif recommended_model and recommended_model in MODEL_S3_PATHS:
        if recommended_model == "flux-schnell" and not can_run_flux():
            logger.info(f"[SMART ROUTE] AI rec=flux-schnell, hardware VRAM insufficient "
                        f"({torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB < 38GB) "
                        f"-> pixart-sigma")
            model_name = DEFAULT_MODEL
        else:
            model_name = recommended_model
            logger.info(f"[SMART ROUTE] AI recommendation -> {model_name}")

    # Priority 3: Default to PixArt-Sigma
    # Keyword→FLUX routing REMOVED: was fragile (OOM) and wrong (intent-unaware).
    # GPU2 Qwen2 handles intelligent model selection via scene analysis.
    else:
        model_name = DEFAULT_MODEL
        logger.info(f"[SMART ROUTE] Default -> {model_name}")

    if not is_model_cached(model_name) and model_name != DEFAULT_MODEL:
        logger.warning(f"Model {model_name} not cached, falling back to {DEFAULT_MODEL}")
        model_name = DEFAULT_MODEL

    steps, guidance = get_tier_defaults(tier, model_name)

    if tier == "FAST" and model_name == "pixart-sigma":
        prompt_lower = prompt.lower()
        if any(word in prompt_lower for word in TEXT_TRIGGER_WORDS):
            steps = 10

    return model_name, steps, guidance


# ============================================================
# GPU memory management
# ============================================================
def clear_gpu_memory():
    gc.collect()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.synchronize()   # flush pending kernels before releasing memory
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def can_run_flux() -> bool:
    """Hardware-aware VRAM gate for FLUX.1-Schnell.

    FLUX transformer alone is ~23GB bf16. On 24GB A10G:
      transformer (23GB) + activations (2-4GB) = OOM guaranteed.
    Requires 40GB+ GPU (A100/H100) for safe operation.

    Future-proof: when GPU is upgraded to 40GB+, FLUX auto-enables.
    No code change or redeploy needed.
    """
    if not torch.cuda.is_available():
        return False
    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    return total_vram_gb >= 38  # 40GB threshold with 2GB safety margin


def unload_generator():
    global CURRENT_MODEL, PIPE
    if CURRENT_MODEL:
        logger.info(f"[HOT-SWAP] Unloading '{CURRENT_MODEL}'...")
        # Flush all pending CUDA kernels BEFORE releasing model tensors.
        # Without this, Python GC may free GPU buffers that CUDA is still writing
        # into, causing silent corruption or CUDA_ILLEGAL_ACCESS on next request.
        # synchronize() blocks until ALL outstanding GPU work is complete.
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        PIPE = None
        CURRENT_MODEL = None
        clear_gpu_memory()


def ensure_model(model_name: str):
    """Guarantee model is loaded with clean GPU state. Must be called under GPU_LOCK.

    If the requested model is already active, returns immediately.
    Otherwise: unloads current model, clears VRAM fragmentation, loads target model.
    This prevents PixArt + FLUX coexistence = OOM.
    """
    if CURRENT_MODEL == model_name and PIPE is not None:
        return
    unload_generator()
    clear_gpu_memory()
    load_generator(model_name)


def _move_postprocessing_to_cpu():
    """Move ALL post-processing models to CPU before any generation.

    Called before every generation (both PixArt and FLUX):
    - PixArt: T5 encoding peaks at ~11GB VRAM; freeing 1.3GB gives safe headroom.
    - FLUX: transformer ~23GB; absolute requirement (blocked by VRAM gate anyway).
    Moving ~1.3GB to CPU takes < 0.5s.
    """
    moved = []
    if CLIP_MODEL is not None:
        try:
            CLIP_MODEL.cpu()
            moved.append("clip")
        except Exception:
            pass
    if REALESRGAN_NET is not None:
        try:
            REALESRGAN_NET.cpu()
            moved.append("realesrgan")
        except Exception:
            pass
    if NUDENET_PIPELINE is not None:
        try:
            NUDENET_PIPELINE.model.cpu()
            moved.append("nudenet")
        except Exception:
            pass
    if moved:
        gc.collect()
        torch.cuda.empty_cache()
        free_mb = 0
        if torch.cuda.is_available():
            free_mb = (torch.cuda.get_device_properties(0).total_memory
                       - torch.cuda.memory_allocated()) / 1e6
        logger.info(f"[VRAM] Moved to CPU: {moved} | GPU free: {free_mb:.0f}MB")
    return moved


def _move_postprocessing_to_gpu():
    """Restore post-processing models to GPU after FLUX generation."""
    moved = []
    if CLIP_MODEL is not None:
        try:
            CLIP_MODEL.to("cuda")
            moved.append("clip")
        except Exception:
            pass
    if REALESRGAN_NET is not None:
        try:
            REALESRGAN_NET.to("cuda")
            moved.append("realesrgan")
        except Exception:
            pass
    if NUDENET_PIPELINE is not None:
        try:
            NUDENET_PIPELINE.model.to("cuda")
            moved.append("nudenet")
        except Exception:
            pass
    if moved:
        logger.info(f"[VRAM] Restored to GPU: {moved}")


# ============================================================
# Post-processing model loaders
# ============================================================
def _load_clip():
    """Load CLIP-ViT-Large for prompt-image quality scoring."""
    global CLIP_MODEL, CLIP_PROCESSOR

    local_path = download_model_from_s3("clip")
    logger.info("[LOAD] Loading CLIP-ViT-Large...")
    load_start = time.time()

    from transformers import CLIPModel, CLIPProcessor

    CLIP_PROCESSOR = CLIPProcessor.from_pretrained(local_path, local_files_only=True)
    CLIP_MODEL = CLIPModel.from_pretrained(
        local_path, torch_dtype=torch.float16, local_files_only=True,
    ).to("cuda").eval()

    _loaded_models.add("clip")
    logger.info(f"[LOAD] CLIP loaded in {time.time()-load_start:.1f}s")


def _load_realesrgan():
    """Load RealESRGAN-x4 upscaler."""
    global REALESRGAN_NET

    local_path = download_model_from_s3("realesrgan")
    model_file = os.path.join(local_path, "RealESRGAN_x4plus.pth")

    if not os.path.exists(model_file):
        logger.error(f"[LOAD] RealESRGAN model not found at {model_file}")
        return

    logger.info("[LOAD] Loading RealESRGAN-x4...")
    load_start = time.time()

    net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                  num_block=23, num_grow_ch=32, scale=4)

    state_dict = torch.load(model_file, map_location="cpu")
    if "params_ema" in state_dict:
        state_dict = state_dict["params_ema"]
    elif "params" in state_dict:
        state_dict = state_dict["params"]

    net.load_state_dict(state_dict, strict=True)
    net = net.half().to("cuda").eval()

    REALESRGAN_NET = net
    _loaded_models.add("realesrgan")
    logger.info(f"[LOAD] RealESRGAN loaded in {time.time()-load_start:.1f}s")


def _load_nudenet():
    """Load NudeNet NSFW classifier (only when NUDENET_ENABLED=true)."""
    global NUDENET_PIPELINE

    if not NUDENET_ENABLED:
        logger.info("[LOAD] NudeNet DISABLED (NUDENET_ENABLED=false) — skipping load")
        return

    local_path = download_model_from_s3("nudenet")
    logger.info("[LOAD] Loading NudeNet...")
    load_start = time.time()

    try:
        from transformers import pipeline as hf_pipeline
        NUDENET_PIPELINE = hf_pipeline(
            "image-classification",
            model=local_path,
            device=0,
            torch_dtype=torch.float16,
        )
        _loaded_models.add("nudenet")
        logger.info(f"[LOAD] NudeNet loaded in {time.time()-load_start:.1f}s")
    except Exception as e:
        logger.warning(f"[LOAD] NudeNet failed: {e}")


def _load_aesthetic_predictor():
    """Load LAION Aesthetic Predictor v2.5 weights from S3.

    Runs on CPU only (~4MB). Must be called after _load_clip() since it
    uses CLIP ViT-L/14 image features at inference time.
    Gracefully skips if S3 download fails — scoring falls back to CLIP+realism.
    """
    global AESTHETIC_PREDICTOR
    import boto3

    local_path = os.path.join(MODELS_CACHE, "aesthetic_predictor.pth")

    if not os.path.exists(local_path):
        logger.info("[LOAD] Downloading aesthetic predictor from S3...")
        s3 = boto3.client("s3")
        try:
            s3.download_file(
                S3_BUCKET,
                "models/ranking/aesthetic_predictor.pth",
                local_path,
            )
        except Exception as e:
            logger.warning(
                f"[LOAD] Aesthetic predictor S3 download failed: {e} "
                f"— jury will use CLIP+realism only (upload with upload-aesthetic-model.ps1)"
            )
            return

    logger.info("[LOAD] Loading Aesthetic Predictor (LAION v2.5)...")
    try:
        model = AestheticMLP()
        weights = torch.load(local_path, map_location="cpu")
        # Handle PyTorch Lightning checkpoint wrapper if present
        if "state_dict" in weights:
            weights = weights["state_dict"]
        model.load_state_dict(weights)
        model.eval()
        AESTHETIC_PREDICTOR = model
        _loaded_models.add("aesthetic-predictor")
        param_count = sum(p.numel() for p in model.parameters())
        logger.info(f"[LOAD] Aesthetic Predictor ready — {param_count:,} params (CPU)")
    except Exception as e:
        logger.warning(f"[LOAD] Aesthetic predictor load failed: {e}")


def _load_yolo_detectors():
    """Load YOLOv8n face + hand detectors from S3 for structural jury filtering.

    Runs on CPU only (~12MB total). Pre-filters PREMIUM candidates with gross
    anatomical defects (melted faces, spaghetti hands) before jury scoring.
    Gracefully skips if download fails — jury runs without structural gate.
    """
    global YOLO_FACE_MODEL, YOLO_HAND_MODEL
    import boto3

    s3 = boto3.client("s3")
    ranking_dir = os.path.join(MODELS_CACHE, "ranking")
    os.makedirs(ranking_dir, exist_ok=True)

    models = {
        "face": ("models/ranking/face_yolov8n.pt", os.path.join(ranking_dir, "face_yolov8n.pt")),
        "hand": ("models/ranking/hand_yolov8n.pt", os.path.join(ranking_dir, "hand_yolov8n.pt")),
    }

    for name, (s3_key, local_path) in models.items():
        if not os.path.exists(local_path):
            logger.info(f"[LOAD] Downloading {name}_yolov8n.pt from S3...")
            try:
                s3.download_file(S3_BUCKET, s3_key, local_path)
            except Exception as e:
                logger.warning(f"[LOAD] YOLO {name} S3 download failed: {e} — structural filter disabled")
                return

    try:
        from ultralytics import YOLO
        YOLO_FACE_MODEL = YOLO(models["face"][1])
        YOLO_HAND_MODEL = YOLO(models["hand"][1])
        _loaded_models.add("yolo-face")
        _loaded_models.add("yolo-hand")
        logger.info("[LOAD] YOLOv8n face + hand detectors ready (CPU, ~12MB)")
    except Exception as e:
        logger.warning(f"[LOAD] YOLOv8n load failed: {e} — structural filter disabled")


def _load_mediapipe_hands():
    """Load MediaPipe Hands for anatomical hand validation.

    21-landmark skeletal model — validates that YOLO-detected hand regions contain
    structurally plausible hands (correct finger topology, natural joint positions).
    CPU-only, ~5MB, ~20ms per hand crop. Gracefully skips if mediapipe not installed.
    """
    global MEDIAPIPE_HANDS
    try:
        import mediapipe as mp
        MEDIAPIPE_HANDS = mp.solutions.hands.Hands(
            static_image_mode=True,
            max_num_hands=1,
            min_detection_confidence=0.3,  # low threshold — we score confidence, not gate on it
        )
        _loaded_models.add("mediapipe-hands")
        logger.info("[LOAD] MediaPipe Hands landmark validator ready (CPU, ~5MB)")
    except ImportError:
        logger.warning("[LOAD] mediapipe not installed — hand landmark validation disabled")
    except Exception as e:
        logger.warning(f"[LOAD] MediaPipe Hands load failed: {e} — hand landmark validation disabled")


# ============================================================
# Cross-model refiner: MOVED TO GPU2 (photogenius-orchestrator).
# RealVisXL + ControlNet + depth estimation now run on GPU2.
# Stub kept to avoid NameErrors from any stale call-sites.
# ============================================================
def _load_realvisxl() -> bool:
    """Load RealVisXL V5.0 pipeline for cross-model refinement.

    Stub: RealVisXL moved to GPU2 (photogenius-orchestrator).
    Returns False immediately — call-sites in PREMIUM path already removed (v25).
    """
    logger.info("[LOAD] RealVisXL skipped — runs on GPU2 post-processor")
    return False


# ============================================================
# Generation model loading (hot-swap)
# ============================================================
def load_generator(model_name: str):
    global CURRENT_MODEL, PIPE, LAST_ACTIVITY_TIME

    if CURRENT_MODEL == model_name and PIPE is not None:
        LAST_ACTIVITY_TIME = time.time()
        return PIPE

    if CURRENT_MODEL and CURRENT_MODEL != model_name:
        logger.info(f"[HOT-SWAP] {CURRENT_MODEL} -> {model_name}")
        unload_generator()

    local_path = download_model_from_s3(model_name)
    logger.info(f"Loading {model_name} from {local_path}...")
    load_start = time.time()

    if model_name == "pixart-sigma":
        # Load components manually to avoid diffusers subfolder resolution bug
        from diffusers import PixArtSigmaPipeline, Transformer2DModel, AutoencoderKL
        from diffusers import DPMSolverMultistepScheduler
        from transformers import T5EncoderModel, T5Tokenizer

        logger.info(f"  Loading tokenizer...")
        tokenizer = T5Tokenizer.from_pretrained(
            os.path.join(local_path, "tokenizer"), local_files_only=True,
        )
        logger.info(f"  Loading text_encoder (T5-XXL)...")
        text_encoder = T5EncoderModel.from_pretrained(
            os.path.join(local_path, "text_encoder"),
            torch_dtype=torch.float16, local_files_only=True,
        )
        logger.info(f"  Loading transformer...")
        transformer = Transformer2DModel.from_pretrained(
            os.path.join(local_path, "transformer"),
            torch_dtype=torch.float16, local_files_only=True,
        )
        logger.info(f"  Loading VAE...")
        vae = AutoencoderKL.from_pretrained(
            os.path.join(local_path, "vae"),
            torch_dtype=torch.float16, local_files_only=True,
        )
        logger.info(f"  Loading scheduler...")
        scheduler = DPMSolverMultistepScheduler.from_pretrained(
            os.path.join(local_path, "scheduler"), local_files_only=True,
        )
        logger.info(f"  Assembling pipeline...")
        pipe = PixArtSigmaPipeline(
            tokenizer=tokenizer,
            text_encoder=text_encoder,
            transformer=transformer,
            vae=vae,
            scheduler=scheduler,
        )
        # Move post-processing to CPU + flush CUDA cache to make room for PixArt (~13GB fp16).
        # pipe.to("cuda") keeps all components on GPU permanently — no CPU<->GPU transfers
        # during denoising, giving fully predictable VRAM usage and eliminating the
        # PyTorch CUDA allocator "reserved but unused" memory issue from cpu_offload.
        _move_postprocessing_to_cpu()
        clear_gpu_memory()
        pipe.to("cuda")
        pipe.vae.enable_slicing()
        pipe.enable_attention_slicing()  # Slice self-attention to reduce peak activation VRAM

    elif model_name == "flux-schnell":
        from diffusers import FluxPipeline
        pipe = FluxPipeline.from_pretrained(
            local_path, torch_dtype=torch.bfloat16,
            local_files_only=True, use_safetensors=True,
        )
        # Sequential CPU offload: moves each transformer layer CPU→GPU one at a time.
        # Allows FLUX (23GB transformer) to run on 24GB A10G with no OOM.
        # Slower than normal offload (~1.5-2x) but safe and correct.
        pipe.enable_sequential_cpu_offload()
        pipe.vae.enable_slicing()

    else:
        raise ValueError(f"No pipeline loader for model: {model_name}")

    CURRENT_MODEL = model_name
    PIPE = pipe
    LAST_ACTIVITY_TIME = time.time()

    load_time = time.time() - load_start
    logger.info(f"[HOT-SWAP] {model_name} loaded in {load_time:.1f}s")

    if torch.cuda.is_available():
        alloc = torch.cuda.memory_allocated() / 1e9
        logger.info(f"[HOT-SWAP] GPU memory: {alloc:.1f}GB allocated")

    return pipe


# ============================================================
# Post-processing: Score Image (CLIP)
# ============================================================
def _score_image(image_b64: str, prompt: str) -> Dict[str, float]:
    """Score image quality using CLIP prompt-image alignment."""
    from PIL import Image
    import numpy as np

    if CLIP_MODEL is None or CLIP_PROCESSOR is None:
        return {"clip_score": 0, "overall_score": 70, "scorer": "fallback"}

    start = time.time()

    img_bytes = base64.b64decode(image_b64)
    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    # Ensure CLIP is on GPU
    device = next(CLIP_MODEL.parameters()).device

    # Truncate prompt to CLIP's 77-token limit. Without truncation=True,
    # long Photography Director prompts (>77 tokens) cause position embedding
    # size mismatch inside CLIPTextModel (fixed 77-position embeddings).
    inputs = CLIP_PROCESSOR(
        text=[prompt], images=image, return_tensors="pt", padding=True,
        truncation=True, max_length=77,
    )
    inputs = {k: v.to(device) if isinstance(v, torch.Tensor) else v
              for k, v in inputs.items()}

    with torch.no_grad():
        outputs = CLIP_MODEL(**inputs)
        clip_score = outputs.logits_per_image.item()

    normalized_score = max(0, min(100, (clip_score - 15) * 5))

    img_array = np.array(image)
    brightness = np.mean(img_array) / 255.0
    contrast = np.std(img_array) / 128.0
    brightness_score = 100 - abs(brightness - 0.45) * 200
    contrast_score = min(100, contrast * 100)

    overall = (normalized_score * 0.6 + brightness_score * 0.2
               + contrast_score * 0.2)
    overall = max(0, min(100, overall))

    logger.info(f"[SCORE] CLIP={clip_score:.1f}, overall={overall:.0f} "
                f"({time.time()-start:.2f}s)")

    return {
        "clip_score": round(clip_score, 2),
        "clip_normalized": round(normalized_score, 1),
        "brightness_score": round(brightness_score, 1),
        "contrast_score": round(contrast_score, 1),
        "overall_score": round(overall, 1),
        "scorer": "clip",
        "score_time": round(time.time() - start, 2),
    }


def _compute_realism_score(image, clip_score: float, aesthetic_score: float = 5.0,
                           freq_score: float = 0.5) -> float:
    """Four-component jury score: Aesthetic + CLIP alignment + texture heuristics + frequency.

    Formula (v7.3 — realism-dominant, CLIP elevated, aesthetic reduced):
        final = 0.45 * realism_norm + 0.35 * clip_norm + 0.10 * aesthetic_norm + 0.10 * freq_norm

    realism_norm (0.45): Texture heuristics (gradient var + edge density + channel micro-var
        + anti-AI symmetry + anti-AI lighting). Penalizes over-smooth backgrounds and plastic skin.
        Capped at 2.5 then normalized. Dominant signal — real texture is the primary quality axis.

    clip_norm (0.35): CLIP text-image similarity / 35.0. Captures subject alignment.
        Elevated from 0.25 — prompt adherence matters more than aesthetic beauty.

    aesthetic_norm (0.10): LAION v2.5 aesthetic predictor score normalized 0-1.
        Reduced from 0.25 — aesthetic was over-weighting pretty-but-fake images.

    freq_norm (0.10): 1/f power spectrum score from _compute_frequency_score().
        Orthogonal signal: catches AI images with unnatural frequency fingerprint
        that pass other metrics. Neutral default 0.5 when not available.

    Runs on CPU with numpy — no GPU memory needed.
    """
    import numpy as np

    try:
        gray = np.array(image.convert("L"), dtype=np.float32)

        # Texture richness via gradient magnitude variance
        # High variance = photographic texture; low = AI smoothed skin/backgrounds
        gy, gx = np.gradient(gray)
        grad_mag = np.sqrt(gx ** 2 + gy ** 2)  # stored for reuse below
        gradient_var = float(grad_mag.var())

        # Edge density — structural complexity of the scene.
        # Real photos have buildings, furniture, hair, wrinkles, objects — all create
        # strong gradient transitions. AI over-smooth backgrounds have very few edges.
        # Threshold 8.0 in gradient-magnitude space (0-360) captures genuine structure.
        # Normalized by pixel count (np.mean) — immune to RealESRGAN upscale bias.
        # Real photos: edge_fraction ~0.25-0.45; AI smooth backgrounds: ~0.08-0.18.
        edge_fraction = float(np.mean(grad_mag > 8.0))
        if edge_fraction < 0.15:
            edge_density_bonus = -0.4    # over-smooth: AI background melt
        elif edge_fraction < 0.22:
            edge_density_bonus = 0.0    # neutral zone
        elif edge_fraction <= 0.55:
            edge_density_bonus = min((edge_fraction - 0.22) * 2.0, 0.5)  # genuine structure
        else:
            edge_density_bonus = -0.2   # over-noisy: noise, not real structure

        # High-frequency sharpness: mean squared pixel differences
        diff_h = np.diff(gray, axis=1)
        diff_v = np.diff(gray, axis=0)
        sharpness = float(np.mean(diff_h ** 2) + np.mean(diff_v ** 2))

        # Center-weighted texture: human brain judges realism primarily from subject zone.
        # Eyes, hands, hairline are almost always near center — weight inner 60% at 1.3x.
        # Blend 40% full-image + 60% center region so subject detail drives jury ranking.
        h_g, w_g = gray.shape
        cy0, cy1 = int(h_g * 0.2), int(h_g * 0.8)
        cx0, cx1 = int(w_g * 0.2), int(w_g * 0.8)
        c_gray = gray[cy0:cy1, cx0:cx1]
        c_gy, c_gx = np.gradient(c_gray)
        center_grad_var = float(np.sqrt(c_gx**2 + c_gy**2).var())
        blended_grad_var = 0.4 * gradient_var + 0.6 * center_grad_var

        # Normalize: realistic photos gradient_var ~200-2000, sharpness ~50-500
        texture_bonus = np.log1p(blended_grad_var) / 4.0  # 0 to ~2
        sharpness_bonus = np.log1p(sharpness) / 8.0       # 0 to ~1

        # Color channel micro-variance: real surfaces have tiny per-pixel R/G/B
        # disagreements (color fringing, sub-pixel spectra). AI smooth surfaces
        # have nearly uniform channel values per pixel.
        rgb_arr = np.array(image, dtype=np.float32)
        channel_var = float(np.mean(np.std(rgb_arr, axis=2)))  # realistic: 8-18, AI smooth: 2-6
        channel_bonus = np.log1p(channel_var) / 6.0  # 0 to ~1

        # Anti-AI penalty 1: Bilateral symmetry — continuous decay (no hard threshold).
        # Real photos have natural asymmetry — people lean, light falls unevenly, scenes messy.
        # AI renders skew toward symmetric compositions (centered subject, balanced lighting).
        # Continuous decay from 0.88 prevents unstable ranking jumps near threshold.
        h_sym, w_sym = gray.shape
        left_half  = gray[:, :w_sym // 2].flatten()
        right_half = np.fliplr(gray[:, w_sym - w_sym // 2:]).flatten()
        min_len = min(len(left_half), len(right_half))
        sym_corr = float(np.corrcoef(left_half[:min_len], right_half[:min_len])[0, 1])
        if sym_corr > 0.88:
            symmetry_penalty = -(sym_corr - 0.88) * 1.8   # max ~-0.22 at perfect symmetry
        else:
            symmetry_penalty = 0.0

        # Anti-AI penalty 2: Uniform lighting — uses variance-of-variances (local texture spread).
        # Real scenes have some blocks very textured (hair, fabric, clutter) and some smooth (sky).
        # This creates high spread in local block variances.
        # AI images: uniformly smooth everywhere → low variance-of-variances.
        # Soft continuous penalty: starts at var_of_var < 600, max −0.30.
        bh, bw = max(1, h_g // 8), max(1, w_g // 8)
        block_variances = []
        for bi in range(8):
            for bj in range(8):
                block = gray[bi * bh:(bi + 1) * bh, bj * bw:(bj + 1) * bw]
                if block.size > 0:
                    block_variances.append(float(block.var()))
        var_of_var = float(np.std(block_variances)) if block_variances else 0.0
        if var_of_var < 600.0:
            lighting_penalty = -min(0.30, (600.0 - var_of_var) / 1500.0)
        else:
            lighting_penalty = 0.0

        # Cap total heuristic bonus (penalties can push it negative — intentional).
        # Cap at 2.5 prevents extreme noise from winning jury.
        total_bonus = (texture_bonus + sharpness_bonus + channel_bonus
                       + edge_density_bonus + symmetry_penalty + lighting_penalty)
        total_bonus = min(total_bonus, 2.5)

        # 4-component normalized score (v7.3 — realism-dominant, aesthetic reduced).
        # WEIGHT ORDER: realism > clip > aesthetic = frequency.
        #
        # realism_norm (0.45): texture + edge + anti-AI penalties — dominant local signal.
        # clip_norm    (0.35): text-image coherence — elevated for prompt adherence.
        # aesthetic_norm(0.10): proxy beauty score — reduced to prevent pretty-but-fake bias.
        # freq_norm    (0.10): 1/f power spectrum — orthogonal AI-fingerprint signal.
        #
        # v7.3 vs v7.2: realism 0.40→0.45, clip 0.25→0.35, aesthetic 0.25→0.10.
        aesthetic_norm = max(0.0, min(1.0, (aesthetic_score - 1.0) / 9.0))
        clip_norm = clip_score / 35.0
        realism_norm = max(0.0, total_bonus) / 2.5
        freq_norm = freq_score  # already 0-1 from _compute_frequency_score

        realism = (0.45 * realism_norm + 0.35 * clip_norm
                   + 0.10 * aesthetic_norm + 0.10 * freq_norm)

        logger.info(
            f"[REALISM] realism={realism_norm:.2f}(w=0.45) "
            f"clip={clip_score:.2f}(norm={clip_norm:.2f} w=0.35) "
            f"aesthetic={aesthetic_score:.2f}(norm={aesthetic_norm:.2f} w=0.10) "
            f"freq={freq_norm:.2f}(w=0.10) "
            f"(tex={texture_bonus:.2f} shp={sharpness_bonus:.2f} ch={channel_bonus:.2f} "
            f"edge={edge_density_bonus:.2f} sym={symmetry_penalty:.2f} "
            f"lit={lighting_penalty:.2f} var_var={var_of_var:.0f} frac={edge_fraction:.2f}) "
            f"-> final={realism:.3f}"
        )
        return realism

    except Exception as e:
        logger.warning(f"[REALISM] Score failed, falling back to clip_score: {e}")
        return float(clip_score)


def _compute_aesthetic_score(image) -> float:
    """Compute aesthetic score on 1-10 scale.

    Primary path: LAION v2.5 aesthetic predictor (MLP on CLIP ViT-L/14 embeddings).
      Real-photo range: 4.5-7.5. AI-smooth range: 3.5-5.5.

    Fallback (when LAION weights not loaded): proxy scorer from image statistics.
      - Colorfulness (Hasler-Suesstrunk 2003): vivid natural palette vs dull AI mush.
      - Luminance entropy: rich tonal variety vs flat overexposed AI sky / skin.
      - Spatial frequency richness (Laplacian variance): sharpness / micro-texture.
      Proxy is orthogonal to CLIP — adds independent signal to the jury formula.

    Runs entirely on CPU — no GPU memory impact.
    """
    import numpy as np

    # ---------- Primary: LAION aesthetic predictor ----------
    if AESTHETIC_PREDICTOR is not None and CLIP_MODEL is not None and CLIP_PROCESSOR is not None:
        try:
            device = next(CLIP_MODEL.parameters()).device
            inputs = CLIP_PROCESSOR(images=image, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(device)

            with torch.no_grad():
                image_features = CLIP_MODEL.get_image_features(pixel_values=pixel_values)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                score = AESTHETIC_PREDICTOR(image_features.cpu().float()).item()

            logger.debug(f"[AESTHETIC] LAION score={score:.3f}")
            return float(score)
        except Exception as e:
            logger.warning(f"[AESTHETIC] LAION predictor failed: {e} — using proxy scorer")

    # ---------- Fallback: proxy aesthetic scorer ----------
    try:
        arr = np.array(image.convert("RGB"), dtype=np.float32)

        # 1. Colorfulness — Hasler & Suesstrunk (2003)
        # Captures vivid, natural palette. Real photos: 30-80. AI mush: 8-25.
        rg = arr[:, :, 0].astype(np.float32) - arr[:, :, 1].astype(np.float32)
        yb = 0.5 * (arr[:, :, 0] + arr[:, :, 1]) - arr[:, :, 2].astype(np.float32)
        colorfulness = (np.sqrt(rg.std() ** 2 + yb.std() ** 2)
                        + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
        # map 5-80 -> 0-1  (below 5 = greyscale, above 80 = oversaturated garish)
        colorfulness_norm = float(np.clip((colorfulness - 5.0) / 75.0, 0.0, 1.0))

        # 2. Luminance entropy
        # Rich tonal variety = good. Flat overexposed AI sky / skin = low entropy.
        gray = np.mean(arr, axis=2)
        hist, _ = np.histogram(gray, bins=64, range=(0, 255), density=True)
        hist = hist[hist > 0]
        entropy = float(-np.sum(hist * np.log2(hist + 1e-10)))
        # map 3-6 -> 0-1  (real photos tend to be 4.5-5.5; solid colors ~0-2)
        luminance_norm = float(np.clip((entropy - 3.0) / 3.0, 0.0, 1.0))

        # 3. Spatial frequency richness (Laplacian variance)
        # Captures micro-texture: fabric weave, hair, brick — real world detail.
        # Real photos: 200-1500. AI over-smooth skin: 30-150.
        gy, gx = np.gradient(gray)
        laplacian_var = float(np.var(gy - gx))
        # log-compress then map to 0-1
        spatial_norm = float(np.clip(np.log1p(laplacian_var) / 14.0, 0.0, 1.0))

        # Combined proxy: mapped to 1-10 scale to match LAION output range
        proxy = 0.50 * colorfulness_norm + 0.30 * luminance_norm + 0.20 * spatial_norm
        score = 1.0 + proxy * 9.0
        logger.debug(
            f"[AESTHETIC] proxy score={score:.2f} "
            f"(color={colorfulness_norm:.2f} lum={luminance_norm:.2f} spat={spatial_norm:.2f})"
        )
        return float(score)

    except Exception as e:
        logger.warning(f"[AESTHETIC] Proxy scorer failed: {e}")
        return 5.0


# ============================================================
# Post-processing: Safety Check (NudeNet)
# ============================================================
def _check_safety_image(image_b64: str) -> Dict[str, Any]:
    """Check image for NSFW content using NudeNet."""
    from PIL import Image

    if NUDENET_PIPELINE is None:
        return {"is_safe": True, "nsfw_score": 0.0, "checker": "bypass"}

    start = time.time()
    img_bytes = base64.b64decode(image_b64)
    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    results = NUDENET_PIPELINE(image)

    nsfw_score = 0.0
    for item in results:
        label = item.get("label", "").lower()
        if label in ("nsfw", "unsafe", "porn", "sexy", "hentai"):
            nsfw_score = max(nsfw_score, item.get("score", 0))

    is_safe = nsfw_score < 0.5

    logger.info(f"[SAFETY] nsfw={nsfw_score:.3f}, safe={is_safe} "
                f"({time.time()-start:.2f}s)")

    return {
        "is_safe": is_safe,
        "nsfw_score": round(nsfw_score, 3),
        "checker": "nudenet",
        "safety_time": round(time.time() - start, 2),
    }


def _check_safety_text(text: str) -> Dict[str, Any]:
    """Basic text safety check using keyword filtering."""
    unsafe_keywords = [
        "nude", "naked", "porn", "explicit", "nsfw", "xxx",
        "violence", "gore", "blood", "murder", "kill",
        "child abuse", "terrorism", "bomb",
    ]
    text_lower = text.lower()
    found = [kw for kw in unsafe_keywords if kw in text_lower]
    return {
        "is_safe": len(found) == 0,
        "flagged_keywords": found,
        "checker": "keyword",
    }


# ============================================================
# Post-processing: Upscale Image (RealESRGAN)
# ============================================================
def _upscale_image(image_b64: str, target_scale: int = 2) -> Dict[str, Any]:
    """Upscale image using RealESRGAN-x4 with tiling."""
    from PIL import Image
    import numpy as np

    if REALESRGAN_NET is None:
        return {"image_base64": image_b64, "upscaled": False, "reason": "not_loaded"}

    start = time.time()
    img_bytes = base64.b64decode(image_b64)
    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    orig_w, orig_h = image.size

    max_input = 512
    if orig_w > max_input or orig_h > max_input:
        ratio = max_input / max(orig_w, orig_h)
        new_w = int(orig_w * ratio) // 4 * 4
        new_h = int(orig_h * ratio) // 4 * 4
        image = image.resize((new_w, new_h), Image.LANCZOS)

    img_np = np.array(image).astype(np.float32) / 255.0
    img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0)

    # Ensure RealESRGAN is on GPU
    device = next(REALESRGAN_NET.parameters()).device
    img_tensor = img_tensor.half().to(device)

    tile_size = 256
    tile_pad = 16
    _, _, h, w = img_tensor.shape

    if h <= tile_size and w <= tile_size:
        with torch.no_grad():
            output_tensor = REALESRGAN_NET(img_tensor)
    else:
        output_tensor = _upscale_tiled(img_tensor, tile_size, tile_pad)

    output_np = output_tensor.squeeze(0).permute(1, 2, 0).clamp(0, 1)
    output_np = (output_np.float().cpu().numpy() * 255).astype(np.uint8)
    output_image = Image.fromarray(output_np)

    if target_scale == 2:
        final_w = orig_w * 2
        final_h = orig_h * 2
        output_image = output_image.resize((final_w, final_h), Image.LANCZOS)

    buf = io.BytesIO()
    output_image.save(buf, format="PNG", optimize=True)
    result_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    del img_tensor, output_tensor
    torch.cuda.empty_cache()

    upscale_time = time.time() - start
    logger.info(f"[UPSCALE] {orig_w}x{orig_h} -> {output_image.size[0]}x{output_image.size[1]} "
                f"in {upscale_time:.1f}s")

    return {
        "image_base64": result_b64,
        "upscaled": True,
        "original_size": f"{orig_w}x{orig_h}",
        "output_size": f"{output_image.size[0]}x{output_image.size[1]}",
        "upscale_time": round(upscale_time, 2),
    }


def _upscale_tiled(img_tensor, tile_size=256, tile_pad=16):
    """Tile-based upscaling to avoid GPU OOM."""
    _, _, h, w = img_tensor.shape
    scale = 4
    out_h, out_w = h * scale, w * scale
    output = torch.zeros(1, 3, out_h, out_w, dtype=img_tensor.dtype,
                         device=img_tensor.device)

    tiles_x = max(1, (w + tile_size - 1) // tile_size)
    tiles_y = max(1, (h + tile_size - 1) // tile_size)

    for iy in range(tiles_y):
        for ix in range(tiles_x):
            in_x0 = max(ix * tile_size - tile_pad, 0)
            in_y0 = max(iy * tile_size - tile_pad, 0)
            in_x1 = min((ix + 1) * tile_size + tile_pad, w)
            in_y1 = min((iy + 1) * tile_size + tile_pad, h)

            tile = img_tensor[:, :, in_y0:in_y1, in_x0:in_x1]

            with torch.no_grad():
                out_tile = REALESRGAN_NET(tile)

            out_x0 = ix * tile_size * scale
            out_y0 = iy * tile_size * scale
            out_x1 = min((ix + 1) * tile_size * scale, out_w)
            out_y1 = min((iy + 1) * tile_size * scale, out_h)

            pad_l = (ix * tile_size - in_x0) * scale
            pad_t = (iy * tile_size - in_y0) * scale
            crop_w = out_x1 - out_x0
            crop_h = out_y1 - out_y0

            output[:, :, out_y0:out_y1, out_x0:out_x1] = \
                out_tile[:, :, pad_t:pad_t + crop_h, pad_l:pad_l + crop_w]

            del tile, out_tile

    return output


# ============================================================
# Camera Defect Pass (PIL + numpy, CPU only, before upscale)
# ============================================================
def _camera_defect_pass(image):
    """Add subtle photographic imperfections to prevent CGI/AI look.

    Applied AFTER RealESRGAN upscaling — upscaler trained on clean images;
    feeding grainy input risks denoising artifacts away. Applying post-upscale
    ensures all effects are preserved at final output resolution.

    Reality Simulation Layer (v6.5):
    1. Luminance-dependent sensor noise — (1-luma)^1.3 sigma, G channel quieter.
       Shadows noisy, highlights clean. Matches real sensor physics (SNR).
    2. Chromatic aberration — 1px R/B channel offset (lens dispersion).
    3. Highlight bloom — 3% lens glow on bright areas.
    4. Exposure rolloff — soft highlight compression (film-style, not hard digital clip).
    5. Exposure gradient — subtle diagonal luminance variation (lens vignetting/sensor response).
    5b.Exposure tone curve — shadow gamma 1.03 + 1.02x lift (removes CGI "perfect histogram").
    6. Radial clarity decay — 4.5% edge blur (lens field curvature). Center sharp, edges softer.
    """
    import numpy as np
    from PIL import Image as _PILDefect, ImageFilter

    try:
        arr = np.array(image, dtype=np.float32)

        # 1. Luminance-dependent sensor noise (replaces flat grain).
        # Real sensors: noise ∝ sqrt(signal). Dark = less signal = more visible noise.
        # Power 1.3 exponent: more aggressive in deep shadows than simple linear falloff.
        # Channel asymmetry: blue noisier, green cleaner (sensor well-depth physics).
        luma_noise = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1]
                      + 0.114 * arr[:, :, 2]) / 255.0
        sigma_map = 3.5 * (1.0 - luma_noise) ** 1.3 + 0.4   # shadow=3.9 → highlight=0.4
        grain_r = np.random.randn(arr.shape[0], arr.shape[1]).astype(np.float32) * sigma_map * 1.00
        grain_g = np.random.randn(arr.shape[0], arr.shape[1]).astype(np.float32) * sigma_map * 0.85
        grain_b = np.random.randn(arr.shape[0], arr.shape[1]).astype(np.float32) * sigma_map * 1.15
        arr += np.stack([grain_r, grain_g, grain_b], axis=2)

        # 2. Chromatic aberration — 1px R/B channel offset (lens dispersion)
        arr_ca = arr.copy()
        arr_ca[:, 1:, 0] = arr[:, :-1, 0]   # Red: shift right 1px
        arr_ca[:, :-1, 2] = arr[:, 1:, 2]   # Blue: shift left 1px
        arr = arr_ca

        # 3. Highlight bloom — 3% gaussian softness on bright areas (lens glow)
        arr_uint8 = np.clip(arr, 0, 255).astype(np.uint8)
        img_tmp = _PILDefect.fromarray(arr_uint8)
        bloom_arr = np.array(
            img_tmp.filter(ImageFilter.GaussianBlur(radius=2)), dtype=np.float32
        )
        luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        bloom_mask = np.clip((luma - 200.0) / 55.0, 0.0, 1.0)[:, :, np.newaxis]
        arr = arr * (1.0 - bloom_mask * 0.03) + bloom_arr * (bloom_mask * 0.03)

        # 4. Exposure rolloff — soft highlight compression (film-style, not hard digital clip)
        high_mask = np.clip((arr - 240.0) / 15.0, 0.0, 1.0)
        arr = arr - high_mask * arr * 0.03

        # 5. Exposure gradient — subtle diagonal luminance variation
        h5, w5 = arr.shape[:2]
        y5 = np.linspace(0.0, 1.0, h5, dtype=np.float32)
        x5 = np.linspace(0.0, 1.0, w5, dtype=np.float32)
        yy5, xx5 = np.meshgrid(y5, x5, indexing='ij')
        exp_gradient = 1.0 + (0.5 - xx5) * 0.010 + (0.5 - yy5) * 0.008
        arr = arr * exp_gradient[:, :, np.newaxis]

        # 5b. Exposure tone curve — shadow compression + slight midtone lift.
        # Perfect histogram = CGI signal. Real cameras compress shadows slightly and
        # lift midtones. gamma=1.03 gives 1-2% shadow compression; 1.02x lift removes
        # the "clinical white" AI look. Applied in normalized [0,1] space.
        arr_n = np.clip(arr / 255.0, 0.0, 1.0)
        arr_n = arr_n ** 1.03           # shadow gamma compression
        arr_n = np.clip(arr_n * 1.02, 0.0, 1.0)   # slight midtone/highlight lift
        arr = arr_n * 255.0

        # 6. Radial clarity decay — 3-5% edge softness (simulates lens field curvature).
        # Real optics: center is sharpest; corners/edges progressively softer.
        # AI images have uniform sharpness everywhere — instantly detectable.
        # Edge weight: 0 at center, up to 0.045 at corners (r^2 falloff, barely perceptible).
        h6, w6 = arr.shape[:2]
        cy, cx = h6 / 2.0, w6 / 2.0
        y6 = np.arange(h6, dtype=np.float32) - cy
        x6 = np.arange(w6, dtype=np.float32) - cx
        dist = np.sqrt(y6[:, np.newaxis] ** 2 + x6[np.newaxis, :] ** 2)
        max_dist = float(np.sqrt(cy ** 2 + cx ** 2))
        edge_weight = np.clip((dist / max_dist) ** 2 * 0.045, 0.0, 0.045)[:, :, np.newaxis]
        arr_uint8_rd = np.clip(arr, 0, 255).astype(np.uint8)
        img_rd = _PILDefect.fromarray(arr_uint8_rd)
        blur_arr = np.array(img_rd.filter(ImageFilter.GaussianBlur(radius=1.5)), dtype=np.float32)
        arr = arr * (1.0 - edge_weight) + blur_arr * edge_weight

        result = _PILDefect.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        logger.info("[DEFECT] Reality simulation pass applied "
                    "(lum-noise + CA + bloom + rolloff + exp_grad + tone_curve + radial_decay)")
        return result

    except Exception as e:
        logger.warning(f"[DEFECT] Camera defect pass failed (non-critical): {e}")
        return image  # return original on any failure


# ============================================================
# Framing Imperfection (subtle crop shift, PREMIUM only, before defect pass)
# ============================================================
def _apply_framing_shift(image, seed: int = 42):
    """Subtle 1-2% directional crop to simulate imperfect photographer framing.

    Real photographers do not always perfectly center their subject — slight
    off-axis captures happen constantly. This removes the "AI-perfect composition"
    tell where the subject is always pixel-perfect center.

    Applied BEFORE camera defect pass so grain distributes evenly across the
    already-cropped image (no grain "boundary" at the crop edge).

    Implementation: crop one side by 1-2%, resize back to original dimensions.
    No rotation — rotation creates black corners and resample softness.
    30% probability per PREMIUM image; deterministic given seed (reproducible).
    """
    from PIL import Image as _PILShift
    import numpy as np

    try:
        rng = np.random.RandomState(seed % (2 ** 31))
        if rng.random() > 0.30:
            return image  # 70% of shots are well-framed — keep them

        w, h = image.size
        shift_pct = rng.uniform(0.01, 0.02)  # 1-2% offset
        direction = rng.choice(["left", "right", "up", "down"])
        sx = int(w * shift_pct)
        sy = int(h * shift_pct)

        if direction == "left":
            box = (sx, 0, w, h)
        elif direction == "right":
            box = (0, 0, w - sx, h)
        elif direction == "up":
            box = (0, sy, w, h)
        else:  # down
            box = (0, 0, w, h - sy)

        shifted = image.crop(box).resize((w, h), _PILShift.LANCZOS)
        logger.info(
            f"[FRAMING] {direction} shift {shift_pct*100:.1f}% "
            f"({sx if direction in ('left','right') else sy}px)"
        )
        return shifted

    except Exception as e:
        logger.warning(f"[FRAMING] Shift failed (non-critical): {e}")
        return image


# ============================================================
# Depth Estimation: MOVED TO GPU2.  Stubs below.
# ============================================================
def _load_depth_estimator() -> bool:
    """Stub — depth estimation moved to GPU2 post-processor."""
    return False


def _extract_depth_map(image):
    """Stub — depth extraction moved to GPU2 post-processor."""
    return None


# ============================================================
# Cross-model Refine: RealVisXL SDXL img2img (PREMIUM only)
# ============================================================
def _realvisxl_refine(image, prompt: str, seed: int, negative: str = "",
                      strength: float = 0.35) -> Optional[object]:
    """Stub — RealVisXL refinement moved to GPU2 post-processor (v25).
    GPU1 returns raw jury-winner for PREMIUM; GPU2 handles refine + upscale.
    """
    return None


# ============================================================
# Micro-Polish Enhancement Stack (PIL-based, CPU only)
# ============================================================
def _micro_polish(image, quality: str = "STANDARD"):
    """Apply professional photo enhancement. CPU-only, ~0.3s."""
    from PIL import Image, ImageFilter, ImageEnhance
    import numpy as np

    start = time.time()

    # 1. Smart Sharpening — reduced to prevent CGI look (AI models are already sharp;
    # over-sharpening creates the telltale artificial edge-crunch of AI images).
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=20, threshold=3))

    # 2. Contrast Enhancement — very subtle 4% (was 7%; less = more film-like)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.04)

    # 3. Color Vibrancy — minimal 2% saturation (was 4%; camera footage is muted)
    enhancer = ImageEnhance.Color(image)
    image = enhancer.enhance(1.02)

    # 4. Cinematic Color Grading - warm shadows, cool highlights
    img_array = np.array(image, dtype=np.float32)

    # Warm the shadows (add slight orange to dark areas)
    shadow_mask = (img_array.mean(axis=2, keepdims=True) < 80).astype(np.float32)
    img_array[:, :, 0] += shadow_mask[:, :, 0] * 3   # slight red
    img_array[:, :, 1] += shadow_mask[:, :, 0] * 1.5  # slight green (warm)

    # Cool the highlights slightly (add slight blue to bright areas)
    highlight_mask = (img_array.mean(axis=2, keepdims=True) > 200).astype(np.float32)
    img_array[:, :, 2] += highlight_mask[:, :, 0] * 2  # slight blue

    img_array = np.clip(img_array, 0, 255).astype(np.uint8)
    image = Image.fromarray(img_array)

    # 5. PREMIUM: Add subtle vignette for focus
    if quality == "PREMIUM":
        w, h = image.size
        vignette = Image.new("L", (w, h), 255)
        vignette_array = np.array(vignette, dtype=np.float32)

        # Create radial gradient
        y_coords, x_coords = np.mgrid[0:h, 0:w]
        center_x, center_y = w / 2, h / 2
        dist = np.sqrt((x_coords - center_x) ** 2 + (y_coords - center_y) ** 2)
        max_dist = np.sqrt(center_x ** 2 + center_y ** 2)
        vignette_array = 1.0 - (dist / max_dist) * 0.15  # 15% darken at corners
        vignette_array = np.clip(vignette_array, 0, 1)

        img_array = np.array(image, dtype=np.float32)
        for c in range(3):
            img_array[:, :, c] *= vignette_array
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        image = Image.fromarray(img_array)

    polish_time = time.time() - start
    logger.info(f"[MICRO-POLISH] Applied in {polish_time:.2f}s (quality={quality})")
    return image


# ============================================================
# Candidate deduplication (CLIP image-to-image cosine similarity)
# ============================================================
def _get_clip_image_embedding(image):
    """Return L2-normalized CLIP image embedding as numpy array, or None on failure.

    Used for candidate deduplication: near-identical outputs share similar latent
    trajectories and waste jury slots. Removing cosine-sim > 0.96 pairs before
    scoring ensures the jury picks from genuinely diverse candidates.

    CLIP_MODEL must already be on GPU (called after _move_postprocessing_to_gpu).
    """
    import numpy as np
    try:
        if CLIP_MODEL is None or CLIP_PROCESSOR is None:
            return None
        device = next(CLIP_MODEL.parameters()).device
        inputs = CLIP_PROCESSOR(images=image, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            emb = CLIP_MODEL.get_image_features(**inputs)
        emb = emb / emb.norm(dim=-1, keepdim=True)
        return emb.squeeze(0).cpu().float().numpy()
    except Exception as e:
        logger.warning(f"[DEDUP] CLIP embedding failed: {e}")
        return None


def _deduplicate_candidates(candidates: list, threshold: float = 0.96) -> list:
    """Remove near-identical candidates using pairwise CLIP cosine similarity.

    Keeps the first occurrence when duplicates are found (earlier seeds are more
    representative of the model's natural distribution for the given prompt).
    Returns the filtered list; original list is untouched.
    """
    import numpy as np
    if len(candidates) <= 1:
        return candidates

    embeddings = [_get_clip_image_embedding(c["image"]) for c in candidates]
    keep = [True] * len(candidates)

    for i in range(len(candidates)):
        if not keep[i] or embeddings[i] is None:
            continue
        for j in range(i + 1, len(candidates)):
            if not keep[j] or embeddings[j] is None:
                continue
            sim = float(np.dot(embeddings[i], embeddings[j]))
            if sim > threshold:
                keep[j] = False
                logger.info(f"[DEDUP] Candidate {j} removed (cosine={sim:.3f} with candidate {i})")

    kept = [c for i, c in enumerate(candidates) if keep[i]]
    removed = len(candidates) - len(kept)
    if removed > 0:
        logger.info(f"[DEDUP] {removed}/{len(candidates)} near-duplicates removed, {len(kept)} unique candidates remain")
    return kept


# ============================================================
# Prompt person-count extraction (for face count verification)
# ============================================================
_NUMBER_WORDS = {
    'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
    'eight': 8, 'nine': 9, 'ten': 10, 'couple': 2, 'pair': 2, 'trio': 3,
}
_GROUP_WORDS = {'group', 'friends', 'people', 'family', 'team', 'crowd', 'soldiers', 'women', 'men', 'boys', 'girls', 'kids', 'children'}

def _extract_expected_faces(prompt: str) -> int:
    """Extract expected person count from prompt for face count verification.

    Parses patterns like:
      "five friends" → 5
      "group of 3 people" → 3
      "a couple walking" → 2
      "two women and a man" → 3
      "portrait of a woman" → 0 (no specific count, skip verification)

    Returns 0 if no specific count can be determined (verification skipped).
    """
    import re
    prompt_lower = prompt.lower()
    words = prompt_lower.split()

    # Pattern 1: digit + group word ("5 friends", "3 people")
    for match in re.finditer(r'(\d+)\s+(?:' + '|'.join(_GROUP_WORDS) + r')', prompt_lower):
        return int(match.group(1))

    # Pattern 2: number word + group word ("five friends", "three people")
    for i, w in enumerate(words):
        if w in _NUMBER_WORDS and i + 1 < len(words) and words[i + 1] in _GROUP_WORDS:
            return _NUMBER_WORDS[w]

    # Pattern 3: "group of N" / "group of five"
    for match in re.finditer(r'group\s+of\s+(\d+)', prompt_lower):
        return int(match.group(1))
    for match in re.finditer(r'group\s+of\s+(\w+)', prompt_lower):
        word = match.group(1)
        if word in _NUMBER_WORDS:
            return _NUMBER_WORDS[word]

    # Pattern 4: standalone number words that imply people ("couple", "trio")
    for w in words:
        if w in ('couple', 'trio'):
            return _NUMBER_WORDS[w]

    return 0  # no specific count — skip verification


# ============================================================
# YOLOv8n structural jury filter
# ============================================================
def _mediapipe_hand_score(img_pil, hand_box) -> float:
    """Validate hand anatomy using MediaPipe 21-landmark skeletal model.

    Returns a penalty score:
      0.00 = structurally sound hand (MediaPipe found all landmarks confidently)
     -0.10 = suspicious (landmarks found but low confidence)
     -0.20 = deformed (MediaPipe can't find valid hand skeleton at all)

    CPU-only, ~20ms per hand crop.
    """
    if MEDIAPIPE_HANDS is None:
        return 0.0  # no penalty if MediaPipe unavailable

    import numpy as np

    try:
        x1, y1, x2, y2 = hand_box
        # Pad crop by 15% for context (MediaPipe needs some surrounding area)
        hw, hh = x2 - x1, y2 - y1
        pad_x, pad_y = int(hw * 0.15), int(hh * 0.15)
        img_w, img_h = img_pil.size
        cx1 = max(0, int(x1) - pad_x)
        cy1 = max(0, int(y1) - pad_y)
        cx2 = min(img_w, int(x2) + pad_x)
        cy2 = min(img_h, int(y2) + pad_y)

        hand_crop = img_pil.crop((cx1, cy1, cx2, cy2))
        # MediaPipe expects RGB numpy array
        hand_rgb = np.array(hand_crop)
        if hand_rgb.ndim != 3 or hand_rgb.shape[2] != 3:
            return 0.0

        result = MEDIAPIPE_HANDS.process(hand_rgb)

        if not result.multi_hand_landmarks:
            # MediaPipe can't find ANY hand skeleton → likely deformed
            return -0.20

        landmarks = result.multi_hand_landmarks[0]
        # Check landmark quality: average visibility/presence scores
        # MediaPipe landmarks have x, y, z — no per-landmark confidence in static mode,
        # but we can check structural plausibility via finger spacing.
        lm = landmarks.landmark

        # Finger tip indices: thumb=4, index=8, middle=12, ring=16, pinky=20
        tips = [lm[4], lm[8], lm[12], lm[16], lm[20]]
        # Finger MCP (base) indices: thumb=2, index=5, middle=9, ring=13, pinky=17
        bases = [lm[2], lm[5], lm[9], lm[13], lm[17]]

        # Check 1: finger tips should be spread apart (not fused)
        tip_positions = np.array([[t.x, t.y] for t in tips])
        pairwise_dists = []
        for a in range(len(tip_positions)):
            for b in range(a + 1, len(tip_positions)):
                pairwise_dists.append(np.linalg.norm(tip_positions[a] - tip_positions[b]))
        min_tip_dist = min(pairwise_dists) if pairwise_dists else 0

        # Check 2: fingers should have nonzero length (tip != base)
        finger_lengths = []
        for tip, base in zip(tips, bases):
            length = np.sqrt((tip.x - base.x)**2 + (tip.y - base.y)**2)
            finger_lengths.append(length)
        min_finger_len = min(finger_lengths) if finger_lengths else 0

        # Thresholds (normalized 0-1 coordinates within crop)
        if min_tip_dist < 0.02 or min_finger_len < 0.03:
            # Fingers fused together or collapsed to same point
            return -0.15

        return 0.0  # hand looks structurally plausible

    except Exception as e:
        logger.debug(f"[MEDIAPIPE] Hand validation error: {e}")
        return 0.0  # fail-open: don't penalize on errors


def _structural_filter_candidates(candidates: list, prompt: str) -> list:
    """Pre-filter candidates with gross anatomical defects using YOLOv8n + MediaPipe.

    Two-stage hand validation:
      Stage 1 (YOLO): Geometric checks — aspect ratio, size, count.
      Stage 2 (MediaPipe): Skeletal check — can a 21-landmark hand model exist here?

    Rejects images with:
      1. Face aspect ratio > 1.8 or < 0.45 (stretched/squished)
      2. Large low-confidence face (conf < 0.35 AND area > 8% of image)
      3. Too many hands relative to faces (hand_count > 2*face_count + 1)
      4. Hand aspect ratio > 3.0 or < 0.3 (spaghetti fingers)
      5. Any single hand > 15% of image area (giant deformed hand)
      6. MediaPipe can't find hand skeleton (deformed anatomy) [NEW v31]
      7. MediaPipe finds fused/collapsed fingers [NEW v31]

    Candidates not rejected outright get a hand_penalty score stored for jury weighting.
    Safety: if ALL candidates rejected, returns original list (let jury decide).
    CPU-only, ~30-70ms per candidate, zero VRAM.
    """
    if YOLO_FACE_MODEL is None or YOLO_HAND_MODEL is None:
        return candidates
    if len(candidates) <= 1:
        return candidates

    import numpy as np

    # Face count verification: extract expected count from prompt (0 = skip check)
    expected_faces = _extract_expected_faces(prompt)
    if expected_faces > 0:
        logger.info(f"[STRUCTURAL] Face count verification: expecting ~{expected_faces} face(s)")

    keep = []
    reasons = []

    for i, cand in enumerate(candidates):
        img = cand["image"]
        img_w, img_h = img.size
        img_area = img_w * img_h
        rejected = False
        reject_reason = ""
        hand_penalty = 0.0  # accumulated MediaPipe penalty for this candidate

        try:
            # Run detections (CPU, conf threshold 0.25 for broad recall)
            face_results = YOLO_FACE_MODEL.predict(img, conf=0.25, device="cpu", verbose=False)
            hand_results = YOLO_HAND_MODEL.predict(img, conf=0.25, device="cpu", verbose=False)

            face_boxes = face_results[0].boxes if len(face_results) > 0 else []
            hand_boxes = hand_results[0].boxes if len(hand_results) > 0 else []

            n_faces = len(face_boxes)
            n_hands = len(hand_boxes)

            # Check face defects
            for fb in face_boxes:
                x1, y1, x2, y2 = fb.xyxy[0].tolist()
                fw, fh = x2 - x1, y2 - y1
                conf = float(fb.conf[0])

                if fh > 0:
                    aspect = fw / fh
                    if aspect > 1.8 or aspect < 0.45:
                        rejected = True
                        reject_reason = f"face aspect={aspect:.2f} (conf={conf:.2f})"
                        break

                face_area = fw * fh
                if conf < 0.35 and (face_area / img_area) > 0.08:
                    rejected = True
                    reject_reason = f"large blurry face conf={conf:.2f} area={face_area/img_area:.1%}"
                    break

            # Check hand defects (only if not already rejected)
            if not rejected:
                # Too many hands relative to faces
                if n_hands > 2 * n_faces + 1:
                    rejected = True
                    reject_reason = f"phantom hands: {n_hands} hands vs {n_faces} faces"

            if not rejected:
                for hb in hand_boxes:
                    x1, y1, x2, y2 = hb.xyxy[0].tolist()
                    hw, hh = x2 - x1, y2 - y1

                    if hh > 0:
                        aspect = hw / hh
                        if aspect > 3.0 or aspect < 0.3:
                            rejected = True
                            reject_reason = f"hand aspect={aspect:.2f}"
                            break

                    hand_area = hw * hh
                    if (hand_area / img_area) > 0.15:
                        rejected = True
                        reject_reason = f"giant hand area={hand_area/img_area:.1%}"
                        break

                    # MediaPipe skeletal validation (only for hands > 2% of image — skip tiny ones)
                    if not rejected and (hand_area / img_area) > 0.02:
                        penalty = _mediapipe_hand_score(img, (x1, y1, x2, y2))
                        hand_penalty += penalty

                        # Hard reject: MediaPipe can't find ANY skeleton in a large hand
                        if penalty <= -0.20 and (hand_area / img_area) > 0.05:
                            rejected = True
                            reject_reason = f"deformed hand (no skeleton found, area={hand_area/img_area:.1%})"
                            break

            # Face count verification (v31): penalize/reject if fewer faces than prompt expects
            face_count_penalty = 0.0
            if not rejected and expected_faces > 0:
                if n_faces < expected_faces:
                    deficit = expected_faces - n_faces
                    if n_faces <= expected_faces // 2:
                        # Less than half expected faces → hard reject
                        rejected = True
                        reject_reason = f"face count {n_faces}/{expected_faces} (less than half expected)"
                    else:
                        # Some faces missing → soft penalty proportional to deficit
                        face_count_penalty = -0.10 * deficit
                        logger.info(f"[STRUCTURAL] Candidate {i}: face count {n_faces}/{expected_faces}, penalty={face_count_penalty:.2f}")

            # Store accumulated penalties for jury weighting
            cand["hand_penalty"] = hand_penalty
            cand["face_count_penalty"] = face_count_penalty

        except Exception as e:
            logger.warning(f"[STRUCTURAL] Detection failed on candidate {i}: {e} — keeping")
            rejected = False
            cand["hand_penalty"] = 0.0
            cand["face_count_penalty"] = 0.0

        if rejected:
            logger.info(f"[STRUCTURAL] Candidate {i} REJECTED: {reject_reason}")
            reasons.append(reject_reason)
        else:
            keep.append(cand)
            mp_info = f", hand_penalty={hand_penalty:.2f}" if hand_penalty != 0 else ""
            fc_info = f", face_penalty={face_count_penalty:.2f}" if face_count_penalty != 0 else ""
            logger.info(f"[STRUCTURAL] Candidate {i} OK (faces={n_faces}, hands={n_hands}{mp_info}{fc_info})")

    # Safety: never reject ALL candidates
    if len(keep) == 0:
        logger.warning(f"[STRUCTURAL] ALL {len(candidates)} candidates rejected — keeping all (safety fallback)")
        return candidates

    removed = len(candidates) - len(keep)
    if removed > 0:
        logger.info(f"[STRUCTURAL] {removed}/{len(candidates)} structurally defective candidates removed, {len(keep)} remain")
    return keep


# ============================================================
# Frequency-domain realism score (1/f power spectrum check)
# ============================================================
def _compute_frequency_score(image) -> float:
    """Score how closely the image power spectrum matches natural photographs.

    Natural images follow a 1/f^beta power law in the frequency domain (beta ~ 1.6-2.2).
    AI-generated images typically deviate: too flat at high frequencies (beta ~ 1.0-1.3,
    over-smoothed textures) or too steep (beta > 2.4, over-blurred).

    This signal is orthogonal to texture/gradient metrics — it catches AI images that
    happen to look sharp and asymmetric but have an unnatural frequency fingerprint.

    Returns: score in [0, 1], peak at beta ~ 1.9, decays outside [1.4, 2.4].
    Cost: ~2ms (pure numpy FFT on grayscale downsampled to 512px).
    """
    import numpy as np

    try:
        from PIL import Image as _PIL
        # Downsample to 512px for speed — FFT cost is O(N log N), 1024px is 4x slower
        img_small = image.convert("L").resize((512, 512), _PIL.LANCZOS)
        gray = np.array(img_small, dtype=np.float64)

        # 2D FFT and shift zero-frequency to center
        fft = np.fft.fft2(gray)
        psd = np.abs(np.fft.fftshift(fft)) ** 2

        # Radial average: collapse 2D PSD to 1D power-vs-frequency
        h, w = psd.shape
        cy, cx = h // 2, w // 2
        y_idx, x_idx = np.ogrid[-cy:h - cy, -cx:w - cx]
        r = np.sqrt(x_idx * x_idx + y_idx * y_idx).astype(int)
        r_max = min(cy, cx) - 1
        radial = np.array([
            psd[r == i].mean() if np.any(r == i) else 0.0
            for i in range(1, r_max)
        ])

        # Fit log-log slope: natural images have beta ~ 1.6-2.2
        freqs = np.log(np.arange(1, len(radial) + 1))
        power = np.log(radial + 1e-10)
        valid = np.isfinite(power) & np.isfinite(freqs) & (radial > 0)
        if valid.sum() < 20:
            return 0.5  # not enough data, return neutral

        beta = -np.polyfit(freqs[valid], power[valid], 1)[0]

        # Gaussian scoring centered at ideal beta=1.9, half-width=0.5
        # Score = 1.0 at beta=1.9, ~0.61 at beta=1.4 or 2.4, ~0.14 at beta=1.0 or 2.8
        score = float(np.exp(-0.5 * ((beta - 1.9) / 0.5) ** 2))

        logger.debug(f"[FREQ] beta={beta:.2f}, score={score:.3f}")
        return max(0.0, min(1.0, score))

    except Exception as e:
        logger.warning(f"[FREQ] Frequency score failed: {e}")
        return 0.5  # neutral fallback


# ============================================================
# Generate Best (Best-of-N + CLIP Jury + Micro-Polish)
# ============================================================
def _handle_generate_best(data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate N candidates, CLIP jury picks best, apply micro-polish."""
    from PIL import Image
    import random

    if not _init_complete.is_set():
        if not _init_complete.wait(timeout=600):
            return {"status": "error", "error": "Models still loading."}

    if _init_error:
        return {"status": "error", "error": f"Init failed: {_init_error}"}

    prompt = data.get("prompt", "")
    tier = (data.get("quality_tier") or "STANDARD").upper()
    negative = data.get("negative_prompt", "")
    width = data.get("width", 1024)
    height = data.get("height", 1024)
    seed = data.get("seed")
    requested_model = data.get("model")
    recommended_model = data.get("recommended_model")

    width = (width // 8) * 8
    height = (height // 8) * 8

    # v31: Categorized complexity scoring — generates more candidates for prompts
    # with higher topology failure risk (hand interaction, multi-person, fine detail,
    # rigid geometry). Each category hit adds +1 candidate (base=3, max=6).
    if tier == "PREMIUM":
        _complexity_categories = {
            'hand_interaction': {
                'holding', 'gripping', 'pouring', 'repairing', 'crafting',
                'cooking', 'lifting', 'carrying', 'touching', 'pinching',
                'writing', 'typing', 'playing', 'sewing', 'knitting',
            },
            'multi_person': {
                'crowd', 'group', 'many', 'multiple', 'several', 'people',
                'friends', 'family', 'team', 'soldiers', 'army', 'couple',
                'wedding', 'party', 'festival', 'gathering',
            },
            'fine_detail': {
                'jewelry', 'mechanical', 'clockwork', 'embroidery', 'lace',
                'filigree', 'engraving', 'tattoo', 'watch', 'necklace',
                'bracelet', 'ring', 'earring', 'brooch', 'tiara',
            },
            'rigid_geometry': {
                'building', 'skyscraper', 'bridge', 'cathedral', 'architecture',
                'tower', 'grid', 'geometric', 'cityscape', 'skyline',
                'interior', 'corridor', 'staircase',
            },
        }
        _prompt_lower = prompt.lower()
        _prompt_words = set(_prompt_lower.split())
        _categories_hit = sum(
            1 for cat_words in _complexity_categories.values()
            if bool(_prompt_words & cat_words)
        )
        # Base 3 candidates + 1 per complexity category (max 6)
        num_candidates = min(6, 3 + _categories_hit)
        logger.info(f"[COMPLEXITY] categories_hit={_categories_hit}, candidates={num_candidates}")
    else:
        num_candidates = 1  # FAST / STANDARD

    # v29: PREMIUM draft at FULL 1024px (was 768px).
    # 768px drafts lacked fine detail — jewelry=12-20px blobs, fabric structure absent.
    # 1024px gives 2x more detail per structural element (earring=30-40px, resolvable).
    # GPU2 v3.0 now uses lower strength (0.20-0.35) = texture injection only,
    # so draft quality matters MORE — must provide strong geometry baseline.
    # Fewer candidates (4→3) compensate for larger per-candidate compute.
    target_w, target_h = width, height
    gen_w, gen_h = width, height
    # No downscale for PREMIUM — generate at full target resolution

    logger.info(f"[BEST-OF-N] Starting: tier={tier}, candidates={num_candidates}, "
                f"draft={gen_w}x{gen_h} target={target_w}x{target_h}, "
                f"recommended_model={recommended_model}, prompt='{prompt[:60]}...'")

    total_start = time.time()

    try:
        with GPU_LOCK:
            model_name, steps, guidance = select_model(
                tier, prompt, requested_model, recommended_model)

            max_pixels = 1024 * 1024
            if width * height > max_pixels:
                ratio = (max_pixels / (width * height)) ** 0.5
                width = int(width * ratio) // 8 * 8
                height = int(height * ratio) // 8 * 8

            # Always move post-processing to CPU during generation.
            # PixArt: T5-XXL encoding peaks at ~11GB VRAM; freeing 1.3GB gives safe headroom.
            # FLUX: required — transformer alone needs ~22GB.
            # Restored unconditionally via _move_postprocessing_to_gpu() after GPU_LOCK.
            is_flux = (model_name == "flux-schnell")
            _move_postprocessing_to_cpu()
            clear_gpu_memory()  # Flush any fragmented CUDA allocator blocks before generation

            try:
                pipe = load_generator(model_name)

                # Generate N candidates
                # Seed stability: same prompt → similar composition (Midjourney consistency).
                # hash(prompt) is deterministic per prompt — gives user predictable style.
                # User-supplied seed overrides this for explicit control.
                base_seed = int(seed) if seed else (hash(prompt) % (2**32))
                candidates = []

                # 6 seed offsets — genuinely different noise trajectories, different compositions.
                _seed_offsets = [0, 37, 89, 123, 456, 789]

                # 6 absolute guidance values — linear spread from 3.6 to 5.6.
                # Lower CFG (3.6-4.0): model deviates from prompt more freely → candid, natural.
                # Higher CFG (5.2-5.6): firmer composition, stronger subject lock.
                # Wide low-end spread: MJ-style → samples low guidance frequently for realism.
                # FLUX uses guidance=0.0 (schnell is distilled, fixed).
                _guidance_values = [3.6, 4.0, 4.4, 4.8, 5.2, 5.6]

                # Mild step variation: different trajectory depth without sacrificing speed.
                # Wraps for all 6 candidates: [0,-2,+2] → steps [12,10,14] (PREMIUM draft).
                _step_variations = [0, -2, +2]

                # Log prompt length for debugging
                logger.info(f"[BEST-OF-N] Prompt length: {len(prompt)} chars, "
                            f"negative length: {len(negative)} chars")

                for i in range(num_candidates):
                    candidate_seed = base_seed + _seed_offsets[i % len(_seed_offsets)]
                    generator = torch.Generator(device="cpu")
                    generator.manual_seed(candidate_seed)

                    # Vary guidance scale and step count for PREMIUM PixArt only
                    candidate_guidance = guidance
                    candidate_steps = steps
                    if tier == "PREMIUM" and model_name == "pixart-sigma" and num_candidates > 1:
                        # Absolute guidance values — no offset arithmetic, predictable distribution.
                        candidate_guidance = _guidance_values[i % len(_guidance_values)]
                        s_off = _step_variations[i % len(_step_variations)]
                        candidate_steps = max(4, steps + s_off)

                    gen_kwargs = {
                        "prompt": prompt,
                        "num_inference_steps": candidate_steps,
                        "guidance_scale": candidate_guidance,
                        "width": gen_w,    # 768px for PREMIUM draft, full res for FAST/STANDARD
                        "height": gen_h,
                        "generator": generator,
                    }

                    if model_name == "pixart-sigma":
                        # Always set max_sequence_length=300 for long Photography Director prompts.
                        gen_kwargs["max_sequence_length"] = 300
                        # PixArt-Sigma T5 encoder uses padding="max_length", max_length=300 for BOTH
                        # positive and negative prompts, so there is NO tensor shape mismatch.
                        # (The old "77 token" issue was in CLIP scoring, not PixArt T5 - now fixed.)
                        # Pass negative_prompt to suppress text artifacts, watermarks, and low quality.
                        pixart_negative = negative if negative else (
                            "text, watermark, signature, blurry, low quality, "
                            "deformed, extra fingers, fused fingers, missing fingers, bad anatomy, "
                            "distorted face, asymmetric eyes, bad teeth, "
                            "overexposed, underexposed, 3d render, cgi"
                        )
                        gen_kwargs["negative_prompt"] = pixart_negative

                    logger.info(f"[BEST-OF-N] Candidate {i+1}: seed={candidate_seed}, "
                                f"steps={candidate_steps}, guidance={candidate_guidance:.1f}, "
                                f"max_seq_len={gen_kwargs.get('max_sequence_length', 'N/A')}")
                    gen_start = time.time()
                    with torch.inference_mode():
                        image = pipe(**gen_kwargs).images[0]
                    gen_time = time.time() - gen_start

                    candidates.append({
                        "image": image,
                        "seed": candidate_seed,
                        "gen_time": round(gen_time, 2),
                    })
                    logger.info(f"[BEST-OF-N] Candidate {i+1}/{num_candidates}: "
                                f"seed={candidate_seed}, time={gen_time:.1f}s")

            finally:
                pass  # post-processing restored unconditionally below after GPU_LOCK

        # === JURY PHASE: Score candidates ===
        # PixArt: pipe.to("cuda") → stays on GPU (~13GB); do NOT unload.
        # Unloading adds ~20s reload overhead for next request.
        # CLIP scoring needs ~0.8GB: 13 + 0.8 = ~14GB, fits on 24GB A10G.
        # FLUX: must unload (22GB) before CLIP scoring — handled below.
        if is_flux:
            # FLUX uses ~22GB - must unload it before CLIP scoring
            logger.info("[BEST-OF-N] FLUX: unloading for jury phase...")
            unload_generator()
            clear_gpu_memory()
        _move_postprocessing_to_gpu()

        all_scores = []
        selected_idx = 0

        if num_candidates > 1 and CLIP_MODEL is not None and CLIP_PROCESSOR is not None:
            logger.info("[BEST-OF-N] Realism Jury v7.3 (Aesthetic + CLIP + texture + frequency)...")

            # Dedup: remove near-identical candidates before scoring.
            # Same prompt + similar seeds occasionally produce collapsed outputs (all candidates
            # converge to same latent basin). Dedup ensures jury picks from diverse options.
            pre_dedup = len(candidates)
            candidates = _deduplicate_candidates(candidates, threshold=0.96)
            if len(candidates) < pre_dedup:
                logger.info(f"[JURY] Dedup: {pre_dedup} -> {len(candidates)} candidates")

            # Structural gate: reject candidates with deformed faces/hands before scoring
            pre_structural = len(candidates)
            candidates = _structural_filter_candidates(candidates, prompt)
            if len(candidates) < pre_structural:
                logger.info(f"[JURY] Structural filter: {pre_structural} -> {len(candidates)} candidates")

            for i, cand in enumerate(candidates):
                img_b64 = image_to_base64(cand["image"])
                score_result = _score_image(img_b64, prompt)
                clip_sc = score_result.get("clip_score", 0)

                # Aesthetic score from LAION v2.5 predictor (uses CLIP image embedding).
                aesthetic_sc = _compute_aesthetic_score(cand["image"])

                # 1/f frequency domain score — orthogonal AI-fingerprint signal.
                freq_sc = _compute_frequency_score(cand["image"])

                # 4-component jury score (v7.3)
                realism_sc = _compute_realism_score(cand["image"], clip_sc, aesthetic_sc, freq_sc)

                cand["score"] = score_result
                # Apply structural penalties to jury score (v31).
                # hand_penalty: 0.0 (good), -0.10 to -0.15 (suspicious), -0.20 (deformed).
                # face_count_penalty: 0.0 (correct count), -0.10 per missing face.
                # Hard-rejected candidates never reach here — these penalize borderline cases.
                hand_pen = cand.get("hand_penalty", 0.0)
                face_pen = cand.get("face_count_penalty", 0.0)
                realism_sc = max(0.0, realism_sc + hand_pen + face_pen)

                cand["realism_score"] = realism_sc
                cand["aesthetic_score"] = aesthetic_sc
                cand["freq_score"] = freq_sc
                all_scores.append({
                    "candidate": i,
                    "seed": cand["seed"],
                    "overall_score": score_result.get("overall_score", 0),
                    "clip_score": round(clip_sc, 2),
                    "aesthetic_score": round(aesthetic_sc, 2),
                    "freq_score": round(freq_sc, 3),
                    "realism_score": round(realism_sc, 2),
                    "hand_penalty": round(hand_pen, 2),
                    "face_count_penalty": round(face_pen, 2),
                })
                penalties = []
                if hand_pen != 0: penalties.append(f"hand={hand_pen:.2f}")
                if face_pen != 0: penalties.append(f"faces={face_pen:.2f}")
                pen_info = f", penalties=[{', '.join(penalties)}]" if penalties else ""
                logger.info(
                    f"[JURY] Candidate {i}: aesthetic={aesthetic_sc:.2f}, "
                    f"clip={clip_sc:.2f}, freq={freq_sc:.3f}{pen_info}, final={realism_sc:.2f}"
                )

            # Pick best by combined 4-component jury score (v7.3)
            selected_idx = max(range(len(all_scores)),
                               key=lambda i: all_scores[i]["realism_score"])
            logger.info(
                f"[JURY] Selected candidate {selected_idx} "
                f"(aesthetic={all_scores[selected_idx]['aesthetic_score']:.2f}, "
                f"clip={all_scores[selected_idx]['clip_score']:.2f}, "
                f"final={all_scores[selected_idx]['realism_score']:.2f})"
            )
        elif num_candidates == 1:
            # Single candidate: score for monitoring — same path as jury but no selection needed.
            img_b64 = image_to_base64(candidates[0]["image"])
            score_result = _score_image(img_b64, prompt)
            clip_sc = score_result.get("clip_score", 0)
            aesthetic_sc = _compute_aesthetic_score(candidates[0]["image"]) if CLIP_MODEL else 5.0
            freq_sc = _compute_frequency_score(candidates[0]["image"])
            realism_sc = _compute_realism_score(candidates[0]["image"], clip_sc, aesthetic_sc, freq_sc)
            candidates[0]["score"] = score_result
            all_scores.append({
                "candidate": 0,
                "seed": candidates[0]["seed"],
                "overall_score": score_result.get("overall_score", 0),
                "clip_score": round(clip_sc, 2),
                "aesthetic_score": round(aesthetic_sc, 2),
                "freq_score": round(freq_sc, 3),
                "realism_score": round(realism_sc, 2),
            })

        best_jury_score = all_scores[selected_idx].get("realism_score", 0.5) if all_scores else 0.5

        # v31: Low-quality regeneration gate.
        # If PREMIUM jury winner is too weak (< 0.45), the draft has such bad geometry
        # that GPU2 can't save it. Better to regenerate once with fresh seeds.
        # Only fires for PREMIUM tier (FAST/STANDARD have 1 candidate — no jury).
        # Max 1 retry to bound latency. Uses completely different base seed.
        if (tier == "PREMIUM" and best_jury_score < 0.45
                and num_candidates > 1 and not cand.get("_regenerated")):
            logger.warning(
                f"[REGEN] Jury winner score {best_jury_score:.3f} < 0.45 — "
                f"regenerating {num_candidates} fresh candidates (retry once)"
            )
            # Generate fresh batch with very different base seed
            regen_base = base_seed + 10000 + random.randint(0, 5000)
            regen_candidates = []
            for ri in range(num_candidates):
                rseed = regen_base + _seed_offsets[ri % len(_seed_offsets)]
                rgen = torch.Generator(device="cpu")
                rgen.manual_seed(rseed)
                rg = _guidance_values[ri % len(_guidance_values)] if model_name == "pixart-sigma" else guidance
                rsteps = steps + _step_variations[ri % len(_step_variations)] if model_name == "pixart-sigma" else steps
                rsteps = max(6, rsteps)

                gen_kwargs = {
                    "prompt": prompt, "width": gen_w, "height": gen_h,
                    "num_inference_steps": rsteps, "guidance_scale": rg,
                    "generator": rgen, "output_type": "pil",
                }
                if model_name == "pixart-sigma":
                    gen_kwargs["max_sequence_length"] = 300
                    pixart_negative = negative if negative else (
                        "text, watermark, signature, blurry, low quality, "
                        "deformed, extra fingers, fused fingers, missing fingers, bad anatomy, "
                        "distorted face, asymmetric eyes, bad teeth, "
                        "overexposed, underexposed, 3d render, cgi"
                    )
                    gen_kwargs["negative_prompt"] = pixart_negative

                rimg = pipe(**gen_kwargs).images[0]
                regen_candidates.append({"image": rimg, "seed": rseed, "_regenerated": True})

            # Score regen candidates through same pipeline
            regen_candidates = _deduplicate_candidates(regen_candidates, threshold=0.96)
            regen_candidates = _structural_filter_candidates(regen_candidates, prompt)

            regen_scores = []
            for ri, rc in enumerate(regen_candidates):
                r_b64 = image_to_base64(rc["image"])
                r_score = _score_image(r_b64, prompt)
                r_clip = r_score.get("clip_score", 0)
                r_aes = _compute_aesthetic_score(rc["image"])
                r_freq = _compute_frequency_score(rc["image"])
                r_real = _compute_realism_score(rc["image"], r_clip, r_aes, r_freq)
                r_hp = rc.get("hand_penalty", 0.0)
                r_fp = rc.get("face_count_penalty", 0.0)
                r_real = max(0.0, r_real + r_hp + r_fp)
                regen_scores.append({"realism_score": round(r_real, 2), "candidate": ri})
                logger.info(f"[REGEN] Candidate {ri}: final={r_real:.2f}")

            # Pick best from regen batch
            if regen_scores:
                regen_best_idx = max(range(len(regen_scores)),
                                     key=lambda x: regen_scores[x]["realism_score"])
                regen_best_score = regen_scores[regen_best_idx]["realism_score"]

                if regen_best_score > best_jury_score:
                    # Regen produced a better candidate — swap
                    logger.info(
                        f"[REGEN] Regen winner ({regen_best_score:.3f}) beats original "
                        f"({best_jury_score:.3f}) — swapping"
                    )
                    # Release old candidates
                    for c in candidates:
                        if "image" in c:
                            del c["image"]
                    candidates = regen_candidates
                    all_scores = regen_scores
                    selected_idx = regen_best_idx
                    best_jury_score = regen_best_score
                else:
                    logger.info(
                        f"[REGEN] Regen best ({regen_best_score:.3f}) didn't beat original "
                        f"({best_jury_score:.3f}) — keeping original"
                    )
                    for rc in regen_candidates:
                        if "image" in rc:
                            del rc["image"]

            gc.collect()

        best_image = candidates[selected_idx]["image"]
        best_seed = candidates[selected_idx]["seed"]
        best_score = candidates[selected_idx].get("score", {})
        best_jury_score = all_scores[selected_idx].get("realism_score", 0.5) if all_scores else 0.5

        # For PREMIUM top-2 refine: keep the runner-up image before releasing all losers.
        second_image = None
        second_seed = None
        second_score_entry = None
        if tier == "PREMIUM" and model_name == "pixart-sigma" and len(candidates) >= 2:
            sorted_by_score = sorted(range(len(all_scores)),
                                     key=lambda i: all_scores[i]["realism_score"], reverse=True)
            runner_up_idx = sorted_by_score[1]
            if runner_up_idx != selected_idx and "image" in candidates[runner_up_idx]:
                second_image = candidates[runner_up_idx]["image"]
                second_seed = candidates[runner_up_idx]["seed"]
                second_score_entry = all_scores[runner_up_idx]
                logger.info(
                    f"[REFINE] Top-2: winner={selected_idx}(score={best_jury_score:.3f}), "
                    f"runner-up={runner_up_idx}(score={all_scores[runner_up_idx]['realism_score']:.3f})"
                )

        # Release all non-selected candidates (except runner-up already captured above).
        for i, cand in enumerate(candidates):
            if i != selected_idx and "image" in cand:
                del cand["image"]
        gc.collect()

        # === SAFETY CHECK (only when NUDENET_ENABLED=true) ===
        safety = {"is_safe": True, "checker": "bypass"}
        if NUDENET_PIPELINE is not None:
            img_b64 = image_to_base64(best_image)
            safety = _check_safety_image(img_b64)
            if not safety.get("is_safe", True):
                return {
                    "status": "error",
                    "error": "Generated image flagged by safety check",
                    "safety": safety,
                }

        # === FRAMING SHIFT (PREMIUM only, 30% chance) ===
        # Applied before returning raw image to GPU2.
        if tier == "PREMIUM":
            best_image = _apply_framing_shift(best_image, seed=best_seed)

        # === PREMIUM: Return raw jury-winner — GPU2 handles refine + upscale ===
        # GPU2 (photogenius-orchestrator) post-processor does:
        #   RealVisXL refine (adaptive strength) + ControlNet + InstantID + upscale
        #   + reality simulation + micro-polish
        # jury_score forwarded so GPU2 can calibrate refine strength.
        if tier == "PREMIUM":
            final_b64 = image_to_lossless_b64(best_image)  # JPEG q=100 4:4:4 near-lossless for GPU2
            del best_image
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                torch.cuda.synchronize()
            total_time = time.time() - total_start
            logger.info(
                f"[BEST-OF-N] PREMIUM complete in {total_time:.1f}s "
                f"(GPU1 raw winner, jury_score={best_jury_score:.3f}) — "
                f"GPU2 will refine + upscale"
            )
            return {
                "status": "success",
                "image": final_b64,
                "jury_score": round(best_jury_score, 4),  # for GPU2 adaptive refine
                "generation_time": round(total_time, 2),
                "model": model_name,
                "steps": steps,
                "guidance_scale": guidance,
                "seed": best_seed,
                "quality_tier": tier,
                "width": gen_w,           # draft resolution (768px)
                "height": gen_h,
                "target_width": target_w,  # user's requested resolution — GPU2 renders here
                "target_height": target_h,
                "candidates_generated": num_candidates,
                "selected_index": selected_idx,
                "all_scores": all_scores,
                "quality_scores": best_score,
                "safety": safety,
                "micro_polished": False,  # GPU2 will polish
            }

        # === FAST/STANDARD: reality sim + micro-polish (no upscale — return at generated res) ===
        # RealESRGAN 2x upscale removed: 1024x1024->2048x2048 was hitting TorchServe 8MB limit
        # for complex photorealistic prompts. Return at generated resolution (1024x1024 max).
        logger.info(f"[BEST-OF-N] Skipping upscale — returning at {best_image.size} (HD)")


        # Reality simulation (AFTER upscale)
        best_image = _camera_defect_pass(best_image)

        # Micro-polish
        logger.info("[BEST-OF-N] Applying micro-polish...")
        polished_image = _micro_polish(best_image, tier)

        # Convert to base64
        final_b64 = image_to_base64(polished_image)

        # GPU memory reset after every generation.
        # Prevents CUDA allocator fragmentation from sequential offload + multi-seed.
        # synchronize() waits for all pending CUDA kernels to finish — prevents the next
        # request from seeing partially-freed allocations (A10G fragmentation issue).
        del polished_image, best_image
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            torch.cuda.synchronize()  # wait for all CUDA ops before accepting next request

        total_time = time.time() - total_start
        logger.info(f"[BEST-OF-N] Complete in {total_time:.1f}s: "
                    f"model={model_name}, candidates={num_candidates}, "
                    f"selected={selected_idx}, score={best_score.get('overall_score', 0):.1f}")

        return {
            "status": "success",
            "image": final_b64,
            "generation_time": round(total_time, 2),
            "model": model_name,
            "steps": steps,
            "guidance_scale": guidance,
            "seed": best_seed,
            "quality_tier": tier,
            "width": width,
            "height": height,
            "candidates_generated": num_candidates,
            "selected_index": selected_idx,
            "all_scores": all_scores,
            "quality_scores": best_score,
            "safety": safety,
            "micro_polished": True,
        }

    except torch.cuda.OutOfMemoryError:
        logger.error(f"[OOM] GPU out of memory on model '{CURRENT_MODEL}'! Auto-fallback to PixArt...")
        with GPU_LOCK:
            unload_generator()
            clear_gpu_memory()
        # Never return an error to user. Retry with PixArt — always succeeds.
        if data.get("recommended_model") != "pixart-sigma" or data.get("model") != "pixart-sigma":
            logger.info("[OOM FALLBACK] Retrying generation with pixart-sigma...")
            fallback_data = {**data, "recommended_model": "pixart-sigma", "model": "pixart-sigma"}
            return _handle_generate_best(fallback_data)
        return {"status": "error", "error": "GPU out of memory even on PixArt."}

    except Exception as e:
        logger.error(f"[BEST-OF-N] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


# ============================================================
# SageMaker interface
# ============================================================
def model_fn(model_dir):
    global MODEL_DIR, _init_error
    MODEL_DIR = model_dir

    logger.info("=" * 60)
    logger.info("PHOTOGENIUS GENERATION GPU v30 — GPU1 slim + YOLOv8n structural filter")
    logger.info("Generation: PixArt-Sigma + FLUX.1-Schnell (hot-swap)")
    logger.info("Refinement: MOVED TO GPU2 (RealVisXL + ControlNet + InstantID)")
    logger.info("Post-Processing: CLIP + AestheticMLP + YOLOv8n + RealESRGAN (FAST/STANDARD)")
    logger.info(f"NudeNet: {'ENABLED' if NUDENET_ENABLED else 'DISABLED (NUDENET_ENABLED=false)'}")
    logger.info(f"S3 Bucket: {S3_BUCKET}")
    logger.info("=" * 60)

    try:
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            logger.info(f"GPU: {gpu_name} ({gpu_mem:.1f} GB)")
    except Exception as e:
        logger.error(f"GPU check error: {e}")

    os.makedirs(MODELS_CACHE, exist_ok=True)

    # Phase 1: Load small post-processing models (~15-30s)
    # AestheticPredictor loaded AFTER CLIP — it uses CLIP embeddings at inference time.
    # NudeNet: only loaded when NUDENET_ENABLED=true (default: false).
    logger.info("[STEP 1] Loading post-processing models...")
    for name, loader in [("CLIP", _load_clip),
                         ("RealESRGAN", _load_realesrgan),
                         ("NudeNet", _load_nudenet),
                         ("AestheticPredictor", _load_aesthetic_predictor),
                         ("YOLOv8n", _load_yolo_detectors),
                         ("MediaPipeHands", _load_mediapipe_hands)]:
        try:
            loader()
        except Exception as e:
            logger.error(f"[STEP 1] {name} failed: {e}")
            import traceback
            traceback.print_exc()

    if torch.cuda.is_available():
        alloc = torch.cuda.memory_allocated() / 1e9
        logger.info(f"[GPU] Post-processing models loaded: {alloc:.1f}GB, "
                    f"models={list(_loaded_models)}")

    # Phase 2: Download + load default generation model
    try:
        logger.info(f"[STEP 2] Downloading {DEFAULT_MODEL} from S3...")
        download_model_from_s3(DEFAULT_MODEL)
    except Exception as e:
        _init_error = f"Failed to download {DEFAULT_MODEL}: {e}"
        logger.error(f"[STEP 2] FAILED: {e}")
        import traceback
        traceback.print_exc()
        _init_complete.set()
        return {"initialized": False, "error": _init_error}

    try:
        logger.info(f"[STEP 3] Loading {DEFAULT_MODEL} into GPU...")
        with GPU_LOCK:
            load_generator(DEFAULT_MODEL)
    except Exception as e:
        logger.error(f"[STEP 3] GPU load failed: {e}")
        import traceback
        traceback.print_exc()

    # Phase 3.5: GPU Warmup — run 4 denoising steps at production resolution.
    # This forces CUDA to compile attention kernels, initialize memory pools,
    # and warm the cuDNN autotune cache before the first real request arrives.
    # Warmup at 1024×1024 (production size) so kernel shapes match real requests.
    # Without this, the first STANDARD/PREMIUM request pays a ~10-15s "cold tax".
    logger.info("[WARMUP] Running GPU warmup at 1024×1024 (4 steps)...")
    warmup_start = time.time()
    try:
        with GPU_LOCK:
            warmup_gen = torch.Generator(device="cpu")
            warmup_gen.manual_seed(42)
            warmup_negative = (
                "blurry, low quality, distorted, watermark, text, bad anatomy"
            )
            _ = PIPE(
                "a professional photograph, cinematic lighting",
                negative_prompt=warmup_negative,
                num_inference_steps=4,
                guidance_scale=4.5,
                width=1024,
                height=1024,
                max_sequence_length=300,
                generator=warmup_gen,
            )
        logger.info(
            f"[WARMUP] CUDA kernels compiled, memory pools ready in "
            f"{time.time()-warmup_start:.1f}s"
        )
        # Release PyTorch CUDA allocator's reserved-but-unused tensors from warmup
        # so the first real request has maximum free VRAM headroom.
        clear_gpu_memory()
        print("MODEL_READY: True", flush=True)
    except Exception as e:
        logger.warning(f"[WARMUP] Warmup failed (non-critical, will warmup on first request): {e}")
        import traceback
        traceback.print_exc()
        clear_gpu_memory()
        print("MODEL_READY: True (warmup skipped)", flush=True)

    _init_complete.set()
    logger.info("=" * 60)
    logger.info("GENERATION GPU READY")
    logger.info(f"Models loaded: {list(_loaded_models)}")
    logger.info("=" * 60)

    # Phase 4: Background download FLUX.1-Schnell (only on 40GB+ GPU).
    # RealVisXL + ControlNet now run on GPU2 — no longer downloaded on GPU1.
    # Saves 6.5GB + 2.3GB = ~8.8GB of background bandwidth per cold start.

    # FLUX download: only start on hardware that can actually run it (40GB+ GPU).
    # On A10G (24GB): can_run_flux() = False, so we skip the 31.5GB download entirely.
    # This saves ~80s of background bandwidth and 120s of warmup on every cold start.
    # When the GPU is upgraded to 40GB+, this block activates automatically.
    if can_run_flux():
        def _bg_flux_download():
            """Download FLUX then run a 2-step warmup to pre-compile CUDA kernels."""
            try:
                logger.info("[BG] FLUX.1-Schnell download starting (31.5GB) — 40GB+ GPU detected...")
                download_model_from_s3("flux-schnell")
                logger.info("[BG] FLUX.1-Schnell download complete. Running FLUX warmup...")
                if not GPU_LOCK.locked():
                    with GPU_LOCK:
                        try:
                            flux_pipe = load_generator("flux-schnell")
                            warmup_gen = torch.Generator(device="cpu")
                            warmup_gen.manual_seed(42)
                            with torch.inference_mode():
                                flux_pipe(
                                    "a photograph, natural light",
                                    num_inference_steps=2,
                                    guidance_scale=0.0,
                                    width=512,
                                    height=512,
                                    generator=warmup_gen,
                                )
                            logger.info("[BG] FLUX warmup complete — CUDA kernels compiled")
                            clear_gpu_memory()
                            load_generator(DEFAULT_MODEL)
                        except Exception as we:
                            logger.warning(f"[BG] FLUX warmup failed (non-critical): {we}")
                            unload_generator()
                            try:
                                load_generator(DEFAULT_MODEL)
                            except Exception:
                                pass
                else:
                    logger.info("[BG] GPU busy during FLUX warmup — skipping")
                logger.info("[BG] FLUX.1-Schnell ready")
            except Exception as e:
                logger.warning(f"[BG] FLUX download failed: {e}")
        threading.Thread(target=_bg_flux_download, daemon=True).start()
    else:
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9 if torch.cuda.is_available() else 0
        logger.info(f"[BG] FLUX skipped — GPU has {vram_gb:.1f}GB VRAM (need 38GB+). Saving 31.5GB download.")

    return {"initialized": True, "backend": "generation-gpu"}


def input_fn(request_body, content_type="application/json"):
    if content_type == "application/json":
        return json.loads(request_body)
    return {}


def predict_fn(data: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    action = data.get("action", "")

    # GPU stress test — pure matrix multiply to saturate GPU for CloudWatch
    if action == "gpu_stress":
        dur = int(data.get("duration", 60))
        logger.info(f"GPU stress test for {dur}s")
        dev = torch.device("cuda")
        a = torch.randn(4096, 4096, device=dev)
        end_t = time.time() + dur
        ops = 0
        while time.time() < end_t:
            torch.matmul(a, a)
            torch.cuda.synchronize()
            ops += 1
        return {"status": "success", "action": "gpu_stress", "duration": dur, "ops": ops}

    # Health check (fast, no lock)
    if action == "health":
        return {
            "status": "healthy",
            "role": "generation_and_postprocessing",
            "current_model": CURRENT_MODEL,
            "cached_models": [m for m in MODEL_S3_PATHS if is_model_cached(m)],
            "loaded_models": list(_loaded_models),
            "gpu_memory_allocated": (
                f"{torch.cuda.memory_allocated() / 1e9:.1f}GB"
                if torch.cuda.is_available() else "N/A"
            ),
        }

    # Text safety check (CPU, no lock)
    if action == "check_text":
        text = data.get("text", "")
        result = _check_safety_text(text)
        return {"status": "success", **result}

    # Process image (score + safety + upscale)
    if action == "process_image":
        return _handle_process_image(data)

    # Best-of-N generation with CLIP jury + micro-polish
    if action == "generate_best":
        return _handle_generate_best(data)

    # Default: Generate image (legacy single-shot)
    return _handle_generate(data)


def _handle_process_image(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle process_image: score + safety (+ optional upscale)."""
    image_b64 = data.get("image_base64", "")
    prompt = data.get("prompt", "")
    quality = data.get("quality_tier", "STANDARD")
    do_upscale = data.get("upscale", False)  # Disabled by default - 1024 HD is enough
    do_score = data.get("score", True)
    do_safety = data.get("safety", True)

    result = {"status": "success"}

    try:
        # Ensure post-processing models are on GPU.
        # PixArt stays loaded on GPU (pipe.to("cuda") ~13GB) — do NOT unload it.
        # CLIP+NudeNet+RealESRGAN (~1.3GB) alongside PixArt = ~14.3GB, fits on 24GB A10G.
        _move_postprocessing_to_gpu()

        with GPU_LOCK:
            if do_score:
                result["scores"] = _score_image(image_b64, prompt)

            if do_safety:
                result["safety"] = _check_safety_image(image_b64)

            if do_upscale and REALESRGAN_NET is not None:
                upscale_result = _upscale_image(image_b64, target_scale=2)
                result["upscale"] = upscale_result
                if upscale_result.get("upscaled"):
                    result["image_base64"] = upscale_result["image_base64"]
                else:
                    result["image_base64"] = image_b64
            else:
                result["image_base64"] = image_b64
                result["upscale"] = {"upscaled": False, "reason": "1024 HD output"}

        return result

    except Exception as e:
        logger.error(f"process_image failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e),
            "image_base64": image_b64,
        }


def _handle_generate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle image generation."""
    if not _init_complete.is_set():
        if not _init_complete.wait(timeout=600):
            return {"status": "error", "error": "Models still loading."}

    if _init_error:
        return {"status": "error", "error": f"Init failed: {_init_error}"}

    prompt = data.get("inputs") or data.get("prompt", "")
    tier = (data.get("quality_tier") or "STANDARD").upper()
    negative = (
        data.get("parameters", {}).get("negative_prompt")
        or data.get("negative_prompt", "")
    )
    width = data.get("parameters", {}).get("width") or data.get("width", 1024)
    height = data.get("parameters", {}).get("height") or data.get("height", 1024)
    seed = data.get("parameters", {}).get("seed") or data.get("seed")
    requested_model = data.get("model")
    recommended_model = data.get("recommended_model")
    guidance_override = data.get("guidance_scale")
    steps_override = data.get("num_inference_steps")

    width = (width // 8) * 8
    height = (height // 8) * 8

    logger.info(f"Request: tier={tier}, model_req={requested_model}, "
                f"recommended={recommended_model}, "
                f"size={width}x{height}, prompt='{prompt[:60]}...'")

    gen_start = time.time()

    try:
        with GPU_LOCK:
            model_name, steps, guidance = select_model(
                tier, prompt, requested_model, recommended_model)

            if guidance_override is not None:
                guidance = float(guidance_override)
            if steps_override is not None:
                steps = int(steps_override)

            max_pixels = 1024 * 1024
            if width * height > max_pixels:
                ratio = (max_pixels / (width * height)) ** 0.5
                width = int(width * ratio) // 8 * 8
                height = int(height * ratio) // 8 * 8

            # Always move post-processing to CPU during generation (same as generate_best).
            is_flux = (model_name == "flux-schnell")
            _move_postprocessing_to_cpu()

            try:
                pipe = load_generator(model_name)

                generator = torch.Generator(device="cpu")
                if seed:
                    generator.manual_seed(int(seed))
                else:
                    generator.manual_seed(int(time.time() * 1000) % (2 ** 32))

                actual_seed = generator.initial_seed()

                gen_kwargs = {
                    "prompt": prompt,
                    "num_inference_steps": steps,
                    "guidance_scale": guidance,
                    "width": width,
                    "height": height,
                    "generator": generator,
                }

                if model_name == "pixart-sigma":
                    gen_kwargs["max_sequence_length"] = 300
                    # PixArt-Sigma T5 uses padding="max_length", max_length=300 for both
                    # positive and negative — no tensor mismatch. Re-enabled to suppress
                    # text artifacts and watermarks that appear at lower step counts.
                    pixart_negative = negative if negative else (
                        "text, watermark, signature, blurry, low quality, "
                        "deformed, extra fingers, fused fingers, missing fingers, bad anatomy, "
                        "distorted face, asymmetric eyes, overexposed, underexposed"
                    )
                    gen_kwargs["negative_prompt"] = pixart_negative

                logger.info(f"Generating: model={model_name}, steps={steps}, "
                            f"guidance={guidance}, seed={actual_seed}")

                with torch.inference_mode():
                    image = pipe(**gen_kwargs).images[0]
            finally:
                # Restore post-processing to GPU after generation
                _move_postprocessing_to_gpu()

            gen_time = time.time() - gen_start
            logger.info(f"[DONE] Generated in {gen_time:.1f}s")

            return {
                "status": "success",
                "image": image_to_base64(image),
                "generation_time": round(gen_time, 2),
                "model": model_name,
                "steps": steps,
                "guidance_scale": guidance,
                "seed": actual_seed,
                "quality_tier": tier,
                "device": "cuda",
                "width": width,
                "height": height,
            }

    except torch.cuda.OutOfMemoryError:
        logger.error("[OOM] GPU out of memory!")
        with GPU_LOCK:
            clear_gpu_memory()
            unload_generator()
        return {"status": "error", "error": "GPU out of memory."}

    except Exception as e:
        logger.error(f"Generation error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def image_to_base64(image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG", optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def image_to_webp_base64(image) -> str:
    """WEBP q=95 — ~40% smaller than PNG for GPU1→GPU2 draft transfer."""
    buffered = io.BytesIO()
    image.save(buffered, format="WEBP", quality=95, method=4)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def image_to_lossless_b64(image) -> str:
    """JPEG q=100 4:4:4 — near-lossless for GPU1→GPU2 PREMIUM transfer.

    Retains >99.5% pixel data vs WEBP q=95 (~95%).
    Safety: auto-fallback to q=98 if base64 > 2MB (GPU2 Nginx threshold).
    """
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=100, subsampling=0)
    b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    if len(b64) > 2 * 1024 * 1024:  # > 2MB base64
        logger.warning("[TRANSFER] q=100 base64 %.1fMB > 2MB, fallback to q=98", len(b64) / 1048576)
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=98, subsampling=0)
        b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return b64


def output_fn(prediction, content_type="application/json"):
    # Return plain JSON string — works correctly for both TorchServe (real-time)
    # and async inference (body is written directly to S3).
    # Returning a tuple (body, content_type) causes HF/async containers to
    # serialize it as a JSON array instead of sending the body directly.
    return json.dumps(prediction)

"""
Multi-ControlNet with Real-Time Reward Guidance.
Guides diffusion process toward satisfying constraints DURING generation.
P0: Deterministic pipeline — Task 4 (multi-ControlNet + online reward guidance).
Task 1.1: Aesthetic guidance inside diffusion loop (reward model + gradient guidance).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

# Optional heavy dependencies (torch, diffusers, transformers, cv2)
try:
    import torch  # type: ignore[reportMissingImports]
    import torch.nn.functional as F  # type: ignore[reportMissingImports]

    HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    HAS_TORCH = False

try:
    from PIL import Image  # type: ignore[reportMissingImports]

    HAS_PIL = True
except ImportError:
    Image = None  # type: ignore[assignment]
    HAS_PIL = False

try:
    import cv2  # type: ignore[reportMissingImports]

    HAS_CV2 = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    HAS_CV2 = False

try:
    from diffusers.models.controlnet import ControlNetModel  # type: ignore[reportMissingImports]
    from diffusers.pipelines.controlnet.pipeline_controlnet_sd_xl import (  # type: ignore[reportMissingImports]
        StableDiffusionXLControlNetPipeline,
    )
    from diffusers.schedulers.scheduling_ddim import DDIMScheduler  # type: ignore[reportMissingImports]

    HAS_DIFFUSERS = True
except ImportError:
    ControlNetModel = None  # type: ignore[assignment]
    StableDiffusionXLControlNetPipeline = None  # type: ignore[assignment]
    DDIMScheduler = None  # type: ignore[assignment]
    HAS_DIFFUSERS = False

try:
    from transformers import CLIPModel, CLIPProcessor  # type: ignore[reportMissingImports]

    HAS_TRANSFORMERS = True
except ImportError:
    CLIPModel = None  # type: ignore[assignment]
    CLIPProcessor = None  # type: ignore[assignment]
    HAS_TRANSFORMERS = False

try:
    from .reward_model import RewardModel as _RewardModelFromFile

    _USE_FILE_REWARD_MODEL = True
except ImportError:
    _RewardModelFromFile = None
    _USE_FILE_REWARD_MODEL = False

# Optional: trained aesthetic predictor for gradient guidance (Task 1.1)
_AestheticPredictor = None
_load_pretrained_aesthetic = None
_AESTHETIC_CLIP_MEAN = [0.48145466, 0.4578275, 0.40821073]
_AESTHETIC_CLIP_STD = [0.26862954, 0.26130258, 0.27577711]

_HAS_AESTHETIC_MODEL = False
try:
    import sys

    _training_dir = Path(__file__).resolve().parent.parent / "training"
    if _training_dir.exists() and str(_training_dir.parent) not in sys.path:
        sys.path.insert(0, str(_training_dir.parent))
    from training.aesthetic_model import (
        load_pretrained as _load_pretrained_aesthetic,
        AestheticPredictor as _AestheticPredictor,
    )

    _HAS_AESTHETIC_MODEL = True
except Exception:
    pass


def _entity_type(e: Any) -> str:
    """Get entity type from EntityNode or dict."""
    if isinstance(e, dict):
        return e.get("type", "object")
    return getattr(e, "type", "object")


def _constraint_severity(c: Any) -> str:
    """Get constraint severity from HardConstraint or dict."""
    if isinstance(c, dict):
        return c.get("severity", "medium")
    return getattr(c, "severity", "medium")


def _draw_line_numpy(
    img: np.ndarray,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    color: Tuple[int, ...],
    thickness: int = 2,
) -> None:
    """Draw a line on img (H,W,C) using numpy. Bresenham-like."""
    x1, y1 = int(pt1[0]), int(pt1[1])
    x2, y2 = int(pt2[0]), int(pt2[1])
    h, w = img.shape[0], img.shape[1]
    n = max(abs(x2 - x1), abs(y2 - y1), 1)
    for i in range(n + 1):
        t = i / n
        x = int(x1 + t * (x2 - x1))
        y = int(y1 + t * (y2 - y1))
        for dy in range(-thickness, thickness + 1):
            for dx in range(-thickness, thickness + 1):
                if 0 <= y + dy < h and 0 <= x + dx < w:
                    img[y + dy, x + dx] = color


def _draw_circle_numpy(
    img: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    color: Tuple[int, ...],
    fill: bool = True,
) -> None:
    """Draw a circle on img (H,W,C) using numpy."""
    cy, cx = int(center[1]), int(center[0])
    h, w = img.shape[0], img.shape[1]
    Y, X = np.ogrid[:h, :w]
    mask = (X - cx) ** 2 + (Y - cy) ** 2 <= radius**2
    if fill:
        img[mask] = color
    else:
        r_out = radius + 1
        mask_out = (X - cx) ** 2 + (Y - cy) ** 2 <= r_out**2
        img[mask_out & ~mask] = color


class _FallbackRewardModel:
    """Fallback reward model when reward_model.py is not available."""

    def __init__(self, device: Optional[str] = None, load_models: bool = False) -> None:
        self.device = device or (
            "cuda" if HAS_TORCH and torch and torch.cuda.is_available() else "cpu"  # type: ignore[reportOptionalMemberAccess]
        )
        self.clip = None
        self.clip_processor = None
        self.aesthetic_model = None
        if load_models and HAS_TRANSFORMERS and HAS_TORCH:
            try:
                clip_model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14")  # type: ignore[reportOptionalMemberAccess]
                self.clip = clip_model.to(self.device)  # type: ignore[reportAttributeAccessIssue]
                self.clip_processor = CLIPProcessor.from_pretrained(  # type: ignore[reportOptionalMemberAccess]
                    "openai/clip-vit-large-patch14"
                )
            except Exception:
                pass
            try:
                from transformers import AutoModel  # type: ignore[reportMissingImports]

                self.aesthetic_model = AutoModel.from_pretrained(
                    "cafeai/cafe_aesthetic", trust_remote_code=True
                ).to(self.device)
            except Exception:
                pass

    def compute_rewards(
        self,
        latents: Any,
        scene_graph: Dict[str, Any],
        physics_state: Dict[str, Any],
        step: int,
        total_steps: int,
        vae: Any = None,
        decode_every_n: int = 5,
    ) -> Dict[str, float]:
        """Compute multi-objective rewards (fallback)."""
        preview = self._decode_latents_fast(latents)
        rewards: Dict[str, float] = {}

        if step > total_steps * 0.3:
            rewards["anatomy"] = self._compute_anatomy_reward(preview, scene_graph)
        else:
            rewards["anatomy"] = 0.5

        rewards["physics"] = self._compute_physics_reward(preview, physics_state)
        rewards["aesthetics"] = self._compute_aesthetic_reward(preview)
        rewards["constraint_satisfaction"] = self._compute_constraint_reward(
            preview, scene_graph
        )
        rewards["surprise"] = self._compute_surprise_reward(preview, scene_graph)
        rewards["overall"] = (
            rewards["anatomy"] * 0.3
            + rewards["physics"] * 0.2
            + rewards["aesthetics"] * 0.25
            + rewards["constraint_satisfaction"] * 0.15
            + rewards["surprise"] * 0.1
        )
        return rewards

    def _decode_latents_fast(self, latents: Any) -> Any:
        if not HAS_PIL or Image is None:
            return None
        return Image.new("RGB", (512, 512), color="gray")  # type: ignore[reportOptionalMemberAccess]

    def _compute_anatomy_reward(self, image: Any, scene_graph: Dict[str, Any]) -> float:
        return 0.7

    def _compute_physics_reward(
        self, image: Any, physics_state: Dict[str, Any]
    ) -> float:
        return 0.8

    def _compute_aesthetic_reward(self, image: Any) -> float:
        return 0.5

    def _compute_constraint_reward(
        self, image: Any, scene_graph: Dict[str, Any]
    ) -> float:
        constraints = scene_graph.get("constraints", [])
        critical = [c for c in constraints if _constraint_severity(c) == "critical"]
        if not critical:
            return 1.0
        return 0.8

    def _compute_surprise_reward(
        self, image: Any, scene_graph: Dict[str, Any]
    ) -> float:
        entities = scene_graph.get("entities", [])
        has_fantasy = any(
            _entity_type(e)
            in ("mythical_creature", "magical_object", "magical_material")
            for e in entities
        )
        return 0.9 if has_fantasy else 0.6


if _USE_FILE_REWARD_MODEL and _RewardModelFromFile is not None:
    RewardModel = _RewardModelFromFile
else:
    RewardModel = _FallbackRewardModel


def _resolve_aesthetic_checkpoint() -> Optional[Path]:
    """Resolve path to aesthetic reward checkpoint (aesthetic_reward_model.pth or aesthetic_predictor_production.pth)."""
    env_dir = __import__("os").environ.get("AESTHETIC_MODEL_DIR")
    if env_dir and Path(env_dir).exists():
        for name in (
            "aesthetic_reward_model.pth",
            "aesthetic_predictor_production.pth",
        ):
            p = Path(env_dir) / name
            if p.exists():
                return p
    root = Path(__file__).resolve().parent.parent
    for name in ("aesthetic_reward_model.pth", "aesthetic_predictor_production.pth"):
        for base in (root / "training", root, root / "models"):
            if base.exists():
                p = base / name
                if p.exists():
                    return p
    return None


class GuidedDiffusionControlNet:
    """Multi-ControlNet generation with online reward guidance and optional aesthetic gradient guidance."""

    def __init__(
        self,
        device: Optional[str] = None,
        aesthetic_guidance_scale: float = 0.3,
    ) -> None:
        self.device = device or (
            "cuda" if HAS_TORCH and torch and torch.cuda.is_available() else "cpu"  # type: ignore[reportOptionalMemberAccess]
        )
        self.controlnets: Dict[str, Any] = {}
        self.openpose_detector = None
        self.hed_detector = None
        self.pipeline = None
        self.reward_model = RewardModel(device=self.device)
        self._aesthetic_guidance_scale = float(aesthetic_guidance_scale)
        self._aesthetic_predictor: Any = None

        if (
            _HAS_AESTHETIC_MODEL
            and _load_pretrained_aesthetic is not None
            and _AestheticPredictor is not None
        ):
            ckpt = _resolve_aesthetic_checkpoint()
            if ckpt is not None:
                try:
                    model_dir = str(ckpt.parent)
                    self._aesthetic_predictor = _load_pretrained_aesthetic(
                        str(ckpt), model_dir=model_dir, device=self.device
                    )
                    self._aesthetic_predictor.eval()
                    logger.info(
                        "Aesthetic predictor loaded from %s (aesthetic_guidance_scale=%.2f)",
                        ckpt,
                        self._aesthetic_guidance_scale,
                    )
                except Exception as e:
                    logger.warning(
                        "Could not load aesthetic predictor for gradient guidance: %s",
                        e,
                    )
                    self._aesthetic_predictor = None
            else:
                logger.debug(
                    "No aesthetic checkpoint found; aesthetic gradient guidance disabled."
                )

        if HAS_CV2:
            try:
                from controlnet_aux import OpenposeDetector, HEDdetector  # type: ignore[reportMissingImports]

                self.openpose_detector = OpenposeDetector.from_pretrained(
                    "lllyasviel/ControlNet"
                )
                self.hed_detector = HEDdetector.from_pretrained("lllyasviel/ControlNet")
            except Exception:
                pass

        # Pipeline loaded lazily on first generate_with_guidance() to avoid slow downloads in __init__
        self._pipeline_loaded = False

    def generate_control_images(
        self,
        scene_graph: Dict[str, Any],
        width: int = 1024,
        height: int = 1024,
    ) -> Dict[str, Any]:
        """
        Generate control images from scene graph.

        Returns: {
            'depth': PIL Image or ndarray,
            'openpose': PIL Image or ndarray,
            'canny': PIL Image or ndarray
        }
        """
        layout = scene_graph.get("layout", {})
        entities = layout.get("entities", [])

        depth_map = self._create_depth_map(entities, width, height)
        openpose_map = self._create_openpose_map(entities, width, height)
        canny_map = self._create_canny_map(openpose_map)

        def to_pil(arr: np.ndarray) -> Any:
            if HAS_PIL and Image is not None:
                if arr.ndim == 2:
                    return Image.fromarray(arr.astype(np.uint8))  # type: ignore[reportOptionalMemberAccess]
                return Image.fromarray(arr.astype(np.uint8))  # type: ignore[reportOptionalMemberAccess]
            return arr

        return {
            "depth": to_pil(depth_map),
            "openpose": to_pil(openpose_map),
            "canny": to_pil(canny_map),
        }

    def _get_bbox(
        self, entity: Dict[str, Any], width: int, height: int
    ) -> Tuple[int, int, int, int]:
        """Get bbox (x1,y1,x2,y2) from entity; derive from center/radius if needed."""
        if "bbox" in entity:
            b = entity["bbox"]
            return (int(b[0]), int(b[1]), int(b[2]), int(b[3]))
        if "center" in entity:
            cx, cy = entity["center"][0], entity["center"][1]
            r = int(entity.get("radius", 100))
            return (
                max(0, cx - r),
                max(0, cy - r),
                min(width, cx + r),
                min(height, cy + r),
            )
        return (0, 0, width, height)

    def _create_depth_map(
        self, entities: List[Any], width: int, height: int
    ) -> np.ndarray:
        """Create depth map: people in foreground, objects slightly behind."""
        depth_map = np.ones((height, width), dtype=np.float32) * 0.85

        for entity in entities:
            e = (
                entity
                if isinstance(entity, dict)
                else getattr(entity, "__dict__", entity)
            )
            if not isinstance(e, dict):
                continue
            etype = e.get("type", "object")
            if etype == "person":
                x1, y1, x2, y2 = self._get_bbox(e, width, height)
                person_depth = np.linspace(0.2, 0.3, max(1, y2 - y1))
                for i, y in enumerate(range(y1, min(y2, height))):
                    if 0 <= y < height and i < len(person_depth):
                        depth_map[y, max(0, x1) : min(width, x2)] = person_depth[
                            min(i, len(person_depth) - 1)
                        ]

        for entity in entities:
            e = (
                entity
                if isinstance(entity, dict)
                else getattr(entity, "__dict__", entity)
            )
            if not isinstance(e, dict):
                continue
            etype = e.get("type", "object")
            if etype in ("umbrella", "object") and "center" in e:
                cx, cy = e["center"][0], e["center"][1]
                radius = int(e.get("radius", 100))
                Y, X = np.ogrid[:height, :width]
                dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
                depth_map[dist <= radius] = 0.35

        return (depth_map * 255).astype(np.uint8)

    def _create_openpose_map(
        self, entities: List[Any], width: int, height: int
    ) -> np.ndarray:
        """Create OpenPose skeleton map; each person gets a complete separate skeleton."""
        pose_map = np.zeros((height, width, 3), dtype=np.uint8)
        color = (255, 255, 255)
        thickness = 4

        for entity in entities:
            e = (
                entity
                if isinstance(entity, dict)
                else getattr(entity, "__dict__", entity)
            )
            if not isinstance(e, dict) or e.get("type") != "person":
                continue

            x1, y1, x2, y2 = self._get_bbox(e, width, height)
            head_pos = e.get("head_position", ((x1 + x2) // 2, y1))
            head_radius = int(e.get("head_radius", 30))
            cx = (x1 + x2) // 2
            person_height = max(1, y2 - y1)
            person_width = max(1, x2 - x1)

            head = (int(head_pos[0]), int(head_pos[1]))
            neck = (cx, head[1] + head_radius + 20)
            shoulder_left = (cx - person_width // 3, neck[1] + 10)
            shoulder_right = (cx + person_width // 3, neck[1] + 10)
            hip_center = (cx, y2 - int(person_height * 0.45))
            hip_left = (cx - person_width // 4, hip_center[1])
            hip_right = (cx + person_width // 4, hip_center[1])
            elbow_left = (
                shoulder_left[0] - 20,
                shoulder_left[1] + int(person_height * 0.25),
            )
            elbow_right = (
                shoulder_right[0] + 20,
                shoulder_right[1] + int(person_height * 0.25),
            )
            wrist_left = (elbow_left[0] - 10, elbow_left[1] + int(person_height * 0.2))
            wrist_right = (
                elbow_right[0] + 10,
                elbow_right[1] + int(person_height * 0.2),
            )
            knee_left = (hip_left[0], hip_left[1] + int(person_height * 0.25))
            knee_right = (hip_right[0], hip_right[1] + int(person_height * 0.25))
            ankle_left = (knee_left[0], y2 - 30)
            ankle_right = (knee_right[0], y2 - 30)

            if HAS_CV2 and cv2 is not None:
                cv2.circle(pose_map, head, head_radius, color, -1)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, neck, hip_center, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, shoulder_left, shoulder_right, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, hip_left, hip_right, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, shoulder_left, elbow_left, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, elbow_left, wrist_left, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, shoulder_right, elbow_right, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, elbow_right, wrist_right, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, hip_left, knee_left, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, knee_left, ankle_left, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, hip_right, knee_right, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                cv2.line(pose_map, knee_right, ankle_right, color, thickness)  # type: ignore[reportOptionalMemberAccess]
                for pt in [
                    neck,
                    shoulder_left,
                    shoulder_right,
                    elbow_left,
                    elbow_right,
                    wrist_left,
                    wrist_right,
                    hip_center,
                    hip_left,
                    hip_right,
                    knee_left,
                    knee_right,
                    ankle_left,
                    ankle_right,
                ]:
                    cv2.circle(pose_map, pt, 6, color, -1)  # type: ignore[reportOptionalMemberAccess]
            else:
                _draw_circle_numpy(pose_map, head, head_radius, color)
                _draw_line_numpy(pose_map, neck, hip_center, color, thickness)
                _draw_line_numpy(
                    pose_map, shoulder_left, shoulder_right, color, thickness
                )
                _draw_line_numpy(pose_map, hip_left, hip_right, color, thickness)
                _draw_line_numpy(pose_map, shoulder_left, elbow_left, color, thickness)
                _draw_line_numpy(pose_map, elbow_left, wrist_left, color, thickness)
                _draw_line_numpy(
                    pose_map, shoulder_right, elbow_right, color, thickness
                )
                _draw_line_numpy(pose_map, elbow_right, wrist_right, color, thickness)
                _draw_line_numpy(pose_map, hip_left, knee_left, color, thickness)
                _draw_line_numpy(pose_map, knee_left, ankle_left, color, thickness)
                _draw_line_numpy(pose_map, hip_right, knee_right, color, thickness)
                _draw_line_numpy(pose_map, knee_right, ankle_right, color, thickness)
                for pt in [
                    neck,
                    shoulder_left,
                    shoulder_right,
                    elbow_left,
                    elbow_right,
                    wrist_left,
                    wrist_right,
                    hip_center,
                    hip_left,
                    hip_right,
                    knee_left,
                    knee_right,
                    ankle_left,
                    ankle_right,
                ]:
                    _draw_circle_numpy(pose_map, pt, 6, color)

        return pose_map

    def _create_canny_map(self, openpose_map: np.ndarray) -> np.ndarray:
        """Create canny edge map from openpose."""
        if openpose_map.ndim == 3:
            gray = np.dot(openpose_map[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
        else:
            gray = openpose_map.astype(np.uint8)
        if HAS_CV2 and cv2 is not None:
            edges = cv2.Canny(gray, 50, 150)  # type: ignore[reportOptionalMemberAccess]
            return np.stack([edges, edges, edges], axis=-1)
        # Simple gradient-based edges without cv2
        gx = np.abs(
            np.diff(
                gray.astype(np.float32), axis=1, prepend=gray[:, :1].astype(np.float32)
            )
        )
        gy = np.abs(
            np.diff(
                gray.astype(np.float32), axis=0, prepend=gray[:1, :].astype(np.float32)
            )
        )
        edges = np.clip(gx + gy, 0, 255).astype(np.uint8)
        return np.stack([edges, edges, edges], axis=-1)

    def _load_pipeline(self) -> None:
        """Lazy-load ControlNets and SDXL pipeline (requires GPU and model download)."""
        if getattr(self, "_pipeline_loaded", False) and self.pipeline is not None:
            return
        self._pipeline_loaded = True
        if not HAS_DIFFUSERS or not HAS_TORCH or torch is None:
            return
        try:
            dtype = torch.float16 if self.device == "cuda" else torch.float32  # type: ignore[reportOptionalMemberAccess]
            depth_cn = ControlNetModel.from_pretrained("diffusers/controlnet-depth-sdxl-1.0", torch_dtype=dtype)  # type: ignore[reportOptionalMemberAccess]
            self.controlnets["depth"] = depth_cn.to(self.device)  # type: ignore[reportAttributeAccessIssue]
            openpose_cn = ControlNetModel.from_pretrained("thibaud/controlnet-openpose-sdxl-1.0", torch_dtype=dtype)  # type: ignore[reportOptionalMemberAccess]
            self.controlnets["openpose"] = openpose_cn.to(self.device)  # type: ignore[reportAttributeAccessIssue]
            canny_cn = ControlNetModel.from_pretrained("diffusers/controlnet-canny-sdxl-1.0", torch_dtype=dtype)  # type: ignore[reportOptionalMemberAccess]
            self.controlnets["canny"] = canny_cn.to(self.device)  # type: ignore[reportAttributeAccessIssue]
            pipe = StableDiffusionXLControlNetPipeline.from_pretrained(  # type: ignore[reportOptionalMemberAccess]
                "stabilityai/stable-diffusion-xl-base-1.0",
                controlnet=list(self.controlnets.values()),
                torch_dtype=dtype,
                variant="fp16" if self.device == "cuda" else None,
            )
            self.pipeline = pipe.to(self.device)  # type: ignore[reportAttributeAccessIssue]
            self.pipeline.scheduler = DDIMScheduler.from_config(  # type: ignore[reportOptionalMemberAccess]
                self.pipeline.scheduler.config
            )
            if self.device == "cuda":
                self.pipeline.enable_model_cpu_offload()
        except Exception:
            self.controlnets = {}
            self.pipeline = None

    def _apply_aesthetic_gradient(
        self,
        latents: Any,
        noise_pred: Any,
        aesthetic_guidance_scale: float,
        step: int,
        total_steps: int,
    ) -> Tuple[Optional[float], Any]:
        """
        Apply gradient-based aesthetic guidance: decode current latents, score with
        AestheticPredictor, backprop to get d(score)/d(latents), add scaled gradient
        to noise_pred. Returns (aesthetic_score, updated_noise_pred) or (None, noise_pred) on failure.
        """
        if not HAS_TORCH or getattr(self, "_aesthetic_predictor", None) is None:
            return (None, noise_pred)
        predictor = self._aesthetic_predictor
        vae = getattr(self.pipeline, "vae", None)
        if vae is None:
            return (None, noise_pred)
        scaling = getattr(getattr(vae, "config", None), "scaling_factor", 1.0)

        try:
            with torch.enable_grad():  # type: ignore[reportOptionalMemberAccess]
                latents_g = latents.detach().clone().requires_grad_(True)
                scaled = latents_g / scaling
                decoded = vae.decode(scaled, return_dict=False)[0]
                img = (decoded / 2.0 + 0.5).clamp(0.0, 1.0)
                img_224 = F.interpolate(  # type: ignore[reportOptionalMemberAccess]
                    img, size=(224, 224), mode="bilinear", align_corners=False
                )
                mean = torch.tensor(  # type: ignore[reportOptionalMemberAccess]
                    _AESTHETIC_CLIP_MEAN,
                    device=img_224.device,
                    dtype=img_224.dtype,
                ).view(1, 3, 1, 1)
                std = torch.tensor(  # type: ignore[reportOptionalMemberAccess]
                    _AESTHETIC_CLIP_STD,
                    device=img_224.device,
                    dtype=img_224.dtype,
                ).view(1, 3, 1, 1)
                img_norm = (img_224 - mean) / std
                if next(predictor.parameters()).dtype == torch.float16:  # type: ignore[reportOptionalMemberAccess]
                    img_norm = img_norm.half()
                score = predictor(img_norm).squeeze()
                loss = -score
                loss.backward()
                grad = latents_g.grad
            if grad is not None:
                grad = grad.detach().clamp_(-1.0, 1.0)
                norm = grad.norm().item()
                if norm > 1e-8:
                    adj = aesthetic_guidance_scale * grad
                    noise_pred = noise_pred + adj
            return (float(score.detach().item()), noise_pred)
        except Exception as e:
            logger.debug("Aesthetic gradient step failed: %s", e)
            return (None, noise_pred)

    def generate_with_guidance(
        self,
        prompt: str,
        negative_prompt: str,
        control_images: Dict[str, Any],
        scene_graph: Dict[str, Any],
        physics_state: Dict[str, Any],
        num_steps: int = 40,
        guidance_scale: float = 7.5,
        reward_weight: float = 0.3,
        aesthetic_guidance_scale: Optional[float] = None,
    ) -> Any:
        """
        Generate image with online reward guidance and optional aesthetic gradient guidance.

        During each denoising step:
        1. Predict noise
        2. Every 5 steps: compute rewards (RewardModel) and optionally apply gradient guidance
           toward higher aesthetic score (trained AestheticPredictor).
        3. Adjust noise prediction based on rewards / aesthetic gradient
        4. Continue denoising
        """
        use_aesthetic_scale = (
            float(aesthetic_guidance_scale)
            if aesthetic_guidance_scale is not None
            else getattr(self, "_aesthetic_guidance_scale", 0.0)
        )
        use_aesthetic_gradient = (
            use_aesthetic_scale > 0
            and getattr(self, "_aesthetic_predictor", None) is not None
        )
        if not HAS_TORCH or not HAS_DIFFUSERS:
            raise RuntimeError(
                "GuidedDiffusionControlNet.generate_with_guidance requires torch and diffusers. "
                "Install: pip install torch diffusers transformers"
            )
        if not getattr(self, "_pipeline_loaded", False) or self.pipeline is None:
            self._load_pipeline()
        if self.pipeline is None:
            raise RuntimeError(
                "Pipeline could not be loaded (GPU and model download required). "
                "Use generate_control_images() without full generation."
            )

        control_image_list = [
            control_images["depth"],
            control_images["openpose"],
            control_images["canny"],
        ]
        controlnet_conditioning_scale = [0.6, 0.9, 0.4]

        with torch.no_grad():  # type: ignore[reportOptionalMemberAccess]
            prompt_embeds = self.pipeline.encode_prompt(
                prompt,
                device=self.device,
                num_images_per_prompt=1,
                do_classifier_free_guidance=True,
                negative_prompt=negative_prompt,
            )
            prepare_img = getattr(self.pipeline, "prepare_image", None) or getattr(
                self.pipeline, "prepare_control_image", None
            )
            if prepare_img is None:
                raise RuntimeError(
                    "Pipeline has no prepare_image or prepare_control_image"
                )
            control_images_tensor = prepare_img(
                image=control_image_list,
                width=1024,
                height=1024,
                batch_size=1 * 2,
                num_images_per_prompt=1,
                device=self.device,
                dtype=torch.float16 if self.device == "cuda" else torch.float32,  # type: ignore[reportOptionalMemberAccess]
                do_classifier_free_guidance=True,
            )
            prepare_lat = getattr(
                self.pipeline, "prepare_latent_image", None
            ) or getattr(self.pipeline, "prepare_latents", None)
            if prepare_lat is None:
                raise RuntimeError(
                    "Pipeline has no prepare_latent_image or prepare_latents"
                )
            latents = prepare_lat(
                batch_size=1,
                num_channels_latents=4,
                height=1024,
                width=1024,
                dtype=prompt_embeds.dtype,
                device=self.device,
                generator=None,
            )
            self.pipeline.scheduler.set_timesteps(num_steps, device=self.device)

            for i, t in enumerate(self.pipeline.scheduler.timesteps):
                latent_model_input = torch.cat([latents] * 2)  # type: ignore[reportOptionalMemberAccess]
                latent_model_input = self.pipeline.scheduler.scale_model_input(
                    latent_model_input, t
                )

                try:
                    down_block_res_samples, mid_block_res_sample = (
                        self.pipeline.controlnet(
                            latent_model_input,
                            t,
                            encoder_hidden_states=prompt_embeds,
                            controlnet_cond=control_images_tensor,
                            conditioning_scale=controlnet_conditioning_scale,
                            return_dict=False,
                        )
                    )
                except TypeError:
                    down_block_res_samples, mid_block_res_sample = (
                        self.pipeline.controlnet(
                            latent_model_input,
                            t,
                            encoder_hidden_states=prompt_embeds,
                            image=control_images_tensor,
                            conditioning_scale=(
                                controlnet_conditioning_scale[0]
                                if controlnet_conditioning_scale
                                else 0.8
                            ),
                            return_dict=False,
                        )
                    )

                noise_pred = self.pipeline.unet(
                    latent_model_input,
                    t,
                    encoder_hidden_states=prompt_embeds,
                    down_block_additional_residuals=down_block_res_samples,
                    mid_block_additional_residual=mid_block_res_sample,
                    return_dict=False,
                )[0]

                noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
                noise_pred = noise_pred_uncond + guidance_scale * (
                    noise_pred_text - noise_pred_uncond
                )

                if i % 5 == 0 and i > num_steps * 0.2:
                    rewards = self.reward_model.compute_rewards(
                        latents,
                        scene_graph,
                        physics_state,
                        i,
                        num_steps,
                        vae=getattr(self.pipeline, "vae", None),
                        decode_every_n=5,
                    )
                    total_reward = (
                        rewards.get("anatomy", 0.5) * 0.3
                        + rewards.get("physics", 0.5) * 0.2
                        + rewards.get("aesthetics", 0.5) * 0.2
                        + rewards.get("constraint_satisfaction", 0.5) * 0.2
                        + rewards.get("surprise", 0.5) * 0.1
                    )
                    if total_reward < 0.6 and not use_aesthetic_gradient:
                        noise_adjustment = (
                            torch.randn_like(noise_pred, device=noise_pred.device)  # type: ignore[reportOptionalMemberAccess]
                            * 0.1
                            * (1 - total_reward)
                        )
                        noise_pred = noise_pred + noise_adjustment * reward_weight

                    if use_aesthetic_gradient:
                        aesthetic_score_val, noise_pred = (
                            self._apply_aesthetic_gradient(
                                latents,
                                noise_pred,
                                use_aesthetic_scale,
                                i,
                                num_steps,
                            )
                        )
                        if aesthetic_score_val is not None:
                            logger.info(
                                "Aesthetic guidance step=%d t=%s score=%.4f",
                                i,
                                t.item() if hasattr(t, "item") else t,
                                aesthetic_score_val,
                            )

                latents = self.pipeline.scheduler.step(
                    noise_pred, t, latents, return_dict=False
                )[0]

            latents = 1 / self.pipeline.vae.config.scaling_factor * latents
            image = self.pipeline.vae.decode(latents, return_dict=False)[0]
            image = self.pipeline.image_processor.postprocess(image, output_type="pil")[
                0
            ]
            return image

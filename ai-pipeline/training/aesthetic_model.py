"""
Shared aesthetic predictor for training and inference.
CLIP ViT-L/14 + MLP head; LAION-style normalization.
Used by aesthetic_reward.py (training) and quality_scorer.py (inference).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

import torch
from PIL import Image
from torchvision import transforms


DEFAULT_MODEL_DIR = os.environ.get("AESTHETIC_MODEL_DIR", "/models")
CLIP_MEAN = [0.48145466, 0.4578275, 0.40821073]
CLIP_STD = [0.26862954, 0.26130258, 0.27577711]


def _transform():
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=CLIP_MEAN, std=CLIP_STD),
    ])


def _build_clip_backbone(model_dir: str):
    from transformers import CLIPModel, CLIPImageProcessor

    model_id = "openai/clip-vit-large-patch14"
    cache_dir = str(Path(model_dir) / "clip-vit-l-14")
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    model = CLIPModel.from_pretrained(
        model_id,
        cache_dir=cache_dir,
        torch_dtype=torch.float16,
    )
    processor = CLIPImageProcessor.from_pretrained(
        model_id,
        cache_dir=cache_dir,
    )
    for p in model.vision_model.parameters():
        p.requires_grad = False
    return model, processor


class AestheticPredictor(torch.nn.Module):
    """
    CLIP ViT-L/14 image encoder + regression head.
    Output: scalar in [0, 1] (normalized aesthetic score).
    """

    def __init__(self, clip_model, processor, hidden_dim: int = 768):
        super().__init__()
        self.clip = clip_model
        self.processor = processor
        feat_dim = self.clip.visual_projection.out_features
        self.mlp = torch.nn.Sequential(
            torch.nn.Linear(feat_dim, hidden_dim),
            torch.nn.ReLU(inplace=True),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(hidden_dim, hidden_dim // 2),
            torch.nn.ReLU(inplace=True),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        vision_out = self.clip.vision_model(pixel_values=pixel_values)
        pooled = vision_out.pooler_output
        proj = self.clip.visual_projection(pooled)
        score = self.mlp(proj).squeeze(-1)
        return torch.sigmoid(score)


def build_predictor(
    model_dir: str = DEFAULT_MODEL_DIR,
    device: str = "cuda",
) -> AestheticPredictor:
    """Build model without loading checkpoint (for training)."""
    clip_model, processor = _build_clip_backbone(model_dir)
    return AestheticPredictor(clip_model, processor).to(device)


def load_pretrained(
    checkpoint_path: str,
    model_dir: str = DEFAULT_MODEL_DIR,
    device: str = "cuda",
) -> AestheticPredictor:
    """Load trained aesthetic model from checkpoint."""
    clip_model, processor = _build_clip_backbone(model_dir)
    model = AestheticPredictor(clip_model, processor).to(device)
    state = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval()
    return model


def get_transform():
    return _transform()


def predict(
    model: AestheticPredictor,
    img: Image.Image,
    device: str = "cuda",
) -> float:
    """Single-image inference. Returns score in [0, 1]."""
    t = get_transform()
    x = t(img.convert("RGB")).unsqueeze(0).to(device)
    if next(model.parameters()).dtype == torch.float16:
        x = x.half()
    with torch.no_grad():
        s = model(x).squeeze().float().item()
    return s


def predict_batch(
    model: AestheticPredictor,
    images: List[Image.Image],
    device: str = "cuda",
    batch_size: int = 32,
) -> List[float]:
    """Batch inference. Returns list of scores in [0, 1]."""
    t = get_transform()
    scores: List[float] = []
    for i in range(0, len(images), batch_size):
        batch = images[i : i + batch_size]
        tensors = [t(im.convert("RGB")) for im in batch]
        x = torch.stack(tensors).to(device)
        if next(model.parameters()).dtype == torch.float16:
            x = x.half()
        with torch.no_grad():
            out = model(x).float().cpu().tolist()
        scores.extend(out)
    return scores

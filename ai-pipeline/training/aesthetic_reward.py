"""
Aesthetic Reward Model Training – replace heuristic quality scoring with learned preference model.

Goal: MJ-level aesthetics; train on AVA (250k) + PhotoGenius user ratings (DynamoDB).
- Architecture: CLIP ViT-L/14 + 2-layer MLP → aesthetic score [0–1], scale to [0–10].
- Training: Regression on AVA + user ratings; 80% AVA, 20% user; 10 epochs, AdamW, MSELoss.
- Export: aesthetic_reward_model.pth (same format as aesthetic_predictor_production.pth for QualityScorer).

Usage:
  # Modal (existing)
  modal run ai-pipeline/training/aesthetic_reward.py::train

  # CLI (local / SageMaker)
  python ai-pipeline/scripts/train_aesthetic.py --dataset ava --epochs 10 --batch-size 64 --lr 1e-4 --output-dir models/aesthetic_reward
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, ConcatDataset, WeightedRandomSampler

# Allow importing aesthetic_model from parent
if __name__ != "__main__":
    _training_dir = Path(__file__).resolve().parent
    if str(_training_dir) not in sys.path:
        sys.path.insert(0, str(_training_dir.parent))

from training.aesthetic_model import (
    build_predictor,
    get_transform,
    AestheticPredictor,
    DEFAULT_MODEL_DIR,
)

# ---------------------------------------------------------------------------
# AVA dataset loading (HuggingFace or local)
# ---------------------------------------------------------------------------

def load_ava_dataset(
    cache_dir: Optional[str] = None,
    split: str = "train",
    max_samples: Optional[int] = None,
) -> Optional[Dataset]:
    """
    Load AVA dataset (250k images with aesthetic ratings).
    Tries HuggingFace (Iceclear/AVA or similar); fallback to local path from env AVA_DATA_DIR.
    Returns PyTorch Dataset of (image_tensor, rating_0_1) or None if unavailable.
    """
    cache_dir = cache_dir or os.environ.get("HF_HOME", os.path.join(os.path.expanduser("~"), ".cache", "huggingface"))
    transform = get_transform()

    try:
        from datasets import load_dataset
        # Try Iceclear/AVA (image + score) or similar
        ds = load_dataset("Iceclear/AVA", split=split, trust_remote_code=True, cache_dir=cache_dir)
    except Exception as e1:
        try:
            # Alternative: ChristophSchuhmann/improved_aesthetics_parquet has URL + score
            ds = load_dataset("ChristophSchuhmann/improved_aesthetics_parquet", split=split, trust_remote_code=True, cache_dir=cache_dir)
        except Exception as e2:
            # Local path: AVA_DATA_DIR with images and a CSV/list of (path, mean_score)
            ava_dir = os.environ.get("AVA_DATA_DIR")
            if ava_dir and Path(ava_dir).exists():
                return _local_ava_dataset(ava_dir, split, transform, max_samples)
            print(f"AVA dataset not available: {e1}; {e2}")
            return None

    if max_samples is not None and len(ds) > max_samples:
        ds = ds.select(range(max_samples))

    class AVAWrapper(Dataset):
        def __init__(self, hf_ds, transform_fn):
            self.hf_ds = hf_ds
            self.transform_fn = transform_fn

        def __len__(self):
            return len(self.hf_ds)

        def __getitem__(self, idx):
            row = self.hf_ds[idx]
            # Iceclear/AVA: "image" (PIL), "mean_score" or "score" (1-10)
            img = row.get("image")
            if img is None and "img" in row:
                img = row["img"]
            if hasattr(img, "convert"):
                img = img.convert("RGB")
            else:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(img.get("bytes", img))).convert("RGB")
            score_raw = float(row.get("mean_score", row.get("score", row.get("aesthetic_score", 5.0)))
            # AVA mean ~5.0 ± 1.2; normalize to [0, 1]
            score = max(0.0, min(1.0, score_raw / 10.0))
            x = self.transform_fn(img)
            return x, torch.tensor(score, dtype=torch.float32)

    return AVAWrapper(ds, transform)


def _local_ava_dataset(
    data_dir: str,
    split: str,
    transform: Any,
    max_samples: Optional[int],
) -> Dataset:
    """Local AVA: data_dir has images and scores.csv (path, mean_score)."""
    import csv
    from PIL import Image
    data_path = Path(data_dir)
    csv_path = data_path / "scores.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"No scores.csv in {data_dir}")
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            path = data_path / r.get("path", r.get("image_path", r.get("filename", "")))
            if path.suffix == "":
                path = path.with_suffix(".jpg")
            score = float(r.get("mean_score", r.get("score", 5.0)))
            rows.append((str(path), score))
    n = len(rows)
    split_idx = int(n * 0.9)
    if split == "train":
        rows = rows[:split_idx]
    else:
        rows = rows[split_idx:]
    if max_samples is not None:
        rows = rows[:max_samples]

    class LocalAVADataset(Dataset):
        def __len__(self):
            return len(rows)

        def __getitem__(self, idx):
            path, score_raw = rows[idx]
            img = Image.open(path).convert("RGB")
            score = max(0.0, min(1.0, score_raw / 10.0))
            x = transform(img)
            return x, torch.tensor(score, dtype=torch.float32)

    return LocalAVADataset()


# ---------------------------------------------------------------------------
# PhotoGenius user ratings (DynamoDB)
# ---------------------------------------------------------------------------

def load_user_ratings(
    table_name: str,
    region: Optional[str] = None,
    s3_bucket: Optional[str] = None,
    max_items: int = 50_000,
) -> List[Tuple[Any, float]]:
    """
    Load PhotoGenius user ratings from DynamoDB.
    Schema: { image_id, generation_id, rating (1-5), timestamp, image_url? }.
    Returns list of (image_tensor_or_pil, rating_0_1). Rating 1-5 → normalize to 0.2-1.0.
    """
    try:
        import boto3
        from PIL import Image
        import io
        import requests
    except ImportError:
        return []

    region = region or os.environ.get("AWS_REGION", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)
    transform = get_transform()

    items: List[Tuple[Any, float]] = []
    scan_kwargs = {"Limit": max_items}
    done = False
    while not done:
        resp = table.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            rating_raw = item.get("rating")
            if rating_raw is None:
                continue
            try:
                r = int(rating_raw)
            except (TypeError, ValueError):
                continue
            if r < 1 or r > 5:
                continue
            # 1-5 → 0.2-1.0
            score = 0.2 + (r - 1) * (0.8 / 4.0)
            image_url = item.get("image_url") or item.get("s3_url")
            image_bytes = item.get("image_bytes")
            if image_bytes:
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            elif image_url:
                try:
                    rq = requests.get(image_url, timeout=10)
                    rq.raise_for_status()
                    img = Image.open(io.BytesIO(rq.content)).convert("RGB")
                except Exception:
                    continue
            else:
                continue
            x = transform(img)
            items.append((x, torch.tensor(score, dtype=torch.float32)))
        token = resp.get("LastEvaluatedKey")
        if not token:
            done = True
        else:
            scan_kwargs["ExclusiveStartKey"] = token
    return items


class UserRatingsDataset(Dataset):
    """Dataset from list of (tensor, score) from load_user_ratings."""

    def __init__(self, pairs: List[Tuple[Any, torch.Tensor]]):
        self.pairs = pairs

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        return self.pairs[idx]


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------

def train_aesthetic_model(
    dataset: str = "ava",
    user_ratings_table: Optional[str] = None,
    epochs: int = 10,
    batch_size: int = 64,
    lr: float = 1e-4,
    output_dir: str = "models/aesthetic_reward",
    model_dir: Optional[str] = None,
    device: str = "cuda",
    ava_max_samples: Optional[int] = None,
    mix_ratio_ava: float = 0.8,
) -> Dict[str, Any]:
    """
    Training pipeline:
    1. Load AVA dataset (250k images with aesthetic ratings)
    2. Mix with PhotoGenius user ratings from DynamoDB (if table provided)
    3. Train for epochs with AdamW, MSELoss
    4. Validate on held-out set
    5. Export for SageMaker / QualityScorer (aesthetic_reward_model.pth)
    """
    model_dir = model_dir or os.environ.get("AESTHETIC_MODEL_DIR", DEFAULT_MODEL_DIR)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 1. AVA
    train_ava = load_ava_dataset(split="train", max_samples=ava_max_samples)
    val_ava = load_ava_dataset(split="validation") or load_ava_dataset(split="test") or load_ava_dataset(split="train")
    if val_ava is not None and val_ava == train_ava:
        n = len(train_ava)
        val_ava = torch.utils.data.Subset(train_ava, range(int(n * 0.9), n))
        train_ava = torch.utils.data.Subset(train_ava, range(int(n * 0.9)))

    # 2. User ratings
    user_pairs: List[Tuple[Any, float]] = []
    if user_ratings_table:
        user_pairs = load_user_ratings(user_ratings_table)
    user_ds = UserRatingsDataset(user_pairs) if user_pairs else None

    # 3. Combined: 80% AVA, 20% user (by weighted sampling or concat with weights)
    if train_ava is None and user_ds is None:
        raise RuntimeError("No data: AVA and user ratings unavailable.")
    if train_ava is not None and user_ds is not None and len(user_ds) > 0:
        n_ava = len(train_ava)
        n_user = len(user_ds)
        total = n_ava + n_user
        w_ava = mix_ratio_ava / max(1e-6, n_ava / total)
        w_user = (1.0 - mix_ratio_ava) / max(1e-6, n_user / total)
        combined = ConcatDataset([train_ava, user_ds])
        weights = [w_ava] * n_ava + [w_user] * n_user
        sampler = WeightedRandomSampler(weights, len(combined))
        train_loader = DataLoader(combined, batch_size=batch_size, sampler=sampler, num_workers=0, pin_memory=True)
    elif train_ava is not None:
        train_loader = DataLoader(train_ava, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)
    else:
        train_loader = DataLoader(user_ds, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)

    val_loader = None
    if val_ava is not None:
        val_loader = DataLoader(val_ava, batch_size=batch_size, shuffle=False, num_workers=0)

    # 4. Model
    model = build_predictor(model_dir=model_dir, device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    criterion = nn.MSELoss()
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    out_path = os.path.join(output_dir, "aesthetic_reward_model.pth")
    prod_path = os.path.join(model_dir, "aesthetic_predictor_production.pth") if Path(model_dir).exists() else None

    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        for batch_idx, (images, ratings) in enumerate(train_loader):
            images = images.to(device, non_blocking=True)
            ratings = ratings.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            preds = model(images).squeeze()
            loss = criterion(preds, ratings)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        train_loss = running_loss / max(1, len(train_loader))
        scheduler.step()

        val_loss = float("inf")
        if val_loader is not None:
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for images, ratings in val_loader:
                    images = images.to(device)
                    ratings = ratings.to(device)
                    preds = model(images).squeeze()
                    val_loss += criterion(preds, ratings).item()
            val_loss /= max(1, len(val_loader))
            model.train()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), out_path)
            if prod_path:
                try:
                    Path(prod_path).parent.mkdir(parents=True, exist_ok=True)
                    torch.save(model.state_dict(), prod_path)
                except Exception:
                    pass
        print(f"Epoch {epoch+1}/{epochs} train_loss={train_loss:.4f} val_loss={val_loss:.4f}")

    return {"best_val_loss": best_val_loss, "checkpoint": out_path}


# ---------------------------------------------------------------------------
# Modal (existing production training)
# ---------------------------------------------------------------------------

try:
    import modal  # type: ignore[reportMissingImports]
except ImportError:
    modal = None

if modal is not None:
    app = modal.App("photogenius-aesthetic-reward")
    MODEL_DIR = "/models"
    DATA_DIR = "/data"
    models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)
    data_volume = modal.Volume.from_name("aesthetic-dataset", create_if_missing=True)

    image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("git", "libgl1-mesa-glx", "libglib2.0-0")
        .pip_install([
            "torch==2.4.1", "torchvision==0.19.1", "transformers==4.44.2",
            "tqdm==4.66.1", "pillow==10.2.0", "numpy==1.26.3", "wandb==0.16.0",
            "datasets>=2.14.0",
        ])
        .env({"HF_HOME": f"{MODEL_DIR}/hf"})
        .add_local_python_source("ai-pipeline/training", remote_path="/app/training")
    )

    @app.function(
        gpu="A100-80GB",
        image=image,
        volumes={MODEL_DIR: models_volume, DATA_DIR: data_volume},
        timeout=86400,
        secrets=[modal.Secret.from_name("wandb-api-key", required=False)],
    )
    def train_production():
        """Production training: AVA (if available) + LAION; saves to /models."""
        import os
        from pathlib import Path
        if "/app" not in sys.path:
            sys.path.insert(0, "/app")
        train_ava = load_ava_dataset(split="train", cache_dir=f"{MODEL_DIR}/hf")
        if train_ava is not None:
            result = train_aesthetic_model(
                dataset="ava",
                epochs=10,
                batch_size=64,
                lr=1e-4,
                output_dir=MODEL_DIR,
                model_dir=MODEL_DIR,
                device="cuda",
                ava_max_samples=100_000,
            )
        else:
            from training.aesthetic_reward import LAIONAestheticDataset  # noqa: F811
            from torch.utils.data import DataLoader
            train_dataset = LAIONAestheticDataset(f"{DATA_DIR}/laion", split="train")
            val_dataset = LAIONAestheticDataset(f"{DATA_DIR}/laion", split="val")
            train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True, num_workers=8, pin_memory=True)
            val_loader = DataLoader(val_dataset, batch_size=128, shuffle=False, num_workers=8, pin_memory=True)
            model = build_predictor(MODEL_DIR, "cuda")
            optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5, weight_decay=0.01)
            criterion = nn.MSELoss()
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=5)
            best_val_loss = float("inf")
            for epoch in range(5):
                model.train()
                for images, scores in train_loader:
                    images, scores = images.to("cuda"), scores.to("cuda")
                    optimizer.zero_grad(set_to_none=True)
                    loss = criterion(model(images).squeeze(), scores)
                    loss.backward()
                    optimizer.step()
                model.eval()
                val_loss = 0.0
                with torch.no_grad():
                    for images, scores in val_loader:
                        images, scores = images.to("cuda"), scores.to("cuda")
                        val_loss += criterion(model(images).squeeze(), scores).item()
                val_loss /= max(1, len(val_loader))
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    torch.save(model.state_dict(), f"{MODEL_DIR}/aesthetic_predictor_production.pth")
                scheduler.step()
            result = {"best_val_loss": best_val_loss}
        models_volume.commit()
        return result

    class LAIONAestheticDataset(torch.utils.data.Dataset):
        """Dataset for LAION-Aesthetics subset under /data/laion (existing)."""
        def __init__(self, data_dir: str, split: str = "train"):
            from pathlib import Path
            import json
            from PIL import Image
            from torchvision import transforms
            self.data_dir = Path(data_dir)
            self.image_paths = sorted(self.data_dir.glob("*.jpg"))
            if not self.image_paths:
                raise RuntimeError(f"No images in {self.data_dir}")
            split_idx = int(len(self.image_paths) * 0.9)
            self.image_paths = self.image_paths[:split_idx] if split == "train" else self.image_paths[split_idx:]
            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.48145466, 0.4578275, 0.40821073], [0.26862954, 0.26130258, 0.27577711]),
            ])

        def __len__(self):
            return len(self.image_paths)

        def __getitem__(self, idx):
            import json
            from PIL import Image
            img_path = self.image_paths[idx]
            json_path = img_path.with_suffix(".json")
            img = Image.open(img_path).convert("RGB")
            score = 5.0
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    score = float(json.load(f).get("aesthetic_score", 5.0))
            score = max(0.0, min(1.0, score / 10.0))
            return self.transform(img), torch.tensor(score, dtype=torch.float32)

    @app.cls(image=image, gpu="T4", volumes={MODEL_DIR: models_volume}, keep_warm=1, timeout=60)
    class AestheticPredictorService:
        @modal.enter()
        def load(self):
            from pathlib import Path
            if "/app" not in sys.path:
                sys.path.insert(0, "/app")
            from training.aesthetic_model import load_pretrained
            ckpt = f"{MODEL_DIR}/aesthetic_reward_model.pth"
            if not Path(ckpt).exists():
                ckpt = f"{MODEL_DIR}/aesthetic_predictor_production.pth"
            self.model = load_pretrained(ckpt, MODEL_DIR, "cuda") if Path(ckpt).exists() else None

        @modal.method()
        def predict(self, image_base64: str) -> float:
            import base64
            from io import BytesIO
            from PIL import Image
            from training.aesthetic_model import predict as _predict
            if self.model is None:
                return 0.5
            raw = base64.b64decode(image_base64)
            img = Image.open(BytesIO(raw)).convert("RGB")
            return _predict(self.model, img, "cuda")

        @modal.method()
        def predict_batch(self, images_base64: list) -> list:
            from training.aesthetic_model import predict_batch as _predict_batch
            import base64
            from io import BytesIO
            from PIL import Image
            if self.model is None or not images_base64:
                return [0.5] * len(images_base64) if images_base64 else []
            imgs = [Image.open(BytesIO(base64.b64decode(b64))).convert("RGB") for b64 in images_base64]
            return _predict_batch(self.model, imgs, "cuda", batch_size=32)

    @app.local_entrypoint()
    def train():
        result = train_production.remote()
        print("Training complete:", result)

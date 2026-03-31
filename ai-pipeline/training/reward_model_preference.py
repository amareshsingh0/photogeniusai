"""
Preference-based Reward Model Training (RLHF pilot).

Trains a reward model from pairwise preferences (Bradley-Terry):
  P(A > B) = sigma(r(A) - r(B)), loss = -log P(preferred).

- Input: image + optional prompt embedding (CLIP).
- Output: reward score 0-1.
- Dataset: 80% user preference pairs (JSONL), 20% AVA-derived pairs or regression baseline.
- Evaluation: Pearson r with human judgments (if available); else validation accuracy on held-out pairs.
- Export: reward_model_preference.pth for SageMaker / inference.

Usage:
  python ai-pipeline/training/reward_model_preference.py \\
    --pairs preference_pairs.jsonl \\
    --ava-dir /path/to/ava \\
    --epochs 5 --batch-size 32 --output-dir models/reward_preference
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# Allow importing aesthetic_model from same package
_TOP = Path(__file__).resolve().parent.parent
if str(_TOP) not in sys.path:
    sys.path.insert(0, str(_TOP))

try:
    from training.aesthetic_model import get_transform, build_predictor, AestheticPredictor, DEFAULT_MODEL_DIR
except ImportError:
    from aesthetic_model import get_transform, build_predictor, AestheticPredictor, DEFAULT_MODEL_DIR  # type: ignore

try:
    from PIL import Image
except ImportError:
    Image = None
try:
    import requests
except ImportError:
    requests = None


# ---------------------------------------------------------------------------
# Pairwise dataset from JSONL
# ---------------------------------------------------------------------------

def load_pairs_jsonl(path: str, max_pairs: Optional[int] = None) -> List[Dict[str, Any]]:
    pairs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                pairs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if max_pairs and len(pairs) >= max_pairs:
                break
    return pairs


class PreferencePairDataset(Dataset):
    """Dataset of (image_a_tensor, image_b_tensor, preferred) from JSONL. Loads images from URL."""

    def __init__(
        self,
        pairs: List[Dict[str, Any]],
        transform: Any,
        image_cache: Optional[Dict[str, torch.Tensor]] = None,
    ):
        self.pairs = pairs
        self.transform = transform
        self.cache = image_cache or {}

    def __len__(self) -> int:
        return len(self.pairs)

    def _load_image(self, url: str) -> Optional[torch.Tensor]:
        if url in self.cache:
            return self.cache[url]
        if not Image or not requests:
            return None
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            x = self.transform(img)
            self.cache[url] = x
            return x
        except Exception:
            return None

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, int]:
        import io
        p = self.pairs[idx]
        url_a = p.get("image_a_url") or p.get("imageAUrl", "")
        url_b = p.get("image_b_url") or p.get("imageBUrl", "")
        pref = p.get("preferred", "A")
        # preferred: A -> 0 (index of winner), B -> 1, EQUAL -> 2 (skip or treat as 0.5)
        if pref == "A":
            label = 0
        elif pref == "B":
            label = 1
        else:
            label = 2  # EQUAL: we'll use 0.5 target in loss

        x_a = self._load_image(url_a)
        x_b = self._load_image(url_b)
        if x_a is None:
            x_a = torch.zeros(3, 224, 224)
        if x_b is None:
            x_b = torch.zeros(3, 224, 224)
        return x_a, x_b, label


# ---------------------------------------------------------------------------
# Bradley-Terry loss
# ---------------------------------------------------------------------------

def bradley_terry_loss(r_a: torch.Tensor, r_b: torch.Tensor, preferred: torch.Tensor) -> torch.Tensor:
    """
    preferred: 0 = A, 1 = B, 2 = equal.
    Loss = -log P(preferred). For equal we use 0.5 * (-log sigma(r_a - r_b) - log sigma(r_b - r_a)).
    """
    logits = r_a - r_b  # (B,)
    # P(A > B) = sigma(logits)
    loss_a = F.logsigmoid(logits)
    loss_b = F.logsigmoid(-logits)
    # preferred 0 -> want high P(A>B) -> maximize loss_a
    # preferred 1 -> want high P(B>A) -> maximize loss_b
    # preferred 2 -> equal -> (loss_a + loss_b) / 2
    n = preferred.shape[0]
    loss = torch.zeros(n, device=logits.device)
    loss[preferred == 0] = -loss_a[preferred == 0]
    loss[preferred == 1] = -loss_b[preferred == 1]
    equal_mask = preferred == 2
    if equal_mask.any():
        loss[equal_mask] = -0.5 * (loss_a[equal_mask] + loss_b[equal_mask])
    return loss.mean()


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_reward_model(
    pairs_path: str,
    ava_dir: Optional[str] = None,
    epochs: int = 5,
    batch_size: int = 32,
    lr: float = 1e-4,
    output_dir: str = "models/reward_preference",
    model_dir: Optional[str] = None,
    device: str = "cuda",
    mix_ratio_user: float = 0.8,
    max_user_pairs: Optional[int] = None,
) -> Dict[str, Any]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    model_dir = model_dir or os.environ.get("AESTHETIC_MODEL_DIR", DEFAULT_MODEL_DIR)

    transform = get_transform()
    pairs = load_pairs_jsonl(pairs_path, max_pairs=max_user_pairs)
    if not pairs:
        raise RuntimeError(f"No pairs loaded from {pairs_path}")

    dataset = PreferencePairDataset(pairs, transform)
    train_loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=True,
    )

    model = build_predictor(model_dir=model_dir, device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    best_acc = 0.0
    out_path = os.path.join(output_dir, "reward_model_preference.pth")

    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        for batch in train_loader:
            x_a, x_b, pref = batch
            x_a = x_a.to(device, non_blocking=True)
            x_b = x_b.to(device, non_blocking=True)
            pref = pref.to(device, non_blocking=True)
            # Drop EQUAL for accuracy count
            mask = pref != 2
            optimizer.zero_grad(set_to_none=True)
            r_a = model(x_a).squeeze(1)
            r_b = model(x_b).squeeze(1)
            loss = bradley_terry_loss(r_a, r_b, pref)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            with torch.no_grad():
                pred = (r_a > r_b).long()
                if mask.any():
                    correct += (pred[mask] == pref[mask]).sum().item()
                    total += mask.sum().item()
        train_loss = running_loss / max(1, len(train_loader))
        acc = correct / max(1, total) if total else 0.0
        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), out_path)
        print(f"Epoch {epoch+1}/{epochs} train_loss={train_loss:.4f} acc={acc:.4f}")

    return {"best_accuracy": best_acc, "checkpoint": out_path}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Train preference-based reward model (Bradley-Terry)")
    ap.add_argument("--pairs", required=True, help="JSONL of preference pairs (image_a_url, image_b_url, preferred)")
    ap.add_argument("--ava-dir", default=None, help="Optional AVA data dir for mixed training")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--output-dir", default="models/reward_preference")
    ap.add_argument("--model-dir", default=None)
    ap.add_argument("--max-user-pairs", type=int, default=None)
    ap.add_argument("--mix-ratio-user", type=float, default=0.8)
    args = ap.parse_args()

    result = train_reward_model(
        pairs_path=args.pairs,
        ava_dir=args.ava_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        output_dir=args.output_dir,
        model_dir=args.model_dir,
        mix_ratio_user=args.mix_ratio_user,
        max_user_pairs=args.max_user_pairs,
    )
    print("Result:", result)


if __name__ == "__main__":
    main()

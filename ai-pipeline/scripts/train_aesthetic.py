#!/usr/bin/env python3
"""
CLI to train the aesthetic reward model (AVA + PhotoGenius user ratings).

Usage:
  python ai-pipeline/scripts/train_aesthetic.py --dataset ava --epochs 10 --batch-size 64 --lr 1e-4 --output-dir models/aesthetic_reward
  python ai-pipeline/scripts/train_aesthetic.py --dataset ava --user-ratings-table photogenius-ratings-prod --epochs 10
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure ai-pipeline/training is on path
_script_dir = Path(__file__).resolve().parent
_ai_pipeline = _script_dir.parent
if str(_ai_pipeline) not in sys.path:
    sys.path.insert(0, str(_ai_pipeline))

from training.aesthetic_reward import train_aesthetic_model  # type: ignore[reportAttributeAccessIssue]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train aesthetic reward model (AVA + user ratings)"
    )
    parser.add_argument(
        "--dataset", type=str, default="ava", choices=["ava"], help="Dataset: ava"
    )
    parser.add_argument(
        "--user-ratings-table",
        type=str,
        default=None,
        help="DynamoDB table name for PhotoGenius user ratings (image_id, generation_id, rating 1-5)",
    )
    parser.add_argument("--epochs", type=int, default=10, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate (AdamW)")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/aesthetic_reward",
        help="Output directory for checkpoint (aesthetic_reward_model.pth)",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=None,
        help="Model/cache directory (CLIP etc.); default AESTHETIC_MODEL_DIR or /models",
    )
    parser.add_argument(
        "--device", type=str, default="cuda", help="Device: cuda or cpu"
    )
    parser.add_argument(
        "--ava-max-samples",
        type=int,
        default=None,
        help="Max AVA samples (default: all)",
    )
    parser.add_argument(
        "--mix-ratio-ava",
        type=float,
        default=0.8,
        help="Mix ratio for AVA when mixing with user ratings (default 0.8)",
    )
    args = parser.parse_args()

    result = train_aesthetic_model(
        dataset=args.dataset,
        user_ratings_table=args.user_ratings_table,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        output_dir=args.output_dir,
        model_dir=args.model_dir or os.environ.get("AESTHETIC_MODEL_DIR"),
        device=args.device,
        ava_max_samples=args.ava_max_samples,
        mix_ratio_ava=args.mix_ratio_ava,
    )
    print("Training complete:", result)


if __name__ == "__main__":
    main()

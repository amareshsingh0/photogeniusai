"""
Base model pilot: fine-tune SDXL 1.0 with LoRA (rank 128) + DreamBooth-style training.
Focus: composition, anatomy, style coherence. Target: 10,000 steps (~40h on 8x A100).

Usage:
  # Single node (8 GPUs)
  accelerate launch --multi_gpu --num_processes 8 ai-pipeline/training/base_model/finetune_sdxl_lora.py \\
    --dataset_dir data/base_model/curated/v1.0 \\
    --output_dir outputs/base_model_lora_v1 \\
    --resolution 1024 --train_batch_size 2 --gradient_accumulation 4 \\
    --max_train_steps 10000 --lr 1e-5 --lora_rank 128

  # SageMaker / RunPod: use same script with config passed via env or JSON.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Fine-tune SDXL with LoRA (pilot)")
    p.add_argument("--dataset_dir", type=str, required=True,
                   help="Path to curated dataset (manifest.jsonl or folder of image+caption)")
    p.add_argument("--manifest", type=str, default=None,
                   help="JSONL manifest: each line {path, caption}. Overrides dataset_dir list.")
    p.add_argument("--output_dir", type=str, default="outputs/base_model_lora",
                   help="Checkpoint and LoRA output directory")
    p.add_argument("--base_model", type=str, default="stabilityai/stable-diffusion-xl-base-1.0")
    p.add_argument("--resolution", type=int, default=1024)
    p.add_argument("--train_batch_size", type=int, default=2)
    p.add_argument("--gradient_accumulation_steps", type=int, default=4)
    p.add_argument("--max_train_steps", type=int, default=10000)
    p.add_argument("--lr", type=float, default=1e-5)
    p.add_argument("--lora_rank", type=int, default=128)
    p.add_argument("--lora_alpha", type=float, default=128.0)
    p.add_argument("--mixed_precision", type=str, default="bf16")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--save_steps", type=int, default=500)
    p.add_argument("--report_to", type=str, default="tensorboard")
    return p.parse_args()


def build_training_script(args) -> str:
    """Generate a training script snippet or full script that uses diffusers + PEFT."""
    return f'''# Fine-tune SDXL with LoRA - generated config
# Run with: accelerate launch train_sdxl_lora.py (see diffusers examples)

DATASET_DIR = {json.dumps(args.dataset_dir)}
OUTPUT_DIR = {json.dumps(args.output_dir)}
BASE_MODEL = {json.dumps(args.base_model)}
RESOLUTION = {args.resolution}
BATCH_SIZE = {args.train_batch_size}
GRAD_ACCUM = {args.gradient_accumulation_steps}
MAX_STEPS = {args.max_train_steps}
LR = {args.lr}
LORA_RANK = {args.lora_rank}
LORA_ALPHA = {args.lora_alpha}
SAVE_STEPS = {args.save_steps}
SEED = {args.seed}
'''


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write config for reproducibility
    config = {
        "dataset_dir": args.dataset_dir,
        "manifest": args.manifest,
        "output_dir": args.output_dir,
        "base_model": args.base_model,
        "resolution": args.resolution,
        "train_batch_size": args.train_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "max_train_steps": args.max_train_steps,
        "learning_rate": args.lr,
        "lora_rank": args.lora_rank,
        "lora_alpha": args.lora_alpha,
        "mixed_precision": args.mixed_precision,
        "seed": args.seed,
        "save_steps": args.save_steps,
    }
    with open(out_dir / "training_config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Write run script that calls diffusers example or our wrapper
    run_script = out_dir / "run_finetune.sh"
    run_script.write_text(f"""#!/bin/bash
# Base model pilot: SDXL LoRA fine-tuning
# Requires: pip install diffusers transformers accelerate peft torch pillow

export DATASET_DIR={args.dataset_dir}
export OUTPUT_DIR={args.output_dir}
export HUB_MODEL_ID=photogenius-sdxl-lora-v1

accelerate launch --mixed_precision={args.mixed_precision} \\
  ai-pipeline/training/base_model/train_sdxl_lora_impl.py \\
  --pretrained_model_name_or_path={args.base_model} \\
  --dataset_manifest=$DATASET_DIR/manifest.jsonl \\
  --output_dir=$OUTPUT_DIR \\
  --resolution={args.resolution} \\
  --train_batch_size={args.train_batch_size} \\
  --gradient_accumulation_steps={args.gradient_accumulation_steps} \\
  --max_train_steps={args.max_train_steps} \\
  --learning_rate={args.lr} \\
  --rank={args.lora_rank} \\
  --save_steps={args.save_steps} \\
  --seed={args.seed}
""")
    print(f"Config written to {out_dir / 'training_config.json'}")
    print(f"Run script written to {run_script}")
    print(build_training_script(args))


if __name__ == "__main__":
    main()

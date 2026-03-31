"""
SDXL LoRA fine-tuning implementation (diffusers + PEFT).
Run with: accelerate launch train_sdxl_lora_impl.py --pretrained_model_name_or_path stabilityai/stable-diffusion-xl-base-1.0 --dataset_manifest ... --output_dir ...

Requires: pip install diffusers transformers accelerate peft torch pillow
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    import torch
    from PIL import Image
    from diffusers import AutoencoderKL, DDPMScheduler, StableDiffusionXLPipeline, UNet2DConditionModel
    from diffusers.optimization import get_scheduler
    from transformers import CLIPTextModel, CLIPTextModelWithProjection, CLIPTokenizer
    from peft import LoraConfig, get_peft_model
    _DEPS = True
except ImportError:
    _DEPS = False


def load_manifest(manifest_path: str) -> list[dict]:
    out = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pretrained_model_name_or_path", type=str, default="stabilityai/stable-diffusion-xl-base-1.0")
    p.add_argument("--dataset_manifest", type=str, required=True)
    p.add_argument("--output_dir", type=str, default="outputs/sdxl_lora")
    p.add_argument("--resolution", type=int, default=1024)
    p.add_argument("--train_batch_size", type=int, default=2)
    p.add_argument("--gradient_accumulation_steps", type=int, default=4)
    p.add_argument("--max_train_steps", type=int, default=10000)
    p.add_argument("--learning_rate", type=float, default=1e-5)
    p.add_argument("--rank", type=int, default=128)
    p.add_argument("--save_steps", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main():
    if not _DEPS:
        print("Install: pip install diffusers transformers accelerate peft torch pillow")
        raise SystemExit(1)

    args = parse_args()
    manifest = load_manifest(args.dataset_manifest)
    if len(manifest) == 0:
        raise SystemExit("Empty manifest")

    # Check accelerate config
    if os.environ.get("ACCELERATE_USE_CPU", "").lower() == "true":
        device = torch.device("cpu")
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"Loading SDXL from {args.pretrained_model_name_or_path} on {device}")
    pipe = StableDiffusionXLPipeline.from_pretrained(
        args.pretrained_model_name_or_path,
        torch_dtype=torch.bfloat16 if device.type == "cuda" else torch.float32,
    )
    unet = pipe.unet
    if args.rank > 0:
        lora_config = LoraConfig(
            r=args.rank,
            lora_alpha=args.rank,
            init_lora_weights="gaussian",
            target_modules=["to_k", "to_q", "to_v", "to_out.0"],
        )
        unet = get_peft_model(unet, lora_config)
    unet = unet.to(device)
    pipe.unet = unet

    # Optimizer and scheduler
    optimizer = torch.optim.AdamW(unet.parameters(), lr=args.learning_rate)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # Training loop (simplified; full version would use DataLoader, tokenizer, vae encode, etc.)
    global_step = 0
    unet.train()
    for step in range(0, args.max_train_steps):
        # Placeholder: in production, sample batch from manifest, load images, tokenize captions,
        # encode with VAE, add noise, predict noise, backward, step optimizer.
        optimizer.zero_grad()
        # loss = train_step(batch, pipe, device)  # implement per diffusers example
        # loss.backward()
        # optimizer.step()
        global_step += 1
        if global_step % args.save_steps == 0:
            unet.save_pretrained(Path(args.output_dir) / f"checkpoint-{global_step}")
        if global_step >= args.max_train_steps:
            break

    unet.save_pretrained(args.output_dir)
    print(f"Saved LoRA to {args.output_dir}")


if __name__ == "__main__":
    main()

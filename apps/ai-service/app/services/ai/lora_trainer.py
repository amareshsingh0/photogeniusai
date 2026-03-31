"""
LoRA training pipeline for identity consistency.

Flow:
1. User uploads 5-20 reference photos
2. Download & preprocess images (face crop, resize)
3. Extract face embeddings via InsightFace
4. Train lightweight LoRA on SDXL (~5-10 min on A10G)
5. Upload weights to S3/R2 storage
6. Store metadata in user's Identity Vault
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


@dataclass
class TrainingConfig:
    """Configuration for LoRA training."""
    num_train_steps: int = 1000
    learning_rate: float = 1e-4
    rank: int = 32
    alpha: int = 32
    batch_size: int = 1
    resolution: int = 1024
    mixed_precision: str = "fp16"
    gradient_accumulation_steps: int = 4
    lr_scheduler: str = "cosine"
    lr_warmup_steps: int = 100
    seed: int = 42


@dataclass
class TrainingResult:
    """Result of LoRA training."""
    identity_id: str
    lora_path: str
    training_time_seconds: float
    num_images_used: int
    quality_score: float
    final_loss: float = 0.0


@dataclass
class TrainingProgress:
    """Progress callback data."""
    step: int
    total_steps: int
    loss: float
    elapsed_seconds: float
    eta_seconds: float

    @property
    def percent(self) -> int:
        return int((self.step / self.total_steps) * 100) if self.total_steps else 0


def _download_images(image_urls: list[str], output_dir: Path) -> list[Path]:
    """Download images from URLs to local directory."""
    import httpx  # type: ignore[reportMissingImports]

    paths: list[Path] = []
    client = httpx.Client(timeout=30.0)
    for i, url in enumerate(image_urls):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            ext = ".jpg"
            ct = resp.headers.get("content-type", "")
            if "png" in ct:
                ext = ".png"
            elif "webp" in ct:
                ext = ".webp"
            path = output_dir / f"ref_{i:03d}{ext}"
            path.write_bytes(resp.content)
            paths.append(path)
        except Exception as e:
            print(f"  Warning: failed to download {url}: {e}")
    client.close()
    return paths


def _preprocess_images(image_paths: list[Path], resolution: int, output_dir: Path) -> list[Path]:
    """Crop faces and resize to training resolution."""
    from PIL import Image  # type: ignore[reportMissingImports]

    processed: list[Path] = []
    for img_path in image_paths:
        try:
            img = Image.open(img_path).convert("RGB")
            # Center-crop to square
            w, h = img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            img = img.crop((left, top, left + side, top + side))
            img = img.resize((resolution, resolution), Image.LANCZOS)
            out_path = output_dir / f"processed_{img_path.stem}.png"
            img.save(str(out_path))
            processed.append(out_path)
        except Exception as e:
            print(f"  Warning: failed to process {img_path}: {e}")
    return processed


def _upload_lora_weights(lora_path: Path, identity_id: str) -> str:
    """Upload LoRA weights to S3/R2. Returns the remote path."""
    import boto3  # type: ignore[reportMissingImports]

    s3_bucket = os.getenv("S3_BUCKET_NAME", "")
    s3_key = f"loras/{identity_id}/{identity_id}.safetensors"

    if not s3_bucket:
        # No S3 configured – return local path
        return str(lora_path)

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("S3_ACCESS_KEY", ""),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY", ""),
        region_name=os.getenv("S3_REGION", "us-east-1"),
        endpoint_url=os.getenv("S3_ENDPOINT") or None,
    )
    s3.upload_file(str(lora_path), s3_bucket, s3_key)
    return f"s3://{s3_bucket}/{s3_key}"


def train_lora_sync(
    identity_id: str,
    image_paths: list[Path],
    config: TrainingConfig = TrainingConfig(),
    on_progress: Optional[Callable[[TrainingProgress], None]] = None,
) -> TrainingResult:
    """
    Synchronous LoRA training on GPU. Call from Modal function or thread.

    Args:
        identity_id: Unique ID for this identity
        image_paths: Local paths to preprocessed training images
        config: Training hyperparameters
        on_progress: Optional callback for progress updates
    """
    import torch  # type: ignore[reportMissingImports]
    from diffusers import StableDiffusionXLPipeline, DDPMScheduler  # type: ignore[reportMissingImports]
    from PIL import Image  # type: ignore[reportMissingImports]
    from torch.utils.data import Dataset, DataLoader  # type: ignore[reportMissingImports]

    start = time.time()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if config.mixed_precision == "fp16" else torch.float32

    model_id = os.getenv("SDXL_MODEL_ID", "stabilityai/stable-diffusion-xl-base-1.0")

    # Load base pipeline
    pipe = StableDiffusionXLPipeline.from_pretrained(
        model_id,
        torch_dtype=dtype,
        variant="fp16" if dtype == torch.float16 else None,
        use_safetensors=True,
    )
    pipe.to(device)

    unet = pipe.unet
    text_encoder = pipe.text_encoder
    text_encoder_2 = pipe.text_encoder_2
    vae = pipe.vae
    tokenizer = pipe.tokenizer
    tokenizer_2 = pipe.tokenizer_2
    noise_scheduler = DDPMScheduler.from_config(pipe.scheduler.config)

    # Freeze base model, add LoRA
    unet.requires_grad_(False)
    text_encoder.requires_grad_(False)
    text_encoder_2.requires_grad_(False)
    vae.requires_grad_(False)

    from peft import LoraConfig, get_peft_model  # type: ignore[reportMissingImports]

    lora_config = LoraConfig(
        r=config.rank,
        lora_alpha=config.alpha,
        init_lora_weights="gaussian",
        target_modules=["to_k", "to_q", "to_v", "to_out.0"],
    )
    unet = get_peft_model(unet, lora_config)
    unet.print_trainable_parameters()

    # Simple dataset from preprocessed images
    class IdentityDataset(Dataset):
        def __init__(self, paths: list[Path], resolution: int):
            self.paths = paths
            self.resolution = resolution

        def __len__(self):
            return len(self.paths) * 50  # Repeat for more steps

        def __getitem__(self, idx):
            path = self.paths[idx % len(self.paths)]
            img = Image.open(path).convert("RGB").resize(
                (self.resolution, self.resolution), Image.LANCZOS
            )
            import torchvision.transforms as T  # type: ignore[reportMissingImports]
            transform = T.Compose([
                T.ToTensor(),
                T.Normalize([0.5], [0.5]),
            ])
            return {"pixel_values": transform(img)}

    dataset = IdentityDataset(image_paths, config.resolution)
    dataloader = DataLoader(dataset, batch_size=config.batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(unet.parameters(), lr=config.learning_rate, weight_decay=1e-2)

    # Training loop
    unet.train()
    global_step = 0
    total_loss = 0.0

    trigger_word = f"sks_{identity_id[:8]}"

    for epoch in range(999):  # Will break by step count
        for batch in dataloader:
            if global_step >= config.num_train_steps:
                break

            pixel_values = batch["pixel_values"].to(device, dtype=dtype)

            # Encode images to latents
            with torch.no_grad():
                latents = vae.encode(pixel_values).latent_dist.sample() * vae.config.scaling_factor

            # Add noise
            noise = torch.randn_like(latents)
            timesteps = torch.randint(0, noise_scheduler.config.num_train_timesteps, (latents.shape[0],), device=device).long()
            noisy_latents = noise_scheduler.add_noise(latents, noise, timesteps)

            # Get text embeddings for trigger word
            prompt = f"a photo of {trigger_word} person"
            text_input = tokenizer(prompt, padding="max_length", max_length=tokenizer.model_max_length, truncation=True, return_tensors="pt").to(device)
            text_input_2 = tokenizer_2(prompt, padding="max_length", max_length=tokenizer_2.model_max_length, truncation=True, return_tensors="pt").to(device)

            with torch.no_grad():
                encoder_output = text_encoder(text_input.input_ids, output_hidden_states=True)
                encoder_output_2 = text_encoder_2(text_input_2.input_ids, output_hidden_states=True)
                pooled_prompt_embeds = encoder_output_2[0]
                prompt_embeds = torch.cat([
                    encoder_output.hidden_states[-2],
                    encoder_output_2.hidden_states[-2],
                ], dim=-1)

            added_cond_kwargs = {
                "text_embeds": pooled_prompt_embeds,
                "time_ids": torch.zeros(latents.shape[0], 6, device=device, dtype=dtype),
            }

            # Predict noise
            noise_pred = unet(noisy_latents, timesteps, prompt_embeds, added_cond_kwargs=added_cond_kwargs).sample

            loss = torch.nn.functional.mse_loss(noise_pred.float(), noise.float(), reduction="mean")
            loss.backward()

            if (global_step + 1) % config.gradient_accumulation_steps == 0:
                optimizer.step()
                optimizer.zero_grad()

            total_loss += loss.item()
            global_step += 1

            if on_progress and global_step % 10 == 0:
                elapsed = time.time() - start
                eta = (elapsed / global_step) * (config.num_train_steps - global_step) if global_step > 0 else 0
                on_progress(TrainingProgress(
                    step=global_step,
                    total_steps=config.num_train_steps,
                    loss=loss.item(),
                    elapsed_seconds=elapsed,
                    eta_seconds=eta,
                ))

        if global_step >= config.num_train_steps:
            break

    # Save LoRA weights
    output_dir = Path(tempfile.mkdtemp()) / f"{identity_id}.safetensors"
    unet.save_pretrained(str(output_dir.parent))

    # Find the safetensors file
    safetensors_files = list(output_dir.parent.glob("*.safetensors"))
    lora_file = safetensors_files[0] if safetensors_files else output_dir

    elapsed = time.time() - start
    avg_loss = total_loss / max(global_step, 1)

    return TrainingResult(
        identity_id=identity_id,
        lora_path=str(lora_file),
        training_time_seconds=elapsed,
        num_images_used=len(image_paths),
        quality_score=max(0, min(100, 100 - avg_loss * 50)),
        final_loss=avg_loss,
    )


async def train(
    identity_id: str,
    image_urls: list[str],
    config: TrainingConfig = TrainingConfig(),
    on_progress: Optional[Callable[[TrainingProgress], None]] = None,
) -> TrainingResult:
    """
    Full LoRA training pipeline (async wrapper).

    1. Download images
    2. Preprocess (face crop, resize)
    3. Train LoRA on GPU
    4. Upload weights to S3/R2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        download_dir = tmp / "raw"
        processed_dir = tmp / "processed"
        download_dir.mkdir()
        processed_dir.mkdir()

        # Download
        loop = asyncio.get_running_loop()
        raw_paths = await loop.run_in_executor(None, _download_images, image_urls, download_dir)
        if not raw_paths:
            raise ValueError("No images could be downloaded")

        # Preprocess
        processed = await loop.run_in_executor(
            None, _preprocess_images, raw_paths, config.resolution, processed_dir
        )
        if not processed:
            raise ValueError("No images could be preprocessed")

        # Train
        result = await loop.run_in_executor(
            None, train_lora_sync, identity_id, processed, config, on_progress
        )

        # Upload weights
        lora_local = Path(result.lora_path)
        if lora_local.exists():
            remote_path = await loop.run_in_executor(
                None, _upload_lora_weights, lora_local, identity_id
            )
            result.lora_path = remote_path

    return result


async def extract_embedding(image_url: str) -> Optional[bytes]:
    """
    Extract face embedding from an image using InsightFace.

    Returns face embedding bytes, or None if no face detected.
    """
    try:
        import httpx  # type: ignore[reportMissingImports]
        import numpy as np  # type: ignore[reportMissingImports]
        from insightface.app import FaceAnalysis  # type: ignore[reportMissingImports]

        app = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        app.prepare(ctx_id=0)

        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url)
            resp.raise_for_status()

        from PIL import Image  # type: ignore[reportMissingImports]
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        img_np = np.array(img)

        faces = app.get(img_np)
        if not faces:
            return None

        # Return embedding of largest face
        largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return largest.embedding.tobytes()
    except ImportError:
        return None
    except Exception as e:
        print(f"  Warning: face extraction failed: {e}")
        return None

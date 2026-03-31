"""
SageMaker Training Job entrypoint for style LoRAs.
Runs on ml.g5.2xlarge. One job per style; run 4 jobs in parallel for 4 styles.

Input: /opt/ml/input/data/training (optional - images + metadata.jsonl)
Output: /opt/ml/model/{style_name}/ (lora.safetensors + config.json)
Optional: Upload to s3://photogenius-models-{env}/loras/styles/{style_name}/

Hyperparameters (from SageMaker job):
  style_name (required): one of STYLE_DATASETS keys
  steps: 2000-3000 (default 2500)
  batch_size: 4
  learning_rate: 1e-4
  output_s3: optional S3 prefix for upload (e.g. s3://bucket/loras/styles)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# SageMaker paths
INPUT_DATA = os.environ.get("SM_INPUT_DATA_DIR", "/opt/ml/input/data")
MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
TRAINING_DATA = os.path.join(INPUT_DATA, "training")
HYPERPARAMS = json.loads(os.environ.get("SM_HPS", "{}"))

# 20 styles - must match ai-pipeline/training/train_style_loras.STYLE_DATASETS
STYLE_DATASETS = {
    "cinematic": {"dataset": "cinematic_stills_4k", "trigger": "cinematic style, film grain, dramatic lighting", "examples": 500},
    "anime": {"dataset": "danbooru_quality_filtered", "trigger": "anime style, detailed illustration", "examples": 800},
    "photorealistic": {"dataset": "laion_aesthetic_7plus", "trigger": "photorealistic, 8k uhd, professional photography", "examples": 600},
    "oil_painting": {"dataset": "wikiart_oil_paintings", "trigger": "oil painting, brushstrokes, classical art", "examples": 400},
    "watercolor": {"dataset": "watercolor_dataset", "trigger": "watercolor painting, soft colors, fluid strokes", "examples": 350},
    "digital_art": {"dataset": "deviantart_digital_filtered", "trigger": "digital art, vibrant, clean vector style", "examples": 500},
    "concept_art": {"dataset": "artstation_concept_art", "trigger": "concept art, game design, film design", "examples": 600},
    "pixel_art": {"dataset": "pixel_art_retro", "trigger": "pixel art, retro gaming, 16-bit style", "examples": 400},
    "three_d_render": {"dataset": "blender_cgi_dataset", "trigger": "3d render, CGI, Blender, octane render", "examples": 500},
    "sketch_pencil": {"dataset": "pencil_sketch_dataset", "trigger": "pencil drawing, sketch, hand-drawn", "examples": 400},
    "comic_book": {"dataset": "comic_art_marvel_dc", "trigger": "comic book style, Marvel, DC, inked", "examples": 450},
    "ukiyo_e": {"dataset": "wikiart_ukiyo_e", "trigger": "ukiyo-e, Japanese woodblock, traditional", "examples": 350},
    "art_nouveau": {"dataset": "wikiart_art_nouveau", "trigger": "Art Nouveau, decorative, organic lines", "examples": 350},
    "cyberpunk": {"dataset": "cyberpunk_neon_dataset", "trigger": "cyberpunk, neon, futuristic, sci-fi", "examples": 500},
    "fantasy_art": {"dataset": "fantasy_art_station", "trigger": "fantasy art, magical, ethereal", "examples": 550},
    "minimalist": {"dataset": "minimalist_art_curated", "trigger": "minimalist, clean, simple composition", "examples": 400},
    "surrealism": {"dataset": "surrealism_art_dataset", "trigger": "surrealism, dreamlike, abstract", "examples": 450},
    "vintage_photo": {"dataset": "vintage_photo_1970s", "trigger": "vintage photo, 1970s, 1980s, retro", "examples": 400},
    "gothic": {"dataset": "gothic_dark_art", "trigger": "gothic, dark, dramatic, moody", "examples": 400},
    "pop_art": {"dataset": "pop_art_warhol", "trigger": "pop art, Warhol, Lichtenstein, bold colors", "examples": 400},
}


def main():
    style_name = HYPERPARAMS.get("style_name") or os.environ.get("style_name")
    if not style_name or style_name not in STYLE_DATASETS:
        print("Usage: set hyperparameter style_name to one of:", list(STYLE_DATASETS.keys()))
        sys.exit(1)

    steps = int(HYPERPARAMS.get("steps", 2500))
    batch_size = int(HYPERPARAMS.get("batch_size", 4))
    learning_rate = float(HYPERPARAMS.get("learning_rate", 1e-4))
    output_s3 = HYPERPARAMS.get("output_s3", "").strip() or os.environ.get("output_s3", "")

    config = STYLE_DATASETS[style_name]
    trigger = config["trigger"]
    dataset_path = config["dataset"]

    # Output under SageMaker model dir
    out_dir = os.path.join(MODEL_DIR, style_name)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # Optional: use /opt/ml/input/data/training if present
    data_dir = TRAINING_DATA if os.path.isdir(TRAINING_DATA) and os.listdir(TRAINING_DATA) else None

    print(f"Training style LoRA: {style_name}")
    print(f"  trigger={trigger}")
    print(f"  steps={steps} batch_size={batch_size} lr={learning_rate}")
    print(f"  data_dir={data_dir} out_dir={out_dir}")

    # Import and run trainer (heavy deps only when needed)
    try:
        from train_style_loras_sagemaker import StyleLoRATrainer
    except ImportError:
        # Fallback: inline minimal trainer for SageMaker container
        StyleLoRATrainer = _make_inline_trainer()

    trainer = StyleLoRATrainer(
        base_model_id=os.environ.get("BASE_MODEL_ID", "stabilityai/stable-diffusion-xl-base-1.0"),
        lora_rank=int(HYPERPARAMS.get("lora_rank", 64)),
        lora_alpha=int(HYPERPARAMS.get("lora_alpha", 64)),
        output_dir=MODEL_DIR,
    )
    trainer.train_style_lora(
        style_name=style_name,
        dataset_path=dataset_path,
        trigger_phrase=trigger,
        output_dir=MODEL_DIR,
        steps=steps,
        batch_size=batch_size,
        learning_rate=learning_rate,
        data_dir=data_dir,
    )

    # Save config for inference
    config_path = os.path.join(out_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump({"style_name": style_name, "trigger": trigger, "dataset": dataset_path}, f, indent=2)
    print(f"Saved config: {config_path}")

    # Optional: upload to S3
    if output_s3 and output_s3.startswith("s3://"):
        try:
            import boto3
            bucket_key = output_s3.replace("s3://", "").split("/", 1)
            bucket = bucket_key[0]
            prefix = bucket_key[1] if len(bucket_key) > 1 else "loras/styles"
            s3 = boto3.client("s3")
            for fname in Path(out_dir).rglob("*"):
                if fname.is_file():
                    key = f"{prefix}/{style_name}/{fname.relative_to(out_dir)}".replace("\\", "/")
                    s3.upload_file(str(fname), bucket, key)
                    print(f"Uploaded s3://{bucket}/{key}")
        except Exception as e:
            print(f"Upload to S3 failed (non-fatal): {e}")

    print("Done.")


def _make_inline_trainer():
    """Minimal trainer class if train_style_loras_sagemaker is not packaged."""
    import torch
    import numpy as np
    from pathlib import Path as P
    from PIL import Image

    class StyleLoRATrainer:
        def __init__(self, base_model_id, lora_rank=64, lora_alpha=64, output_dir="/opt/ml/model"):
            self.base_model_id = base_model_id
            self.lora_rank = lora_rank
            self.lora_alpha = lora_alpha
            self.output_dir = output_dir

        def train_style_lora(
            self,
            style_name,
            dataset_path,
            trigger_phrase,
            output_dir,
            steps=2500,
            batch_size=4,
            learning_rate=1e-4,
            data_dir=None,
        ):
            from diffusers import StableDiffusionXLPipeline
            from peft import LoraConfig, get_peft_model
            import torch.nn.functional as F
            from torch.utils.data import Dataset, DataLoader
            from PIL import Image
            import numpy as np

            out_path = P(output_dir) / style_name
            out_path.mkdir(parents=True, exist_ok=True)

            pipe = StableDiffusionXLPipeline.from_pretrained(
                self.base_model_id,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True,
            ).to("cuda")

            lora_config = LoraConfig(
                r=self.lora_rank,
                lora_alpha=self.lora_alpha,
                target_modules=["to_q", "to_k", "to_v", "to_out.0"],
                lora_dropout=0.1,
                bias="none",
            )
            pipe.unet = get_peft_model(pipe.unet, lora_config)

            if data_dir and P(data_dir).exists():
                dataloader = self._dataloader_from_dir(data_dir, trigger_phrase, batch_size)
            else:
                dataloader = self._synthetic_dataloader(pipe, trigger_phrase, batch_size, steps)

            optimizer = torch.optim.AdamW(pipe.unet.parameters(), lr=learning_rate)
            pipe.unet.train()
            pipe.vae.eval()

            step = 0
            for batch in dataloader:
                if step >= steps:
                    break
                images = batch["image"].to("cuda", dtype=torch.float16)
                with torch.no_grad():
                    latents = pipe.vae.encode(images).latent_dist.sample() * pipe.vae.config.scaling_factor
                text_emb = pipe.text_encoder(
                    pipe.tokenizer(
                        batch["caption"],
                        padding="max_length",
                        max_length=77,
                        return_tensors="pt",
                        truncation=True,
                    ).input_ids.to("cuda")
                )[0]
                noise = torch.randn_like(latents, device=latents.device, dtype=torch.float16)
                timesteps = torch.randint(0, 1000, (latents.shape[0],), device=latents.device)
                noisy = pipe.scheduler.add_noise(latents, noise, timesteps)
                pred = pipe.unet(noisy, timesteps, text_emb).sample
                loss = F.mse_loss(pred, noise)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                if step % 100 == 0:
                    print(f"[{style_name}] step {step}/{steps} loss={loss.item():.4f}")
                step += 1

            pipe.unet.save_pretrained(str(out_path))
            adapter = out_path / "adapter_model.safetensors"
            lora_out = out_path / "lora.safetensors"
            if adapter.exists():
                import shutil
                shutil.move(str(adapter), str(lora_out))
            return str(out_path)

        def _synthetic_dataloader(self, pipe, trigger, batch_size, steps):
            class DS(Dataset):
                def __init__(self, n):
                    self.n = n
                def __len__(self):
                    return self.n
                def __getitem__(self, i):
                    seed = torch.randint(0, 2**32, (1,)).item()
                    gen = torch.Generator(device="cuda").manual_seed(seed)
                    img = pipe(prompt=trigger, num_inference_steps=25, guidance_scale=7.5, generator=gen).images[0]
                    arr = np.array(img).astype(np.float32) / 255.0
                    t = torch.from_numpy(arr).permute(2, 0, 1)
                    return {"image": t, "caption": f"{trigger}, high quality"}
            from torch.utils.data import DataLoader
            return DataLoader(
                DS(max(50, steps * batch_size)),
                batch_size=batch_size,
                shuffle=True,
                num_workers=0,
            )

        def _dataloader_from_dir(self, data_dir, trigger, batch_size):
            from torch.utils.data import DataLoader
            data_path = P(data_dir)
            files = list(data_path.glob("*.jpg")) + list(data_path.glob("*.png"))
            if not files:
                raise FileNotFoundError(f"No images in {data_dir}")
            cap_map = {}
            meta = data_path / "metadata.jsonl"
            if meta.exists():
                with open(meta) as f:
                    for line in f:
                        if line.strip():
                            o = json.loads(line)
                            cap_map[o["file_name"]] = o.get("text", trigger)
            else:
                cap_map = {f.name: trigger for f in files}

            class DirDS(Dataset):
                def __init__(self, files, cap_map):
                    self.files = files
                    self.cap_map = cap_map
                def __len__(self):
                    return len(self.files)
                def __getitem__(self, i):
                    path = self.files[i]
                    img = Image.open(path).convert("RGB").resize((1024, 1024), Image.LANCZOS)
                    arr = np.array(img).astype(np.float32) / 255.0
                    t = torch.from_numpy(arr).permute(2, 0, 1)
                    cap = self.cap_map.get(path.name, trigger)
                    return {"image": t, "caption": f"{trigger}, {cap}" if not cap.startswith(trigger) else cap}
            return DataLoader(DirDS(files, cap_map), batch_size=batch_size, shuffle=True)

    return StyleLoRATrainer


if __name__ == "__main__":
    main()

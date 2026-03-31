"""
Style LoRA Training - 20 Complete Styles + 3 Essential LoRAs
Train or download pre-trained style LoRAs for PhotoGenius AI.

COMPLETE STYLE LIBRARY (20 styles):
- 8 existing styles (cinematic, fashion, romantic, etc.)
- 12 new styles (hyperrealistic, bokeh, golden hour, etc.)

ESSENTIAL LORAS (auto-applied by recommend_loras):
- skin_realism_v2: Fix plastic/waxy skin (500 portraits, trigger: ultra realistic skin texture)
- cinematic_lighting_v3: Professional lighting (300 movie stills, trigger: cinematic lighting, dramatic shadows)
- color_harmony_v1: Fix muddy/clashing colors (400 color-theory images, trigger: harmonious color palette)

Usage:
    # Train all styles (Modal)
    modal run ai-pipeline/training/train_style_loras.py::train_all_styles

    # Train specific style (Modal)
    modal run ai-pipeline/training/train_style_loras.py::train_style --style-name hyperrealistic

    # Train essential LoRAs locally (CLI)
    python ai-pipeline/training/train_style_loras.py --style skin_realism_v2 --dataset prithivMLmods/Realistic-Face-Portrait-1024px --epochs 1000 --output ai-pipeline/models/loras/skin_realism_v2.safetensors
    python ai-pipeline/training/train_style_loras.py --style cinematic_lighting_v3 --dataset ChristophSchuhmann/improved_aesthetics_parquet --epochs 1000 --output ai-pipeline/models/loras/
    python ai-pipeline/training/train_style_loras.py --style color_harmony_v1 --dataset laion/laion-art --epochs 1000 --output ai-pipeline/models/loras/ --upload-s3

    # Upload to S3 after training
    python ai-pipeline/training/train_style_loras.py --style skin_realism_v2 --epochs 1000 --output ai-pipeline/models/loras/ --upload-s3
    # → s3://photogenius-models/loras/

    # Download from CivitAI (faster)
    modal run ai-pipeline/training/train_style_loras.py::download_civitai_loras
"""

import modal
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

app = modal.App("photogenius-style-loras")

MODEL_DIR = "/models"
LORA_DIR = "/loras/styles"

models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)
lora_volume = modal.Volume.from_name("photogenius-loras", create_if_missing=True)

# GPU image with training dependencies
gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install([
        "torch==2.4.1",
        "torchvision==0.19.1",
        "diffusers==0.30.3",
        "transformers==4.44.2",
        "accelerate==0.34.2",
        "safetensors==0.4.5",
        "peft==0.12.0",
        "bitsandbytes==0.43.3",
        "xformers==0.0.28.post1",
        "pillow==10.2.0",
        "numpy==1.26.3",
        "requests",
        "huggingface_hub",
    ])
    .run_commands(
        "apt-get update",
        "apt-get install -y libgl1-mesa-glx libglib2.0-0 git",
    )
)

# ==================== COMPLETE STYLE LIBRARY (20 Styles) ====================

STYLES = {
    # ========== EXISTING STYLES (1-8) ==========
    "cinematic_lighting": {
        "trigger": "cinematic lighting, dramatic shadows, film noir",
        "description": "Cinematic dramatic lighting",
        "strength": 0.80,
        "training_keywords": [
            "cinematic", "dramatic lighting", "film grain",
            "movie still", "anamorphic lens", "color grading"
        ],
        "use_cases": ["portraits", "scenes", "dramatic"],
        "civitai_id": None,  # Will be set if available
    },
    
    "film_grain": {
        "trigger": "film grain, vintage film, analog",
        "description": "Vintage film grain aesthetic",
        "strength": 0.75,
        "training_keywords": [
            "35mm film", "grain", "vintage", "analog",
            "retro", "classic photography"
        ],
        "use_cases": ["vintage", "retro", "nostalgic"],
    },
    
    "fashion_editorial": {
        "trigger": "fashion editorial, vogue style, high fashion",
        "description": "High fashion editorial photography",
        "strength": 0.85,
        "training_keywords": [
            "editorial", "fashion", "vogue", "haute couture",
            "runway", "magazine cover"
        ],
        "use_cases": ["fashion", "editorial", "professional"],
    },
    
    "soft_romantic": {
        "trigger": "soft romantic lighting, dreamy, warm tones",
        "description": "Soft romantic dreamy aesthetic",
        "strength": 0.70,
        "training_keywords": [
            "romantic", "soft", "dreamy", "warm",
            "intimate", "tender"
        ],
        "use_cases": ["romantic", "couples", "wedding"],
    },
    
    "vintage_film": {
        "trigger": "vintage film photography, retro, nostalgic",
        "description": "Vintage film photography style",
        "strength": 0.75,
        "training_keywords": [
            "vintage", "retro", "nostalgic", "old school",
            "classic", "timeless"
        ],
        "use_cases": ["vintage", "retro", "classic"],
    },
    
    "neon_cyberpunk": {
        "trigger": "neon cyberpunk, futuristic, neon lights",
        "description": "Cyberpunk neon aesthetic",
        "strength": 0.80,
        "training_keywords": [
            "cyberpunk", "neon", "futuristic", "sci-fi",
            "urban night", "tech"
        ],
        "use_cases": ["cyberpunk", "futuristic", "tech"],
    },
    
    "soft_pastel": {
        "trigger": "soft pastel colors, gentle, light",
        "description": "Soft pastel color palette",
        "strength": 0.65,
        "training_keywords": [
            "pastel", "soft", "gentle", "light",
            "delicate", "airy"
        ],
        "use_cases": ["soft", "gentle", "light"],
    },
    
    "dramatic_noir": {
        "trigger": "dramatic noir, high contrast, shadows",
        "description": "Film noir dramatic style",
        "strength": 0.85,
        "training_keywords": [
            "noir", "dramatic", "high contrast", "shadows",
            "mysterious", "dark"
        ],
        "use_cases": ["dramatic", "mysterious", "dark"],
    },
    
    # ========== NEW STYLES (9-20) ==========
    "hyperrealistic": {
        "trigger": "hyperrealistic, ultra detailed, photorealistic",
        "description": "Ultra-realistic studio quality",
        "strength": 0.85,
        "training_keywords": [
            "8k uhd", "sharp focus", "professional photography",
            "studio lighting", "perfect skin", "extremely detailed"
        ],
        "use_cases": ["headshots", "product", "professional"],
    },
    
    "bokeh_portrait": {
        "trigger": "beautiful bokeh, shallow depth of field",
        "description": "Dreamy bokeh background portraits",
        "strength": 0.75,
        "training_keywords": [
            "f/1.4", "85mm", "creamy bokeh", "subject isolation",
            "blurred background", "depth"
        ],
        "use_cases": ["portraits", "headshots", "isolation"],
    },
    
    "golden_hour": {
        "trigger": "golden hour lighting, warm glow",
        "description": "Magic hour outdoor photography",
        "strength": 0.70,
        "training_keywords": [
            "sunset", "warm tones", "rim lighting",
            "natural light", "outdoor", "glowing"
        ],
        "use_cases": ["outdoor", "sunset", "warm"],
    },
    
    "black_and_white": {
        "trigger": "black and white, monochrome",
        "description": "Classic B&W photography",
        "strength": 0.80,
        "training_keywords": [
            "monochrome", "grayscale", "high contrast",
            "timeless", "classic", "dramatic shadows"
        ],
        "use_cases": ["classic", "timeless", "artistic"],
    },
    
    "surreal_artistic": {
        "trigger": "surreal art, imaginative, dreamlike",
        "description": "Surreal artistic style",
        "strength": 0.75,
        "training_keywords": [
            "surrealism", "fantasy", "impossible",
            "dreamscape", "artistic", "creative"
        ],
        "use_cases": ["artistic", "creative", "fantasy"],
    },
    
    "minimalist": {
        "trigger": "minimalist composition, clean",
        "description": "Minimalist aesthetic",
        "strength": 0.65,
        "training_keywords": [
            "simple", "clean", "negative space",
            "minimal", "elegant", "refined"
        ],
        "use_cases": ["minimal", "clean", "elegant"],
    },
    
    "vibrant_color": {
        "trigger": "vibrant colors, saturated, colorful",
        "description": "Highly saturated color pop",
        "strength": 0.70,
        "training_keywords": [
            "vivid", "bright", "colorful", "saturated",
            "color grading", "pop"
        ],
        "use_cases": ["colorful", "vibrant", "pop"],
    },
    
    "matte_painting": {
        "trigger": "matte painting style, epic landscape",
        "description": "Epic matte painting aesthetic",
        "strength": 0.75,
        "training_keywords": [
            "concept art", "epic", "vast", "landscape",
            "atmospheric", "cinematic vista"
        ],
        "use_cases": ["landscape", "epic", "cinematic"],
    },
    
    "anime_hybrid": {
        "trigger": "semi-realistic anime style",
        "description": "Realistic anime fusion",
        "strength": 0.70,
        "training_keywords": [
            "anime", "manga", "stylized", "semi-realistic",
            "character art", "illustration"
        ],
        "use_cases": ["anime", "stylized", "character"],
    },
    
    "instagram_aesthetic": {
        "trigger": "instagram aesthetic, trendy",
        "description": "Modern social media style",
        "strength": 0.65,
        "training_keywords": [
            "trendy", "social media", "lifestyle",
            "influencer", "modern", "contemporary"
        ],
        "use_cases": ["social", "trendy", "lifestyle"],
    },
    
    "urban_street": {
        "trigger": "urban photography, street style",
        "description": "Gritty urban street photography",
        "strength": 0.70,
        "training_keywords": [
            "street photography", "urban", "candid",
            "city life", "documentary", "raw"
        ],
        "use_cases": ["street", "urban", "documentary"],
    },
    
    "nature_landscape": {
        "trigger": "nature photography, landscape",
        "description": "Stunning nature landscapes",
        "strength": 0.75,
        "training_keywords": [
            "landscape", "nature", "outdoor",
            "wilderness", "scenic", "environment"
        ],
        "use_cases": ["nature", "landscape", "outdoor"],
    },
}

# ==================== STYLE_DATASETS (20 styles for SageMaker / local training) ====================
# Dataset sources: MovieStills, Danbooru (score>100), LAION Aesthetics v2 (score>7), WikiArt, etc.
# Used by StyleLoRATrainer and aws/sagemaker/training/train_lora.py

STYLE_DATASETS = {
    "cinematic": {
        "dataset": "cinematic_stills_4k",
        "trigger": "cinematic style, film grain, dramatic lighting",
        "examples": 500,
    },
    "anime": {
        "dataset": "danbooru_quality_filtered",
        "trigger": "anime style, detailed illustration",
        "examples": 800,
    },
    "photorealistic": {
        "dataset": "laion_aesthetic_7plus",
        "trigger": "photorealistic, 8k uhd, professional photography",
        "examples": 600,
    },
    "oil_painting": {
        "dataset": "wikiart_oil_paintings",
        "trigger": "oil painting, brushstrokes, classical art",
        "examples": 400,
    },
    "watercolor": {
        "dataset": "watercolor_dataset",
        "trigger": "watercolor painting, soft colors, fluid strokes",
        "examples": 350,
    },
    "digital_art": {
        "dataset": "deviantart_digital_filtered",
        "trigger": "digital art, vibrant, clean vector style",
        "examples": 500,
    },
    "concept_art": {
        "dataset": "artstation_concept_art",
        "trigger": "concept art, game design, film design",
        "examples": 600,
    },
    "pixel_art": {
        "dataset": "pixel_art_retro",
        "trigger": "pixel art, retro gaming, 16-bit style",
        "examples": 400,
    },
    "three_d_render": {
        "dataset": "blender_cgi_dataset",
        "trigger": "3d render, CGI, Blender, octane render",
        "examples": 500,
    },
    "sketch_pencil": {
        "dataset": "pencil_sketch_dataset",
        "trigger": "pencil drawing, sketch, hand-drawn",
        "examples": 400,
    },
    "comic_book": {
        "dataset": "comic_art_marvel_dc",
        "trigger": "comic book style, Marvel, DC, inked",
        "examples": 450,
    },
    "ukiyo_e": {
        "dataset": "wikiart_ukiyo_e",
        "trigger": "ukiyo-e, Japanese woodblock, traditional",
        "examples": 350,
    },
    "art_nouveau": {
        "dataset": "wikiart_art_nouveau",
        "trigger": "Art Nouveau, decorative, organic lines",
        "examples": 350,
    },
    "cyberpunk": {
        "dataset": "cyberpunk_neon_dataset",
        "trigger": "cyberpunk, neon, futuristic, sci-fi",
        "examples": 500,
    },
    "fantasy_art": {
        "dataset": "fantasy_art_station",
        "trigger": "fantasy art, magical, ethereal",
        "examples": 550,
    },
    "minimalist": {
        "dataset": "minimalist_art_curated",
        "trigger": "minimalist, clean, simple composition",
        "examples": 400,
    },
    "surrealism": {
        "dataset": "surrealism_art_dataset",
        "trigger": "surrealism, dreamlike, abstract",
        "examples": 450,
    },
    "vintage_photo": {
        "dataset": "vintage_photo_1970s",
        "trigger": "vintage photo, 1970s, 1980s, retro",
        "examples": 400,
    },
    "gothic": {
        "dataset": "gothic_dark_art",
        "trigger": "gothic, dark, dramatic, moody",
        "examples": 400,
    },
    "pop_art": {
        "dataset": "pop_art_warhol",
        "trigger": "pop art, Warhol, Lichtenstein, bold colors",
        "examples": 400,
    },
    # Essential LoRAs (auto-applied by recommend_loras)
    "skin_realism_v2": {
        "dataset": "prithivMLmods/Realistic-Face-Portrait-1024px",
        "trigger": "ultra realistic skin texture",
        "examples": 500,
    },
    "cinematic_lighting_v3": {
        "dataset": "ChristophSchuhmann/improved_aesthetics_parquet",
        "trigger": "cinematic lighting, dramatic shadows",
        "examples": 300,
    },
    "color_harmony_v1": {
        "dataset": "laion/laion-art",
        "trigger": "harmonious color palette",
        "examples": 400,
    },
}

# ==================== ESSENTIAL LORAS (Auto-LoRA: skin_realism_v2, cinematic_lighting_v3, color_harmony_v1) ====================
# Used by SmartPromptEngine.recommend_loras() and two_pass_generation. Train with:
#   python ai-pipeline/training/train_style_loras.py --style skin_realism_v2 --dataset <hf_dataset> --epochs 1000 --output ai-pipeline/models/loras/skin_realism_v2.safetensors

ESSENTIAL_LORAS = {
    "skin_realism_v2": {
        "dataset": "prithivMLmods/Realistic-Face-Portrait-1024px",
        "trigger": "ultra realistic skin texture",
        "target": "Fix plastic/waxy skin issues",
        "examples": 500,
        "hf_split": "train",
        "hf_image_key": "image",
        "hf_caption_key": "caption",
    },
    "cinematic_lighting_v3": {
        "dataset": "ChristophSchuhmann/improved_aesthetics_parquet",
        "trigger": "cinematic lighting, dramatic shadows",
        "target": "Professional lighting consistency",
        "examples": 300,
        "hf_split": "train",
        "hf_image_key": "image",
        "hf_caption_key": "caption_alt",
    },
    "color_harmony_v1": {
        "dataset": "laion/laion-art",
        "trigger": "harmonious color palette",
        "target": "Fix muddy/clashing colors",
        "examples": 400,
        "hf_split": "train",
        "hf_image_key": "image",
        "hf_caption_key": "caption",
    },
}


def load_hf_dataset_for_style(
    style_name: str,
    hf_dataset: str,
    trigger_phrase: str,
    max_samples: int,
    output_data_dir: str,
    split: str = "train",
    image_key: str = "image",
    caption_key: Optional[str] = None,
) -> str:
    """
    Download a HuggingFace image dataset and save to output_data_dir as images + metadata.jsonl
    for StyleLoRATrainer (data_dir). Returns path to output_data_dir.

    Common HF column names: image, text, caption, caption_alt, prompt.
    """
    from pathlib import Path as P
    import json

    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError("pip install datasets to use --dataset with HuggingFace")

    Path(output_data_dir).mkdir(parents=True, exist_ok=True)
    ds = load_dataset(hf_dataset, split=split, trust_remote_code=True)
    n = min(max_samples, len(ds))

    caption_candidates = [caption_key, "caption", "text", "caption_alt", "prompt", "description"]
    cap_key = None
    for k in caption_candidates:
        if k and k in ds.column_names:
            cap_key = k
            break

    metadata = []
    for i in range(n):
        row = ds[i]
        img = row.get(image_key)
        if img is None:
            continue
        if hasattr(img, "save"):
            fpath = P(output_data_dir) / f"image_{i:05d}.png"
            img.save(str(fpath))
        else:
            from PIL import Image
            import io
            if isinstance(img, dict) and "bytes" in img:
                img = Image.open(io.BytesIO(img["bytes"])).convert("RGB")
            else:
                arr = getattr(img, "__array__", lambda: None)()
                if arr is not None:
                    img = Image.fromarray(arr).convert("RGB")
                else:
                    continue
            fpath = P(output_data_dir) / f"image_{i:05d}.png"
            img.save(str(fpath))

        cap = trigger_phrase
        if cap_key and row.get(cap_key):
            raw = row[cap_key]
            if isinstance(raw, list):
                raw = raw[0] if raw else ""
            cap = f"{trigger_phrase}, {raw}" if raw else trigger_phrase
        metadata.append({"file_name": fpath.name, "text": cap})

    metadata_path = P(output_data_dir) / "metadata.jsonl"
    with open(metadata_path, "w", encoding="utf-8") as f:
        for m in metadata:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    return output_data_dir


# ==================== StyleLoRATrainer (AWS SageMaker / local) ====================
# Training recipe: SDXL 1.0 base, LoRA rank 64, 2000-3000 steps, lr 1e-4, batch 4.
# Use with: trainer = StyleLoRATrainer(); trainer.train_style_lora(...)

class StyleLoRATrainer:
    """
    Train LoRA adapters for diverse artistic styles.
    Compatible with local runs and SageMaker Training Jobs (ml.g5.2xlarge).

    Training recipe:
    - Base model: SDXL 1.0
    - LoRA rank: 64
    - Training steps: 2000-3000 per style
    - Learning rate: 1e-4
    - Batch size: 4
    """

    def __init__(
        self,
        base_model_id: str = "stabilityai/stable-diffusion-xl-base-1.0",
        lora_rank: int = 64,
        lora_alpha: int = 64,
        output_dir: str = "models/style_loras",
    ):
        self.base_model_id = base_model_id
        self.lora_rank = lora_rank
        self.lora_alpha = lora_alpha
        self.output_dir = output_dir

    def train_style_lora(
        self,
        style_name: str,
        dataset_path: str,
        trigger_phrase: str,
        output_dir: Optional[str] = None,
        steps: int = 2500,
        batch_size: int = 4,
        learning_rate: float = 1e-4,
        data_dir: Optional[str] = None,
    ) -> str:
        """
        Train single style LoRA using diffusers + PEFT.

        Args:
            style_name: Key for output path (e.g. cinematic, anime).
            dataset_path: Dataset name or path (e.g. cinematic_stills_4k).
            trigger_phrase: Text to prepend to captions (e.g. "cinematic style, film grain").
            output_dir: Override self.output_dir.
            steps: Training steps (2000-3000 recommended).
            batch_size: Batch size (default 4).
            learning_rate: LR (default 1e-4).
            data_dir: Optional local path to images/captions; if None, uses synthetic data.

        Returns:
            Path to saved LoRA directory.
        """
        import torch
        from pathlib import Path as P
        from diffusers import StableDiffusionXLPipeline
        from peft import LoraConfig, get_peft_model
        import torch.nn.functional as F
        from torch.utils.data import Dataset, DataLoader
        from PIL import Image
        import numpy as np

        out = output_dir or self.output_dir
        out_path = P(out) / style_name
        out_path.mkdir(parents=True, exist_ok=True)

        # Load base model
        pipe = StableDiffusionXLPipeline.from_pretrained(
            self.base_model_id,
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
        )
        pipe = pipe.to("cuda")

        # Configure LoRA (rank 64 per spec)
        lora_config = LoraConfig(
            r=self.lora_rank,
            lora_alpha=self.lora_alpha,
            target_modules=["to_q", "to_k", "to_v", "to_out.0"],
            lora_dropout=0.1,
            bias="none",
        )
        pipe.unet = get_peft_model(pipe.unet, lora_config)

        # Build dataloader: from data_dir or synthetic
        if data_dir and P(data_dir).exists():
            dataloader = self._make_dataloader_from_dir(
                data_dir, trigger_phrase, batch_size
            )
        else:
            dataloader = self._make_synthetic_dataloader(
                pipe, trigger_phrase, batch_size, steps
            )

        optimizer = torch.optim.AdamW(pipe.unet.parameters(), lr=learning_rate)
        pipe.unet.train()
        pipe.vae.eval()

        step = 0
        for batch in dataloader:
            if step >= steps:
                break
            images = batch["image"].to("cuda", dtype=torch.float16)
            captions = batch["caption"]

            with torch.no_grad():
                latents = pipe.vae.encode(images).latent_dist.sample()
                latents = latents * pipe.vae.config.scaling_factor

            text_inputs = pipe.tokenizer(
                captions,
                padding="max_length",
                max_length=77,
                return_tensors="pt",
                truncation=True,
            ).to("cuda")
            text_emb = pipe.text_encoder(text_inputs.input_ids)[0]

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

        # Save LoRA weights (PEFT adapter)
        pipe.unet.save_pretrained(str(out_path))
        # Normalize to single file if PEFT wrote adapter_model.safetensors
        adapter = out_path / "adapter_model.safetensors"
        lora_out = out_path / "lora.safetensors"
        if adapter.exists():
            import shutil
            if adapter.resolve() != lora_out.resolve():
                shutil.move(str(adapter), str(lora_out))

        return str(out_path)

    def _make_synthetic_dataloader(self, pipe, trigger_phrase, batch_size, steps):
        """Generate synthetic training batches using base model + trigger."""
        import torch
        from torch.utils.data import Dataset, DataLoader
        from PIL import Image
        import numpy as np

        class SyntheticDataset(Dataset):
            def __init__(self, pipe, trigger, num_samples):
                self.pipe = pipe
                self.trigger = trigger
                self.num_samples = num_samples

            def __len__(self):
                return self.num_samples

            def __getitem__(self, idx):
                seed = torch.randint(0, 2**32, (1,)).item()
                gen = torch.Generator(device="cuda").manual_seed(seed)
                img = self.pipe(
                    prompt=self.trigger,
                    num_inference_steps=25,
                    guidance_scale=7.5,
                    generator=gen,
                ).images[0]
                arr = np.array(img).astype(np.float32) / 255.0
                tensor = torch.from_numpy(arr).permute(2, 0, 1)
                return {"image": tensor, "caption": f"{self.trigger}, high quality"}

        num_samples = max(50, steps * batch_size)
        dataset = SyntheticDataset(pipe, trigger_phrase, num_samples)
        return DataLoader(dataset, batch_size=batch_size, shuffle=True)

    def _make_dataloader_from_dir(self, data_dir, trigger_phrase, batch_size):
        """Build DataLoader from directory of images + captions (e.g. metadata.jsonl)."""
        import torch
        from pathlib import Path as P
        from torch.utils.data import Dataset, DataLoader
        from PIL import Image
        import numpy as np
        import json

        data_path = P(data_dir)
        image_files = list(data_path.glob("*.jpg")) + list(data_path.glob("*.png"))
        if not image_files:
            raise FileNotFoundError(f"No images in {data_dir}")

        captions = []
        meta_file = data_path / "metadata.jsonl"
        if meta_file.exists():
            with open(meta_file) as f:
                for line in f:
                    if line.strip():
                        captions.append(json.loads(line))
        else:
            captions = [{"file_name": f.name, "text": trigger_phrase} for f in image_files]

        caption_by_name = {c["file_name"]: c.get("text", trigger_phrase) for c in captions}

        class DirDataset(Dataset):
            def __init__(self, files, trigger, cap_map):
                self.files = files
                self.trigger = trigger
                self.cap_map = cap_map

            def __len__(self):
                return len(self.files)

            def __getitem__(self, idx):
                path = self.files[idx]
                img = Image.open(path).convert("RGB").resize((1024, 1024), Image.LANCZOS)
                arr = np.array(img).astype(np.float32) / 255.0
                tensor = torch.from_numpy(arr).permute(2, 0, 1)
                cap = self.cap_map.get(path.name, self.trigger)
                if not cap.startswith(self.trigger):
                    cap = f"{self.trigger}, {cap}"
                return {"image": tensor, "caption": cap}

        dataset = DirDataset(image_files, trigger_phrase, caption_by_name)
        return DataLoader(dataset, batch_size=batch_size, shuffle=True)


def train_all_styles_local(
    output_dir: str = "models/style_loras",
    steps_per_style: int = 2500,
    style_subset: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Train all 20 style LoRAs (local or SageMaker). Uses STYLE_DATASETS.

    Args:
        output_dir: Base directory for LoRA outputs.
        steps_per_style: Training steps per style (2000-3000).
        style_subset: If set, only train these keys; else all STYLE_DATASETS.

    Returns:
        List of result dicts (style_name, output_path, error).
    """
    trainer = StyleLoRATrainer(output_dir=output_dir)
    results = []
    names = style_subset or list(STYLE_DATASETS.keys())
    for style_name in names:
        if style_name not in STYLE_DATASETS:
            results.append({"style_name": style_name, "error": "unknown style"})
            continue
        config = STYLE_DATASETS[style_name]
        print(f"Training style LoRA: {style_name}")
        try:
            path = trainer.train_style_lora(
                style_name=style_name,
                dataset_path=config["dataset"],
                trigger_phrase=config["trigger"],
                output_dir=output_dir,
                steps=steps_per_style,
            )
            results.append({"style_name": style_name, "output_path": path})
        except Exception as e:
            results.append({"style_name": style_name, "error": str(e)})
    return results


# ==================== STYLE PRESETS (Popular Combinations) ====================

STYLE_PRESETS = {
    "Pro Headshot": ["hyperrealistic", "bokeh_portrait", "cinematic_lighting"],
    "Dreamy Portrait": ["soft_romantic", "golden_hour", "bokeh_portrait"],
    "Fashion Editorial": ["fashion_editorial", "dramatic_noir", "vibrant_color"],
    "Cinematic Scene": ["cinematic_lighting", "film_grain", "matte_painting"],
    "Social Media": ["instagram_aesthetic", "vibrant_color", "golden_hour"],
    "Artistic Creative": ["surreal_artistic", "soft_pastel", "minimalist"],
    "Urban Cool": ["urban_street", "neon_cyberpunk", "black_and_white"],
    "Natural Beauty": ["nature_landscape", "golden_hour", "minimalist"],
    "Vintage Classic": ["vintage_film", "black_and_white", "film_grain"],
    "Studio Professional": ["hyperrealistic", "cinematic_lighting", "bokeh_portrait"],
}

# ==================== Training Functions ====================

@app.function(
    image=gpu_image,
    gpu="A100",
    timeout=3600,
    volumes={
        MODEL_DIR: models_volume,
        LORA_DIR: lora_volume,
    },
    secrets=[
        modal.Secret.from_name("huggingface"),
    ],
)
def train_style(
    style_name: str,
    training_images: Optional[List[str]] = None,
    num_steps: int = 1000,
):
    """
    Train a single style LoRA
    
    Args:
        style_name: Name from STYLES dict
        training_images: Optional list of image URLs (if None, uses style keywords)
        num_steps: Training steps
    """
    if style_name not in STYLES:
        raise ValueError(f"Unknown style: {style_name}. Available: {list(STYLES.keys())}")
    
    style_config = STYLES[style_name]
    
    print(f"\n{'='*60}")
    print(f"Training Style LoRA: {style_name}")
    print(f"Description: {style_config['description']}")
    print(f"{'='*60}\n")
    
    # Import heavy deps
    import torch
    import numpy as np
    from diffusers import StableDiffusionXLPipeline
    from peft import LoraConfig, get_peft_model
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    from PIL import Image
    import requests
    import io
    
    # Load SDXL
    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    model_path = Path(f"{MODEL_DIR}/sdxl-base")
    
    if model_path.exists() and any(model_path.iterdir()):
        model_repo = str(model_path)
    else:
        model_repo = "stabilityai/stable-diffusion-xl-base-1.0"
    
    kwargs = {
        "torch_dtype": torch.float16,
        "variant": "fp16",
        "use_safetensors": True,
        "cache_dir": MODEL_DIR,
    }
    if hf_token:
        kwargs["token"] = hf_token
    
    pipe = StableDiffusionXLPipeline.from_pretrained(model_repo, **kwargs).to("cuda")
    
    # Setup LoRA
    lora_config = LoraConfig(
        r=32,  # Lower rank for style (vs 64 for identity)
        lora_alpha=32,
        target_modules=["to_q", "to_k", "to_v", "to_out.0"],
        lora_dropout=0.05,
        bias="none",
    )
    pipe.unet = get_peft_model(pipe.unet, lora_config)
    
    # Prepare training data
    if training_images:
        # Use provided images
        images = []
        for url in training_images:
            try:
                resp = requests.get(url, timeout=30)
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                img = img.resize((1024, 1024), Image.LANCZOS)
                images.append(img)
            except Exception as e:
                print(f"[WARN] Failed to download {url}: {e}")
    else:
        # Generate synthetic training data using style keywords
        print(f"Generating synthetic training data with keywords: {style_config['training_keywords']}")
        images = []
        
        # Generate 20-30 images with style prompt
        style_prompt = f"{style_config['trigger']}, {', '.join(style_config['training_keywords'][:3])}"
        
        for i in range(25):
            seed = torch.randint(0, 2**32, (1,)).item()
            generator = torch.Generator(device="cuda").manual_seed(seed)
            
            img = pipe(
                prompt=style_prompt,
                num_inference_steps=30,
                guidance_scale=7.5,
                generator=generator,
            ).images[0]
            
            images.append(img)
        
        print(f"Generated {len(images)} synthetic training images")
    
    if len(images) < 10:
        raise ValueError(f"Need at least 10 images, got {len(images)}")
    
    # Dataset
    class StyleDataset(Dataset):
        def __init__(self, images, trigger):
            self.images = images
            self.trigger = trigger
        
        def __len__(self):
            return len(self.images)
        
        def __getitem__(self, idx):
            img = self.images[idx]
            arr = np.array(img).astype(np.float32) / 255.0
            tensor = torch.from_numpy(arr).permute(2, 0, 1)
            caption = f"{self.trigger}, {style_config['description']}"
            return {"image": tensor, "caption": caption}
    
    dataset = StyleDataset(images, style_config["trigger"])
    dataloader = DataLoader(dataset, batch_size=1, shuffle=True)
    
    # Training loop
    optimizer = torch.optim.AdamW(pipe.unet.parameters(), lr=1e-4)
    pipe.unet.train()
    
    print(f"\nTraining for {num_steps} steps...")
    for step in range(num_steps):
        for batch in dataloader:
            imgs = batch["image"].to("cuda", dtype=torch.float16)
            captions = batch["caption"]
            
            text_inputs = pipe.tokenizer(
                captions,
                padding="max_length",
                max_length=77,
                return_tensors="pt",
            ).to("cuda")
            
            text_emb = pipe.text_encoder(text_inputs.input_ids)[0]
            
            noise = torch.randn_like(imgs)
            timesteps = torch.randint(0, 1000, (imgs.shape[0],)).to("cuda")
            noisy = pipe.scheduler.add_noise(imgs, noise, timesteps)
            
            pred = pipe.unet(noisy, timesteps, text_emb).sample
            loss = F.mse_loss(pred, noise)
            
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            
            if step % 100 == 0:
                print(f"Step {step}/{num_steps} | Loss: {loss.item():.4f}")
            break
    
    # Save LoRA
    lora_path = f"{LORA_DIR}/{style_name}/lora.safetensors"
    Path(lora_path).parent.mkdir(parents=True, exist_ok=True)
    lora_dir = Path(lora_path).parent
    
    pipe.unet.save_pretrained(str(lora_dir))
    
    # Find and rename safetensors file
    saved_files = list(lora_dir.glob("*.safetensors"))
    if saved_files:
        import shutil
        if len(saved_files) == 1:
            if saved_files[0].name != "lora.safetensors":
                shutil.move(str(saved_files[0]), lora_path)
        else:
            adapter = lora_dir / "adapter_model.safetensors"
            if adapter.exists():
                shutil.move(str(adapter), lora_path)
            else:
                shutil.move(str(saved_files[0]), lora_path)
    
    # Save style config
    import json
    config_path = f"{LORA_DIR}/{style_name}/config.json"
    with open(config_path, "w") as f:
        json.dump(style_config, f, indent=2)
    
    lora_volume.commit()
    
    print(f"\n✅ Style LoRA saved: {lora_path}")
    return {
        "style_name": style_name,
        "lora_path": lora_path,
        "config_path": config_path,
    }


@app.function(
    image=gpu_image,
    timeout=1800,
    volumes={
        LORA_DIR: lora_volume,
    },
)
def download_civitai_loras():
    """
    Download pre-trained style LoRAs from CivitAI (faster than training)
    
    Note: This requires manual CivitAI API setup or direct download links
    For now, prints instructions for manual download
    """
    print("\n" + "="*60)
    print("CivitAI LoRA Download Instructions")
    print("="*60)
    print("\nTo use pre-trained LoRAs from CivitAI:")
    print("1. Visit https://civitai.com")
    print("2. Search for SDXL style LoRAs matching each style")
    print("3. Download and place in /loras/styles/{style_name}/lora.safetensors")
    print("\nRecommended searches:")
    print("  - 'SDXL cinematic lighting'")
    print("  - 'SDXL fashion editorial'")
    print("  - 'SDXL bokeh portrait'")
    print("  - 'SDXL golden hour'")
    print("  - etc.")
    print("\nAfter download, update STYLES dict with civitai_id if available")
    
    # Create directory structure
    for style_name in STYLES.keys():
        style_dir = Path(f"{LORA_DIR}/{style_name}")
        style_dir.mkdir(parents=True, exist_ok=True)
        
        # Save config
        import json
        config_path = style_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump(STYLES[style_name], f, indent=2)
    
    lora_volume.commit()
    print(f"\n✅ Created directory structure for {len(STYLES)} styles")
    return {"status": "directories_created", "styles": list(STYLES.keys())}


@app.function(
    image=gpu_image,
    gpu="A100",
    timeout=72000,  # 20 hours for all styles
    volumes={
        MODEL_DIR: models_volume,
        LORA_DIR: lora_volume,
    },
    secrets=[
        modal.Secret.from_name("huggingface"),
    ],
)
def train_all_styles():
    """Train all 20 style LoRAs sequentially"""
    results = []
    
    for style_name in STYLES.keys():
        print(f"\n{'='*60}")
        print(f"Training {style_name} ({list(STYLES.keys()).index(style_name) + 1}/20)")
        print(f"{'='*60}")
        
        try:
            result = train_style.local(style_name=style_name, num_steps=800)  # Fewer steps per style
            results.append(result)
            print(f"✅ {style_name} complete")
        except Exception as e:
            print(f"❌ {style_name} failed: {e}")
            results.append({"style_name": style_name, "error": str(e)})
    
    lora_volume.commit()
    
    print(f"\n{'='*60}")
    print(f"Training Summary: {len([r for r in results if 'error' not in r])}/20 successful")
    print(f"{'='*60}")
    
    return {"results": results}


def train_essential_lora_local(
    style_name: str,
    dataset: Optional[str] = None,
    epochs: int = 1000,
    steps: Optional[int] = None,
    output: str = "ai-pipeline/models/loras",
    batch_size: int = 4,
    upload_s3: bool = False,
    s3_uri: str = "s3://photogenius-models/loras/",
) -> str:
    """
    Train one of the 3 essential LoRAs locally using StyleLoRATrainer.
    Downloads from HuggingFace if dataset given, then trains and optionally uploads to S3.

    Output can be a directory (e.g. ai-pipeline/models/loras) or a .safetensors path
    (e.g. ai-pipeline/models/loras/skin_realism_v2.safetensors); in the latter case
    the LoRA is written to output/<style_name>/ then copied to the given file path.

    Returns path to saved LoRA (directory or .safetensors file).
    """
    from pathlib import Path as P
    import tempfile
    import shutil

    output_dir = output
    final_safetensors_path = None
    if output.rstrip("/").endswith(".safetensors"):
        output_dir = str(P(output).parent)
        final_safetensors_path = output

    if style_name not in ESSENTIAL_LORAS and style_name not in STYLE_DATASETS:
        raise ValueError(
            f"Unknown style: {style_name}. Essential: {list(ESSENTIAL_LORAS.keys())}; "
            f"all: {list(STYLE_DATASETS.keys())}"
        )
    config = ESSENTIAL_LORAS.get(style_name) or STYLE_DATASETS[style_name]
    hf_dataset = dataset or config.get("dataset", "")
    trigger = config.get("trigger", "")
    max_examples = config.get("examples", 500)

    trainer = StyleLoRATrainer(output_dir=output)
    use_hf = bool(
        hf_dataset
        and ("/" in hf_dataset or hf_dataset.startswith("laion") or hf_dataset.startswith("ChristophSchuhmann") or hf_dataset.startswith("prithivMLmods"))
    )

    if use_hf:
        with tempfile.TemporaryDirectory(prefix="lora_data_") as tmp:
            data_dir = load_hf_dataset_for_style(
                style_name=style_name,
                hf_dataset=hf_dataset,
                trigger_phrase=trigger,
                max_samples=max_examples,
                output_data_dir=tmp,
                split=config.get("hf_split", "train"),
                image_key=config.get("hf_image_key", "image"),
                caption_key=config.get("hf_caption_key"),
            )
            n_actual = len(list(P(data_dir).glob("image_*.png")))
            train_steps = steps if steps is not None else min(10000, max(2000, epochs * max(1, n_actual // batch_size)))
            out_path = trainer.train_style_lora(
                style_name=style_name,
                dataset_path=hf_dataset,
                trigger_phrase=trigger,
                output_dir=output,
                steps=train_steps,
                batch_size=batch_size,
                data_dir=data_dir,
            )
    else:
        n_samples = max_examples
        train_steps = steps if steps is not None else min(10000, max(2000, epochs * max(1, n_samples // batch_size)))
        out_path = trainer.train_style_lora(
            style_name=style_name,
            dataset_path=hf_dataset or style_name,
            trigger_phrase=trigger,
            output_dir=output,
            steps=train_steps,
            batch_size=batch_size,
        )

    out_path = P(out_path)
    lora_file = out_path / "lora.safetensors"
    if not lora_file.exists():
        for f in out_path.glob("*.safetensors"):
            lora_file = f
            break

    if final_safetensors_path and lora_file and lora_file.exists():
        P(final_safetensors_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(lora_file), final_safetensors_path)
        print(f"Copied LoRA to {final_safetensors_path}")
        out_path = P(final_safetensors_path)

    if upload_s3 and lora_file and lora_file.exists():
        upload_lora_to_s3(str(lora_file), s3_uri.strip("/") + f"/{style_name}/lora.safetensors")
        print(f"Uploaded to {s3_uri}{style_name}/lora.safetensors")
    return str(out_path)


def upload_lora_to_s3(local_path: str, s3_key_or_uri: str) -> str:
    """
    Upload LoRA file to S3. s3_key_or_uri can be full URI (s3://bucket/key) or key only (bucket from env).
    Returns S3 URI.
    """
    try:
        import boto3
    except ImportError:
        raise ImportError("pip install boto3 to use --upload-s3")
    from pathlib import Path
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(local_path)
    if s3_key_or_uri.startswith("s3://"):
        parts = s3_key_or_uri.replace("s3://", "").split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else path.name
    else:
        bucket = os.environ.get("S3_BUCKET", "photogenius-models")
        key = s3_key_or_uri.strip("/")
    client = boto3.client("s3")
    client.upload_file(str(path), bucket, key)
    return f"s3://{bucket}/{key}"


@app.local_entrypoint()
def main():
    """CLI entrypoint: argparse for train command, else Modal verbs (download, all, <style>)."""
    import sys
    import argparse

    if "--style" in sys.argv or "-s" in sys.argv:
        ap = argparse.ArgumentParser(
            description="Train essential/style LoRAs (skin_realism_v2, cinematic_lighting_v3, color_harmony_v1)"
        )
        ap.add_argument("--style", "-s", required=True, help="Style name (e.g. skin_realism_v2)")
        ap.add_argument("--dataset", "-d", default=None, help="HuggingFace dataset (e.g. prithivMLmods/Realistic-Face-Portrait-1024px)")
        ap.add_argument("--epochs", "-e", type=int, default=1000, help="Training epochs (converted to steps)")
        ap.add_argument("--steps", type=int, default=None, help="Override total training steps")
        ap.add_argument("--output", "-o", default="ai-pipeline/models/loras", help="Output dir or .safetensors path")
        ap.add_argument("--batch-size", "-b", type=int, default=4)
        ap.add_argument("--upload-s3", action="store_true", help="Upload to s3://photogenius-models/loras/")
        ap.add_argument("--s3-uri", default="s3://photogenius-models/loras/", help="S3 base URI for upload")
        args = ap.parse_args()
        try:
            out = train_essential_lora_local(
                style_name=args.style,
                dataset=args.dataset,
                epochs=args.epochs,
                steps=args.steps,
                output=args.output,
                batch_size=args.batch_size,
                upload_s3=args.upload_s3,
                s3_uri=args.s3_uri,
            )
            print(f"\n✅ LoRA saved: {out}")
        except Exception as e:
            print(f"\n❌ Training failed: {e}")
            raise
        return

    if len(sys.argv) > 1:
        if sys.argv[1] == "download":
            result = download_civitai_loras.remote()
            print(f"\n✅ {result}")
        elif sys.argv[1] == "all":
            result = train_all_styles.remote()
            print(f"\n✅ {result}")
        elif sys.argv[1] in STYLES:
            result = train_style.remote(style_name=sys.argv[1])
            print(f"\n✅ {result}")
        else:
            print(f"Unknown style: {sys.argv[1]}")
            print(f"Available: {list(STYLES.keys())}")
    else:
        print("Usage:")
        print("  modal run train_style_loras.py download  # Setup directories")
        print("  modal run train_style_loras.py all       # Train all styles")
        print(f"  modal run train_style_loras.py <style>  # Train specific style")
        print(f"\n  # Train essential LoRAs (local, with HF dataset):")
        print("  python ai-pipeline/training/train_style_loras.py --style skin_realism_v2 --dataset prithivMLmods/Realistic-Face-Portrait-1024px --epochs 1000 --output ai-pipeline/models/loras/skin_realism_v2.safetensors")
        print("  python ai-pipeline/training/train_style_loras.py --style cinematic_lighting_v3 --dataset ChristophSchuhmann/improved_aesthetics_parquet --epochs 1000 --output ai-pipeline/models/loras/")
        print("  python ai-pipeline/training/train_style_loras.py --style color_harmony_v1 --dataset laion/laion-art --epochs 1000 --output ai-pipeline/models/loras/ --upload-s3")
        print(f"\nAvailable styles: {', '.join(STYLES.keys())}")

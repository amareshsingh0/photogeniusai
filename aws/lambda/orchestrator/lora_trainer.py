"""
LoRA Training Service on Modal GPU.

Includes AdvancedLoRATrainer for augmentation, regularization, and Prodigy optimizer.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, List, Optional, Tuple

import modal  # type: ignore[reportMissingImports]

# Heavy imports moved inside functions/class to avoid local import errors

app = modal.App("photogenius-lora-trainer")
stub = app  # Alias for compatibility

# ==================== Self-contained Modal Config ====================
# Define image and volumes directly (Modal uploads files individually)

MODEL_DIR = "/models"
LORA_DIR = "/loras"

# Persistent volumes
models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)
lora_volume = modal.Volume.from_name("photogenius-loras", create_if_missing=True)

# GPU image with all dependencies
gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.1",
        "torchvision==0.19.1",
        "diffusers==0.30.3",
        "transformers==4.44.2",
        "accelerate==0.34.2",
        "safetensors==0.4.5",
        "peft==0.12.0",
        "bitsandbytes==0.43.3",
        "xformers==0.0.28.post1",
        "insightface==0.7.3",
        "onnxruntime-gpu==1.18.0",
        "opencv-python==4.9.0.80",
        "pillow==10.2.0",
        "numpy==1.26.3",
        "scipy==1.12.0",
        "requests",
        "datasets",  # For REGULARIZATION_DATASET (HuggingFace)
        "fastapi[standard]",  # Required for web endpoints
        "prodigyopt",  # Prodigy optimizer for advanced LoRA training
    )
    .run_commands(
        "apt-get update",
        "apt-get install -y libgl1-mesa-glx libglib2.0-0",
    )
)


# ==================== AdvancedLoRATrainer (augmentation + regularization + validation) ====================

class AdvancedLoRATrainer:
    """
    Enhanced LoRA training with augmentation and regularization.
    Use from train_lora_advanced (Modal) or locally with pipe + face_app.
    """

    # Standard validation prompts for face consistency
    VALIDATION_PROMPTS = [
        "professional headshot, business attire",
        "casual photo, outdoor setting",
        "artistic portrait, dramatic lighting",
    ]

    def __init__(
        self,
        pipe: Any,
        face_app: Any,
        trigger_word: str = "sks",
        device: str = "cuda",
        lora_dir: Optional[str] = None,
    ):
        self.pipe = pipe
        self.face_app = face_app
        self.trigger_word = trigger_word
        self.device = device
        self.lora_dir = lora_dir

    def _augment_training_images(self, images: List[Any]) -> List[Any]:
        """
        Apply augmentation to increase diversity and prevent overfitting.
        3x augmentation per input image.

        Augmentations:
        1. Random crops (zoom in/out)
        2. Color jitter (brightness, contrast, saturation)
        3. Horizontal flip (for symmetric faces)
        4. Slight rotation (-5° to +5°)
        5. Gaussian blur (simulate different focal lengths)
        """
        from torchvision import transforms

        # Keep 1024 for SDXL VAE; scale 0.8–1.0 for zoom variation
        augmentation = transforms.Compose([
            transforms.RandomResizedCrop(1024, scale=(0.8, 1.0)),
            transforms.ColorJitter(
                brightness=0.1,
                contrast=0.1,
                saturation=0.1,
                hue=0.05,
            ),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=5),
            transforms.RandomApply([
                transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 2.0)),
            ], p=0.3),
        ])

        augmented: List[Any] = []
        for img in images:
            for _ in range(3):
                aug_img = augmentation(img)
                augmented.append(aug_img)
        return augmented

    def _detect_and_crop_faces(self, images: List[Any]) -> List[Any]:
        """Detect and crop faces from raw images; return list of PIL 1024x1024 crops."""
        import numpy as np
        from PIL import Image

        processed = []
        for img in images:
            img_array = np.array(img)
            faces = self.face_app.get(img_array)
            if not faces:
                continue
            face = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            margin_x = int((x2 - x1) * 0.3)
            margin_y = int((y2 - y1) * 0.3)
            x1 = max(0, x1 - margin_x)
            y1 = max(0, y1 - margin_y)
            x2 = min(img.width, x2 + margin_x)
            y2 = min(img.height, y2 + margin_y)
            face_crop = img.crop((x1, y1, x2, y2)).resize((1024, 1024), Image.LANCZOS)
            processed.append(face_crop)
        return processed

    # Default regularization URLs (picsum.photos) so the 20% branch is used when env is unset.
    _DEFAULT_REGULARIZATION_URLS: List[str] = [
        "https://picsum.photos/id/1/1024/1024", "https://picsum.photos/id/2/1024/1024",
        "https://picsum.photos/id/3/1024/1024", "https://picsum.photos/id/4/1024/1024",
        "https://picsum.photos/id/5/1024/1024", "https://picsum.photos/id/6/1024/1024",
        "https://picsum.photos/id/7/1024/1024", "https://picsum.photos/id/8/1024/1024",
        "https://picsum.photos/id/9/1024/1024", "https://picsum.photos/id/10/1024/1024",
        "https://picsum.photos/id/11/1024/1024", "https://picsum.photos/id/12/1024/1024",
        "https://picsum.photos/id/13/1024/1024", "https://picsum.photos/id/14/1024/1024",
        "https://picsum.photos/id/15/1024/1024", "https://picsum.photos/id/16/1024/1024",
        "https://picsum.photos/id/17/1024/1024", "https://picsum.photos/id/18/1024/1024",
        "https://picsum.photos/id/19/1024/1024", "https://picsum.photos/id/20/1024/1024",
    ]

    def _load_default_regularization(self) -> List[Any]:
        """
        Load diverse regularization images to maintain general quality (1024x1024 PIL).
        Set REGULARIZATION_URLS (comma-separated or JSON list of URLs) and/or
        REGULARIZATION_DATASET (HuggingFace dataset name, e.g. "celeb_a" or "imagefolder")
        so the 20% regularization branch is used. Max ~200 images from dataset.
        If neither is set, uses built-in default URLs (picsum.photos) so the 20% branch runs.
        Fallback: returns empty list only if all sources fail (training uses 100% identity then).
        """
        import os
        import json
        from PIL import Image

        out: List[Any] = []
        size_1024 = (1024, 1024)

        # 1) REGULARIZATION_URLS: comma-separated or JSON list of image URLs
        urls_raw = os.environ.get("REGULARIZATION_URLS", "").strip()
        if urls_raw:
            try:
                urls = json.loads(urls_raw) if urls_raw.startswith("[") else [u.strip() for u in urls_raw.split(",") if u.strip()]
            except json.JSONDecodeError:
                urls = [u.strip() for u in urls_raw.split(",") if u.strip()]
            if urls:
                import requests
                for url in urls[:500]:  # cap URLs
                    try:
                        r = requests.get(url, timeout=30)
                        r.raise_for_status()
                        img = Image.open(io.BytesIO(r.content)).convert("RGB")
                        if img.size != size_1024:
                            img = img.resize(size_1024, Image.LANCZOS)
                        out.append(img)
                    except Exception:
                        continue
                if out:
                    return out
            # else fall through to dataset

        # 2) REGULARIZATION_DATASET: HuggingFace dataset name (e.g. "celeb_a", "imagefolder")
        name = os.environ.get("REGULARIZATION_DATASET", "").strip()
        if name:
            try:
                from datasets import load_dataset
                max_images = int(os.environ.get("REGULARIZATION_MAX_IMAGES", "200"))
                ds = load_dataset(name, split="train", trust_remote_code=True)
                n = min(len(ds), max_images)
                for i in range(n):
                    row = ds[i]
                    img = None
                    if "image" in row:
                        img = row["image"]
                    elif "pixel_values" in row:
                        from PIL import Image as PImage
                        arr = row["pixel_values"]
                        if hasattr(arr, "numpy"):
                            arr = arr.numpy()
                        import numpy as np
                        if isinstance(arr, np.ndarray):
                            if arr.ndim == 3 and arr.shape[0] in (3, 1):
                                arr = np.transpose(arr, (1, 2, 0))
                            if arr.dtype in (np.float32, np.float64) and arr.max() <= 1.0:
                                arr = (arr * 255).astype(np.uint8)
                            img = PImage.fromarray(arr).convert("RGB")
                    if img is not None and hasattr(img, "resize"):
                        if getattr(img, "size", (0, 0)) != size_1024:
                            img = img.resize(size_1024, Image.LANCZOS)
                        out.append(img)
                return out[:max_images]
            except Exception:
                pass

        # 3) Default: use built-in URLs so the 20% regularization branch is used when env is unset
        if not out:
            import requests
            default_urls = AdvancedLoRATrainer._DEFAULT_REGULARIZATION_URLS
            for url in default_urls[:500]:
                try:
                    r = requests.get(url, timeout=30)
                    r.raise_for_status()
                    img = Image.open(io.BytesIO(r.content)).convert("RGB")
                    if img.size != size_1024:
                        img = img.resize(size_1024, Image.LANCZOS)
                    out.append(img)
                except Exception:
                    continue
            if out:
                return out
        return out

    def _compute_face_similarity(self, face_img1: Any, face_img2: Any) -> float:
        """Compute cosine similarity between two face images using InsightFace embeddings."""
        import numpy as np

        def embed(img: Any) -> np.ndarray:
            arr = np.array(img)
            faces = self.face_app.get(arr)
            if not faces:
                return np.zeros(512, dtype=np.float32)
            return faces[0].embedding

        e1 = embed(face_img1)
        e2 = embed(face_img2)
        if np.linalg.norm(e1) < 1e-9 or np.linalg.norm(e2) < 1e-9:
            return 0.0
        return float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2)))

    def _validate_lora(self, reference_face: Any) -> float:
        """
        Test LoRA on standard prompts, measure face consistency.
        Returns mean cosine similarity (0–1) across validation prompts.
        """
        import torch

        self.pipe.unet.eval()
        scores = []
        with torch.no_grad():
            for prompt in self.VALIDATION_PROMPTS:
                full_prompt = f"a photo of {self.trigger_word} person, {prompt}"
                try:
                    gen = self.pipe(
                        prompt=full_prompt,
                        num_inference_steps=30,
                        guidance_scale=7.5,
                    ).images[0]
                    sim = self._compute_face_similarity(reference_face, gen)
                    scores.append(sim)
                except Exception:
                    scores.append(0.0)
        self.pipe.unet.train()
        return float(sum(scores) / len(scores)) if scores else 0.0

    def train_identity_lora(
        self,
        identity_images: List[Any],
        regularization_images: Optional[List[Any]] = None,
        steps: int = 3000,
        batch_size: int = 4,
        identity_ratio: float = 0.8,
    ) -> Tuple[Any, float]:
        """
        Train identity LoRA with augmentation and optional regularization.

        Pipeline:
        1. Detect and crop faces (if images are full-frame)
        2. Augment training images (3x per image)
        3. Mix with regularization images (80% identity, 20% reg)
        4. Train LoRA with Prodigy (or AdamW fallback), latent-space
        5. Validate on standard prompts

        Returns:
            (lora_state_or_path, validation_score)
        """
        import random
        import torch
        import torch.nn.functional as F
        import numpy as np
        from PIL import Image

        # Assume identity_images are already face crops (1024x1024) from caller, or full photos
        # If first image is 1024x1024 and square, treat as crops; else detect faces
        if identity_images and (identity_images[0].size[0] != 1024 or identity_images[0].size[1] != 1024):
            identity_faces = self._detect_and_crop_faces(identity_images)
        else:
            identity_faces = list(identity_images)
        if len(identity_faces) < 2:
            raise ValueError("Need at least 2 identity face images after crop")

        augmented_faces = self._augment_training_images(identity_faces)
        reg_images = regularization_images if regularization_images is not None else self._load_default_regularization()

        # Build caption per image: identity uses trigger, reg uses generic
        identity_captions = [f"a photo of {self.trigger_word} person"] * len(augmented_faces)
        reg_captions = ["a photo of a person"] * len(reg_images) if reg_images else []

        n_id = len(augmented_faces)
        n_reg = len(reg_images)
        total = n_id + n_reg
        if total == 0:
            raise ValueError("No training images")

        # Prodigy optimizer (or AdamW fallback)
        try:
            from prodigyopt import Prodigy
            optimizer = Prodigy(
                self.pipe.unet.parameters(),
                lr=1.0,
                weight_decay=0.01,
            )
        except Exception:
            optimizer = torch.optim.AdamW(
                self.pipe.unet.parameters(),
                lr=1e-4,
                weight_decay=0.01,
            )

        self.pipe.unet.train()
        self.pipe.vae.eval()

        # Latent-space training for SDXL
        def _pil_to_latent(imgs: List[Any]) -> torch.Tensor:
            import numpy as np
            tensors = []
            for img in imgs:
                arr = np.array(img).astype(np.float32) / 255.0
                t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(self.device, dtype=torch.float16)
                with torch.no_grad():
                    lat = self.pipe.vae.encode(t).latent_dist.sample() * self.pipe.vae.config.scaling_factor
                tensors.append(lat)
            return torch.cat(tensors, dim=0)

        step = 0
        while step < steps:
            # 80% identity, 20% regularization
            k_id = max(1, int(batch_size * identity_ratio))
            k_reg = batch_size - k_id
            if n_reg == 0:
                k_reg = 0
                k_id = min(batch_size, n_id)
            batch_imgs: List[Any] = []
            batch_caps: List[str] = []
            if k_id and n_id:
                idx_id = random.sample(range(n_id), min(k_id, n_id))
                batch_imgs.extend([augmented_faces[i] for i in idx_id])
                batch_caps.extend([identity_captions[0]] * len(idx_id))  # same caption for identity
            if k_reg and n_reg:
                idx_reg = random.sample(range(n_reg), min(k_reg, n_reg))
                batch_imgs.extend([reg_images[i] for i in idx_reg])
                batch_caps.extend([reg_captions[i] for i in idx_reg])

            if not batch_imgs:
                break
            # Resize to 1024 if augmentation produced smaller (e.g. 512)
            from PIL import Image as PILImage
            resized = []
            for im in batch_imgs:
                if getattr(im, "size", (0, 0)) != (1024, 1024):
                    im = im.resize((1024, 1024), PILImage.LANCZOS) if hasattr(im, "resize") else im
                resized.append(im)
            batch_imgs = resized
            latents = _pil_to_latent(batch_imgs)
            text_inputs = self.pipe.tokenizer(
                batch_caps,
                padding="max_length",
                max_length=77,
                return_tensors="pt",
                truncation=True,
            ).to(self.device)
            text_emb = self.pipe.text_encoder(text_inputs.input_ids)[0]

            noise = torch.randn_like(latents, device=latents.device, dtype=torch.float16)
            timesteps = torch.randint(0, 1000, (latents.shape[0],), device=latents.device)
            noisy = self.pipe.scheduler.add_noise(latents, noise, timesteps)
            pred = self.pipe.unet(noisy, timesteps, text_emb).sample
            loss = F.mse_loss(pred, noise)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            if step % 100 == 0:
                print(f"[AdvancedLoRA] step {step}/{steps} loss={loss.item():.4f}")
            step += 1

        validation_score = self._validate_lora(identity_faces[0])
        print(f"[AdvancedLoRA] validation score (face consistency): {validation_score:.4f}")
        return self.pipe.unet, validation_score


@app.function(
    image=gpu_image,
    gpu="A100",  # A100 for training
    timeout=3600,
    volumes={
        MODEL_DIR: models_volume,
        LORA_DIR: lora_volume,
    },
    secrets=[
        modal.Secret.from_name("huggingface"),  # HUGGINGFACE_TOKEN (optional - will be None if not set)
    ],
)
def train_lora(
    user_id: str,
    identity_id: str,
    image_urls: list[str],
    trigger_word: str = "sks",
    training_steps: int = 1000,
):
    """
    Train LoRA for identity
    
    Args:
        user_id: User ID
        identity_id: Identity ID
        image_urls: List of S3 URLs for training images
        trigger_word: Trigger word for LoRA
        training_steps: Number of training steps
    
    Returns:
        dict with lora_path and face_embedding
    """
    # Import heavy dependencies inside function
    from PIL import Image  # type: ignore[reportMissingImports]
    import torch  # type: ignore[reportMissingImports]
    import numpy as np  # type: ignore[reportMissingImports]
    from diffusers import StableDiffusionXLPipeline, DDPMScheduler  # type: ignore[reportMissingImports]
    from transformers import CLIPTextModel, CLIPTokenizer  # type: ignore[reportMissingImports]
    import torch.nn.functional as F  # type: ignore[reportMissingImports]
    from torch.utils.data import Dataset, DataLoader  # type: ignore[reportMissingImports]
    import requests
    from insightface.app import FaceAnalysis  # type: ignore[reportMissingImports]
    from peft import LoraConfig, get_peft_model  # type: ignore[reportMissingImports]
    
    print(f"[*] Starting LoRA training for {identity_id}")
    print(f"[*] Training images: {len(image_urls)}")
    
    # ==================== STEP 1: Download Images ====================
    print("\n[*] Step 1: Downloading training images...")
    images = []
    for url in image_urls:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content)).convert("RGB")
            images.append(img)
            print(f"[OK] Downloaded image from {url}")
        except Exception as e:
            print(f"[WARN] Failed to download {url}: {e}")
            continue
    
    print(f"[OK] Downloaded {len(images)} images")
    
    if len(images) < 5:
        raise ValueError(f"Need at least 5 images, got {len(images)}")
    
    # ==================== STEP 2: Face Detection & Cropping ====================
    print("\n[*] Step 2: Detecting and cropping faces...")
    
    face_app = FaceAnalysis(name='buffalo_l')
    face_app.prepare(ctx_id=0, det_size=(640, 640))
    
    processed_images = []
    face_embeddings = []
    face_data = []  # Store face info with quality scores
    
    for idx, img in enumerate(images):
        img_array = np.array(img)
        faces = face_app.get(img_array)
        
        if len(faces) == 0:
            print(f"[WARN] No face detected in image {idx}, skipping...")
            continue
        
        # Get primary face (largest)
        face = sorted(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))[-1]
        
        # Extract face embedding (512-dim)
        face_emb = face.embedding
        face_embeddings.append(face_emb)
        
        # Calculate face quality score (detection confidence)
        det_score = face.det_score if hasattr(face, 'det_score') else 0.9
        
        # Crop face with margin
        bbox = face.bbox.astype(int)
        x1, y1, x2, y2 = bbox
        
        # Add 30% margin
        margin_x = int((x2 - x1) * 0.3)
        margin_y = int((y2 - y1) * 0.3)
        
        x1 = max(0, x1 - margin_x)
        y1 = max(0, y1 - margin_y)
        x2 = min(img.width, x2 + margin_x)
        y2 = min(img.height, y2 + margin_y)
        
        face_crop = img.crop((x1, y1, x2, y2))
        
        # Resize to 1024x1024
        face_crop = face_crop.resize((1024, 1024), Image.LANCZOS)
        processed_images.append(face_crop)
        
        # Store face data for later use
        face_data.append({
            'image': face_crop,
            'embedding': face_emb,
            'det_score': det_score,
            'bbox': bbox,
        })
    
    print(f"[OK] Processed {len(processed_images)} faces")
    
    if len(processed_images) < 5:
        raise ValueError("Need at least 5 valid face images for training")
    
    # ==================== STEP 2.5: Save Face Embedding & Reference Image ====================
    print("\n[*] Step 2.5: Saving face embedding and reference image...")
    
    # Pick the best/largest face (as specified)
    best_face = max(face_data, key=lambda f: (f['bbox'][2] - f['bbox'][0]) * (f['bbox'][3] - f['bbox'][1]))
    best_face_img = best_face['image']
    best_face_embedding = best_face['embedding']
    best_face_quality = float(best_face['det_score'])
    
    # Create output directory
    import os
    lora_dir = f"{LORA_DIR}/{user_id}/{identity_id}"
    os.makedirs(lora_dir, exist_ok=True)
    
    # Validate embedding shape
    if best_face_embedding.shape != (512,):
        raise ValueError(f"Invalid embedding shape: {best_face_embedding.shape}, expected (512,)")
    
    # Save face embedding (with retry on failure)
    face_embedding_path = f"{lora_dir}/face_embedding.npy"
    try:
        np.save(face_embedding_path, best_face_embedding)
        print(f"✅ Face embedding saved: {face_embedding_path} (shape: {best_face_embedding.shape})")
    except Exception as e:
        print(f"[WARN] Failed to save face embedding: {e}, retrying...")
        # Retry once
        try:
            np.save(face_embedding_path, best_face_embedding)
            print(f"✅ Face embedding saved on retry")
        except Exception as e2:
            print(f"[ERROR] Failed to save face embedding after retry: {e2}")
            # Continue with training but log the error (non-critical)
            face_embedding_path = None
    
    # Save best face as reference image (for IP-Adapter)
    face_reference_path = f"{lora_dir}/face_reference.jpg"
    try:
        best_face_img.save(face_reference_path, "JPEG", quality=95)
        print(f"[OK] Face reference image saved: {face_reference_path} (quality score: {best_face_quality:.3f})")
    except Exception as e:
        print(f"[WARN] Failed to save face reference image: {e}, retrying...")
        # Retry once
        try:
            best_face_img.save(face_reference_path, "JPEG", quality=95)
            print(f"[OK] Face reference image saved on retry")
        except Exception as e2:
            print(f"[ERROR] Failed to save face reference image after retry: {e2}")
            # Continue with training but log the error (non-critical)
            face_reference_path = None
    
    # ==================== STEP 3: Load Base Model ====================
    print("\n[*] Step 3: Loading SDXL model...")
    
    # Get HuggingFace token from Modal secret (if available)
    import os
    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    if hf_token:
        print("[*] Using HuggingFace token for authenticated downloads")
    
    # Check if model exists locally, otherwise download from HuggingFace
    model_path = Path(f"{MODEL_DIR}/sdxl-base")
    
    # Try to use local model first, fallback to HuggingFace
    try:
        if model_path.exists() and any(model_path.iterdir()):
            print(f"[*] Using cached model at {MODEL_DIR}/sdxl-base")
            model_repo = str(model_path)
        else:
            raise FileNotFoundError("Model not cached")
    except (FileNotFoundError, OSError):
        print(f"[*] Model not found at {MODEL_DIR}/sdxl-base, downloading from HuggingFace...")
        print("[*] This may take 5-10 minutes on first run...")
        model_repo = "stabilityai/stable-diffusion-xl-base-1.0"
    
    # Prepare kwargs for from_pretrained
    pretrained_kwargs = {
        "torch_dtype": torch.float16,
        "variant": "fp16",
        "use_safetensors": True,
        "cache_dir": MODEL_DIR,
    }
    
    # Add token if available (for gated models or rate limit bypass)
    if hf_token:
        pretrained_kwargs["token"] = hf_token
    
    pipe = StableDiffusionXLPipeline.from_pretrained(
        model_repo,
        **pretrained_kwargs
    ).to("cuda")
    
    print("[OK] Model loaded")
    
    # ==================== STEP 4: Setup LoRA ====================
    print("\n[*] Step 4: Configuring LoRA...")
    
    lora_config = LoraConfig(
        r=64,  # Rank
        lora_alpha=64,
        target_modules=["to_q", "to_k", "to_v", "to_out.0"],
        lora_dropout=0.1,
        bias="none",
    )
    
    # Apply LoRA to UNet
    pipe.unet = get_peft_model(pipe.unet, lora_config)
    pipe.unet.print_trainable_parameters()
    
    # ==================== STEP 5: Prepare Dataset ====================
    print("\n[*] Step 5: Preparing training dataset...")
    
    class LoRADataset(Dataset):
        def __init__(self, images, trigger_word):
            self.images = images
            self.trigger_word = trigger_word
        
        def __len__(self):
            return len(self.images)
        
        def __getitem__(self, idx):
            image = self.images[idx]
            
            # Simple caption
            caption = f"a photo of {self.trigger_word} person"
            
            # Convert to tensor
            image_array = np.array(image).astype(np.float32) / 255.0
            image_tensor = torch.from_numpy(image_array).permute(2, 0, 1)
            
            return {
                "image": image_tensor,
                "caption": caption,
            }
    
    dataset = LoRADataset(processed_images, trigger_word)
    dataloader = DataLoader(dataset, batch_size=1, shuffle=True)
    
    # ==================== STEP 6: Training Loop ====================
    print(f"\n[*] Step 6: Training for {training_steps} steps...")
    
    optimizer = torch.optim.AdamW(
        pipe.unet.parameters(),
        lr=1e-4,
    )
    
    pipe.unet.train()
    
    for step in range(training_steps):
        for batch in dataloader:
            # Get batch
            images = batch["image"].to("cuda", dtype=torch.float16)
            captions = batch["caption"]
            
            # Encode text
            text_inputs = pipe.tokenizer(
                captions,
                padding="max_length",
                max_length=77,
                return_tensors="pt",
            ).to("cuda")
            
            text_embeddings = pipe.text_encoder(
                text_inputs.input_ids,
            )[0]
            
            # Add noise to images
            noise = torch.randn_like(images)
            timesteps = torch.randint(0, 1000, (images.shape[0],)).to("cuda")
            
            noisy_images = pipe.scheduler.add_noise(images, noise, timesteps)
            
            # Predict noise
            model_pred = pipe.unet(
                noisy_images,
                timesteps,
                text_embeddings,
            ).sample
            
            # Calculate loss
            loss = F.mse_loss(model_pred, noise)
            
            # Backward pass
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            
            # Progress logging
            if step % 50 == 0:
                print(f"Step {step}/{training_steps} | Loss: {loss.item():.4f}")
            
            break  # One batch per step
    
    print("[OK] Training complete!")
    
    # ==================== STEP 7: Save LoRA ====================
    print("\n[*] Step 7: Saving LoRA weights...")
    
    lora_path = f"{LORA_DIR}/{user_id}/{identity_id}/lora.safetensors"
    Path(lora_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Save LoRA weights
    # Note: PEFT's save_pretrained saves to a directory, not a single file
    # We'll save to the directory and then check for the safetensors file
    lora_dir = Path(lora_path).parent
    try:
        # Save LoRA to directory
        pipe.unet.save_pretrained(str(lora_dir))
        
        # Find the saved safetensors file
        saved_files = list(lora_dir.glob("*.safetensors"))
        if saved_files:
            # If multiple files, use the adapter_model one, or rename to lora.safetensors
            if len(saved_files) == 1:
                # Rename to expected name
                import shutil
                if saved_files[0].name != "lora.safetensors":
                    shutil.move(str(saved_files[0]), lora_path)
            else:
                # Multiple files - find adapter_model or use first
                adapter_file = lora_dir / "adapter_model.safetensors"
                if adapter_file.exists():
                    import shutil
                    shutil.move(str(adapter_file), lora_path)
                else:
                    import shutil
                    shutil.move(str(saved_files[0]), lora_path)
        else:
            print(f"[WARN] No safetensors file found after save_pretrained")
        
        print(f"[OK] LoRA saved to {lora_path}")
    except Exception as e:
        print(f"[WARN] Error saving LoRA: {e}")
        # Try alternative save method - extract only LoRA weights
        try:
            from safetensors.torch import save_file  # type: ignore[reportMissingImports]
            # Extract LoRA weights from PEFT model
            lora_state_dict = {}
            for name, param in pipe.unet.named_parameters():
                if "lora" in name.lower() and param.requires_grad:
                    lora_state_dict[name] = param.cpu().clone()
            
            if lora_state_dict:
                save_file(lora_state_dict, lora_path)
                print(f"[OK] LoRA saved (alternative method) to {lora_path}")
            else:
                print(f"[ERROR] No LoRA weights found to save")
                raise ValueError("No LoRA weights found")
        except Exception as e2:
            print(f"[ERROR] Failed to save LoRA: {e2}")
            raise
    
    # ==================== STEP 8: Generate Test Image ====================
    print("\n[*] Step 8: Generating test image...")
    
    pipe.unet.eval()
    
    with torch.no_grad():
        test_prompt = f"professional headshot of {trigger_word} person"
        test_image = pipe(
            prompt=test_prompt,
            num_inference_steps=30,
            guidance_scale=7.5,
        ).images[0]
    
    test_image_path = f"{LORA_DIR}/{user_id}/{identity_id}_test.png"
    test_image.save(test_image_path)
    
    print(f"[OK] Test image saved to {test_image_path}")
    
    # ==================== STEP 8.5: Validation (face consistency score) ====================
    # Same metric as AdvancedLoRATrainer._validate_lora for fair benchmark comparison
    validation_prompts = [
        "professional headshot, business attire",
        "casual photo, outdoor setting",
        "artistic portrait, dramatic lighting",
    ]
    validation_scores_list = []
    with torch.no_grad():
        for vprompt in validation_prompts:
            full_prompt = f"a photo of {trigger_word} person, {vprompt}"
            try:
                gen_img = pipe(
                    prompt=full_prompt,
                    num_inference_steps=30,
                    guidance_scale=7.5,
                ).images[0]
                # Face similarity: reference vs generated
                arr_ref = np.array(best_face_img)
                arr_gen = np.array(gen_img)
                faces_ref = face_app.get(arr_ref)
                faces_gen = face_app.get(arr_gen)
                if faces_ref and faces_gen:
                    e_ref = faces_ref[0].embedding
                    e_gen = faces_gen[0].embedding
                    norm_r = np.linalg.norm(e_ref)
                    norm_g = np.linalg.norm(e_gen)
                    if norm_r >= 1e-9 and norm_g >= 1e-9:
                        sim = float(np.dot(e_ref, e_gen) / (norm_r * norm_g))
                        validation_scores_list.append(sim)
            except Exception:
                pass
    validation_score = float(sum(validation_scores_list) / len(validation_scores_list)) if validation_scores_list else 0.0
    print(f"[OK] Validation score (face consistency): {validation_score:.4f}")
    
    # Return results
    result = {
        "lora_path": lora_path,
        "face_embedding": best_face_embedding.tolist(),  # Best face embedding (backward compatibility)
        "trigger_word": trigger_word,
        "training_loss": loss.item(),
        "test_image_path": test_image_path,
        "validation_score": validation_score,
    }
    
    # Add face embedding path and quality if saved successfully
    if face_embedding_path and os.path.exists(face_embedding_path):
        result["face_embedding_path"] = face_embedding_path
        result["face_embedding_shape"] = list(best_face_embedding.shape)
        file_size = os.path.getsize(face_embedding_path)
        print(f"[OK] Face embedding file size: {file_size} bytes (expected ~2048 bytes for 512 floats)")
    
    # Add face quality score
    result["face_quality"] = best_face_quality
    print(f"[OK] Face quality score: {best_face_quality:.3f}")
    
    if face_reference_path and os.path.exists(face_reference_path):
        result["face_reference_path"] = face_reference_path
        file_size = os.path.getsize(face_reference_path)
        print(f"[OK] Face reference image saved: {file_size} bytes")
    
    return result

# ==================== Advanced LoRA training (augmentation + regularization + Prodigy) ====================

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
def train_lora_advanced(
    user_id: str,
    identity_id: str,
    image_urls: list[str],
    trigger_word: str = "sks",
    training_steps: int = 3000,
    use_regularization: bool = True,
):
    """
    Train identity LoRA with augmentation and optional regularization (AdvancedLoRATrainer).
    Uses Prodigy optimizer and validation pipeline.
    """
    from PIL import Image
    import requests
    import numpy as np
    from diffusers import StableDiffusionXLPipeline
    from peft import LoraConfig, get_peft_model
    from insightface.app import FaceAnalysis
    import os
    import shutil

    print("[*] Advanced LoRA training: download images...")
    images = []
    for url in image_urls:
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            images.append(img)
        except Exception as e:
            print(f"[WARN] Skip {url}: {e}")
    if len(images) < 5:
        raise ValueError(f"Need at least 5 images, got {len(images)}")

    print("[*] Face detection...")
    face_app = FaceAnalysis(name="buffalo_l")
    face_app.prepare(ctx_id=0, det_size=(640, 640))

    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    model_path = Path(f"{MODEL_DIR}/sdxl-base")
    model_repo = str(model_path) if model_path.exists() and any(model_path.iterdir()) else "stabilityai/stable-diffusion-xl-base-1.0"
    kwargs = {"torch_dtype": __import__("torch").float16, "variant": "fp16", "use_safetensors": True, "cache_dir": MODEL_DIR}
    if hf_token:
        kwargs["token"] = hf_token
    pipe = StableDiffusionXLPipeline.from_pretrained(model_repo, **kwargs).to("cuda")
    lora_config = LoraConfig(r=64, lora_alpha=64, target_modules=["to_q", "to_k", "to_v", "to_out.0"], lora_dropout=0.1, bias="none")
    pipe.unet = get_peft_model(pipe.unet, lora_config)

    trainer = AdvancedLoRATrainer(pipe=pipe, face_app=face_app, trigger_word=trigger_word, device="cuda", lora_dir=f"{LORA_DIR}/{user_id}/{identity_id}")
    identity_faces = trainer._detect_and_crop_faces(images)
    if len(identity_faces) < 2:
        raise ValueError("Need at least 2 valid face crops")
    reg_images = trainer._load_default_regularization() if use_regularization else []
    print(f"[*] Augmentation + training ({training_steps} steps, reg={len(reg_images)} images)...")
    unet, validation_score = trainer.train_identity_lora(
        identity_images=identity_faces,
        regularization_images=reg_images if reg_images else None,
        steps=training_steps,
        batch_size=4,
        identity_ratio=0.8,
    )

    lora_dir = f"{LORA_DIR}/{user_id}/{identity_id}"
    os.makedirs(lora_dir, exist_ok=True)
    pipe.unet = unet
    pipe.unet.save_pretrained(lora_dir)
    lora_path = f"{lora_dir}/lora.safetensors"
    adapter = Path(lora_dir) / "adapter_model.safetensors"
    if adapter.exists():
        shutil.move(str(adapter), lora_path)

    # Best face embedding and reference (use first identity face)
    ref_face_img = identity_faces[0]
    ref_faces = face_app.get(np.array(ref_face_img))
    if ref_faces:
        np.save(f"{lora_dir}/face_embedding.npy", ref_faces[0].embedding)
    ref_face_img.save(f"{lora_dir}/face_reference.jpg", "JPEG", quality=95)

    return {
        "lora_path": lora_path,
        "validation_score": validation_score,
        "trigger_word": trigger_word,
        "training_steps": training_steps,
    }


# ==================== Web Endpoint ====================
@app.function(
    image=gpu_image,
    gpu="A100",
    timeout=3600,
    volumes={
        MODEL_DIR: models_volume,
        LORA_DIR: lora_volume,
    },
    secrets=[
        modal.Secret.from_name("huggingface"),  # HUGGINGFACE_TOKEN (optional - will be None if not set)
    ],
)
@modal.fastapi_endpoint(method="POST")
def train_lora_web(item: dict):
    """
    Web endpoint wrapper for train_lora.
    Accepts POST with JSON body.
    """
    # Call the main function via .local() (runs in same container)
    result = train_lora.local(
        user_id=item.get("user_id", ""),
        identity_id=item.get("identity_id", ""),
        image_urls=item.get("image_urls", []),
        trigger_word=item.get("trigger_word", "sks"),
        training_steps=item.get("training_steps", 1000),
    )
    return result


@app.local_entrypoint()
def benchmark_lora(
    identities_path: str = "ai-pipeline/scripts/benchmark_identities.json",
    training_steps_baseline: int = 1000,
    training_steps_advanced: int = 3000,
    limit: int = 0,
):
    """
    Run train_lora vs train_lora_advanced on the same identities and compare validation_score.
    Use REGULARIZATION_URLS or REGULARIZATION_DATASET so the 20% regularization branch is used in advanced.
    Reports mean improvement and percentage of identities with >10% improvement.

    Example:
        modal run ai-pipeline/services/lora_trainer.py::benchmark_lora --identities-path ai-pipeline/scripts/benchmark_identities.json
        modal run ai-pipeline/services/lora_trainer.py::benchmark_lora --limit 5  # first 5 identities only
    """
    import json
    from pathlib import Path

    path = Path(identities_path)
    if not path.exists():
        print(f"[ERROR] Identities file not found: {path}")
        return
    with open(path, encoding="utf-8") as f:
        identities = json.load(f)
    if not isinstance(identities, list):
        identities = identities.get("identities", identities)
    if limit > 0:
        identities = identities[:limit]
    n = len(identities)
    print(f"[*] Benchmarking {n} identities (baseline steps={training_steps_baseline}, advanced steps={training_steps_advanced})")
    results = []
    for i, ident in enumerate(identities):
        user_id = ident.get("user_id", "benchmark")
        identity_id = ident.get("identity_id", f"ident_{i}")
        image_urls = ident.get("image_urls", [])
        if not image_urls or len(image_urls) < 5:
            print(f"[SKIP] {identity_id}: need at least 5 image_urls")
            continue
        print(f"[{i+1}/{n}] {identity_id} ...")
        try:
            r_baseline = train_lora.remote(
                user_id=user_id,
                identity_id=identity_id + "_baseline",
                image_urls=image_urls,
                trigger_word="sks",
                training_steps=training_steps_baseline,
            )
            r_advanced = train_lora_advanced.remote(
                user_id=user_id,
                identity_id=identity_id + "_advanced",
                image_urls=image_urls,
                trigger_word="sks",
                training_steps=training_steps_advanced,
                use_regularization=True,
            )
            baseline = r_baseline.get()
            advanced = r_advanced.get()
            score_b = baseline.get("validation_score")
            score_a = advanced.get("validation_score")
            if score_b is None:
                score_b = 0.0
            if score_a is None:
                score_a = 0.0
            improvement = (score_a - score_b) / score_b if score_b and score_b > 1e-9 else (score_a - score_b)
            improvement_pct = improvement * 100.0
            results.append({
                "identity_id": identity_id,
                "validation_score_baseline": score_b,
                "validation_score_advanced": score_a,
                "improvement_pct": improvement_pct,
            })
            print(f"    baseline={score_b:.4f} advanced={score_a:.4f} improvement={improvement_pct:+.1f}%")
        except Exception as e:
            print(f"    [FAIL] {e}")
    if not results:
        print("[ERROR] No results to report")
        return
    mean_b = sum(r["validation_score_baseline"] for r in results) / len(results)
    mean_a = sum(r["validation_score_advanced"] for r in results) / len(results)
    mean_improvement_pct = sum(r["improvement_pct"] for r in results) / len(results)
    over_10 = sum(1 for r in results if r["improvement_pct"] > 10.0)
    pct_over_10 = 100.0 * over_10 / len(results)
    print("\n" + "=" * 60)
    print("BENCHMARK REPORT: train_lora vs train_lora_advanced")
    print("=" * 60)
    print(f"Identities: {len(results)}")
    print(f"Mean validation_score (baseline):   {mean_b:.4f}")
    print(f"Mean validation_score (advanced):   {mean_a:.4f}")
    print(f"Mean improvement:                   {mean_improvement_pct:+.1f}%")
    print(f"Identities with >10% improvement:   {over_10} ({pct_over_10:.1f}%)")
    print("=" * 60)
    print("\nFor downstream face consistency: compare generated samples per identity (baseline vs advanced)")
    print("or run identity_engine / FaceConsistencyScorer on outputs to get face similarity metrics.")


@app.local_entrypoint()
def test_training():
    """
    Test LoRA training with sample images.
    
    NOTE: This test requires valid image URLs. Replace with real S3 URLs
    or use placeholder images from a public image service.
    
    Example:
        image_urls = [
            "https://your-s3-bucket.s3.amazonaws.com/training/photo1.jpg",
            "https://your-s3-bucket.s3.amazonaws.com/training/photo2.jpg",
            # ... at least 5 images total
        ]
    """
    print("\n[INFO] LoRA Training Test")
    print("=" * 50)
    print("This test requires at least 5 valid image URLs.")
    print("Please provide real S3 URLs or skip this test.")
    print("=" * 50)
    
    # Skip test if no valid URLs provided
    # Uncomment and provide real URLs to test:
    """
    image_urls = [
        "https://your-s3-bucket.s3.amazonaws.com/training/photo1.jpg",
        "https://your-s3-bucket.s3.amazonaws.com/training/photo2.jpg",
        "https://your-s3-bucket.s3.amazonaws.com/training/photo3.jpg",
        "https://your-s3-bucket.s3.amazonaws.com/training/photo4.jpg",
        "https://your-s3-bucket.s3.amazonaws.com/training/photo5.jpg",
    ]
    
    result = train_lora.remote(
        user_id="test_user",
        identity_id="test_identity_1",
        image_urls=image_urls,
        trigger_word="sks",
        training_steps=100,  # Use 100 for testing, 1000 for production
    )
    
    print("\n[OK] Training Complete!")
    print(f"LoRA Path: {result['lora_path']}")
    print(f"Test Image: {result['test_image_path']}")
    """
    
    print("\n[SKIP] Test skipped - no image URLs provided")
    print("To run this test, uncomment the code above and provide valid image URLs.")

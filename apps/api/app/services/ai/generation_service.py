"""
Production-grade SDXL Generation Service for PhotoGenius AI.

Features:
- SDXL base model integration with lazy loading
- LoRA weight loading from S3 with caching and strength control
- InstantID face analyzer for embedding extraction (requires insightface)
- Mode-specific generation (REALISM, CREATIVE, ROMANTIC)
- Multi-candidate generation with best-of-N selection
- Quality scoring integration
- Performance optimization (VAE slicing, xformers, CPU offload)
- GPU memory management
- Comprehensive error handling and validation
- Progress callbacks for real-time updates

InstantID Integration Notes:
- Face analyzer is initialized and can extract embeddings from images
- Full InstantID ControlNet pipeline requires additional setup:
  * InstantID ControlNet model (separate from base SDXL)
  * IP-Adapter for face embedding injection
  * Custom pipeline combining SDXL + ControlNet + IP-Adapter
- Current implementation uses LoRA for identity preservation
- Face embeddings are extracted and prepared for future InstantID integration
"""

import torch  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from pathlib import Path
import asyncio
import logging
from PIL import Image  # type: ignore[reportMissingImports]
import io
import time
import os

# Diffusers
from diffusers import (  # type: ignore[reportMissingImports]
    StableDiffusionXLPipeline,
    DPMSolverMultistepScheduler,
    EulerAncestralDiscreteScheduler,
)
from diffusers.loaders import LoraLoaderMixin  # type: ignore[reportMissingImports]

# InstantID (if available)
try:
    from insightface.app import FaceAnalysis  # type: ignore[reportMissingImports]

    INSTANTID_AVAILABLE = True
except ImportError:
    INSTANTID_AVAILABLE = False
    logging.warning("InstantID not available - face consistency will be reduced")

from app.core.config import get_settings
from app.services.storage.s3_service import get_s3_service

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for generation"""

    mode: str  # REALISM, CREATIVE, ROMANTIC
    num_candidates: int
    num_inference_steps: int
    guidance_scale: float
    width: int
    height: int
    seed: Optional[int]
    controlnet_scale: float  # Identity strength
    use_best_selection: bool


@dataclass
class GenerationResult:
    """Result of image generation"""

    images: List[Image.Image]
    seeds: List[int]
    generation_time: float
    selected_index: Optional[int]
    quality_scores: Optional[List[Dict[str, float]]]
    metadata: Dict


class SDXLGenerationService:
    """
    Production-grade SDXL generation service

    Features:
    - LoRA integration for identity preservation
    - InstantID for face consistency
    - Mode-specific optimization
    - Multi-candidate generation
    - Automatic best selection
    - GPU memory management
    """

    # Mode-specific default configs
    MODE_CONFIGS = {
        "REALISM": GenerationConfig(
            mode="REALISM",
            num_candidates=4,  # Generate 4, return top 2
            num_inference_steps=40,
            guidance_scale=7.5,
            width=1024,
            height=1024,
            seed=None,
            controlnet_scale=0.90,  # High identity preservation
            use_best_selection=True,
        ),
        "CREATIVE": GenerationConfig(
            mode="CREATIVE",
            num_candidates=6,  # More variety
            num_inference_steps=35,
            guidance_scale=8.0,
            width=1024,
            height=1024,
            seed=None,
            controlnet_scale=0.70,  # Medium identity
            use_best_selection=True,
        ),
        "ROMANTIC": GenerationConfig(
            mode="ROMANTIC",
            num_candidates=4,
            num_inference_steps=35,
            guidance_scale=7.5,
            width=1024,
            height=1024,
            seed=None,
            controlnet_scale=0.80,
            use_best_selection=True,
        ),
        "CINEMATIC": GenerationConfig(
            mode="CINEMATIC",
            num_candidates=4,
            num_inference_steps=40,
            guidance_scale=8.0,
            width=1216,
            height=832,
            seed=None,
            controlnet_scale=0.75,
            use_best_selection=True,
        ),
        "FASHION": GenerationConfig(
            mode="FASHION",
            num_candidates=4,
            num_inference_steps=40,
            guidance_scale=7.5,
            width=832,
            height=1216,
            seed=None,
            controlnet_scale=0.80,
            use_best_selection=True,
        ),
        "COOL_EDGY": GenerationConfig(
            mode="COOL_EDGY",
            num_candidates=4,
            num_inference_steps=40,
            guidance_scale=8.0,
            width=1024,
            height=1024,
            seed=None,
            controlnet_scale=0.70,
            use_best_selection=True,
        ),
        "ARTISTIC": GenerationConfig(
            mode="ARTISTIC",
            num_candidates=5,
            num_inference_steps=45,
            guidance_scale=8.5,
            width=1024,
            height=1024,
            seed=None,
            controlnet_scale=0.65,
            use_best_selection=True,
        ),
        "MAX_SURPRISE": GenerationConfig(
            mode="MAX_SURPRISE",
            num_candidates=5,
            num_inference_steps=45,
            guidance_scale=9.0,
            width=1024,
            height=1024,
            seed=None,
            controlnet_scale=0.60,
            use_best_selection=True,
        ),
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: Optional[str] = None,
        enable_cpu_offload: bool = False,
    ):
        """
        Initialize SDXL generation service

        Args:
            model_path: HuggingFace model path (defaults to config)
            device: Device to use (cuda/cpu, defaults to auto-detect)
            enable_cpu_offload: Enable model CPU offload for memory
        """
        logger.info("Initializing SDXL Generation Service...")

        settings = get_settings()

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_path = model_path or settings.SDXL_MODEL_PATH
        self.enable_cpu_offload = enable_cpu_offload

        # Initialize pipeline (lazy loading - only when needed)
        self.pipe: Optional[StableDiffusionXLPipeline] = None
        self._pipe_initialized = False

        # Initialize InstantID if available
        self.face_analyzer = None
        self.instantid_available = False
        if INSTANTID_AVAILABLE:
            try:
                # Only initialize on CUDA (CPU is too slow for production)
                if self.device == "cuda":
                    self.face_analyzer = FaceAnalysis(name="buffalo_l")
                    self.face_analyzer.prepare(ctx_id=0, det_size=(640, 640))
                    self.instantid_available = True
                    logger.info("✓ InstantID face analyzer loaded")
                else:
                    logger.info("InstantID available but skipped (CPU mode - too slow)")
            except Exception as e:
                logger.warning(f"InstantID initialization failed: {e}")

        # Currently loaded LoRA
        self.current_lora_path = None

        # Statistics
        self.stats = {
            "total_generations": 0,
            "total_images": 0,
            "avg_generation_time": 0.0,
            "lora_loads": 0,
        }

        logger.info("[OK] SDXL Generation Service initialized (lazy loading enabled)")

    def _ensure_pipeline_loaded(self):
        """Lazy load the pipeline on first use"""
        if self._pipe_initialized:
            return

        logger.info(f"Loading SDXL from {self.model_path}...")

        try:
            # Load base pipeline
            self.pipe = StableDiffusionXLPipeline.from_pretrained(
                self.model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                variant="fp16" if self.device == "cuda" else None,
                use_safetensors=True,
            )

            assert self.pipe is not None
            # Move to device
            if not self.enable_cpu_offload:
                self.pipe = self.pipe.to(self.device)
            else:
                self.pipe.enable_model_cpu_offload()
                logger.info("CPU offload enabled for memory optimization")

            # Enable memory optimizations
            self.pipe.enable_vae_slicing()
            self.pipe.enable_vae_tiling()

            # Try to enable xformers
            try:
                self.pipe.enable_xformers_memory_efficient_attention()
                logger.info("✓ xformers memory efficient attention enabled")
            except Exception as e:
                logger.warning(f"xformers not available: {e}")

            # Use faster scheduler
            self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                self.pipe.scheduler.config,
                use_karras_sigmas=True,
                algorithm_type="dpmsolver++",
            )

            self._pipe_initialized = True
            logger.info("✓ SDXL pipeline loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load SDXL pipeline: {e}")
            raise

    def _validate_identity_data(self, identity_data: Optional[Dict]) -> None:
        """
        Validate identity data structure

        Args:
            identity_data: Identity data dict to validate

        Raises:
            ValueError: If identity_data is invalid
        """
        if identity_data is None:
            return  # None is valid (no identity)

        if not isinstance(identity_data, dict):
            raise ValueError("identity_data must be a dictionary")

        # Check for at least one identity method
        has_lora = bool(identity_data.get("lora_path"))
        has_face_embedding = identity_data.get("face_embedding") is not None
        has_face_image = bool(identity_data.get("face_image"))

        if not (has_lora or has_face_embedding or has_face_image):
            raise ValueError(
                "identity_data must contain at least one of: "
                "lora_path, face_embedding, or face_image"
            )

        # Validate lora_path if provided
        if has_lora:
            lora_path = identity_data["lora_path"]
            if not isinstance(lora_path, str):
                raise ValueError("lora_path must be a string")
            if not (lora_path.startswith("s3://") or os.path.exists(lora_path)):
                logger.warning(f"LoRA path may not exist: {lora_path}")

        # Validate face_embedding if provided
        if has_face_embedding:
            face_emb = identity_data["face_embedding"]
            if not isinstance(face_emb, np.ndarray):
                raise ValueError("face_embedding must be a numpy array")
            if len(face_emb.shape) != 1 or face_emb.shape[0] not in [512, 1024]:
                raise ValueError(
                    f"face_embedding must be 1D array of shape (512,) or (1024,), "
                    f"got {face_emb.shape}"
                )

        # Validate lora_strength if provided
        if identity_data.get("lora_strength") is not None:
            strength = identity_data["lora_strength"]
            if not isinstance(strength, (int, float)) or not (0.0 <= strength <= 1.0):
                raise ValueError("lora_strength must be a float between 0.0 and 1.0")

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        identity_data: Optional[Dict] = None,
        mode: str = "REALISM",
        config_override: Optional[GenerationConfig] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> GenerationResult:
        """
        Generate images with identity preservation

        Args:
            prompt: Positive prompt
            negative_prompt: Negative prompt (optional, defaults to mode-specific)
            identity_data: Dict with optional keys:
                - lora_path: S3 URL or local path to LoRA weights
                - face_embedding: numpy array of face embedding (512 or 1024 dim)
                - face_image: PIL Image or path/bytes to face image
                - trigger_word: LoRA trigger word (default: "sks")
                - lora_strength: LoRA strength 0.0-1.0 (default: 0.8)
            mode: Generation mode (REALISM, CREATIVE, ROMANTIC)
            config_override: Override default config
            progress_callback: Callback for progress updates (progress: int, message: str)

        Returns:
            GenerationResult with images and metadata

        Raises:
            ValueError: If parameters are invalid
            FileNotFoundError: If LoRA file not found
            RuntimeError: If generation fails
        """
        start_time = time.time()

        try:
            # Validate inputs
            if not prompt or not isinstance(prompt, str):
                raise ValueError("prompt must be a non-empty string")

            # Validate identity data
            self._validate_identity_data(identity_data)

            # Ensure pipeline is loaded
            self._ensure_pipeline_loaded()

            # Get config
            mode_upper = mode.upper()
            if mode_upper not in self.MODE_CONFIGS:
                raise ValueError(
                    f"Invalid mode: {mode}. Must be one of: REALISM, CREATIVE, ROMANTIC, CINEMATIC, FASHION, COOL_EDGY, ARTISTIC, MAX_SURPRISE"
                )

            config = config_override or self.MODE_CONFIGS[mode_upper]

            # Default negative prompt
            if not negative_prompt:
                negative_prompt = self._get_default_negative_prompt(mode_upper)

            # Progress: Loading LoRA
            cb = progress_callback
            if cb:
                await cb(10, "Loading identity model...")

            # Process identity data
            face_embedding = None
            if identity_data:
                # Load LoRA weights if provided
                if identity_data.get("lora_path"):
                    await self._load_lora(
                        identity_data["lora_path"], strength=identity_data.get("lora_strength", 0.8)
                    )

                # Get or extract face embedding for InstantID
                face_embedding = identity_data.get("face_embedding")

                # If face_embedding is None but face_image is provided, extract it
                if face_embedding is None and identity_data.get("face_image"):
                    face_image_input = identity_data["face_image"]
                    face_image = self._convert_face_image(face_image_input)

                    if face_image is None:
                        logger.warning(
                            "Failed to convert face image, skipping embedding extraction"
                        )
                    else:
                        face_embedding = await self._extract_face_embedding(face_image)

                        if face_embedding is None:
                            logger.warning("Failed to extract face embedding from image")
                        else:
                            # Store extracted embedding for potential reuse
                            identity_data["face_embedding"] = face_embedding

            # Add trigger word to prompt
            trigger_word = identity_data.get("trigger_word", "sks") if identity_data else "sks"
            enhanced_prompt = self._enhance_prompt_with_trigger(prompt, trigger_word, mode_upper)

            # Progress: Generating candidates
            if cb:
                await cb(30, f"Generating {config.num_candidates} candidates...")

            # Generate multiple candidates
            candidates = await self._generate_candidates(
                prompt=enhanced_prompt,
                negative_prompt=negative_prompt,
                face_embedding=face_embedding,
                config=config,
                progress_callback=progress_callback,
            )

            # Progress: Selecting best
            if cb:
                await cb(90, "Selecting best images...")

            # Select best images if enabled
            selected_index = None
            quality_scores = None

            if config.use_best_selection:
                # Import quality scorer
                from .quality_scorer import QualityScorer

                scorer = QualityScorer()

                # Score all candidates
                quality_scores = await scorer.score_batch(
                    images=candidates["images"],
                    reference_embedding=face_embedding,
                    mode=mode_upper,
                )

                # Sort by total score
                qs = quality_scores
                assert qs is not None
                sorted_indices = sorted(
                    range(len(qs)), key=lambda i: qs[i]["total_score"], reverse=True
                )

                # Select top 2 for realism, top 3 for creative
                num_to_return = 2 if mode_upper == "REALISM" else 3
                best_indices = sorted_indices[:num_to_return]

                # Reorder
                candidates["images"] = [candidates["images"][i] for i in best_indices]
                candidates["seeds"] = [candidates["seeds"][i] for i in best_indices]
                quality_scores = [qs[i] for i in best_indices]

                selected_index = 0  # Best is now first

            # Calculate generation time
            generation_time = time.time() - start_time

            # Update statistics
            self.stats["total_generations"] += 1
            self.stats["total_images"] += len(candidates["images"])
            self.stats["avg_generation_time"] = (
                self.stats["avg_generation_time"] * (self.stats["total_generations"] - 1)
                + generation_time
            ) / self.stats["total_generations"]

            # Progress: Complete
            if cb:
                await cb(100, "Generation complete!")

            return GenerationResult(
                images=candidates["images"],
                seeds=candidates["seeds"],
                generation_time=generation_time,
                selected_index=selected_index,
                quality_scores=quality_scores,
                metadata={
                    "mode": mode_upper,
                    "num_candidates": config.num_candidates,
                    "num_returned": len(candidates["images"]),
                    "config": config.__dict__,
                    "model": self.model_path,
                },
            )

        except Exception as e:
            logger.error(f"Generation failed: {e}", exc_info=True)
            raise

    async def _load_lora(self, lora_path: str, strength: float = 0.8):
        """
        Load LoRA weights from S3 or local path

        Args:
            lora_path: S3 URL or local path to LoRA weights
            strength: LoRA strength (0.0-1.0), controls influence on generation
        """
        try:
            # Skip if already loaded
            if self.current_lora_path == lora_path:
                logger.debug("LoRA already loaded, skipping")
                return

            # Download from S3 if needed
            if lora_path.startswith("s3://"):
                local_path = await self._download_from_s3(lora_path)
            else:
                local_path = lora_path

            # Ensure pipeline is loaded
            self._ensure_pipeline_loaded()

            # Unload previous LoRA
            if self.current_lora_path and self.pipe:
                try:
                    if hasattr(self.pipe, "unload_lora_weights"):
                        self.pipe.unload_lora_weights()
                except Exception as e:
                    logger.warning(f"Failed to unload previous LoRA: {e}")

            # Load new LoRA
            logger.info(f"Loading LoRA from {local_path}")

            # Check if file exists
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"LoRA file not found: {local_path}")

            pipe = self.pipe
            if pipe is not None and hasattr(pipe, "load_lora_weights"):
                # Diffusers supports adapter_name and weight_name for multiple LoRAs
                # For single LoRA, we can use the weight parameter
                try:
                    pipe.load_lora_weights(
                        local_path,
                        weight_name=None,  # Auto-detect weight file
                    )
                    # Set LoRA scale if supported
                    if hasattr(pipe, "set_adapters"):
                        # For newer diffusers with adapter support
                        pipe.set_adapters(["default"], adapter_weights=[strength])
                    elif hasattr(pipe, "fuse_lora"):
                        # Fuse LoRA with strength
                        pipe.fuse_lora(lora_scale=strength)
                    else:
                        # Apply strength via LoRA scale parameter
                        logger.info(
                            f"LoRA loaded with strength {strength} (applied during generation)"
                        )
                except Exception as e:
                    logger.warning(f"Failed to load LoRA with strength parameter: {e}")
                    # Fallback: load without strength (will use default)
                    pipe.load_lora_weights(local_path)
            else:
                # Fallback for older diffusers versions
                logger.warning("LoRA loading not supported in this diffusers version")

            self.current_lora_path = lora_path
            self.stats["lora_loads"] += 1

            logger.info("✓ LoRA loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load LoRA: {e}", exc_info=True)
            raise

    async def _download_from_s3(self, s3_url: str) -> str:
        """
        Download LoRA from S3 to local cache

        Args:
            s3_url: S3 URL (s3://bucket/path/to/lora.safetensors)

        Returns:
            Local file path
        """
        try:
            from urllib.parse import urlparse

            # Parse S3 URL
            parsed = urlparse(s3_url)
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")

            # Local cache path
            cache_dir = Path("/tmp/lora_cache")
            if os.name == "nt":  # Windows
                cache_dir = Path(os.getenv("TEMP", "C:/temp")) / "lora_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            local_path = cache_dir / Path(key).name

            # Check if already cached
            if local_path.exists():
                logger.debug(f"Using cached LoRA: {local_path}")
                return str(local_path)

            # Download from S3 using S3Service
            logger.info(f"Downloading LoRA from S3: {s3_url}")

            s3_service = get_s3_service()
            settings = get_settings()

            # Get credentials (support both AWS_* and S3_* env vars)
            access_key = settings.AWS_ACCESS_KEY_ID or settings.S3_ACCESS_KEY
            secret_key = settings.AWS_SECRET_ACCESS_KEY or settings.S3_SECRET_KEY
            region = settings.AWS_REGION or settings.S3_REGION or "us-east-1"

            # Use async download
            async with s3_service.async_session.client(
                "s3",
                endpoint_url=s3_service.endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            ) as s3:
                await s3.download_file(bucket, key, str(local_path))

            logger.info(f"✓ LoRA downloaded to {local_path}")
            return str(local_path)

        except Exception as e:
            logger.error(f"S3 download failed: {e}", exc_info=True)
            raise

    def _convert_face_image(self, face_image) -> Optional[Image.Image]:
        """
        Convert various face image formats to PIL Image

        Args:
            face_image: Can be PIL Image, file path (str), or bytes

        Returns:
            PIL Image or None if conversion fails
        """
        try:
            if isinstance(face_image, Image.Image):
                return face_image.convert("RGB")
            elif isinstance(face_image, str):
                # File path
                return Image.open(face_image).convert("RGB")
            elif isinstance(face_image, bytes):
                # Bytes data
                return Image.open(io.BytesIO(face_image)).convert("RGB")
            else:
                logger.error(f"Unsupported face_image type: {type(face_image)}")
                return None
        except Exception as e:
            logger.error(f"Failed to convert face image: {e}", exc_info=True)
            return None

    async def _extract_face_embedding(self, face_image: Image.Image) -> Optional[np.ndarray]:
        """
        Extract face embedding from image using InstantID face analyzer

        Args:
            face_image: PIL Image containing a face

        Returns:
            Face embedding array (512-dim) or None if extraction fails
        """
        if not self.face_analyzer:
            logger.warning("Face analyzer not available, cannot extract embedding")
            return None

        try:
            # Convert PIL to numpy array for InsightFace
            import cv2  # type: ignore[reportMissingImports]

            img_array = np.array(face_image.convert("RGB"))
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

            # Detect faces
            faces = self.face_analyzer.get(img_array)

            if not faces or len(faces) == 0:
                logger.warning("No faces detected in image")
                return None

            # Use the first (largest) face
            face = faces[0]

            # Get face embedding (normed_embedding)
            # InsightFace returns 512-dimensional embedding
            embedding = face.normed_embedding

            # Ensure it's a numpy array
            if not isinstance(embedding, np.ndarray):
                embedding = np.array(embedding)

            logger.info(f"✓ Face embedding extracted: shape {embedding.shape}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to extract face embedding: {e}", exc_info=True)
            return None

    async def _generate_candidates(
        self,
        prompt: str,
        negative_prompt: str,
        face_embedding: Optional[np.ndarray],
        config: GenerationConfig,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, List]:
        """
        Generate multiple candidate images

        Returns dict with images and seeds
        """
        images = []
        seeds = []

        # Prepare generation kwargs
        generation_kwargs = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "num_inference_steps": config.num_inference_steps,
            "guidance_scale": config.guidance_scale,
            "height": config.height,
            "width": config.width,
            "num_images_per_prompt": 1,
        }

        # Add face embedding support for InstantID/IP-Adapter
        if face_embedding is not None:
            try:
                # Convert numpy embedding to tensor
                face_embedding_tensor = torch.from_numpy(face_embedding).to(
                    device=self.device, dtype=torch.float32
                )
                # Reshape if needed (InstantID typically uses [1, 512] or [512])
                if len(face_embedding_tensor.shape) == 1:
                    face_embedding_tensor = face_embedding_tensor.unsqueeze(0)

                # Try IP-Adapter first (if pipeline supports it)
                if hasattr(self.pipe, "set_ip_adapter_scale"):
                    ip_adapter_scale = config.controlnet_scale
                    # Note: IP-Adapter typically expects image, not embedding
                    # This is a placeholder - full InstantID requires ControlNet
                    logger.debug(f"IP-Adapter available but requires image input, not embedding")

                # Store embedding for potential use in custom pipeline
                # In full InstantID implementation, this would be passed to ControlNet
                generation_kwargs["_face_embedding"] = face_embedding_tensor
                generation_kwargs["_controlnet_scale"] = config.controlnet_scale

                logger.debug(
                    f"Face embedding prepared for generation (scale: {config.controlnet_scale})"
                )

            except Exception as e:
                logger.warning(f"Failed to prepare face embedding: {e}")
                # Continue without face embedding - LoRA will handle identity

        pcb = progress_callback
        for i in range(config.num_candidates):
            # Progress update
            if pcb:
                progress = 30 + int((i / config.num_candidates) * 60)
                await pcb(progress, f"Generating image {i+1}/{config.num_candidates}...")

            # Generate seed
            if config.seed is not None:
                seed = config.seed + i
            else:
                seed = torch.randint(0, 2**32, (1,)).item()

            generator = torch.Generator(device=self.device).manual_seed(seed)
            generation_kwargs["generator"] = generator

            # Remove internal kwargs before passing to pipeline
            face_emb = generation_kwargs.pop("_face_embedding", None)
            controlnet_scale = generation_kwargs.pop("_controlnet_scale", None)

            # Generate image
            pipe = self.pipe
            if pipe is None:
                raise RuntimeError("Pipeline not loaded")
            with torch.inference_mode():
                result = pipe(**generation_kwargs)

            # Note: Full InstantID integration would require:
            # 1. InstantID ControlNet pipeline (separate from base SDXL)
            # 2. IP-Adapter for face embedding injection
            # 3. Custom pipeline combining SDXL + ControlNet + IP-Adapter
            # Current implementation uses LoRA for identity, which works well
            # but doesn't provide the same level of face consistency as InstantID

            images.append(result.images[0])
            seeds.append(seed)

            # Clear CUDA cache periodically
            if (i + 1) % 2 == 0 and self.device == "cuda":
                torch.cuda.empty_cache()

        return {
            "images": images,
            "seeds": seeds,
        }

    def _enhance_prompt_with_trigger(self, prompt: str, trigger_word: str, mode: str) -> str:
        """
        Add trigger word and mode-specific enhancements

        Args:
            prompt: Original prompt
            trigger_word: LoRA trigger word (e.g., "sks")
            mode: Generation mode

        Returns:
            Enhanced prompt
        """
        # Replace generic person references with trigger word
        prompt = prompt.replace("person", f"{trigger_word} person")
        prompt = prompt.replace("man", f"{trigger_word} man")
        prompt = prompt.replace("woman", f"{trigger_word} woman")

        # Add trigger if not present
        if trigger_word not in prompt:
            prompt = f"{trigger_word}, {prompt}"

        # Mode-specific enhancements
        if mode == "REALISM":
            if "professional" not in prompt.lower():
                prompt += ", professional photography, high quality, sharp focus"
        elif mode == "CREATIVE":
            if "art" not in prompt.lower():
                prompt += ", creative, artistic, detailed"
        elif mode == "ROMANTIC":
            if "elegant" not in prompt.lower():
                prompt += ", elegant, tasteful, romantic atmosphere"
        elif mode == "CINEMATIC":
            if "cinematic" not in prompt.lower():
                prompt += ", cinematic, dramatic lighting, film grain"
        elif mode == "FASHION":
            if "editorial" not in prompt.lower():
                prompt += ", editorial, high fashion, studio lighting"
        elif mode == "COOL_EDGY":
            if "moody" not in prompt.lower():
                prompt += ", moody, neon, cyberpunk, high contrast"
        elif mode == "ARTISTIC":
            if "surreal" not in prompt.lower():
                prompt += ", surreal, painterly, artistic, dreamlike"
        elif mode == "MAX_SURPRISE":
            if "bold" not in prompt.lower():
                prompt += ", bold, unconventional, striking, unique"
        return prompt

    def _get_default_negative_prompt(self, mode: str) -> str:
        """Get default negative prompt for mode (includes anatomy/object coherence)."""
        base_negative = (
            "blurry, low quality, distorted, deformed, ugly, bad anatomy, "
            "bad proportions, extra limbs, duplicate, mutilated, disfigured, "
            "out of frame, extra fingers, mutated hands, poorly drawn hands, "
            "poorly drawn face, mutation, deformed, bad art, bad proportions, "
            "extra limbs, cloned face, disfigured, gross proportions, malformed limbs, "
            "missing arms, missing legs, missing hands, amputated, hand cut off, "
            "invisible hand, phantom limb, hand absorbed, duplicate object, extra ball, "
            "floating duplicate, cloned object, extra arms, extra legs, fused fingers, "
            "too many fingers, long neck, watermark, signature"
        )

        if mode == "REALISM":
            return base_negative + ", cartoon, anime, painting, illustration, drawing"
        elif mode == "CREATIVE":
            return base_negative + ", boring, plain, uninteresting"
        elif mode == "ROMANTIC":
            return base_negative + ", inappropriate, explicit, nsfw"
        elif mode == "CINEMATIC":
            return base_negative + ", flat, boring, amateur, cartoon, anime"
        elif mode == "FASHION":
            return base_negative + ", casual, sloppy, amateur, flat lighting"
        elif mode == "COOL_EDGY":
            return base_negative + ", bright, cheerful, pastel, soft, boring"
        elif mode == "ARTISTIC":
            return base_negative + ", photorealistic, boring, plain, conventional"
        elif mode == "MAX_SURPRISE":
            return base_negative + ", boring, generic, predictable, safe"
        return base_negative

    def get_statistics(self) -> Dict:
        """Get generation statistics"""
        stats = self.stats.copy()
        stats["instantid_available"] = self.instantid_available
        return stats

    def is_instantid_available(self) -> bool:
        """Check if InstantID is available and ready"""
        return self.instantid_available and self.face_analyzer is not None

    def clear_cache(self):
        """Clear GPU cache and unload models"""
        if self.current_lora_path and self.pipe:
            try:
                self.pipe.unload_lora_weights()
            except Exception:
                pass
            self.current_lora_path = None

        if self.device == "cuda":
            torch.cuda.empty_cache()

        logger.info("Cache cleared")


# ==================== SINGLETON INSTANCE ====================

_generation_service: Optional[SDXLGenerationService] = None


def get_generation_service() -> SDXLGenerationService:
    """Get or create generation service singleton"""
    global _generation_service
    if _generation_service is None:
        settings = get_settings()
        _generation_service = SDXLGenerationService(
            model_path=settings.SDXL_MODEL_PATH,
            device=None,  # Auto-detect
            enable_cpu_offload=False,  # Can be made configurable
        )
    return _generation_service

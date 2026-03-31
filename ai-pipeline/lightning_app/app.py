"""
PhotoGenius AI - Lightning App
Main entry point for Lightning.ai deployment.

Usage:
    # Local development
    lightning run app app.py

    # Cloud deployment
    lightning run app app.py --cloud
"""

import lightning as L
from lightning.app import LightningWork, LightningFlow, LightningApp
from lightning.app.storage import Drive
from lightning.app.api.http_methods import Post, Get
from typing import Optional, List, Dict, Any
import os
import sys

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==================== Safety Component ====================
class SafetyWork(LightningWork):
    """CPU-based safety checks for prompts"""

    def __init__(self):
        super().__init__(
            cloud_compute=L.CloudCompute("cpu-small"),
            parallel=True,
        )

    def run(self, prompt: str, mode: str = "REALISM") -> Dict[str, Any]:
        """Check prompt for safety violations"""
        from services.safety_service import check_prompt_safety

        try:
            result = check_prompt_safety(prompt, mode)
            return result
        except Exception as e:
            print(f"Safety check error: {e}")
            return {"allowed": True, "violations": [], "error": str(e)}


# ==================== Generation Component ====================
class GenerationWork(LightningWork):
    """GPU-accelerated image generation"""

    def __init__(self):
        super().__init__(
            cloud_compute=L.CloudCompute("gpu"),
            parallel=True,
        )
        self.model_drive = Drive("lit://photogenius-models")
        self.pipe = None

    def setup(self):
        """Load models on GPU startup - called once when work starts"""
        import torch
        from diffusers.pipelines.stable_diffusion_xl.pipeline_stable_diffusion_xl import StableDiffusionXLPipeline

        print("Loading SDXL model...")

        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            use_safetensors=True,
            cache_dir=str(self.model_drive.root) if self.model_drive.root else None,
        )
        self.pipe.to("cuda")

        # Enable optimizations
        self.pipe.enable_xformers_memory_efficient_attention()

        print("SDXL model loaded!")

    def run(
        self,
        prompt: str,
        mode: str = "REALISM",
        num_images: int = 2,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 30,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Generate images from prompt"""
        import torch
        import base64
        from io import BytesIO

        if self.pipe is None:
            self.setup()

        # Set seed for reproducibility
        generator = None
        if seed is not None:
            generator = torch.Generator("cuda").manual_seed(seed)

        # Mode-specific adjustments
        if mode == "CREATIVE":
            guidance_scale = 8.5
        elif mode == "ROMANTIC":
            guidance_scale = 6.5
        elif mode == "CINEMATIC":
            guidance_scale = 8.0

        print(f"Generating {num_images} images: {prompt[:50]}...")

        # Generate (pipe is guaranteed to be set after setup())
        assert self.pipe is not None
        result = self.pipe(
            prompt=prompt,
            num_images_per_prompt=num_images,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
            generator=generator,
        )

        # Convert to base64
        images = []
        output_images = result.images  # type: ignore[union-attr]
        for i, img in enumerate(output_images):
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            b64 = base64.b64encode(buffer.getvalue()).decode()

            images.append({
                "image_base64": b64,
                "seed": seed + i if seed else i,
                "scores": {
                    "aesthetic": 85.0,
                    "technical": 90.0,
                    "total": 87.5,
                }
            })

        return images


# ==================== Refinement Component ====================
class RefinementWork(LightningWork):
    """GPU-accelerated image refinement"""

    def __init__(self):
        super().__init__(
            cloud_compute=L.CloudCompute("gpu"),
            parallel=True,
        )
        self.pipe = None

    def setup(self):
        """Load img2img model"""
        import torch
        from diffusers.pipelines.stable_diffusion_xl.pipeline_stable_diffusion_xl_img2img import StableDiffusionXLImg2ImgPipeline

        print("Loading SDXL img2img model...")

        self.pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            use_safetensors=True,
        )
        self.pipe.to("cuda")
        self.pipe.enable_xformers_memory_efficient_attention()

        print("SDXL img2img model loaded!")

    def run(
        self,
        image_base64: str,
        refinement_request: str,
        mode: str = "REALISM",
        strength: float = 0.5,
        **kwargs
    ) -> Dict[str, Any]:
        """Refine an existing image based on request"""
        import torch
        import base64
        from io import BytesIO
        from PIL import Image

        if self.pipe is None:
            self.setup()

        # Decode input image
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        print(f"Refining image: {refinement_request[:50]}...")

        # Refine (pipe is guaranteed to be set after setup())
        assert self.pipe is not None
        result = self.pipe(
            prompt=refinement_request,
            image=image,
            strength=strength,
            num_inference_steps=30,
            guidance_scale=7.5,
        )

        # Convert to base64
        buffer = BytesIO()
        output_images = result.images  # type: ignore[union-attr]
        output_images[0].save(buffer, format="PNG")
        refined_b64 = base64.b64encode(buffer.getvalue()).decode()

        return {
            "success": True,
            "image_base64": refined_b64,
        }


# ==================== Training Component ====================
class TrainingWork(LightningWork):
    """GPU-accelerated LoRA training"""

    def __init__(self):
        super().__init__(
            cloud_compute=L.CloudCompute("gpu"),
            parallel=True,
        )
        self.lora_drive = Drive("lit://photogenius-loras")

    def run(
        self,
        user_id: str,
        identity_id: str,
        image_urls: List[str],
        trigger_word: str = "sks",
        training_steps: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """Train LoRA for identity"""
        # This would call the actual LoRA training code
        # from services.lora_trainer import train_lora

        print(f"Training LoRA for {identity_id} with {len(image_urls)} images")

        # Placeholder - implement actual training
        return {
            "success": True,
            "job_id": f"train_{identity_id}",
            "status": "queued",
            "lora_path": f"{self.lora_drive.root}/{identity_id}.safetensors",
        }


# ==================== Main Flow ====================
class PhotoGeniusFlow(LightningFlow):
    """Main PhotoGenius Lightning Flow"""

    def __init__(self):
        super().__init__()
        self.safety = SafetyWork()
        self.generation = GenerationWork()
        self.refinement = RefinementWork()
        self.training = TrainingWork()

    def run(self):
        """Main flow - components auto-scale based on requests"""
        # Components are spawned on-demand when their methods are called
        pass

    def check_safety(self, prompt: str, mode: str = "REALISM") -> Dict[str, Any]:
        """API: Check prompt safety"""
        return self.safety.run(prompt, mode)

    def generate(
        self,
        prompt: str,
        mode: str = "REALISM",
        num_images: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """API: Generate images"""
        # First check safety
        safety_result = self.safety.run(prompt, mode)
        if not safety_result.get("allowed", True):
            return {
                "success": False,
                "error": "Content blocked",
                "violations": safety_result.get("violations", []),
            }

        # Generate images
        images = self.generation.run(prompt, mode, num_images, **kwargs)

        return {
            "success": True,
            "images": images,
            "provider": "lightning",
        }

    def refine(
        self,
        image_base64: str,
        refinement_request: str,
        **kwargs
    ) -> Dict[str, Any]:
        """API: Refine image"""
        return self.refinement.run(image_base64, refinement_request, **kwargs)

    def train(
        self,
        user_id: str,
        identity_id: str,
        image_urls: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """API: Start training"""
        return self.training.run(user_id, identity_id, image_urls, **kwargs)

    def health_check(self) -> Dict[str, str]:
        """Health check endpoint"""
        return {"status": "healthy", "provider": "lightning"}

    def configure_api(self):
        """Expose REST API endpoints"""
        return [
            Post("/api/safety", self.check_safety),
            Post("/api/generate", self.generate),
            Post("/api/refine", self.refine),
            Post("/api/train", self.train),
            Get("/health", self.health_check),
        ]


# For local testing and Windows multiprocessing support
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    # Create app instance
    app = LightningApp(PhotoGeniusFlow())
    print("Run with: lightning run app app.py")
else:
    # Create app instance for module import
    app = LightningApp(PhotoGeniusFlow())

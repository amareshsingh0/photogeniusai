"""
Modal Client - Triggers Modal functions from FastAPI

This client provides async methods to call Modal serverless GPU functions
for LoRA training, image generation, and safety checks.

INVOCATION MODES:
1. HTTP Mode (Current): Calls Modal HTTP endpoints
   - Requires MODAL_API_URL, MODAL_TOKEN_ID, MODAL_TOKEN_SECRET
   - For external services or cross-language integration
   - Use when: Calling from different repo/service

2. SDK Mode (Recommended): Uses Modal Python SDK directly
   - No MODAL_API_URL needed
   - No MODAL_TOKEN_ID/SECRET needed
   - Modal CLI auth sufficient
   - Better error handling, type safety
   - Use when: FastAPI in same repo as ai-pipeline

To switch to SDK mode:
  from ai_pipeline.services.generation_service import generate_images
  result = await generate_images.remote(...)
"""
import os
import httpx  # type: ignore[reportMissingImports]
import logging
from typing import List, Dict, Optional, Any
import asyncio

# Load environment from .env.local
from dotenv import load_dotenv
from pathlib import Path

# Load .env.local if it exists
# Path: modal_client.py -> services -> app -> api -> .env.local
env_file = Path(__file__).resolve().parents[2] / ".env.local"
if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    # Try parent folder (workspace root)
    env_file = Path(__file__).resolve().parents[4] / "apps" / "api" / ".env.local"
    if env_file.exists():
        load_dotenv(env_file, override=True)

logger = logging.getLogger(__name__)

# Modal configuration - read from environment (loaded from .env.local)
MODAL_API_URL = os.getenv("MODAL_API_URL", "https://api.modal.com")
MODAL_TOKEN_ID = os.getenv("MODAL_TOKEN_ID")
MODAL_TOKEN_SECRET = os.getenv("MODAL_TOKEN_SECRET")
MODAL_USERNAME = os.getenv("MODAL_USERNAME", "amareshsingh0")

# Log Modal configuration status
if MODAL_TOKEN_ID and MODAL_TOKEN_SECRET:
    logger.info(f"Modal credentials loaded. Username: {MODAL_USERNAME}")
else:
    logger.warning("Modal credentials not configured. Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET.")

# Modal App names (must match the app names in ai-pipeline/services/*.py)
MODAL_APPS = {
    "lora_trainer": "photogenius-lora-trainer",
    "generation": "photogenius-generation",
    "safety": "photogenius-safety",
}


class ModalClientError(Exception):
    """Custom exception for Modal client errors"""
    pass


class ModalClient:
    """
    Client for calling Modal serverless GPU functions.
    
    Provides async methods to trigger:
    - LoRA training for identity consistency
    - SDXL image generation with LoRA
    - Safety checks (prompt + image)
    """
    
    def __init__(self):
        self.base_url = MODAL_API_URL
        self.token_id = MODAL_TOKEN_ID
        self.token_secret = MODAL_TOKEN_SECRET
        
        if not self.token_id or not self.token_secret:
            logger.warning("Modal credentials not configured. Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET.")
        
        self.headers = {
            "Content-Type": "application/json",
        }
        
        # Add auth if credentials are available
        if self.token_id and self.token_secret:
            self.headers["Authorization"] = f"Bearer {self.token_id}:{self.token_secret}"
    
    def _get_function_url(self, app_name: str, function_name: str) -> str:
        """Build the Modal function URL"""
        # Modal web endpoint format: https://{username}--{app_name}-{function_name}.modal.run
        # Underscores in function names are converted to hyphens
        # Function names already include _web suffix, so don't add -web again
        function_name_hyphen = function_name.replace("_", "-")
        return f"https://{MODAL_USERNAME}--{app_name}-{function_name_hyphen}.modal.run"
    
    async def _call_function(
        self,
        app_key: str,
        function_name: str,
        payload: Dict[str, Any],
        timeout: float = 600.0,
    ) -> Dict:
        """
        Generic method to call a Modal function.
        
        Args:
            app_key: Key from MODAL_APPS dict
            function_name: Name of the function to call
            payload: JSON payload to send
            timeout: Request timeout in seconds
            
        Returns:
            Response JSON as dict
        """
        app_name = MODAL_APPS.get(app_key)
        if not app_name:
            raise ModalClientError(f"Unknown app key: {app_key}")
        
        url = self._get_function_url(app_name, function_name)
        
        logger.info(f"Calling Modal function: {app_name}/{function_name}")
        logger.debug(f"URL: {url}")
        logger.debug(f"Payload keys: {list(payload.keys())}")
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.TimeoutException as e:
            logger.error(f"Modal function timeout: {function_name}")
            raise ModalClientError(f"Request timeout calling {function_name}") from e
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Modal function HTTP error: {e.response.status_code}")
            raise ModalClientError(
                f"HTTP {e.response.status_code} from {function_name}: {e.response.text}"
            ) from e
            
        except Exception as e:
            logger.error(f"Modal function error: {str(e)}")
            raise ModalClientError(f"Error calling {function_name}: {str(e)}") from e
    
    # ==================== LoRA Training ====================
    
    async def train_lora(
        self,
        user_id: str,
        identity_id: str,
        image_urls: List[str],
        trigger_word: str = "sks",
        training_steps: int = 1000,
    ) -> Dict:
        """
        Trigger LoRA training on Modal GPU.
        
        Args:
            user_id: User ID
            identity_id: Identity ID
            image_urls: List of S3 URLs for training images (min 5)
            trigger_word: Trigger word for the LoRA (default: "sks")
            training_steps: Number of training steps (default: 1000)
        
        Returns:
            dict with:
                - lora_path: Path to saved LoRA weights
                - face_embedding: 512-dim face embedding list
                - trigger_word: The trigger word used
                - training_loss: Final training loss
                - test_image_path: Path to test image
        """
        logger.info(f"Starting LoRA training for identity: {identity_id}")
        logger.info(f"Training images: {len(image_urls)}, Steps: {training_steps}")
        
        return await self._call_function(
            app_key="lora_trainer",
            function_name="train_lora_web",  # Use web endpoint
            payload={
                "user_id": user_id,
                "identity_id": identity_id,
                "image_urls": image_urls,
                "trigger_word": trigger_word,
                "training_steps": training_steps,
            },
            timeout=3600.0,  # 1 hour for training
        )
    
    # ==================== Image Generation ====================
    
    async def generate_images(
        self,
        user_id: str,
        identity_id: str,
        prompt: str,
        mode: str = "REALISM",
        num_candidates: int = 4,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 40,
        seed: Optional[int] = None,
        face_embedding: Optional[List[float]] = None,
    ) -> List[Dict]:
        """
        Trigger SDXL image generation with LoRA on Modal GPU.
        
        Args:
            user_id: User ID
            identity_id: Identity ID (for loading LoRA)
            prompt: Generation prompt
            mode: Generation mode (REALISM/CREATIVE/ROMANTIC)
            num_candidates: Number of images to generate (default: 4)
            guidance_scale: CFG scale (default: 7.5)
            num_inference_steps: Denoising steps (default: 40)
            seed: Optional random seed for reproducibility
            face_embedding: Optional 512-dim face embedding for scoring
        
        Returns:
            List of dicts, each with:
                - image_base64: Base64 encoded PNG image
                - seed: Random seed used
                - prompt: Full enhanced prompt
                - negative_prompt: Negative prompt used
                - scores: Dict with face_match, aesthetic, technical, total
        """
        logger.info(f"Starting generation for identity: {identity_id}")
        logger.info(f"Mode: {mode}, Candidates: {num_candidates}")
        
        result = await self._call_function(
            app_key="generation",
            function_name="generate_images_web",  # Use web endpoint
            payload={
                "user_id": user_id,
                "identity_id": identity_id,
                "prompt": prompt,
                "mode": mode,
                "num_candidates": num_candidates,
                "guidance_scale": guidance_scale,
                "num_inference_steps": num_inference_steps,
                "seed": seed,
                "face_embedding": face_embedding,
            },
            timeout=600.0,  # 10 minutes
        )
        
        logger.info(f"Generation complete: {len(result)} images")
        return result if isinstance(result, list) else [result]
    
    # ==================== Safety Checks ====================
    
    async def check_prompt_safety(
        self,
        prompt: str,
        mode: str,
    ) -> Dict:
        """
        Check prompt safety before generation.
        
        Args:
            prompt: User's prompt
            mode: Generation mode (REALISM/CREATIVE/ROMANTIC)
        
        Returns:
            dict with:
                - allowed: bool - whether prompt is safe
                - violations: List of violation dicts
                - prompt: Original prompt
                - mode: Generation mode
        """
        logger.info(f"Checking prompt safety: {prompt[:50]}...")
        
        return await self._call_function(
            app_key="safety",
            function_name="check_prompt_safety_web",
            payload={
                "prompt": prompt,
                "mode": mode,
            },
            timeout=30.0,
        )
    
    async def check_image_safety(
        self,
        image_base64: str,
        mode: str,
    ) -> Dict:
        """
        Check generated image safety.
        
        Args:
            image_base64: Base64 encoded image
            mode: Generation mode (REALISM/CREATIVE/ROMANTIC)
        
        Returns:
            dict with:
                - safe: bool - whether image is safe
                - nsfw_score: float 0-1
                - age_score: float (estimated age)
                - violence_score: float 0-1
                - violations: List of violation dicts
        """
        logger.info("Checking image safety...")
        
        return await self._call_function(
            app_key="safety",
            function_name="check_image_safety_web",  # Use web endpoint
            payload={
                "image_base64": image_base64,
                "mode": mode,
            },
            timeout=60.0,
        )
    
    # ==================== Full Pipeline ====================
    
    async def generate_with_safety(
        self,
        user_id: str,
        identity_id: str,
        prompt: str,
        mode: str = "REALISM",
        num_candidates: int = 4,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 40,
        seed: Optional[int] = None,
        face_embedding: Optional[List[float]] = None,
    ) -> Dict:
        """
        Full generation pipeline with safety checks.
        
        1. Check prompt safety
        2. Generate images
        3. Check each image safety
        4. Return only safe images
        
        Args:
            Same as generate_images()
        
        Returns:
            dict with:
                - success: bool
                - images: List of safe images
                - prompt_check: Prompt safety result
                - image_checks: List of image safety results
                - error: Optional error message
        """
        result = {
            "success": False,
            "images": [],
            "prompt_check": None,
            "image_checks": [],
            "error": None,
        }
        
        try:
            # Step 1: Check prompt safety
            logger.info("Step 1: Checking prompt safety...")
            prompt_check = await self.check_prompt_safety(prompt, mode)
            result["prompt_check"] = prompt_check
            
            if not prompt_check.get("allowed", False):
                result["error"] = "Prompt failed safety check"
                logger.warning(f"Prompt blocked: {prompt_check.get('violations')}")
                return result
            
            # Step 2: Generate images
            logger.info("Step 2: Generating images...")
            generated = await self.generate_images(
                user_id=user_id,
                identity_id=identity_id,
                prompt=prompt,
                mode=mode,
                num_candidates=num_candidates,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                seed=seed,
                face_embedding=face_embedding,
            )
            
            # Step 3: Check each image safety
            logger.info("Step 3: Checking image safety...")
            safe_images = []
            
            for i, img in enumerate(generated):
                logger.info(f"Checking image {i+1}/{len(generated)}...")
                
                image_check = await self.check_image_safety(
                    img["image_base64"],
                    mode,
                )
                result["image_checks"].append(image_check)
                
                if image_check.get("safe", False):
                    safe_images.append(img)
                else:
                    logger.warning(f"Image {i+1} blocked: {image_check.get('violations')}")
            
            result["images"] = safe_images
            result["success"] = len(safe_images) > 0
            
            if not result["success"]:
                result["error"] = "All generated images failed safety check"
            
            logger.info(f"Pipeline complete: {len(safe_images)}/{len(generated)} safe images")
            
        except ModalClientError as e:
            result["error"] = str(e)
            logger.error(f"Pipeline error: {e}")
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            logger.exception("Pipeline error")
        
        return result


# Singleton instance for use across the app
modal_client = ModalClient()


# Convenience functions
async def train_identity_lora(
    user_id: str,
    identity_id: str,
    image_urls: List[str],
    trigger_word: str = "sks",
    training_steps: int = 1000,
) -> Dict:
    """Convenience function for LoRA training"""
    return await modal_client.train_lora(
        user_id=user_id,
        identity_id=identity_id,
        image_urls=image_urls,
        trigger_word=trigger_word,
        training_steps=training_steps,
    )


async def generate_identity_images(
    user_id: str,
    identity_id: str,
    prompt: str,
    mode: str = "REALISM",
    face_embedding: Optional[List[float]] = None,
) -> List[Dict]:
    """Convenience function for image generation"""
    return await modal_client.generate_images(
        user_id=user_id,
        identity_id=identity_id,
        prompt=prompt,
        mode=mode,
        face_embedding=face_embedding,
    )


async def generate_safe_images(
    user_id: str,
    identity_id: str,
    prompt: str,
    mode: str = "REALISM",
    face_embedding: Optional[List[float]] = None,
) -> Dict:
    """Convenience function for full safe generation pipeline"""
    return await modal_client.generate_with_safety(
        user_id=user_id,
        identity_id=identity_id,
        prompt=prompt,
        mode=mode,
        face_embedding=face_embedding,
    )

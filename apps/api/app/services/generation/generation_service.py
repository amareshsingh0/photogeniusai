"""
Generation Service - Advanced image generation with mode-specific templates

Adapted from ai-pipeline/services/generation_service.py for FastAPI
Uses existing generation_router for actual generation
"""

from typing import Dict, Optional, List
import time

from app.services.smart import (
    mode_detector,
    category_detector,
    prompt_enhancer,
    generation_router
)


# Mode-specific prompt templates (from ai-pipeline)
PROMPT_TEMPLATES = {
    "REALISM": {
        "prefix": "RAW photo, ",
        "quality_boost": "professional photography, high quality, sharp focus, 8k uhd, dslr, soft lighting, film grain, Fujifilm XT3, detailed skin texture, natural lighting",
        "technical": "highly detailed, photorealistic, perfect composition, depth of field, natural colors, subsurface scattering",
        "negative": "cartoon, 3d render, anime, drawing, painting, illustration, disfigured, bad art, deformed, extra limbs, close up, b&w, weird colors, blurry, duplicate, morbid, mutilated, out of frame, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, ugly, bad anatomy, bad proportions, cloning, cropped, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck, lowres, bad quality, jpeg artifacts, watermark, username, signature, text, worst quality, low quality, normal quality, overexposed, underexposed, oversaturated",
    },
    "CINEMATIC": {
        "prefix": "",
        "quality_boost": "cinematic still, anamorphic lens, film grain, dramatic lighting, movie scene, blockbuster",
        "technical": "35mm film, color grading, atmospheric, volumetric lighting, lens flare, shallow depth of field, epic composition",
        "negative": "flat, boring, amateur, low quality, blurry, bad anatomy, deformed, ugly, worst quality, overexposed, cartoon, anime, drawing",
    },
    "CREATIVE": {
        "prefix": "",
        "quality_boost": "trending on artstation, award winning, masterpiece, highly detailed, 4k, 8k, intricate details",
        "technical": "professional digital art, concept art, perfect lighting, vibrant colors, dynamic composition, cinematic color grading",
        "negative": "ugly, tiling, poorly drawn hands, poorly drawn feet, poorly drawn face, out of frame, mutation, mutated, extra limbs, extra legs, extra arms, disfigured, deformed, cross-eye, body out of frame, blurry, bad art, bad anatomy, blurred, text, watermark, grainy, worst quality, low quality, amateur, sketch, unfinished",
    },
    "FANTASY": {
        "prefix": "",
        "quality_boost": "fantasy art, magical, ethereal lighting, enchanted, mystical atmosphere, otherworldly, epic",
        "technical": "high fantasy, detailed, vibrant colors, atmospheric, dramatic lighting, intricate details, magical glow",
        "negative": "realistic, boring, plain, amateur, low quality, blurry, ugly, deformed, bad anatomy, mundane, ordinary",
    },
    "ANIME": {
        "prefix": "",
        "quality_boost": "anime style, manga aesthetic, vibrant colors, cel shading, clean lineart, detailed illustration",
        "technical": "Japanese anime, professional illustration, dynamic pose, expressive, detailed eyes, clean lines",
        "negative": "realistic, 3d render, western cartoon, ugly, bad anatomy, poorly drawn, low quality, blurry, deformed",
    }
}


class GenerationService:
    """
    Advanced generation service with mode-specific templates

    Features:
    - Auto mode detection
    - Mode-specific prompt templates
    - Advanced prompt enhancement
    - Quality-based routing
    """

    def __init__(self):
        """Initialize generation service"""
        pass

    async def generate(
        self,
        prompt: str,
        quality: str = 'STANDARD',
        width: int = 1024,
        height: int = 1024,
        mode: Optional[str] = None,
        category: Optional[str] = None,
        use_advanced_templates: bool = True,
        **kwargs
    ) -> Dict:
        """
        Generate image with advanced mode-specific templates

        Args:
            prompt: User prompt
            quality: FAST, STANDARD, or PREMIUM
            width: Image width
            height: Image height
            mode: Override mode detection (optional)
            category: Override category detection (optional)
            use_advanced_templates: Use ai-pipeline templates

        Returns:
            dict: Generation result with metadata
        """
        start_time = time.time()

        # Step 1: Detect mode and category if not provided
        if not mode:
            mode = mode_detector.detect_mode(prompt)

        if not category:
            category = category_detector.detect_category(prompt)

        # Step 2: Enhance prompt
        if use_advanced_templates and mode in PROMPT_TEMPLATES:
            # Use ai-pipeline templates
            enhanced_prompt = self._enhance_with_template(prompt, mode, quality)
            negative_prompt = PROMPT_TEMPLATES[mode]['negative']
        else:
            # Use simple smart enhancer
            enhancement = prompt_enhancer.enhance(prompt, mode, category, quality)
            enhanced_prompt = enhancement['enhanced']
            negative_prompt = enhancement['negative']

        # Step 3: Generate based on quality tier
        if quality == 'FAST':
            result = await generation_router.generate_fast(
                prompt=enhanced_prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height
            )
        elif quality == 'STANDARD':
            result = await generation_router.generate_standard(
                prompt=enhanced_prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                mode=mode
            )
        else:  # PREMIUM
            result = await generation_router.generate_premium(
                prompt=enhanced_prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                mode=mode
            )

        # Step 4: Add metadata
        result['generation_time'] = time.time() - start_time
        result['mode'] = mode
        result['category'] = category
        result['original_prompt'] = prompt
        result['enhanced_prompt'] = enhanced_prompt
        result['quality_tier'] = quality

        return result

    def _enhance_with_template(self, prompt: str, mode: str, quality: str) -> str:
        """
        Enhance prompt using ai-pipeline templates

        Args:
            prompt: Original prompt
            mode: Generation mode
            quality: Quality tier

        Returns:
            str: Enhanced prompt
        """
        if mode not in PROMPT_TEMPLATES:
            return prompt

        template = PROMPT_TEMPLATES[mode]

        # Build enhanced prompt
        enhanced_parts = []

        # Add prefix if exists
        if template.get('prefix'):
            enhanced_parts.append(template['prefix'])

        # Add original prompt
        enhanced_parts.append(prompt)

        # Add quality boost
        enhanced_parts.append(template.get('quality_boost', ''))

        # Add technical details for PREMIUM
        if quality == 'PREMIUM':
            enhanced_parts.append(template.get('technical', ''))

        return ', '.join(filter(None, enhanced_parts))

    def get_available_modes(self) -> List[str]:
        """Get list of available modes"""
        return list(PROMPT_TEMPLATES.keys())

    def get_mode_template(self, mode: str) -> Optional[Dict]:
        """Get template for specific mode"""
        return PROMPT_TEMPLATES.get(mode)


# Singleton instance
generation_service = GenerationService()

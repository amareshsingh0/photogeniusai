"""
Two-Pass Generator - Preview + Full Quality Generation

Features:
- Pass 1: Fast preview (SDXL-Turbo, 4 steps, ~3-5s)
- Pass 2: Full quality (SDXL-Base or Base+Refiner, 30-50 steps)

Benefits:
- User sees quick preview
- Can cancel before full generation
- Better UX than waiting 30-50s
"""

from typing import Dict, Optional
import asyncio
import time

from app.services.smart import generation_router
from .generation_service import generation_service, PROMPT_TEMPLATES


class TwoPassGenerator:
    """
    Two-pass generation system

    Workflow:
    1. Generate fast preview (SDXL-Turbo)
    2. Show preview to user
    3. Generate full quality (SDXL-Base+Refiner)
    4. Return both images
    """

    def __init__(self):
        """Initialize two-pass generator"""
        pass

    async def generate_two_pass(
        self,
        prompt: str,
        quality: str = 'STANDARD',
        width: int = 1024,
        height: int = 1024,
        mode: Optional[str] = None,
        category: Optional[str] = None,
        skip_preview: bool = False,
        **kwargs
    ) -> Dict:
        """
        Generate with two-pass system

        Args:
            prompt: User prompt
            quality: STANDARD or PREMIUM (no FAST)
            width: Image width
            height: Image height
            mode: Override mode detection
            category: Override category detection
            skip_preview: Skip preview pass (just full quality)

        Returns:
            dict: {
                'preview': {...},      # Fast preview result
                'full': {...},         # Full quality result
                'metadata': {...}
            }
        """
        start_time = time.time()

        # Don't use two-pass for FAST tier
        if quality == 'FAST':
            result = await generation_service.generate(
                prompt=prompt,
                quality='FAST',
                width=width,
                height=height,
                mode=mode,
                category=category,
                **kwargs
            )
            return {
                'preview': None,
                'full': result,
                'metadata': {
                    'total_time': time.time() - start_time,
                    'used_two_pass': False
                }
            }

        # Skip preview if requested
        if skip_preview:
            full_result = await generation_service.generate(
                prompt=prompt,
                quality=quality,
                width=width,
                height=height,
                mode=mode,
                category=category,
                **kwargs
            )
            return {
                'preview': None,
                'full': full_result,
                'metadata': {
                    'total_time': time.time() - start_time,
                    'used_two_pass': False
                }
            }

        # Pass 1: Fast preview
        preview_start = time.time()
        preview_result = await generation_service.generate(
            prompt=prompt,
            quality='FAST',  # Force FAST for preview
            width=width,
            height=height,
            mode=mode,
            category=category,
            use_advanced_templates=False,  # Keep simple for preview
            **kwargs
        )
        preview_time = time.time() - preview_start

        # Pass 2: Full quality
        full_start = time.time()
        full_result = await generation_service.generate(
            prompt=prompt,
            quality=quality,  # Use requested quality
            width=width,
            height=height,
            mode=mode,
            category=category,
            use_advanced_templates=True,  # Use advanced templates
            **kwargs
        )
        full_time = time.time() - full_start

        return {
            'preview': {
                **preview_result,
                'generation_time': preview_time,
                'pass': 1
            },
            'full': {
                **full_result,
                'generation_time': full_time,
                'pass': 2
            },
            'metadata': {
                'total_time': time.time() - start_time,
                'preview_time': preview_time,
                'full_time': full_time,
                'used_two_pass': True,
                'quality_tier': quality
            }
        }

    async def generate_streaming(
        self,
        prompt: str,
        quality: str = 'STANDARD',
        width: int = 1024,
        height: int = 1024,
        callback=None,
        **kwargs
    ):
        """
        Generate with streaming updates

        Args:
            prompt: User prompt
            quality: Quality tier
            width: Image width
            height: Image height
            callback: Async callback function (status, data)

        Yields:
            dict: Progress updates
        """
        # Yield preview generation start
        if callback:
            await callback('preview_start', {'stage': 'preview', 'progress': 0})

        # Generate preview
        preview_result = await generation_service.generate(
            prompt=prompt,
            quality='FAST',
            width=width,
            height=height,
            **kwargs
        )

        # Yield preview complete
        if callback:
            await callback('preview_complete', {
                'stage': 'preview',
                'progress': 50,
                'image_url': preview_result.get('image_url')
            })

        # Yield full generation start
        if callback:
            await callback('full_start', {'stage': 'full', 'progress': 50})

        # Generate full quality
        full_result = await generation_service.generate(
            prompt=prompt,
            quality=quality,
            width=width,
            height=height,
            **kwargs
        )

        # Yield full complete
        if callback:
            await callback('full_complete', {
                'stage': 'full',
                'progress': 100,
                'image_url': full_result.get('image_url')
            })

        return {
            'preview': preview_result,
            'full': full_result
        }


# Singleton instance
two_pass_generator = TwoPassGenerator()

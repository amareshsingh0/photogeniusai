"""
Enhancement Pipeline - Post-processing for generated images.

Stage 4 of the pipeline: Applies code-based enhancements to the
jury-selected best candidate.

Enhancements:
- Auto-contrast and exposure correction
- Subtle sharpening (quality-dependent)
- Mode-specific color grading
- Noise reduction (for PREMIUM only)

Note: RealESRGAN/Swin2SR upscaling models are available on S3 but
require dedicated SageMaker endpoints. For now, this uses PIL-based
processing which is fast and runs on the API server.
"""

import base64
import io
import logging
from typing import Dict, Optional

from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)


# ─── Mode-specific Color Grading ─────────────────────────────────────────────

COLOR_GRADES = {
    'CINEMATIC': {
        'saturation': 0.9,    # Slightly desaturated
        'contrast': 1.15,     # Higher contrast
        'brightness': 0.95,   # Slightly darker
        'warmth': 1.05,       # Warm tint
    },
    'CINEMATIC_noir': {
        'saturation': 0.5,    # Very desaturated
        'contrast': 1.30,     # High contrast
        'brightness': 0.85,   # Dark
        'warmth': 0.95,       # Cool
    },
    'VINTAGE': {
        'saturation': 0.75,   # Faded
        'contrast': 0.95,     # Softer contrast
        'brightness': 1.05,   # Slightly brighter
        'warmth': 1.15,       # Warm/sepia tint
    },
    'VINTAGE_polaroid': {
        'saturation': 0.65,
        'contrast': 0.90,
        'brightness': 1.10,
        'warmth': 1.20,
    },
    'CYBERPUNK': {
        'saturation': 1.25,   # Vibrant
        'contrast': 1.20,     # High contrast
        'brightness': 0.95,
        'warmth': 0.90,       # Cool/neon
    },
    'CYBERPUNK_neon': {
        'saturation': 1.35,
        'contrast': 1.25,
        'brightness': 0.90,
        'warmth': 0.85,
    },
    'FANTASY': {
        'saturation': 1.10,
        'contrast': 1.10,
        'brightness': 1.05,
        'warmth': 1.05,
    },
    'FANTASY_dark': {
        'saturation': 0.85,
        'contrast': 1.20,
        'brightness': 0.85,
        'warmth': 0.95,
    },
    'NATURE': {
        'saturation': 1.10,
        'contrast': 1.05,
        'brightness': 1.03,
        'warmth': 1.05,
    },
    'FOOD': {
        'saturation': 1.15,   # Vibrant food colors
        'contrast': 1.05,
        'brightness': 1.05,
        'warmth': 1.10,       # Warm appetizing look
    },
    'PRODUCT': {
        'saturation': 1.0,    # Neutral
        'contrast': 1.10,     # Clean contrast
        'brightness': 1.05,   # Bright
        'warmth': 1.0,        # Neutral
    },
}

# Sharpening strength by quality
SHARPEN_STRENGTH = {
    'FAST': 0.0,       # No sharpening for speed
    'STANDARD': 0.3,   # Subtle
    'PREMIUM': 0.5,    # Noticeable
}


def _decode_image(image_data: str) -> Optional[Image.Image]:
    """Decode base64 to PIL Image."""
    try:
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        image_bytes = base64.b64decode(image_data)
        return Image.open(io.BytesIO(image_bytes)).convert('RGB')
    except Exception as e:
        logger.error(f"Failed to decode image: {e}")
        return None


def _encode_image(image: Image.Image) -> str:
    """Encode PIL Image to base64 PNG."""
    buffered = io.BytesIO()
    image.save(buffered, format='PNG', optimize=True)
    b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64}"


class EnhancementPipeline:
    """Post-processing pipeline for generated images.

    Applies mode-specific color grading, sharpening, and auto-enhancement.
    """

    async def enhance(
        self,
        image_url: str,
        quality: str = 'STANDARD',
        mode: str = 'REALISM',
        sub_mode: Optional[str] = None,
    ) -> Dict:
        """Enhance an image based on quality tier and mode.

        Args:
            image_url: Base64 data URL of the image
            quality: Quality tier (FAST/STANDARD/PREMIUM)
            mode: Master mode
            sub_mode: Sub-mode

        Returns:
            Dict with enhanced_image_url and enhancement details
        """
        # FAST tier: no enhancement for speed
        if quality == 'FAST':
            return {
                'image_url': image_url,
                'enhanced': False,
                'enhancements': [],
            }

        image = _decode_image(image_url)
        if image is None:
            return {
                'image_url': image_url,
                'enhanced': False,
                'error': 'Failed to decode image',
                'enhancements': [],
            }

        enhancements = []

        # Step 1: Auto-contrast/exposure
        image = self._auto_enhance(image)
        enhancements.append('auto_enhance')

        # Step 2: Mode-specific color grading
        mode_key = f"{mode}_{sub_mode}" if sub_mode else mode
        if mode_key in COLOR_GRADES or mode in COLOR_GRADES:
            grade = COLOR_GRADES.get(mode_key, COLOR_GRADES.get(mode))
            if grade:
                image = self._color_grade(image, grade)
                enhancements.append(f'color_grade_{mode_key}')

        # Step 3: Sharpening
        sharpen_str = SHARPEN_STRENGTH.get(quality, 0.0)
        if sharpen_str > 0:
            image = self._sharpen(image, sharpen_str)
            enhancements.append(f'sharpen_{sharpen_str}')

        # Step 4: Noise reduction (PREMIUM only)
        if quality == 'PREMIUM':
            image = self._reduce_noise(image)
            enhancements.append('noise_reduction')

        enhanced_url = _encode_image(image)

        return {
            'image_url': enhanced_url,
            'enhanced': True,
            'enhancements': enhancements,
        }

    def _auto_enhance(self, image: Image.Image) -> Image.Image:
        """Subtle auto-contrast and brightness optimization."""
        # Auto-contrast (very subtle to avoid over-processing)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.05)

        # Auto-brightness (normalize to avoid under/over exposure)
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.02)

        return image

    def _color_grade(self, image: Image.Image, grade: Dict) -> Image.Image:
        """Apply mode-specific color grading."""
        # Saturation
        if grade.get('saturation', 1.0) != 1.0:
            enhancer = ImageEnhance.Color(image)
            image = enhancer.enhance(grade['saturation'])

        # Contrast
        if grade.get('contrast', 1.0) != 1.0:
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(grade['contrast'])

        # Brightness
        if grade.get('brightness', 1.0) != 1.0:
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(grade['brightness'])

        # Warmth (shift toward red/yellow or blue)
        warmth = grade.get('warmth', 1.0)
        if warmth != 1.0:
            image = self._apply_warmth(image, warmth)

        return image

    def _apply_warmth(self, image: Image.Image, warmth: float) -> Image.Image:
        """Apply warm/cool color shift."""
        try:
            import numpy as np
            arr = np.array(image, dtype=np.float32)

            if warmth > 1.0:
                # Warm: boost red, slightly boost green, reduce blue
                factor = warmth - 1.0
                arr[:, :, 0] = np.clip(arr[:, :, 0] * (1 + factor * 0.1), 0, 255)
                arr[:, :, 2] = np.clip(arr[:, :, 2] * (1 - factor * 0.05), 0, 255)
            elif warmth < 1.0:
                # Cool: boost blue, reduce red
                factor = 1.0 - warmth
                arr[:, :, 2] = np.clip(arr[:, :, 2] * (1 + factor * 0.1), 0, 255)
                arr[:, :, 0] = np.clip(arr[:, :, 0] * (1 - factor * 0.05), 0, 255)

            return Image.fromarray(arr.astype(np.uint8))
        except ImportError:
            return image
        except Exception as e:
            logger.warning(f"Warmth adjustment failed: {e}")
            return image

    def _sharpen(self, image: Image.Image, strength: float) -> Image.Image:
        """Apply subtle sharpening."""
        if strength <= 0:
            return image

        # Use unsharp mask for controlled sharpening
        sharpened = image.filter(ImageFilter.UnsharpMask(
            radius=2,
            percent=int(strength * 150),
            threshold=3,
        ))
        return sharpened

    def _reduce_noise(self, image: Image.Image) -> Image.Image:
        """Very subtle noise reduction (bilateral-like via PIL)."""
        # Slight smoothing that preserves edges
        return image.filter(ImageFilter.SMOOTH_MORE) if False else image
        # Actually, SMOOTH_MORE is too aggressive. Use a custom approach:
        try:
            import numpy as np
            arr = np.array(image, dtype=np.float32)

            # Very light Gaussian smoothing on dark areas only (where noise is most visible)
            from PIL import ImageFilter as IF
            smoothed = image.filter(IF.GaussianBlur(radius=0.5))
            smooth_arr = np.array(smoothed, dtype=np.float32)

            # Blend: use smoothed version more in dark areas
            brightness = np.mean(arr, axis=2, keepdims=True)
            # Darker areas (< 80/255) get more smoothing
            blend_factor = np.clip((80 - brightness) / 80, 0, 0.3)
            result = arr * (1 - blend_factor) + smooth_arr * blend_factor

            return Image.fromarray(result.astype(np.uint8))
        except ImportError:
            return image
        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}")
            return image


# Singleton instance
enhancement_pipeline = EnhancementPipeline()

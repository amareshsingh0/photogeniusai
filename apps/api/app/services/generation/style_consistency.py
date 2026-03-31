"""
Style Consistency Engine - Maintains a recognizable "house look".

The secret weapon of top AI image generators:
Every output has a consistent visual signature.

Features:
1. Extract style DNA from images (color palette, contrast curve, lighting)
2. Store style profiles per user/brand
3. Bias new generations toward the style profile
4. Cross-generation consistency (all images feel "from the same studio")

Style DNA Components:
- Color Palette: Dominant 5 colors + distribution
- Contrast Curve: Shadow/midtone/highlight balance
- Warmth Signature: Cool-to-warm bias
- Saturation Profile: Vibrant vs muted
- Lighting Signature: High-key vs low-key
- Grain/Texture: Clean vs textured

PhotoGenius House Style:
- Slightly warm (warmth: 1.03)
- Rich midtones
- Clean shadows (no crushed blacks)
- Micro-contrast boost (detail pop)
- Subtle vignette on premium
- Consistent white balance
"""

import base64
import io
import logging
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)


@dataclass
class StyleDNA:
    """Visual DNA of a style - extracted from images or defined manually."""
    # Color palette (top 5 dominant RGB colors)
    palette: List[Tuple[int, int, int]] = field(default_factory=list)
    palette_weights: List[float] = field(default_factory=list)

    # Tonal properties
    warmth: float = 1.0          # 0.8=cool, 1.0=neutral, 1.2=warm
    saturation: float = 1.0      # 0.7=muted, 1.0=normal, 1.3=vibrant
    contrast: float = 1.0        # 0.8=flat, 1.0=normal, 1.3=punchy
    brightness: float = 1.0      # 0.8=dark, 1.0=normal, 1.2=bright

    # Tonal curve (shadow, midtone, highlight balance)
    shadow_strength: float = 0.0     # -1=lifted, 0=normal, 1=crushed
    midtone_boost: float = 0.0      # -0.5 to 0.5
    highlight_softness: float = 0.0  # -1=clipped, 0=normal, 1=rolled

    # Texture
    grain_amount: float = 0.0    # 0=none, 0.5=subtle, 1.0=heavy
    sharpness: float = 0.0       # -1=soft, 0=normal, 1=crispy

    # Lighting
    key: str = 'neutral'         # 'high_key', 'neutral', 'low_key'
    vignette: float = 0.0        # 0=none, 0.3=subtle, 0.8=heavy

    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# Predefined House Styles (PhotoGenius brand looks)
# ═══════════════════════════════════════════════════════════════════════

HOUSE_STYLES = {
    'photogenius_signature': StyleDNA(
        warmth=1.03,
        saturation=1.05,
        contrast=1.08,
        brightness=1.0,
        shadow_strength=-0.1,    # Slightly lifted shadows
        midtone_boost=0.05,      # Rich midtones
        highlight_softness=0.1,  # Soft highlights
        sharpness=0.15,          # Subtle micro-contrast
        vignette=0.05,           # Barely noticeable
        key='neutral',
    ),

    'cinematic_studio': StyleDNA(
        warmth=1.06,
        saturation=0.92,
        contrast=1.18,
        brightness=0.95,
        shadow_strength=0.2,     # Deeper shadows
        midtone_boost=0.1,
        highlight_softness=0.2,  # Rolled-off highlights
        grain_amount=0.1,        # Subtle film grain
        sharpness=0.1,
        vignette=0.15,
        key='low_key',
    ),

    'fashion_editorial': StyleDNA(
        warmth=0.98,
        saturation=0.95,
        contrast=1.12,
        brightness=1.05,
        shadow_strength=-0.15,   # Lifted shadows
        midtone_boost=0.0,
        highlight_softness=-0.1, # Crisp highlights
        sharpness=0.2,
        vignette=0.0,
        key='high_key',
    ),

    'moody_portrait': StyleDNA(
        warmth=1.08,
        saturation=0.85,
        contrast=1.15,
        brightness=0.90,
        shadow_strength=0.25,
        midtone_boost=0.08,
        highlight_softness=0.15,
        grain_amount=0.15,
        sharpness=0.05,
        vignette=0.2,
        key='low_key',
    ),

    'vibrant_pop': StyleDNA(
        warmth=1.0,
        saturation=1.2,
        contrast=1.10,
        brightness=1.05,
        shadow_strength=-0.1,
        midtone_boost=0.05,
        highlight_softness=0.0,
        sharpness=0.15,
        vignette=0.0,
        key='high_key',
    ),

    'vintage_film': StyleDNA(
        warmth=1.12,
        saturation=0.75,
        contrast=0.95,
        brightness=1.05,
        shadow_strength=-0.2,    # Very lifted shadows (film look)
        midtone_boost=-0.05,
        highlight_softness=0.2,  # Soft highlights
        grain_amount=0.3,
        sharpness=-0.1,          # Slightly soft
        vignette=0.25,
        key='neutral',
    ),

    'dark_drama': StyleDNA(
        warmth=0.95,
        saturation=0.88,
        contrast=1.25,
        brightness=0.85,
        shadow_strength=0.3,     # Deep blacks
        midtone_boost=0.12,
        highlight_softness=0.1,
        sharpness=0.1,
        vignette=0.3,
        key='low_key',
    ),

    'clean_commercial': StyleDNA(
        warmth=1.0,
        saturation=1.0,
        contrast=1.05,
        brightness=1.08,
        shadow_strength=-0.15,
        midtone_boost=0.0,
        highlight_softness=-0.05,
        sharpness=0.2,
        vignette=0.0,
        key='high_key',
    ),

    'anime_vivid': StyleDNA(
        warmth=1.0,
        saturation=1.25,
        contrast=1.15,
        brightness=1.02,
        shadow_strength=-0.05,
        midtone_boost=0.0,
        highlight_softness=0.0,
        sharpness=0.25,          # Crisp lines
        vignette=0.0,
        key='high_key',
    ),

    'nature_golden': StyleDNA(
        warmth=1.10,
        saturation=1.12,
        contrast=1.08,
        brightness=1.03,
        shadow_strength=-0.05,
        midtone_boost=0.08,
        highlight_softness=0.15,
        sharpness=0.1,
        vignette=0.1,
        key='neutral',
    ),
}

# ═══════════════════════════════════════════════════════════════════════
# Mode → Default House Style Mapping
# ═══════════════════════════════════════════════════════════════════════

MODE_STYLE_MAP = {
    'REALISM':           'photogenius_signature',
    'REALISM_portrait':  'moody_portrait',
    'REALISM_fashion':   'fashion_editorial',
    'REALISM_wedding':   'photogenius_signature',
    'REALISM_street':    'cinematic_studio',
    'CINEMATIC':         'cinematic_studio',
    'CINEMATIC_noir':    'dark_drama',
    'CINEMATIC_action':  'cinematic_studio',
    'CINEMATIC_drama':   'moody_portrait',
    'CINEMATIC_romance': 'photogenius_signature',
    'CREATIVE':          'vibrant_pop',
    'FANTASY':           'vibrant_pop',
    'FANTASY_dark':      'dark_drama',
    'ANIME':             'anime_vivid',
    'ART':               'photogenius_signature',
    'DIGITAL_ART':       'vibrant_pop',
    'DESIGN':            'clean_commercial',
    'PRODUCT':           'clean_commercial',
    'ARCHITECTURE':      'clean_commercial',
    'FOOD':              'nature_golden',
    'NATURE':            'nature_golden',
    'SCIENTIFIC':        'clean_commercial',
    'CYBERPUNK':         'dark_drama',
    'VINTAGE':           'vintage_film',
    'GEOMETRIC':         'vibrant_pop',
}


class StyleConsistencyEngine:
    """Ensures all outputs have a consistent, recognizable visual signature.

    This is the difference between "random AI images" and a "recognizable brand".
    """

    def __init__(self):
        self._user_styles: Dict[str, StyleDNA] = {}

    def get_style(
        self,
        mode: str,
        sub_mode: Optional[str] = None,
        user_id: Optional[str] = None,
        style_name: Optional[str] = None,
    ) -> StyleDNA:
        """Get the appropriate style for a generation request.

        Priority:
        1. Explicit style_name override
        2. User's saved custom style
        3. Mode-specific default style
        4. PhotoGenius signature style

        Returns:
            StyleDNA to apply to the generated image
        """
        # 1. Explicit style name
        if style_name and style_name in HOUSE_STYLES:
            return HOUSE_STYLES[style_name]

        # 2. User's custom style
        if user_id and user_id in self._user_styles:
            return self._user_styles[user_id]

        # 3. Mode-specific style
        mode_key = f"{mode}_{sub_mode}" if sub_mode else mode
        style_key = MODE_STYLE_MAP.get(mode_key) or MODE_STYLE_MAP.get(mode)

        if style_key and style_key in HOUSE_STYLES:
            return HOUSE_STYLES[style_key]

        # 4. Default signature
        return HOUSE_STYLES['photogenius_signature']

    async def apply_style(
        self,
        image_url: str,
        style: StyleDNA,
        intensity: float = 0.7,
    ) -> Dict:
        """Apply a style DNA to an image.

        Args:
            image_url: Base64 data URL
            style: StyleDNA to apply
            intensity: How strongly to apply (0=none, 1=full)

        Returns:
            Dict with styled image URL and metadata
        """
        image = self._decode_image(image_url)
        if image is None:
            return {'image_url': image_url, 'styled': False, 'error': 'decode_failed'}

        applied = []

        # 1. Warmth
        if style.warmth != 1.0:
            image = self._apply_warmth(image, style.warmth, intensity)
            applied.append('warmth')

        # 2. Saturation
        if style.saturation != 1.0:
            factor = 1.0 + (style.saturation - 1.0) * intensity
            image = ImageEnhance.Color(image).enhance(factor)
            applied.append('saturation')

        # 3. Contrast
        if style.contrast != 1.0:
            factor = 1.0 + (style.contrast - 1.0) * intensity
            image = ImageEnhance.Contrast(image).enhance(factor)
            applied.append('contrast')

        # 4. Brightness
        if style.brightness != 1.0:
            factor = 1.0 + (style.brightness - 1.0) * intensity
            image = ImageEnhance.Brightness(image).enhance(factor)
            applied.append('brightness')

        # 5. Tonal curve (shadows, midtones, highlights)
        if any([style.shadow_strength, style.midtone_boost, style.highlight_softness]):
            image = self._apply_tonal_curve(
                image, style.shadow_strength, style.midtone_boost,
                style.highlight_softness, intensity
            )
            applied.append('tonal_curve')

        # 6. Micro-contrast / Sharpness
        if style.sharpness != 0.0:
            sharp_factor = style.sharpness * intensity
            if sharp_factor > 0:
                image = image.filter(ImageFilter.UnsharpMask(
                    radius=1.5, percent=int(sharp_factor * 80), threshold=2
                ))
            elif sharp_factor < 0:
                image = image.filter(ImageFilter.GaussianBlur(
                    radius=abs(sharp_factor) * 0.5
                ))
            applied.append('sharpness')

        # 7. Film grain
        if style.grain_amount > 0:
            image = self._apply_grain(image, style.grain_amount * intensity)
            applied.append('grain')

        # 8. Vignette
        if style.vignette > 0:
            image = self._apply_vignette(image, style.vignette * intensity)
            applied.append('vignette')

        styled_url = self._encode_image(image)

        return {
            'image_url': styled_url,
            'styled': True,
            'style_applied': applied,
            'intensity': intensity,
        }

    def extract_style(self, image_url: str) -> StyleDNA:
        """Extract style DNA from an image.

        Analyzes the visual properties and returns a StyleDNA
        that can reproduce the same "feel".
        """
        image = self._decode_image(image_url)
        if image is None:
            return HOUSE_STYLES['photogenius_signature']

        try:
            import numpy as np
            arr = np.array(image, dtype=np.float32)

            # Extract warmth
            r_mean = float(np.mean(arr[:,:,0]))
            b_mean = float(np.mean(arr[:,:,2]))
            warmth = 1.0 + (r_mean - b_mean) / 500  # Rough warmth estimate

            # Extract saturation (via HSV)
            from colorsys import rgb_to_hsv
            # Sample points
            h, w = arr.shape[:2]
            samples = arr[::h//20, ::w//20].reshape(-1, 3) / 255.0
            saturations = [rgb_to_hsv(r, g, b)[1] for r, g, b in samples]
            avg_sat = sum(saturations) / max(len(saturations), 1)
            saturation = avg_sat / 0.5  # Normalize around 0.5 = 1.0

            # Extract contrast
            gray = np.mean(arr, axis=2)
            contrast_metric = float(np.std(gray)) / 64.0  # 64 = "normal" std

            # Extract brightness
            brightness = float(np.mean(gray)) / 128.0  # 128 = "normal" mean

            # Extract tonal info
            shadow_pct = float(np.percentile(gray, 10))
            highlight_pct = float(np.percentile(gray, 90))
            shadow_strength = (40 - shadow_pct) / 40  # Lower shadows = higher strength
            highlight_softness = (highlight_pct - 220) / -30  # Lower highlights = softer

            # Dominant colors (simplified k-means via binning)
            palette = self._extract_palette(arr)

            return StyleDNA(
                palette=palette,
                warmth=round(max(0.8, min(1.2, warmth)), 3),
                saturation=round(max(0.5, min(1.5, saturation)), 3),
                contrast=round(max(0.7, min(1.4, contrast_metric)), 3),
                brightness=round(max(0.7, min(1.3, brightness)), 3),
                shadow_strength=round(max(-0.5, min(0.5, shadow_strength)), 3),
                highlight_softness=round(max(-0.3, min(0.3, highlight_softness)), 3),
            )

        except ImportError:
            return HOUSE_STYLES['photogenius_signature']

    def save_user_style(self, user_id: str, style: StyleDNA):
        """Save a custom style for a user."""
        self._user_styles[user_id] = style
        logger.info(f"Saved custom style for user {user_id}")

    def list_styles(self) -> Dict:
        """List all available house styles."""
        return {
            name: {
                'warmth': s.warmth,
                'saturation': s.saturation,
                'contrast': s.contrast,
                'key': s.key,
            }
            for name, s in HOUSE_STYLES.items()
        }

    # ─── Internal Processing ───────────────────────────────────────

    def _apply_warmth(self, image: Image.Image, warmth: float, intensity: float) -> Image.Image:
        """Apply warm/cool tint with controlled intensity."""
        try:
            import numpy as np
            arr = np.array(image, dtype=np.float32)

            effective_warmth = 1.0 + (warmth - 1.0) * intensity

            if effective_warmth > 1.0:
                factor = effective_warmth - 1.0
                arr[:,:,0] = np.clip(arr[:,:,0] * (1 + factor * 0.08), 0, 255)  # Boost red
                arr[:,:,1] = np.clip(arr[:,:,1] * (1 + factor * 0.02), 0, 255)  # Slight green
                arr[:,:,2] = np.clip(arr[:,:,2] * (1 - factor * 0.04), 0, 255)  # Reduce blue
            elif effective_warmth < 1.0:
                factor = 1.0 - effective_warmth
                arr[:,:,2] = np.clip(arr[:,:,2] * (1 + factor * 0.08), 0, 255)  # Boost blue
                arr[:,:,0] = np.clip(arr[:,:,0] * (1 - factor * 0.04), 0, 255)  # Reduce red

            return Image.fromarray(arr.astype(np.uint8))
        except ImportError:
            return image

    def _apply_tonal_curve(
        self,
        image: Image.Image,
        shadow_strength: float,
        midtone_boost: float,
        highlight_softness: float,
        intensity: float,
    ) -> Image.Image:
        """Apply tonal curve adjustment (shadows, midtones, highlights)."""
        try:
            import numpy as np
            arr = np.array(image, dtype=np.float32)

            # Normalize to 0-1
            arr_norm = arr / 255.0

            # Build tone curve
            shadow_adj = shadow_strength * intensity * 0.1
            mid_adj = midtone_boost * intensity * 0.08
            high_adj = highlight_softness * intensity * 0.08

            # Apply using a soft S-curve approach
            # Shadows (values < 0.3)
            shadow_mask = np.clip((0.3 - arr_norm) / 0.3, 0, 1)
            arr_norm = arr_norm - shadow_mask * shadow_adj

            # Midtones (values 0.3-0.7)
            mid_mask = 1.0 - np.abs(arr_norm - 0.5) / 0.5
            mid_mask = np.clip(mid_mask, 0, 1)
            arr_norm = arr_norm + mid_mask * mid_adj

            # Highlights (values > 0.7)
            high_mask = np.clip((arr_norm - 0.7) / 0.3, 0, 1)
            arr_norm = arr_norm - high_mask * high_adj

            arr = np.clip(arr_norm * 255.0, 0, 255)
            return Image.fromarray(arr.astype(np.uint8))
        except ImportError:
            return image

    def _apply_grain(self, image: Image.Image, amount: float) -> Image.Image:
        """Add subtle film grain."""
        try:
            import numpy as np
            arr = np.array(image, dtype=np.float32)

            noise = np.random.normal(0, amount * 12, arr.shape)
            arr = np.clip(arr + noise, 0, 255)

            return Image.fromarray(arr.astype(np.uint8))
        except ImportError:
            return image

    def _apply_vignette(self, image: Image.Image, strength: float) -> Image.Image:
        """Add subtle edge darkening (vignette)."""
        try:
            import numpy as np

            h, w = image.size[1], image.size[0]
            arr = np.array(image, dtype=np.float32)

            # Create radial gradient
            y, x = np.ogrid[:h, :w]
            center_y, center_x = h / 2, w / 2
            radius = min(h, w) / 2

            # Distance from center, normalized
            dist = np.sqrt((x - center_x)**2 + (y - center_y)**2) / radius

            # Vignette mask (1 at center, darkens toward edges)
            vignette_mask = 1.0 - np.clip((dist - 0.5) * strength * 2, 0, strength)
            vignette_mask = vignette_mask[:, :, np.newaxis]

            arr = arr * vignette_mask
            arr = np.clip(arr, 0, 255)

            return Image.fromarray(arr.astype(np.uint8))
        except ImportError:
            return image

    def _extract_palette(self, arr, n_colors: int = 5) -> List[Tuple[int, int, int]]:
        """Extract dominant colors from image array."""
        try:
            import numpy as np

            # Downsample for speed
            small = arr[::8, ::8].reshape(-1, 3)

            # Simple binning approach (faster than k-means)
            bins = 6  # 6^3 = 216 color bins
            quantized = (small / (256 / bins)).astype(int)
            # Create bin labels
            labels = quantized[:, 0] * bins * bins + quantized[:, 1] * bins + quantized[:, 2]

            # Find most common bins
            unique, counts = np.unique(labels, return_counts=True)
            top_indices = np.argsort(counts)[-n_colors:]

            palette = []
            for idx in reversed(top_indices):
                label = unique[idx]
                b_idx = label % bins
                g_idx = (label // bins) % bins
                r_idx = label // (bins * bins)
                center = int(256 / bins / 2)
                palette.append((
                    int(r_idx * (256 / bins) + center),
                    int(g_idx * (256 / bins) + center),
                    int(b_idx * (256 / bins) + center),
                ))

            return palette
        except Exception:
            return []

    # ─── Image I/O ─────────────────────────────────────────────────

    def _decode_image(self, image_data: str) -> Optional[Image.Image]:
        try:
            if ',' in image_data:
                image_data = image_data.split(',', 1)[1]
            image_bytes = base64.b64decode(image_data)
            return Image.open(io.BytesIO(image_bytes)).convert('RGB')
        except Exception as e:
            logger.error(f"Failed to decode image: {e}")
            return None

    def _encode_image(self, image: Image.Image) -> str:
        buffered = io.BytesIO()
        image.save(buffered, format='PNG', optimize=True)
        b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{b64}"


# Singleton
style_consistency = StyleConsistencyEngine()

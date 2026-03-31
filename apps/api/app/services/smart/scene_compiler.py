"""
Scene Compiler - AI Director that builds structured scene JSON from user prompt.

Stage 0 of the pipeline: Understands user intent and creates a complete scene
specification including camera, lighting, composition, background, and style
directives. This structured output drives all downstream stages.
"""

from typing import Dict, Optional, Any
from .mode_detector import mode_detector
from .category_detector import category_detector
from .mega_templates import get_template, build_enhanced_prompt, get_negative_prompt


# ─── Camera Presets ───────────────────────────────────────────────────────────

CAMERA_PRESETS = {
    # Portrait cameras
    'portrait_close': {'focal_mm': 85, 'aperture': 'f/1.4', 'angle': 'eye_level', 'distance': 'close'},
    'portrait_medium': {'focal_mm': 50, 'aperture': 'f/1.8', 'angle': 'eye_level', 'distance': 'medium'},
    'portrait_wide': {'focal_mm': 35, 'aperture': 'f/2.8', 'angle': 'eye_level', 'distance': 'wide'},
    'headshot': {'focal_mm': 105, 'aperture': 'f/2.0', 'angle': 'eye_level', 'distance': 'tight'},

    # Landscape cameras
    'landscape_wide': {'focal_mm': 16, 'aperture': 'f/11', 'angle': 'eye_level', 'distance': 'infinity'},
    'landscape_tele': {'focal_mm': 200, 'aperture': 'f/5.6', 'angle': 'eye_level', 'distance': 'far'},
    'panoramic': {'focal_mm': 24, 'aperture': 'f/8', 'angle': 'eye_level', 'distance': 'infinity'},

    # Cinematic cameras
    'cinematic_wide': {'focal_mm': 24, 'aperture': 'f/2.8', 'angle': 'low', 'distance': 'medium'},
    'cinematic_close': {'focal_mm': 35, 'aperture': 'f/1.4', 'angle': 'eye_level', 'distance': 'close'},
    'cinematic_epic': {'focal_mm': 14, 'aperture': 'f/4', 'angle': 'low', 'distance': 'far'},
    'dutch_angle': {'focal_mm': 28, 'aperture': 'f/2.8', 'angle': 'dutch', 'distance': 'medium'},

    # Product cameras
    'product_studio': {'focal_mm': 100, 'aperture': 'f/8', 'angle': 'slightly_above', 'distance': 'medium'},
    'product_hero': {'focal_mm': 85, 'aperture': 'f/4', 'angle': 'eye_level', 'distance': 'close'},
    'flat_lay': {'focal_mm': 50, 'aperture': 'f/5.6', 'angle': 'top_down', 'distance': 'medium'},

    # Macro cameras
    'macro_extreme': {'focal_mm': 100, 'aperture': 'f/2.8', 'angle': 'eye_level', 'distance': 'extreme_close'},
    'macro_detail': {'focal_mm': 60, 'aperture': 'f/4', 'angle': 'slightly_above', 'distance': 'very_close'},

    # Architecture cameras
    'architecture_wide': {'focal_mm': 14, 'aperture': 'f/8', 'angle': 'low', 'distance': 'medium'},
    'architecture_detail': {'focal_mm': 50, 'aperture': 'f/5.6', 'angle': 'eye_level', 'distance': 'medium'},
    'interior_wide': {'focal_mm': 16, 'aperture': 'f/8', 'angle': 'eye_level', 'distance': 'wide'},

    # Aerial cameras
    'aerial_high': {'focal_mm': 24, 'aperture': 'f/5.6', 'angle': 'top_down', 'distance': 'very_far'},
    'aerial_angled': {'focal_mm': 35, 'aperture': 'f/4', 'angle': 'high_angle', 'distance': 'far'},

    # Sports/action
    'action_fast': {'focal_mm': 200, 'aperture': 'f/2.8', 'angle': 'eye_level', 'distance': 'medium'},
    'action_wide': {'focal_mm': 24, 'aperture': 'f/4', 'angle': 'low', 'distance': 'medium'},

    # Default
    'default': {'focal_mm': 50, 'aperture': 'f/4', 'angle': 'eye_level', 'distance': 'medium'},
}

# ─── Lighting Presets ─────────────────────────────────────────────────────────

LIGHTING_PRESETS = {
    'studio_soft': {'key': 'soft', 'fill': 'moderate', 'style': 'studio', 'mood': 'professional', 'color_temp': 'neutral'},
    'studio_dramatic': {'key': 'hard', 'fill': 'minimal', 'style': 'rembrandt', 'mood': 'dramatic', 'color_temp': 'warm'},
    'natural_golden': {'key': 'soft', 'fill': 'natural', 'style': 'golden_hour', 'mood': 'warm', 'color_temp': 'warm'},
    'natural_overcast': {'key': 'diffused', 'fill': 'even', 'style': 'overcast', 'mood': 'soft', 'color_temp': 'cool'},
    'natural_harsh': {'key': 'hard', 'fill': 'strong_shadows', 'style': 'midday_sun', 'mood': 'intense', 'color_temp': 'neutral'},
    'cinematic_noir': {'key': 'hard', 'fill': 'none', 'style': 'noir', 'mood': 'mysterious', 'color_temp': 'cool'},
    'cinematic_warm': {'key': 'soft', 'fill': 'warm', 'style': 'cinematic', 'mood': 'inviting', 'color_temp': 'warm'},
    'neon_glow': {'key': 'colored', 'fill': 'neon', 'style': 'cyberpunk', 'mood': 'futuristic', 'color_temp': 'mixed'},
    'backlit': {'key': 'rim', 'fill': 'silhouette', 'style': 'backlit', 'mood': 'ethereal', 'color_temp': 'warm'},
    'flat_even': {'key': 'even', 'fill': 'full', 'style': 'product', 'mood': 'clean', 'color_temp': 'neutral'},
    'moody_low': {'key': 'low', 'fill': 'minimal', 'style': 'chiaroscuro', 'mood': 'moody', 'color_temp': 'warm'},
    'fantasy_ethereal': {'key': 'magical', 'fill': 'glow', 'style': 'fantasy', 'mood': 'ethereal', 'color_temp': 'cool'},
    'underwater_caustic': {'key': 'filtered', 'fill': 'scattered', 'style': 'underwater', 'mood': 'serene', 'color_temp': 'blue'},
    'space_ambient': {'key': 'starlight', 'fill': 'ambient', 'style': 'space', 'mood': 'vast', 'color_temp': 'cool'},
    'vintage_warm': {'key': 'soft', 'fill': 'warm', 'style': 'vintage', 'mood': 'nostalgic', 'color_temp': 'very_warm'},
    'food_appetizing': {'key': 'soft_side', 'fill': 'bounce', 'style': 'food', 'mood': 'appetizing', 'color_temp': 'warm'},
    'default': {'key': 'natural', 'fill': 'moderate', 'style': 'balanced', 'mood': 'neutral', 'color_temp': 'neutral'},
}

# ─── Composition Presets ──────────────────────────────────────────────────────

COMPOSITION_PRESETS = {
    'rule_of_thirds': {'rule': 'rule_of_thirds', 'balance': 'asymmetric', 'depth': 'layered'},
    'centered': {'rule': 'centered', 'balance': 'symmetric', 'depth': 'focused'},
    'golden_ratio': {'rule': 'golden_ratio', 'balance': 'dynamic', 'depth': 'layered'},
    'leading_lines': {'rule': 'leading_lines', 'balance': 'dynamic', 'depth': 'deep'},
    'symmetry': {'rule': 'symmetry', 'balance': 'perfect_symmetric', 'depth': 'flat'},
    'diagonal': {'rule': 'diagonal', 'balance': 'dynamic', 'depth': 'layered'},
    'framing': {'rule': 'frame_within_frame', 'balance': 'focused', 'depth': 'layered'},
    'minimalist': {'rule': 'negative_space', 'balance': 'clean', 'depth': 'shallow'},
    'fill_frame': {'rule': 'fill', 'balance': 'tight', 'depth': 'shallow'},
    'panoramic': {'rule': 'panoramic', 'balance': 'wide', 'depth': 'deep'},
    'default': {'rule': 'rule_of_thirds', 'balance': 'balanced', 'depth': 'natural'},
}

# ─── Mode → Preset Mappings ──────────────────────────────────────────────────

MODE_CAMERA_MAP = {
    'REALISM': 'portrait_medium',
    'REALISM_portrait': 'portrait_close',
    'REALISM_group': 'portrait_wide',
    'REALISM_fashion': 'portrait_medium',
    'REALISM_wedding': 'portrait_medium',
    'REALISM_street': 'cinematic_wide',
    'CINEMATIC': 'cinematic_wide',
    'CINEMATIC_noir': 'cinematic_close',
    'CINEMATIC_action': 'cinematic_epic',
    'CINEMATIC_scifi': 'cinematic_wide',
    'CINEMATIC_horror': 'cinematic_close',
    'CREATIVE': 'default',
    'FANTASY': 'cinematic_epic',
    'FANTASY_epic': 'cinematic_epic',
    'FANTASY_dark': 'cinematic_close',
    'ANIME': 'default',
    'ART': 'default',
    'DIGITAL_ART': 'default',
    'DIGITAL_ART_3d_render': 'product_studio',
    'DIGITAL_ART_isometric': 'aerial_angled',
    'DESIGN': 'default',
    'DESIGN_poster': 'default',
    'PRODUCT': 'product_studio',
    'PRODUCT_luxury': 'product_hero',
    'PRODUCT_food': 'product_studio',
    'ARCHITECTURE': 'architecture_wide',
    'ARCHITECTURE_interior': 'interior_wide',
    'ARCHITECTURE_render': 'architecture_wide',
    'FOOD': 'product_studio',
    'NATURE': 'landscape_wide',
    'NATURE_wildlife': 'action_fast',
    'NATURE_macro': 'macro_extreme',
    'NATURE_underwater': 'default',
    'SCIENTIFIC': 'default',
    'CYBERPUNK': 'cinematic_wide',
    'CYBERPUNK_neon': 'cinematic_wide',
    'VINTAGE': 'portrait_medium',
    'GEOMETRIC': 'default',
}

MODE_LIGHTING_MAP = {
    'REALISM': 'studio_soft',
    'REALISM_portrait': 'studio_soft',
    'REALISM_fashion': 'studio_dramatic',
    'REALISM_wedding': 'natural_golden',
    'REALISM_street': 'natural_overcast',
    'CINEMATIC': 'cinematic_warm',
    'CINEMATIC_noir': 'cinematic_noir',
    'CINEMATIC_action': 'cinematic_warm',
    'CINEMATIC_scifi': 'neon_glow',
    'CINEMATIC_horror': 'moody_low',
    'CREATIVE': 'default',
    'FANTASY': 'fantasy_ethereal',
    'FANTASY_epic': 'cinematic_warm',
    'FANTASY_dark': 'moody_low',
    'ANIME': 'flat_even',
    'ART': 'studio_soft',
    'DIGITAL_ART': 'flat_even',
    'DESIGN': 'flat_even',
    'PRODUCT': 'flat_even',
    'PRODUCT_luxury': 'studio_dramatic',
    'PRODUCT_food': 'food_appetizing',
    'ARCHITECTURE': 'natural_golden',
    'ARCHITECTURE_interior': 'studio_soft',
    'FOOD': 'food_appetizing',
    'NATURE': 'natural_golden',
    'NATURE_wildlife': 'natural_golden',
    'NATURE_macro': 'natural_overcast',
    'NATURE_underwater': 'underwater_caustic',
    'SCIENTIFIC': 'flat_even',
    'CYBERPUNK': 'neon_glow',
    'CYBERPUNK_neon': 'neon_glow',
    'VINTAGE': 'vintage_warm',
    'GEOMETRIC': 'flat_even',
}

MODE_COMPOSITION_MAP = {
    'REALISM': 'rule_of_thirds',
    'REALISM_portrait': 'centered',
    'REALISM_group': 'rule_of_thirds',
    'CINEMATIC': 'golden_ratio',
    'CINEMATIC_noir': 'diagonal',
    'CREATIVE': 'golden_ratio',
    'FANTASY': 'leading_lines',
    'ANIME': 'rule_of_thirds',
    'ART': 'golden_ratio',
    'DIGITAL_ART': 'rule_of_thirds',
    'DESIGN': 'centered',
    'PRODUCT': 'centered',
    'ARCHITECTURE': 'leading_lines',
    'ARCHITECTURE_interior': 'leading_lines',
    'FOOD': 'rule_of_thirds',
    'NATURE': 'rule_of_thirds',
    'SCIENTIFIC': 'centered',
    'CYBERPUNK': 'diagonal',
    'VINTAGE': 'centered',
    'GEOMETRIC': 'symmetry',
}


# ─── Subject Detection ────────────────────────────────────────────────────────

SUBJECT_KEYWORDS = {
    'person': ['person', 'man', 'woman', 'child', 'girl', 'boy', 'human', 'people',
               'portrait', 'headshot', 'selfie', 'model', 'face', 'celebrity', 'actor'],
    'animal': ['animal', 'dog', 'cat', 'bird', 'horse', 'lion', 'tiger', 'wolf',
               'bear', 'deer', 'fox', 'rabbit', 'fish', 'dolphin', 'eagle', 'owl'],
    'object': ['product', 'object', 'item', 'bottle', 'phone', 'watch', 'jewelry',
               'car', 'vehicle', 'shoe', 'bag', 'device', 'gadget', 'instrument'],
    'building': ['building', 'house', 'architecture', 'skyscraper', 'tower', 'bridge',
                 'castle', 'palace', 'temple', 'church', 'monument', 'cathedral'],
    'nature': ['mountain', 'forest', 'river', 'lake', 'ocean', 'beach', 'waterfall',
               'desert', 'valley', 'meadow', 'sunset', 'sunrise', 'sky', 'clouds'],
    'food': ['food', 'meal', 'dish', 'cake', 'pizza', 'burger', 'sushi', 'steak',
             'dessert', 'bread', 'fruit', 'coffee', 'wine', 'cocktail'],
    'creature': ['dragon', 'unicorn', 'phoenix', 'monster', 'alien', 'robot',
                 'cyborg', 'mermaid', 'fairy', 'demon', 'angel', 'mythical'],
    'text': ['text', 'logo', 'typography', 'lettering', 'sign', 'title', 'label'],
    'abstract': ['abstract', 'pattern', 'geometric', 'fractal', 'mandala', 'shapes'],
    'scene': ['landscape', 'cityscape', 'interior', 'room', 'space', 'underwater'],
}


# ─── Background Detection ────────────────────────────────────────────────────

BACKGROUND_KEYWORDS = {
    'studio_white': ['white background', 'studio', 'clean background', 'isolated'],
    'studio_dark': ['dark background', 'black background', 'moody background'],
    'studio_gradient': ['gradient background', 'colored background'],
    'nature_outdoor': ['outdoor', 'nature', 'forest', 'mountain', 'field', 'garden', 'park'],
    'urban': ['city', 'urban', 'street', 'downtown', 'building'],
    'interior': ['indoor', 'room', 'interior', 'office', 'studio', 'home'],
    'fantasy': ['magical', 'enchanted', 'mystical', 'otherworldly', 'realm'],
    'space': ['space', 'galaxy', 'cosmos', 'nebula', 'stars'],
    'underwater': ['underwater', 'ocean', 'deep sea', 'coral reef'],
    'abstract': ['abstract background', 'bokeh', 'blurred', 'gradient'],
    'transparent': ['transparent', 'no background', 'cutout', 'isolated object'],
}


class SceneCompiler:
    """AI Director - Compiles user prompt into structured scene specification.

    Takes a raw user prompt and produces a complete scene JSON that drives
    all downstream pipeline stages (prompt engineering, generation, scoring).
    """

    def compile(self, prompt: str, quality: str = 'STANDARD',
                width: int = 1024, height: int = 1024) -> Dict[str, Any]:
        """Compile user prompt into structured scene specification.

        Args:
            prompt: Raw user prompt
            quality: Quality tier (FAST/STANDARD/PREMIUM)
            width: Target image width
            height: Target image height

        Returns:
            Complete scene specification dict
        """
        if not prompt:
            return self._empty_scene(quality, width, height)

        prompt_lower = prompt.lower()

        # Stage 0a: Detect mode and sub-mode
        mode = mode_detector.detect_mode(prompt)
        sub_mode = None  # detect_sub_mode not yet implemented

        # Stage 0b: Detect category
        category = category_detector.detect_category(prompt)
        cat_info = {"category": category, "category_type": "general"}

        # Stage 0c: Get template for this mode/sub_mode
        template = get_template(mode, sub_mode)

        # Stage 0d: Detect subject
        subject = self._detect_subject(prompt_lower)

        # Stage 0e: Get camera/lighting/composition
        mode_key = f"{mode}_{sub_mode}" if sub_mode else mode
        camera = self._get_camera(mode_key, cat_info['category'])
        lighting = self._get_lighting(mode_key, cat_info['category'])
        composition = self._get_composition(mode_key, cat_info['category'])

        # Stage 0f: Detect background
        background = self._detect_background(prompt_lower, mode)

        # Stage 0g: Determine aspect ratio context
        aspect = self._get_aspect_context(width, height)

        # Stage 0h: Build prompt strategy
        enhanced_prompt = build_enhanced_prompt(prompt, template, quality)
        negative_prompt = get_negative_prompt(template)

        return {
            'mode': mode,
            'sub_mode': sub_mode,
            'category': cat_info['category'],
            'category_type': cat_info['category_type'],
            'template_key': f"{mode}_{sub_mode}" if sub_mode else mode,
            'subject': subject,
            'camera': camera,
            'lighting': lighting,
            'composition': composition,
            'background': background,
            'aspect': aspect,
            'dimensions': {'width': width, 'height': height},
            'quality': quality,
            'prompt_strategy': {
                'original_prompt': prompt,
                'enhanced_prompt': enhanced_prompt,
                'negative_prompt': negative_prompt,
                'prefix': template.get('prefix', ''),
                'quality_boost': template.get('quality_boost', ''),
                'technical': template.get('technical', ''),
            },
            'pipeline_hints': self._get_pipeline_hints(mode, sub_mode, quality, cat_info['category_type']),
        }

    def _detect_subject(self, prompt_lower: str) -> Dict[str, Any]:
        """Detect the primary subject of the image."""
        scores = {}
        for subject_type, keywords in SUBJECT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            scores[subject_type] = score

        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return {'type': 'scene', 'confidence': 0.0}

        total = sum(scores.values())
        return {
            'type': best,
            'confidence': round(scores[best] / total, 2) if total > 0 else 0.0,
            'secondary': sorted(
                [(k, v) for k, v in scores.items() if v > 0 and k != best],
                key=lambda x: x[1], reverse=True
            )[:2],
        }

    def _get_camera(self, mode_key: str, category: str) -> Dict:
        """Get camera preset for mode and category."""
        # Try specific mode_submode first
        preset_name = MODE_CAMERA_MAP.get(mode_key)
        if not preset_name:
            # Try master mode
            master = mode_key.split('_')[0]
            preset_name = MODE_CAMERA_MAP.get(master, 'default')

        # Category-specific overrides
        if category in ('macro',) and preset_name == 'default':
            preset_name = 'macro_extreme'
        elif category in ('aerial',) and preset_name == 'default':
            preset_name = 'aerial_high'
        elif category in ('sports',) and preset_name == 'default':
            preset_name = 'action_fast'
        elif category in ('food',) and preset_name == 'default':
            preset_name = 'product_studio'

        preset = CAMERA_PRESETS.get(preset_name, CAMERA_PRESETS['default'])
        return {**preset, 'preset_name': preset_name}

    def _get_lighting(self, mode_key: str, category: str) -> Dict:
        """Get lighting preset for mode and category."""
        preset_name = MODE_LIGHTING_MAP.get(mode_key)
        if not preset_name:
            master = mode_key.split('_')[0]
            preset_name = MODE_LIGHTING_MAP.get(master, 'default')

        # Category overrides
        if category == 'food' and preset_name == 'default':
            preset_name = 'food_appetizing'
        elif category == 'underwater' and preset_name == 'default':
            preset_name = 'underwater_caustic'
        elif category == 'space' and preset_name == 'default':
            preset_name = 'space_ambient'

        preset = LIGHTING_PRESETS.get(preset_name, LIGHTING_PRESETS['default'])
        return {**preset, 'preset_name': preset_name}

    def _get_composition(self, mode_key: str, category: str) -> Dict:
        """Get composition preset for mode and category."""
        preset_name = MODE_COMPOSITION_MAP.get(mode_key)
        if not preset_name:
            master = mode_key.split('_')[0]
            preset_name = MODE_COMPOSITION_MAP.get(master, 'default')

        preset = COMPOSITION_PRESETS.get(preset_name, COMPOSITION_PRESETS['default'])
        return {**preset, 'preset_name': preset_name}

    def _detect_background(self, prompt_lower: str, mode: str) -> Dict:
        """Detect background type from prompt context."""
        scores = {}
        for bg_type, keywords in BACKGROUND_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            scores[bg_type] = score

        best = max(scores, key=scores.get)
        if scores[best] == 0:
            # Default backgrounds by mode
            defaults = {
                'REALISM': 'studio_white',
                'CINEMATIC': 'urban',
                'FANTASY': 'fantasy',
                'CYBERPUNK': 'urban',
                'NATURE': 'nature_outdoor',
                'PRODUCT': 'studio_white',
                'FOOD': 'studio_white',
                'SCIENTIFIC': 'studio_white',
                'SPACE': 'space',
            }
            best = defaults.get(mode, 'studio_white')

        return {'type': best, 'blur': self._get_blur_strength(best, mode)}

    def _get_blur_strength(self, bg_type: str, mode: str) -> float:
        """Determine background blur based on context."""
        if bg_type.startswith('studio'):
            return 0.0  # Studio backgrounds are intentional
        if mode in ('REALISM', 'PRODUCT', 'FOOD'):
            return 0.6  # Shallow DOF for focus
        if mode in ('CINEMATIC',):
            return 0.4
        if mode in ('NATURE', 'ARCHITECTURE'):
            return 0.1  # Keep background sharp
        return 0.3

    def _get_aspect_context(self, width: int, height: int) -> Dict:
        """Analyze aspect ratio for composition guidance."""
        ratio = width / height if height > 0 else 1.0

        if ratio > 1.8:
            aspect_type = 'ultra_wide'
            composition_hint = 'panoramic, cinematic widescreen'
        elif ratio > 1.3:
            aspect_type = 'landscape'
            composition_hint = 'wide composition, horizontal flow'
        elif ratio > 0.9:
            aspect_type = 'square'
            composition_hint = 'balanced, centered composition'
        elif ratio > 0.6:
            aspect_type = 'portrait'
            composition_hint = 'vertical composition, tall framing'
        else:
            aspect_type = 'ultra_tall'
            composition_hint = 'vertical panoramic, stacked elements'

        return {
            'type': aspect_type,
            'ratio': round(ratio, 2),
            'hint': composition_hint,
        }

    def _get_pipeline_hints(self, mode: str, sub_mode: Optional[str],
                            quality: str, category_type: str) -> Dict:
        """Generate hints for downstream pipeline stages."""
        # Candidate counts
        candidate_counts = {'FAST': 1, 'STANDARD': 2, 'PREMIUM': 3}

        # Whether enhancement should be applied
        enhance = quality in ('STANDARD', 'PREMIUM')

        # Whether to use color grading
        color_grade = mode in ('CINEMATIC', 'VINTAGE', 'CYBERPUNK', 'FANTASY')

        # Whether sharpening is needed
        sharpen = category_type == 'photographic' and quality != 'FAST'

        return {
            'candidates': candidate_counts.get(quality, 2),
            'apply_enhancement': enhance,
            'apply_color_grade': color_grade,
            'apply_sharpen': sharpen,
            'use_negative_prompt': True,
            'priority': 'speed' if quality == 'FAST' else 'quality',
        }

    def _empty_scene(self, quality: str, width: int, height: int) -> Dict:
        """Return minimal scene for empty prompt."""
        return {
            'mode': 'REALISM',
            'sub_mode': None,
            'category': 'general',
            'category_type': 'general',
            'template_key': 'REALISM',
            'subject': {'type': 'scene', 'confidence': 0.0},
            'camera': {**CAMERA_PRESETS['default'], 'preset_name': 'default'},
            'lighting': {**LIGHTING_PRESETS['default'], 'preset_name': 'default'},
            'composition': {**COMPOSITION_PRESETS['default'], 'preset_name': 'default'},
            'background': {'type': 'studio_white', 'blur': 0.0},
            'aspect': self._get_aspect_context(width, height),
            'dimensions': {'width': width, 'height': height},
            'quality': quality,
            'prompt_strategy': {
                'original_prompt': '',
                'enhanced_prompt': '',
                'negative_prompt': '',
                'prefix': '',
                'quality_boost': '',
                'technical': '',
            },
            'pipeline_hints': self._get_pipeline_hints('REALISM', None, quality, 'general'),
        }


# Singleton instance
scene_compiler = SceneCompiler()

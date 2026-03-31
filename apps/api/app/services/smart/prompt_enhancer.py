"""
Smart Prompt Enhancer - AI enhances prompts based on mode, category, and quality

Features:
- Mode-specific enhancements (REALISM, CINEMATIC, etc.)
- Category-specific keywords (portrait, landscape, etc.)
- Quality-based optimization (FAST, STANDARD, PREMIUM)
- Automatic negative prompts
"""

from typing import Dict


class SmartPromptEnhancer:
    """AI-powered prompt enhancement for better generation quality"""

    # Mode-specific enhancements
    MODE_ENHANCEMENTS = {
        'REALISM': 'professional photography, photorealistic, sharp focus, natural lighting, high resolution, detailed',
        'CINEMATIC': 'cinematic lighting, film grain, dramatic, movie quality, volumetric lighting, depth of field, anamorphic lens',
        'CREATIVE': 'artistic, creative composition, unique perspective, imaginative, expressive, original artwork',
        'FANTASY': 'fantasy art, magical, ethereal lighting, enchanted, mystical atmosphere, otherworldly, epic',
        'ANIME': 'anime style, manga aesthetic, vibrant colors, cel shading, clean lineart, detailed illustration'
    }

    # Category-specific enhancements
    CATEGORY_ENHANCEMENTS = {
        'portrait': 'professional portrait, shallow depth of field, bokeh background, sharp eyes, facial details, studio quality',
        'landscape': 'wide angle, golden hour, high dynamic range, dramatic sky, atmospheric perspective, scenic view',
        'product': 'product photography, studio lighting, clean background, commercial quality, sharp details, professional',
        'architecture': 'architectural photography, symmetrical, sharp details, perspective correction, structural clarity',
        'food': 'food photography, appetizing, macro details, natural lighting, fresh, delicious presentation',
        'animal': 'wildlife photography, sharp focus on subject, natural habitat, behavioral moment, detailed fur/feathers',
        'abstract': 'abstract composition, color harmony, geometric precision, artistic pattern, visual balance',
        'interior': 'interior design, ambient lighting, spacious, architectural details, cozy atmosphere',
        'general': 'professional quality, well composed, balanced lighting, clear subject'
    }

    # Quality-based keywords
    QUALITY_KEYWORDS = {
        'FAST': 'good quality',
        'STANDARD': 'high quality, detailed, 8k uhd, professional',
        'PREMIUM': 'masterpiece, best quality, ultra detailed, 8k uhd, award winning, exceptional detail, perfect composition'
    }

    # Universal negative prompts
    NEGATIVE_PROMPTS = {
        'REALISM': 'blurry, low quality, distorted, deformed, ugly, bad anatomy, disfigured, poorly drawn, mutation',
        'CINEMATIC': 'low quality, amateur, poor composition, flat lighting, overexposed, underexposed',
        'CREATIVE': 'boring, generic, unoriginal, poorly executed, messy, chaotic',
        'FANTASY': 'low quality, amateur, poorly drawn, inconsistent style, muddy colors',
        'ANIME': 'low quality, bad anatomy, poorly drawn face, mutation, deformed, ugly, blurry'
    }

    def enhance(
        self,
        user_prompt: str,
        mode: str = 'REALISM',
        category: str = 'general',
        quality: str = 'STANDARD'
    ) -> Dict:
        """
        Enhance user's prompt with AI-generated quality keywords

        Args:
            user_prompt: Original user prompt
            mode: Generation mode (REALISM, CINEMATIC, etc.)
            category: Image category (portrait, landscape, etc.)
            quality: Quality tier (FAST, STANDARD, PREMIUM)

        Returns:
            dict: {
                'original': str,
                'enhanced': str,
                'negative': str,
                'mode': str,
                'category': str,
                'quality': str
            }

        Example:
            >>> enhancer = SmartPromptEnhancer()
            >>> result = enhancer.enhance(
            ...     "sunset over mountains",
            ...     mode="CINEMATIC",
            ...     category="landscape",
            ...     quality="PREMIUM"
            ... )
            >>> print(result['enhanced'])
            'sunset over mountains, cinematic lighting, film grain, dramatic...'
        """
        if not user_prompt or not user_prompt.strip():
            raise ValueError("Prompt cannot be empty")

        # Build enhanced prompt
        enhanced_parts = [user_prompt.strip()]

        # Add mode enhancement
        if mode in self.MODE_ENHANCEMENTS:
            enhanced_parts.append(self.MODE_ENHANCEMENTS[mode])

        # Add category enhancement
        if category in self.CATEGORY_ENHANCEMENTS:
            enhanced_parts.append(self.CATEGORY_ENHANCEMENTS[category])

        # Add quality keywords
        if quality in self.QUALITY_KEYWORDS:
            enhanced_parts.append(self.QUALITY_KEYWORDS[quality])

        # Join with commas
        enhanced_prompt = ', '.join(enhanced_parts)

        # Get negative prompt
        negative_prompt = self.NEGATIVE_PROMPTS.get(mode, self.NEGATIVE_PROMPTS['REALISM'])

        return {
            'original': user_prompt,
            'enhanced': enhanced_prompt,
            'negative': negative_prompt,
            'mode': mode,
            'category': category,
            'quality': quality,
            'enhancements_applied': {
                'mode_enhancement': self.MODE_ENHANCEMENTS.get(mode, ''),
                'category_enhancement': self.CATEGORY_ENHANCEMENTS.get(category, ''),
                'quality_keywords': self.QUALITY_KEYWORDS.get(quality, '')
            }
        }

    def enhance_simple(self, user_prompt: str, mode: str = 'REALISM', quality: str = 'STANDARD') -> str:
        """
        Simple enhancement - just return the enhanced prompt string

        Args:
            user_prompt: Original prompt
            mode: Generation mode
            quality: Quality tier

        Returns:
            str: Enhanced prompt
        """
        result = self.enhance(user_prompt, mode=mode, quality=quality)
        return result['enhanced']

    def get_negative_prompt(self, mode: str = 'REALISM') -> str:
        """
        Get negative prompt for a mode

        Args:
            mode: Generation mode

        Returns:
            str: Negative prompt
        """
        return self.NEGATIVE_PROMPTS.get(mode, self.NEGATIVE_PROMPTS['REALISM'])

    def preview_enhancement(
        self,
        user_prompt: str,
        mode: str = 'REALISM',
        category: str = 'general',
        quality: str = 'STANDARD'
    ) -> Dict:
        """
        Preview what enhancements will be applied without actually enhancing

        Args:
            user_prompt: Original prompt
            mode: Generation mode
            category: Image category
            quality: Quality tier

        Returns:
            dict: Preview of enhancements
        """
        return {
            'original_prompt': user_prompt,
            'mode': mode,
            'category': category,
            'quality': quality,
            'will_add': {
                'mode_keywords': self.MODE_ENHANCEMENTS.get(mode, 'none'),
                'category_keywords': self.CATEGORY_ENHANCEMENTS.get(category, 'none'),
                'quality_keywords': self.QUALITY_KEYWORDS.get(quality, 'none'),
                'negative_prompt': self.NEGATIVE_PROMPTS.get(mode, 'default')
            }
        }


# Singleton instance
prompt_enhancer = SmartPromptEnhancer()

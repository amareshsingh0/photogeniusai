"""
Universal Prompt Enhancer - Multi-domain intelligent enhancement

Features:
- Domain classification (photography, art, design, etc.)
- Domain-specific enhancement
- Style transfer keywords
- Quality boosters
- Wow factor optimization

Adapted from ai-pipeline/services/universal_prompt_enhancer.py
"""

from typing import Dict, List, Optional
from enum import Enum


class PromptDomain(Enum):
    """Prompt domain categories"""
    PHOTOGRAPHY = "photography"
    DIGITAL_ART = "digital_art"
    CONCEPT_ART = "concept_art"
    ILLUSTRATION = "illustration"
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    PRODUCT = "product"
    ARCHITECTURE = "architecture"
    FASHION = "fashion"
    CINEMATIC = "cinematic"
    SURREAL = "surreal"
    GENERAL = "general"


class UniversalPromptEnhancer:
    """
    Universal prompt enhancement across all domains

    Workflow:
    1. Classify prompt domain
    2. Apply domain-specific enhancements
    3. Add quality boosters
    4. Optimize for wow factor
    """

    # Domain-specific enhancements
    DOMAIN_KEYWORDS = {
        PromptDomain.PHOTOGRAPHY: {
            'style': ['professional photography', 'DSLR', 'high-end camera'],
            'technical': ['sharp focus', 'perfect exposure', 'bokeh', 'depth of field'],
            'lighting': ['natural lighting', 'golden hour', 'studio lighting'],
            'quality': ['8k resolution', 'RAW format', 'professional grade']
        },
        PromptDomain.CINEMATIC: {
            'style': ['cinematic', 'movie still', 'film scene'],
            'technical': ['anamorphic lens', 'film grain', 'color grading'],
            'lighting': ['dramatic lighting', 'volumetric', 'atmospheric'],
            'quality': ['blockbuster quality', 'Hollywood production', '4k cinematography']
        },
        PromptDomain.DIGITAL_ART: {
            'style': ['digital art', 'trending on artstation', 'concept art'],
            'technical': ['highly detailed', 'intricate', 'professional illustration'],
            'lighting': ['perfect lighting', 'vibrant colors', 'dynamic composition'],
            'quality': ['masterpiece', 'award winning', '8k digital painting']
        },
        PromptDomain.PORTRAIT: {
            'style': ['professional portrait', 'studio portrait', 'headshot'],
            'technical': ['sharp focus on eyes', 'perfect skin texture', 'detailed features'],
            'lighting': ['soft lighting', 'Rembrandt lighting', 'portrait lighting'],
            'quality': ['high-end portrait', 'professional quality', '85mm lens']
        }
    }

    # Universal quality boosters
    QUALITY_BOOSTERS = [
        'masterpiece',
        'best quality',
        'ultra detailed',
        'high resolution',
        'professional',
        'stunning',
        'exceptional'
    ]

    # Wow factor keywords
    WOW_KEYWORDS = [
        'breathtaking',
        'stunning',
        'award winning',
        'exceptional',
        'extraordinary',
        'magnificent',
        'spectacular'
    ]

    def __init__(self):
        """Initialize universal enhancer"""
        pass

    def classify_domain(self, prompt: str) -> PromptDomain:
        """
        Classify prompt into domain

        Args:
            prompt: User prompt

        Returns:
            PromptDomain: Detected domain
        """
        prompt_lower = prompt.lower()

        # Check for specific domain keywords
        if any(kw in prompt_lower for kw in ['photo', 'photograph', 'shot', 'camera']):
            return PromptDomain.PHOTOGRAPHY

        if any(kw in prompt_lower for kw in ['cinematic', 'movie', 'film', 'scene']):
            return PromptDomain.CINEMATIC

        if any(kw in prompt_lower for kw in ['portrait', 'headshot', 'face', 'person']):
            return PromptDomain.PORTRAIT

        if any(kw in prompt_lower for kw in ['landscape', 'scenery', 'nature', 'outdoor']):
            return PromptDomain.LANDSCAPE

        if any(kw in prompt_lower for kw in ['product', 'commercial', 'showcase']):
            return PromptDomain.PRODUCT

        if any(kw in prompt_lower for kw in ['digital art', 'artwork', 'illustration']):
            return PromptDomain.DIGITAL_ART

        return PromptDomain.GENERAL

    def enhance(
        self,
        prompt: str,
        domain: Optional[PromptDomain] = None,
        wow_factor: float = 0.7,
        quality_level: str = 'high'
    ) -> Dict:
        """
        Enhance prompt universally

        Args:
            prompt: Original prompt
            domain: Override domain detection
            wow_factor: How much wow to add (0-1)
            quality_level: 'basic', 'high', 'ultra'

        Returns:
            dict: Enhanced prompt with metadata
        """
        # Detect domain if not provided
        if not domain:
            domain = self.classify_domain(prompt)

        # Get domain-specific keywords
        domain_keywords = self.DOMAIN_KEYWORDS.get(
            domain,
            self.DOMAIN_KEYWORDS[PromptDomain.DIGITAL_ART]
        )

        # Build enhanced prompt
        enhanced_parts = [prompt]

        # Add style keywords
        enhanced_parts.append(', '.join(domain_keywords['style'][:2]))

        # Add technical keywords
        enhanced_parts.append(', '.join(domain_keywords['technical'][:2]))

        # Add lighting
        enhanced_parts.append(domain_keywords['lighting'][0])

        # Add quality based on level
        if quality_level == 'ultra':
            enhanced_parts.extend(self.QUALITY_BOOSTERS[:4])
            enhanced_parts.append(domain_keywords['quality'][0])
        elif quality_level == 'high':
            enhanced_parts.extend(self.QUALITY_BOOSTERS[:2])

        # Add wow factor
        if wow_factor >= 0.8:
            enhanced_parts.extend(self.WOW_KEYWORDS[:2])
        elif wow_factor >= 0.5:
            enhanced_parts.append(self.WOW_KEYWORDS[0])

        enhanced_prompt = ', '.join(enhanced_parts)

        return {
            'original': prompt,
            'enhanced': enhanced_prompt,
            'domain': domain.value,
            'wow_factor': wow_factor,
            'quality_level': quality_level,
            'keywords_added': {
                'style': domain_keywords['style'][:2],
                'technical': domain_keywords['technical'][:2],
                'lighting': [domain_keywords['lighting'][0]],
                'quality': self.QUALITY_BOOSTERS[:2]
            }
        }

    def enhance_with_style(
        self,
        prompt: str,
        style: str,
        intensity: float = 0.8
    ) -> Dict:
        """
        Enhance with specific style

        Args:
            prompt: Original prompt
            style: Style name (e.g., 'cyberpunk', 'vintage', 'minimalist')
            intensity: Style intensity (0-1)

        Returns:
            dict: Enhanced prompt
        """
        style_keywords = {
            'cyberpunk': ['neon lights', 'futuristic', 'high-tech', 'dystopian'],
            'vintage': ['retro', 'nostalgic', 'film photography', 'aged'],
            'minimalist': ['clean', 'simple', 'minimal', 'elegant'],
            'surreal': ['dreamlike', 'surreal', 'impossible', 'otherworldly'],
            'dramatic': ['dramatic', 'intense', 'powerful', 'emotional']
        }

        keywords = style_keywords.get(style, [])
        count = max(1, int(len(keywords) * intensity))

        enhanced = f"{prompt}, {', '.join(keywords[:count])}"

        return {
            'original': prompt,
            'enhanced': enhanced,
            'style': style,
            'intensity': intensity
        }


# Singleton instance
universal_enhancer = UniversalPromptEnhancer()

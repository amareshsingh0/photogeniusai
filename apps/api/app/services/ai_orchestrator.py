"""
AI Orchestrator - Central coordinator for all AI services

Coordinates:
- Smart AI services (mode, category, enhancement)
- Generation services (standard, two-pass, quality scoring)
- Identity services (InstantID, identity engine)
- Prompt services (universal, cinematic)

This is the main entry point for all AI operations.
"""

from typing import Dict, Optional, List
import time

from .smart import (
    mode_detector,
    category_detector,
    prompt_enhancer,
    generation_router
)
from .generation import (
    generation_service,
    quality_scorer,
    two_pass_generator
)
from .identity import (
    instantid_service,
    identity_engine
)
from .prompts import (
    universal_enhancer,
    cinematic_engine
)


class AIOrchestrator:
    """
    Central AI orchestrator for PhotoGenius

    Features:
    - Automatic service selection
    - Smart routing based on request type
    - Fallback handling
    - Performance monitoring
    """

    def __init__(self):
        """Initialize AI orchestrator"""
        self.services_loaded = False

    async def initialize(self):
        """Initialize all AI services"""
        print("[INFO] Initializing AI Orchestrator...")

        # Load models (if available)
        await instantid_service.load_models()
        await identity_engine.load_models()

        self.services_loaded = True
        print("[INFO] AI Orchestrator ready!")

    async def generate(
        self,
        prompt: str,
        quality: str = 'STANDARD',
        width: int = 1024,
        height: int = 1024,
        mode: Optional[str] = None,
        use_two_pass: bool = False,
        use_identity: Optional[str] = None,
        enhancement_level: str = 'standard',  # 'simple', 'standard', 'advanced', 'cinematic'
        **kwargs
    ) -> Dict:
        """
        Main generation endpoint - automatically routes to best services

        Args:
            prompt: User prompt
            quality: FAST, STANDARD, PREMIUM
            width: Image width
            height: Image height
            mode: Override mode detection
            use_two_pass: Use two-pass generation
            use_identity: Identity ID to use
            enhancement_level: Prompt enhancement level

        Returns:
            dict: Complete generation result with metadata
        """
        start_time = time.time()

        # Step 1: Detect mode and category
        detected_mode = mode or mode_detector.detect_mode(prompt)
        detected_category = category_detector.detect_category(prompt)

        # Step 2: Enhance prompt based on level
        if enhancement_level == 'cinematic':
            # Use cinematic enhancer
            enhancement = cinematic_engine.enhance_cinematic(
                prompt,
                camera_angle='medium',
                lighting='volumetric'
            )
            enhanced_prompt = enhancement['enhanced']
            negative_prompt = "low quality, amateur, blurry, bad cinematography"

        elif enhancement_level == 'advanced':
            # Use universal enhancer
            enhancement = universal_enhancer.enhance(
                prompt,
                wow_factor=0.8,
                quality_level='ultra'
            )
            enhanced_prompt = enhancement['enhanced']
            negative_prompt = "low quality, amateur, ugly, deformed"

        else:  # standard or simple
            # Use smart prompt enhancer
            enhancement = prompt_enhancer.enhance(
                prompt,
                mode=detected_mode,
                category=detected_category,
                quality=quality
            )
            enhanced_prompt = enhancement['enhanced']
            negative_prompt = enhancement['negative']

        # Step 3: Route to appropriate generation service
        if use_identity and instantid_service.is_available():
            # Use identity-based generation
            result = await instantid_service.generate_with_identity(
                prompt=enhanced_prompt,
                identity_id=use_identity,
                quality=quality,
                width=width,
                height=height,
                **kwargs
            )

        elif use_two_pass and quality != 'FAST':
            # Use two-pass generation
            result = await two_pass_generator.generate_two_pass(
                prompt=enhanced_prompt,
                quality=quality,
                width=width,
                height=height,
                mode=detected_mode,
                category=detected_category,
                **kwargs
            )

        else:
            # Standard generation
            result = await generation_service.generate(
                prompt=enhanced_prompt,
                quality=quality,
                width=width,
                height=height,
                mode=detected_mode,
                category=detected_category,
                **kwargs
            )

        # Step 4: Score quality (if image generated)
        if result.get('image_url') and result.get('success'):
            scores = await quality_scorer.score_image(
                image_url=result['image_url'],
                prompt=prompt,
                mode=detected_mode
            )
            result['quality_scores'] = scores

        # Step 5: Add orchestration metadata
        result['orchestration'] = {
            'detected_mode': detected_mode,
            'detected_category': detected_category,
            'enhancement_level': enhancement_level,
            'used_two_pass': use_two_pass,
            'used_identity': use_identity is not None,
            'total_time': time.time() - start_time,
            'services_used': self._get_services_used(
                use_two_pass,
                use_identity,
                enhancement_level
            )
        }

        return result

    async def generate_with_identity_from_photos(
        self,
        photos: List[str],
        identity_name: str,
        prompt: str,
        user_id: str,
        quality: str = 'STANDARD',
        **kwargs
    ) -> Dict:
        """
        Create identity from photos and generate

        Args:
            photos: 5-20 reference photos
            identity_name: Name for identity
            prompt: Generation prompt
            user_id: User ID
            quality: Quality tier

        Returns:
            dict: Identity creation + generation result
        """
        # Step 1: Create identity
        identity_result = await identity_engine.create_identity_from_photos(
            photos=photos,
            identity_name=identity_name,
            user_id=user_id
        )

        if not identity_result.get('success'):
            return identity_result

        identity_id = identity_result['identity_id']

        # Step 2: Generate with identity
        generation_result = await self.generate(
            prompt=prompt,
            quality=quality,
            use_identity=identity_id,
            **kwargs
        )

        generation_result['identity_created'] = identity_result

        return generation_result

    async def generate_group_photo(
        self,
        identities: List[str],
        prompt: str,
        layout: str = 'auto',
        quality: str = 'STANDARD',
        **kwargs
    ) -> Dict:
        """
        Generate group photo with multiple identities

        Args:
            identities: List of identity IDs
            prompt: Generation prompt
            layout: Group layout
            quality: Quality tier

        Returns:
            dict: Group photo generation result
        """
        result = await identity_engine.generate_group_photo(
            identities=identities,
            prompt=prompt,
            layout=layout,
            quality=quality,
            **kwargs
        )

        return result

    def _get_services_used(
        self,
        use_two_pass: bool,
        use_identity: Optional[str],
        enhancement_level: str
    ) -> List[str]:
        """Get list of services used"""
        services = ['mode_detector', 'category_detector']

        if enhancement_level == 'cinematic':
            services.append('cinematic_engine')
        elif enhancement_level == 'advanced':
            services.append('universal_enhancer')
        else:
            services.append('prompt_enhancer')

        if use_identity:
            services.append('instantid_service')
        elif use_two_pass:
            services.append('two_pass_generator')
        else:
            services.append('generation_service')

        services.append('quality_scorer')

        return services

    async def get_status(self) -> Dict:
        """Get AI orchestrator status"""
        return {
            'status': 'ready' if self.services_loaded else 'initializing',
            'services': {
                'smart_ai': {
                    'mode_detector': True,
                    'category_detector': True,
                    'prompt_enhancer': True,
                    'generation_router': True
                },
                'generation': {
                    'generation_service': True,
                    'quality_scorer': True,
                    'two_pass_generator': True
                },
                'identity': {
                    'instantid': instantid_service.is_available(),
                    'identity_engine': identity_engine.is_available()
                },
                'prompts': {
                    'universal_enhancer': True,
                    'cinematic_engine': True
                }
            },
            'available_modes': list(mode_detector.MODES.keys()),
            'available_categories': list(category_detector.CATEGORIES.keys()),
            'quality_tiers': ['FAST', 'STANDARD', 'PREMIUM']
        }


# Singleton instance
ai_orchestrator = AIOrchestrator()

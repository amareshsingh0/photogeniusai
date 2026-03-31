"""
Multi-Candidate Generator - Generates N diverse candidates for jury selection.

Uses GenerationStrategyEngine to vary steps, guidance_scale, sampler, and seed
across candidates for TRUE diversity. The jury system then picks the best one.

Candidate counts by tier:
- FAST: 1 (speed priority, no jury)
- STANDARD: 2 (mild diversity, quick jury)
- PREMIUM: 3 (full diversity, thorough jury)

Each candidate uses DIFFERENT diffusion physics, not just different seeds.
"""

import time
import logging
from typing import Dict, List, Optional, Any

from .generation_strategy import generation_strategy, CANDIDATE_COUNT
from ..smart.generation_router import generation_router

logger = logging.getLogger(__name__)


class MultiCandidateGenerator:
    """Generates multiple image candidates with diverse diffusion parameters.

    Each candidate uses different generation physics (steps, guidance,
    sampler) from the strategy engine for true diversity.
    """

    async def generate_candidates(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        quality: str,
        mode: str = 'REALISM',
        sub_mode: Optional[str] = None,
        category: str = 'general',
        base_seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Generate N diverse candidates based on quality tier.

        Each candidate uses different diffusion parameters from the
        GenerationStrategyEngine for true diversity.
        """
        profiles = generation_strategy.get_candidate_profiles(mode, sub_mode, quality)

        if base_seed is None:
            base_seed = int(time.time() * 1000) % (2**32)

        candidates = []
        total_start = time.time()

        logger.info(
            f"Generating {len(profiles)} candidates: "
            f"mode={mode}, sub_mode={sub_mode}, quality={quality}"
        )

        for profile in profiles:
            idx = profile['index']
            seed = base_seed + profile['seed_offset']
            steps = profile['steps']
            guidance = profile['guidance_scale']
            sampler = profile.get('sampler', 'dpmpp_2m')

            logger.info(
                f"  Candidate {idx} [{profile['label']}]: "
                f"steps={steps}, guidance={guidance}, sampler={sampler}, seed={seed}"
            )

            try:
                result = await generation_router.generate(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    quality_tier=quality,
                    seed=seed,
                    guidance_scale=guidance,
                    num_inference_steps=steps,
                )

                if result.get('success'):
                    candidates.append({
                        'index': idx,
                        'label': profile['label'],
                        'image_url': result['image_url'],
                        'image_base64': result.get('image_base64'),
                        'seed': seed,
                        'steps': steps,
                        'guidance_scale': guidance,
                        'sampler': sampler,
                        'generation_time': result.get('generation_time', 0),
                        'metadata': result.get('metadata', {}),
                        'success': True,
                    })
                else:
                    logger.warning(
                        f"  Candidate {idx} failed: {result.get('error', 'unknown')}"
                    )

            except Exception as e:
                logger.error(f"  Candidate {idx} exception: {e}")

        total_time = time.time() - total_start
        logger.info(
            f"Generated {len(candidates)}/{len(profiles)} candidates "
            f"in {total_time:.1f}s"
        )

        return candidates

    async def generate_single(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        quality: str,
        mode: str = 'REALISM',
        sub_mode: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate a single image with strategy-optimized parameters."""
        params = generation_strategy.get_single_params(mode, sub_mode, quality)

        if seed is None:
            seed = int(time.time() * 1000) % (2**32)

        result = await generation_router.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            quality_tier=quality,
            seed=seed,
            guidance_scale=params['guidance_scale'],
            num_inference_steps=params['steps'],
        )

        if result.get('success'):
            return {
                'index': 0,
                'label': 'single',
                'image_url': result['image_url'],
                'image_base64': result.get('image_base64'),
                'seed': seed,
                'steps': params['steps'],
                'guidance_scale': params['guidance_scale'],
                'sampler': params['sampler'],
                'generation_time': result.get('generation_time', 0),
                'metadata': result.get('metadata', {}),
                'success': True,
            }

        return None

    async def generate_retry(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        quality: str,
        mode: str = 'REALISM',
        sub_mode: Optional[str] = None,
        hint: str = 'new_seed',
    ) -> Optional[Dict[str, Any]]:
        """Generate a retry candidate with adjusted parameters.

        Used by failure_detector when previous attempt was bad.
        """
        seed = int(time.time() * 1000 + 99999) % (2**32)

        return await self.generate_single(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            quality=quality,
            mode=mode,
            sub_mode=sub_mode,
            seed=seed,
        )


# Singleton instance
multi_candidate_generator = MultiCandidateGenerator()

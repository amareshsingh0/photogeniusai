"""
Generation Strategy Engine - Diffusion parameter planning per mode/category.

The "Diffusion Brain": Decides HOW to generate technically.
Different image types need different diffusion physics.
Portrait vs Poster vs Anime should NOT use same params.

Determines: steps, guidance_scale, sampler, scheduler, cfg_rescale,
highres_fix, tiling, and multi-candidate diversity strategies.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class GenerationParams:
    """Complete set of diffusion parameters for a generation request."""
    steps: int
    guidance_scale: float
    sampler: str
    scheduler: str
    highres_fix: bool
    cfg_rescale: float
    enable_tiling: bool


# ─── Mode Presets (Diffusion Physics per Mode) ───────────────────────────────

MODE_PRESETS: Dict[str, GenerationParams] = {
    "REALISM": GenerationParams(
        steps=34, guidance_scale=6.5, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "REALISM_portrait": GenerationParams(
        steps=36, guidance_scale=6.0, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "REALISM_fashion": GenerationParams(
        steps=36, guidance_scale=6.5, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "REALISM_wedding": GenerationParams(
        steps=38, guidance_scale=6.0, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "REALISM_street": GenerationParams(
        steps=32, guidance_scale=6.5, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=False, cfg_rescale=0.6, enable_tiling=False,
    ),
    "CINEMATIC": GenerationParams(
        steps=38, guidance_scale=7.0, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "CINEMATIC_noir": GenerationParams(
        steps=40, guidance_scale=7.5, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.8, enable_tiling=False,
    ),
    "CINEMATIC_action": GenerationParams(
        steps=36, guidance_scale=7.0, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "CINEMATIC_scifi": GenerationParams(
        steps=40, guidance_scale=7.5, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "CINEMATIC_horror": GenerationParams(
        steps=38, guidance_scale=7.0, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=False, cfg_rescale=0.7, enable_tiling=False,
    ),
    "CREATIVE": GenerationParams(
        steps=32, guidance_scale=7.0, sampler="dpmpp_2m", scheduler="normal",
        highres_fix=False, cfg_rescale=0.5, enable_tiling=False,
    ),
    "CREATIVE_surreal": GenerationParams(
        steps=36, guidance_scale=7.5, sampler="dpmpp_sde", scheduler="normal",
        highres_fix=False, cfg_rescale=0.5, enable_tiling=False,
    ),
    "FANTASY": GenerationParams(
        steps=38, guidance_scale=7.5, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "FANTASY_epic": GenerationParams(
        steps=42, guidance_scale=8.0, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.8, enable_tiling=False,
    ),
    "FANTASY_dark": GenerationParams(
        steps=38, guidance_scale=7.5, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "ANIME": GenerationParams(
        steps=28, guidance_scale=7.5, sampler="euler", scheduler="normal",
        highres_fix=False, cfg_rescale=0.5, enable_tiling=False,
    ),
    "ANIME_manga": GenerationParams(
        steps=28, guidance_scale=7.5, sampler="euler", scheduler="normal",
        highres_fix=False, cfg_rescale=0.5, enable_tiling=False,
    ),
    "ANIME_chibi": GenerationParams(
        steps=26, guidance_scale=8.0, sampler="euler", scheduler="normal",
        highres_fix=False, cfg_rescale=0.5, enable_tiling=False,
    ),
    "ANIME_ghibli": GenerationParams(
        steps=30, guidance_scale=7.0, sampler="euler", scheduler="normal",
        highres_fix=False, cfg_rescale=0.5, enable_tiling=False,
    ),
    "ART": GenerationParams(
        steps=34, guidance_scale=7.0, sampler="dpmpp_2m", scheduler="normal",
        highres_fix=False, cfg_rescale=0.6, enable_tiling=False,
    ),
    "ART_oil_painting": GenerationParams(
        steps=40, guidance_scale=7.0, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "ART_watercolor": GenerationParams(
        steps=30, guidance_scale=6.5, sampler="euler", scheduler="normal",
        highres_fix=False, cfg_rescale=0.5, enable_tiling=False,
    ),
    "ART_pencil_sketch": GenerationParams(
        steps=28, guidance_scale=7.0, sampler="dpmpp_2m", scheduler="normal",
        highres_fix=False, cfg_rescale=0.5, enable_tiling=False,
    ),
    "DIGITAL_ART": GenerationParams(
        steps=34, guidance_scale=7.0, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.6, enable_tiling=False,
    ),
    "DIGITAL_ART_concept": GenerationParams(
        steps=38, guidance_scale=7.5, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "DIGITAL_ART_3d_render": GenerationParams(
        steps=38, guidance_scale=7.5, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "DIGITAL_ART_isometric": GenerationParams(
        steps=34, guidance_scale=7.5, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=False, cfg_rescale=0.6, enable_tiling=False,
    ),
    "DESIGN": GenerationParams(
        steps=40, guidance_scale=8.5, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.8, enable_tiling=False,
    ),
    "DESIGN_poster": GenerationParams(
        steps=42, guidance_scale=8.5, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.8, enable_tiling=False,
    ),
    "DESIGN_social_media": GenerationParams(
        steps=36, guidance_scale=8.0, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=False, cfg_rescale=0.7, enable_tiling=False,
    ),
    "PRODUCT": GenerationParams(
        steps=38, guidance_scale=7.0, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "PRODUCT_luxury": GenerationParams(
        steps=42, guidance_scale=7.5, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.8, enable_tiling=False,
    ),
    "ARCHITECTURE": GenerationParams(
        steps=36, guidance_scale=7.0, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.6, enable_tiling=False,
    ),
    "ARCHITECTURE_render": GenerationParams(
        steps=40, guidance_scale=7.5, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "FOOD": GenerationParams(
        steps=34, guidance_scale=6.5, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.6, enable_tiling=False,
    ),
    "NATURE": GenerationParams(
        steps=32, guidance_scale=6.5, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.6, enable_tiling=False,
    ),
    "NATURE_macro": GenerationParams(
        steps=36, guidance_scale=7.0, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "SCIENTIFIC": GenerationParams(
        steps=36, guidance_scale=8.0, sampler="dpmpp_2m", scheduler="karras",
        highres_fix=True, cfg_rescale=0.8, enable_tiling=False,
    ),
    "CYBERPUNK": GenerationParams(
        steps=36, guidance_scale=7.5, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "CYBERPUNK_neon": GenerationParams(
        steps=38, guidance_scale=8.0, sampler="dpmpp_sde", scheduler="karras",
        highres_fix=True, cfg_rescale=0.7, enable_tiling=False,
    ),
    "VINTAGE": GenerationParams(
        steps=30, guidance_scale=6.0, sampler="euler", scheduler="normal",
        highres_fix=False, cfg_rescale=0.5, enable_tiling=False,
    ),
    "GEOMETRIC": GenerationParams(
        steps=32, guidance_scale=7.8, sampler="heun", scheduler="normal",
        highres_fix=False, cfg_rescale=0.6, enable_tiling=True,
    ),
    "GEOMETRIC_fractal": GenerationParams(
        steps=36, guidance_scale=8.0, sampler="heun", scheduler="normal",
        highres_fix=False, cfg_rescale=0.7, enable_tiling=True,
    ),
    "GEOMETRIC_mandala": GenerationParams(
        steps=34, guidance_scale=8.0, sampler="heun", scheduler="normal",
        highres_fix=False, cfg_rescale=0.7, enable_tiling=True,
    ),
}


# ─── Candidate Diversity Profiles ────────────────────────────────────────────
# Each candidate uses different diffusion physics for true diversity

CANDIDATE_VARIATIONS = [
    {"steps_offset": -4, "cfg_offset": -0.4, "sampler": "euler", "label": "lighter"},
    {"steps_offset": 0,  "cfg_offset": 0.0,  "sampler": "dpmpp_2m", "label": "balanced"},
    {"steps_offset": 4,  "cfg_offset": 0.4,  "sampler": "dpmpp_sde", "label": "detailed"},
    {"steps_offset": 8,  "cfg_offset": 0.8,  "sampler": "heun", "label": "heavy"},
]

# How many candidates per quality tier
# Single candidate: avoids 2-3x SageMaker latency.
# Quality comes from better prompts + correct model, not multiple candidates.
CANDIDATE_COUNT = {
    'FAST': 1,
    'STANDARD': 1,
    'PREMIUM': 1,
}


class GenerationStrategyEngine:
    """Plans diffusion parameters for optimal image generation.

    The Diffusion Brain: automatically picks the best generation
    physics based on what type of image is being created.
    """

    def get_strategy(self, mode: str, sub_mode: Optional[str] = None,
                     quality: str = 'STANDARD') -> GenerationParams:
        """Get optimized generation params for mode + quality.

        Args:
            mode: Master mode
            sub_mode: Sub-mode
            quality: Quality tier

        Returns:
            GenerationParams with optimized diffusion settings
        """
        mode_key = f"{mode}_{sub_mode}" if sub_mode else mode
        base = MODE_PRESETS.get(mode_key, MODE_PRESETS.get(mode, MODE_PRESETS["REALISM"]))

        # Clone to avoid mutating presets
        params = GenerationParams(
            steps=base.steps,
            guidance_scale=base.guidance_scale,
            sampler=base.sampler,
            scheduler=base.scheduler,
            highres_fix=base.highres_fix,
            cfg_rescale=base.cfg_rescale,
            enable_tiling=base.enable_tiling,
        )

        # Quality tier adjustments
        if quality == "FAST":
            params.steps = max(4, params.steps - 10)
            params.highres_fix = False
        elif quality == "PREMIUM":
            params.steps += 8
            params.guidance_scale += 0.3

        return params

    def get_candidate_profiles(self, mode: str, sub_mode: Optional[str],
                               quality: str) -> List[Dict[str, Any]]:
        """Get diverse candidate profiles for multi-candidate generation.

        Each candidate uses different diffusion physics for true diversity.
        """
        base = self.get_strategy(mode, sub_mode, quality)
        count = CANDIDATE_COUNT.get(quality, 2)

        profiles = []
        for i in range(count):
            variation = CANDIDATE_VARIATIONS[i % len(CANDIDATE_VARIATIONS)]

            candidate_steps = max(4, base.steps + variation["steps_offset"])
            candidate_cfg = max(1.0, base.guidance_scale + variation["cfg_offset"])

            profiles.append({
                'index': i,
                'steps': candidate_steps,
                'guidance_scale': round(candidate_cfg, 1),
                'sampler': variation["sampler"],
                'scheduler': base.scheduler,
                'cfg_rescale': base.cfg_rescale,
                'highres_fix': base.highres_fix,
                'enable_tiling': base.enable_tiling,
                'seed_offset': i * 12345,
                'label': variation["label"],
            })

        return profiles

    def get_single_params(self, mode: str, sub_mode: Optional[str] = None,
                          quality: str = 'STANDARD') -> Dict[str, Any]:
        """Get params for single generation (no multi-candidate).

        Returns dict compatible with generation_router.generate().
        """
        params = self.get_strategy(mode, sub_mode, quality)
        return {
            'steps': params.steps,
            'guidance_scale': params.guidance_scale,
            'sampler': params.sampler,
            'scheduler': params.scheduler,
            'cfg_rescale': params.cfg_rescale,
        }


# Singleton instance
generation_strategy = GenerationStrategyEngine()

"""
Mutation system for Creative Engine – parameter and prompt variations.

No Modal dependencies. Used by creative_engine and by tests.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List


class MutationSystem:
    """Generate parameter variations for creative diversity and ensemble generation."""

    MUTATION_PRESETS = {
        "subtle": {
            "guidance_range": (0.9, 1.1),
            "steps_range": (0.95, 1.05),
            "cfg_range": (0.9, 1.1),
        },
        "moderate": {
            "guidance_range": (0.8, 1.2),
            "steps_range": (0.9, 1.1),
            "cfg_range": (0.8, 1.2),
        },
        "wild": {
            "guidance_range": (0.6, 1.4),
            "steps_range": (0.8, 1.2),
            "cfg_range": (0.6, 1.4),
        },
    }

    @staticmethod
    def mutate_params(
        base_params: Dict[str, Any],
        mutation_level: str = "moderate",
        num_mutations: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Generate parameter mutations.

        Args:
            base_params: Base generation parameters
            mutation_level: subtle / moderate / wild
            num_mutations: Number of variants to generate

        Returns:
            List of mutated parameter dicts
        """
        preset = MutationSystem.MUTATION_PRESETS.get(
            mutation_level, MutationSystem.MUTATION_PRESETS["moderate"]
        )
        mutations: List[Dict[str, Any]] = []
        base_guidance = base_params.get("guidance_scale", 7.5)
        base_steps = base_params.get("num_inference_steps", 50)
        base_seed = base_params.get("seed")

        for i in range(num_mutations):
            mutated = dict(base_params)

            g_mult = random.uniform(*preset["guidance_range"])
            mutated["guidance_scale"] = max(1.0, min(20.0, base_guidance * g_mult))

            s_mult = random.uniform(*preset["steps_range"])
            mutated["num_inference_steps"] = max(20, min(80, int(base_steps * s_mult)))

            if base_seed is not None:
                mutated["seed"] = base_seed + i

            if random.random() < 0.2:
                mutated["style_strength"] = random.uniform(0.3, 0.9)

            mutations.append(mutated)

        return mutations

    @staticmethod
    def mutate_prompt(
        base_prompt: str,
        style_keywords: List[str],
        num_variations: int = 4,
    ) -> List[str]:
        """
        Generate prompt variations with style keywords.

        Args:
            base_prompt: Original prompt
            style_keywords: Keywords for this style
            num_variations: Number of prompt variations

        Returns:
            List of mutated prompts (first is original)
        """
        variations = [base_prompt]
        if not style_keywords or num_variations <= 1:
            return variations

        for _ in range(num_variations - 1):
            n = random.randint(1, min(3, len(style_keywords)))
            selected = random.sample(style_keywords, n)
            position = random.choice(["prefix", "suffix", "middle"])

            if position == "prefix":
                varied = f"{', '.join(selected)}, {base_prompt}"
            elif position == "suffix":
                varied = f"{base_prompt}, {', '.join(selected)}"
            else:
                words = base_prompt.split()
                mid = max(1, len(words) // 2)
                varied = " ".join(words[:mid] + selected + words[mid:])

            variations.append(varied)

        return variations

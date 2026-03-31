"""
Preference Learning System - Learns which variations are better.

Inspired by RLHF (Reinforcement Learning from Human Feedback):
1. Generate multiple variations
2. Rank by quality (validation scores)
3. Learn preference patterns
4. Apply learnings to future generations
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

try:
    from .experience_memory import GenerationExperience
except ImportError:
    from ai_pipeline.services.experience_memory import GenerationExperience  # type: ignore


@dataclass
class PreferencePair:
    """A pair of generations for preference comparison."""

    better_experience: GenerationExperience
    worse_experience: GenerationExperience
    score_difference: float
    preference_strength: float  # 0.0-1.0, how much better


class PreferenceLearning:
    """
    Learn preferences from generation comparisons.

    Learns:
    - Which ControlNet scales work better for different scenes
    - Optimal guidance scales for different prompts
    - When to use higher reward guidance
    - Scene-specific parameter preferences
    """

    def __init__(self) -> None:
        self.preference_pairs: List[PreferencePair] = []
        self.learned_preferences: Dict[str, Dict[str, Any]] = {
            "controlnet_scales": {},
            "guidance_scale": {},
            "reward_weight": {},
        }

    def add_preference_pair(
        self,
        better: GenerationExperience,
        worse: GenerationExperience,
    ) -> None:
        """
        Add a preference pair (better vs worse generation).

        Automatically called when we have multiple attempts at same prompt.
        """
        score_diff = better.final_score - worse.final_score

        if score_diff < 0.05:
            return

        preference_strength = min(score_diff / 0.5, 1.0)

        pair = PreferencePair(
            better_experience=better,
            worse_experience=worse,
            score_difference=score_diff,
            preference_strength=preference_strength,
        )
        self.preference_pairs.append(pair)
        self._update_preferences(pair)

    def _update_preferences(self, pair: PreferencePair) -> None:
        """Update preference models based on new pair."""
        better = pair.better_experience
        scene_key = self._get_scene_key(better)

        if scene_key not in self.learned_preferences["controlnet_scales"]:
            self.learned_preferences["controlnet_scales"][scene_key] = {
                "samples": [],
                "avg_scales": None,
            }

        self.learned_preferences["controlnet_scales"][scene_key]["samples"].append({
            "scales": list(better.controlnet_scales),
            "score": better.final_score,
            "weight": pair.preference_strength,
        })
        self._recompute_averages(scene_key)

    def _get_scene_key(self, experience: GenerationExperience) -> str:
        """Generate key for scene type."""
        key_parts = []

        if experience.person_count == 0:
            key_parts.append("no_people")
        elif experience.person_count == 1:
            key_parts.append("single_person")
        elif experience.person_count <= 3:
            key_parts.append("small_group")
        else:
            key_parts.append("large_group")

        if experience.scene_complexity > 0.7:
            key_parts.append("complex")

        if experience.has_weather:
            key_parts.append("weather")
        if experience.has_fantasy:
            key_parts.append("fantasy")

        return "_".join(key_parts)

    def _recompute_averages(self, scene_key: str) -> None:
        """Recompute average preferred parameters for scene type."""
        if scene_key not in self.learned_preferences["controlnet_scales"]:
            return
        entry = self.learned_preferences["controlnet_scales"][scene_key]
        samples = entry.get("samples", [])
        if not samples:
            return

        weights = np.array([s["weight"] * s["score"] for s in samples], dtype=np.float64)
        total = weights.sum()
        if total <= 0:
            return
        weights = weights / total

        scales = np.array([s["scales"] for s in samples], dtype=np.float64)
        avg_scales = np.average(scales, axis=0, weights=weights).tolist()
        entry["avg_scales"] = avg_scales

    def get_recommended_parameters(
        self,
        person_count: int,
        scene_complexity: float,
        has_weather: bool,
        has_fantasy: bool,
    ) -> Dict[str, Any]:
        """
        Get recommended parameters based on learned preferences.

        Returns:
            {
                'controlnet_scales': [depth, openpose, canny],
                'guidance_scale': float,
                'reward_weight': float,
                'confidence': float,
                'sample_count': int (optional)
            }
        """
        temp_exp = GenerationExperience(
            id="temp",
            timestamp="",
            prompt="",
            prompt_embedding=np.zeros(512, dtype=np.float32),
            person_count=person_count,
            scene_complexity=scene_complexity,
            has_weather=has_weather,
            has_fantasy=has_fantasy,
            iterations_needed=0,
            final_score=0.0,
            success=False,
            validation_scores={},
            issues_encountered=[],
            fixes_applied=[],
            controlnet_scales=[0.6, 0.9, 0.4],
            guidance_scale=7.5,
            reward_weight=0.3,
        )

        scene_key = self._get_scene_key(temp_exp)

        if scene_key in self.learned_preferences["controlnet_scales"]:
            learned = self.learned_preferences["controlnet_scales"][scene_key]
            if learned.get("avg_scales"):
                sample_count = len(learned["samples"])
                confidence = min(sample_count / 10.0, 1.0)
                return {
                    "controlnet_scales": learned["avg_scales"],
                    "guidance_scale": 7.5,
                    "reward_weight": 0.3,
                    "confidence": confidence,
                    "sample_count": sample_count,
                }

        return {
            "controlnet_scales": [0.6, 0.9, 0.4],
            "guidance_scale": 7.5,
            "reward_weight": 0.3,
            "confidence": 0.0,
            "sample_count": 0,
        }

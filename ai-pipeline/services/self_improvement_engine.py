"""
Self-Improvement Engine - The Learning Brain of PhotoGenius AI.

Orchestrates:
1. Experience collection from every generation
2. Pattern learning from successes and failures
3. Preference learning from multiple attempts
4. Auto-application of learned optimizations
5. Periodic fine-tuning (future: actual model fine-tuning)

Makes PhotoGenius AI smarter with every generation.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from .experience_memory import (
        ExperienceMemory,
        GenerationExperience,
        create_experience_id,
    )
    from .preference_learning import PreferenceLearning
except ImportError:
    from ai_pipeline.services.experience_memory import (
        ExperienceMemory,
        GenerationExperience,
        create_experience_id,
    )
    from ai_pipeline.services.preference_learning import PreferenceLearning

# Optional CLIP for embeddings
try:
    from transformers import CLIPModel, CLIPProcessor
    HAS_CLIP = True
except Exception:
    HAS_CLIP = False
    CLIPModel = None  # type: ignore
    CLIPProcessor = None  # type: ignore

EMBEDDING_DIM = 512


def _entity_type(e: Any) -> Optional[str]:
    """Get entity type from EntityNode or dict."""
    if hasattr(e, "type"):
        return getattr(e, "type", None)
    if isinstance(e, dict):
        return e.get("type")
    return None


def _entity_properties(e: Any) -> Dict[str, Any]:
    """Get entity properties from EntityNode or dict."""
    if hasattr(e, "properties"):
        return getattr(e, "properties", {}) or {}
    if isinstance(e, dict):
        return e.get("properties", {}) or {}
    return {}


class SelfImprovementEngine:
    """
    Self-improving intelligence layer.

    Wraps the refinement engine and learns from every generation.
    """

    def __init__(self, storage_dir: str = "data/self_improvement") -> None:
        self.memory = ExperienceMemory(storage_dir=f"{storage_dir}/memory")
        self.preference_learner = PreferenceLearning()
        self._clip_model = None
        self._clip_processor = None

        if HAS_CLIP and CLIPModel is not None and CLIPProcessor is not None:
            try:
                self._clip_model = CLIPModel.from_pretrained(
                    "openai/clip-vit-large-patch14"
                )
                self._clip_processor = CLIPProcessor.from_pretrained(
                    "openai/clip-vit-large-patch14"
                )
            except Exception:
                self._clip_model = None
                self._clip_processor = None

    def generate_with_learning(
        self,
        refinement_engine: Any,
        prompt: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate image while learning from the process.

        Steps:
        1. Check memory for similar past experiences
        2. Apply learned optimizations
        3. Generate with refinement engine
        4. Record experience
        5. Learn from result
        """
        prompt_embedding = self._embed_prompt(prompt)

        similar_experiences = self.memory.find_similar_experiences(
            prompt_embedding, k=5
        )

        if similar_experiences:
            for i, (exp, dist) in enumerate(similar_experiences[:3]):
                pass  # Optional: log

        failure_patterns = self.memory.get_failure_patterns_for_prompt(prompt)
        insights = self.memory.get_success_insights(prompt_embedding)
        optimizations = self._get_optimizations(prompt, insights)
        kwargs = {**optimizations.get("parameters", {}), **kwargs}

        result = refinement_engine.generate_perfect(prompt, **kwargs)

        scene_graph = result.get("scene_graph") or {}
        if not scene_graph and hasattr(refinement_engine, "scene_compiler"):
            try:
                scene_graph = refinement_engine.scene_compiler.compile(prompt)
            except Exception:
                scene_graph = {}

        experience = self._create_experience(
            prompt,
            prompt_embedding,
            result,
            scene_graph,
        )
        self.memory.add_experience(experience)
        self._learn_from_result(experience, similar_experiences)

        result["self_improvement"] = {
            "experience_id": experience.id,
            "similar_experiences": len(similar_experiences),
            "optimizations_applied": optimizations.get("applied", []),
            "failure_patterns_detected": len(failure_patterns),
            "memory_size": len(self.memory.experiences),
        }
        return result

    def _embed_prompt(self, prompt: str) -> np.ndarray:
        """Generate CLIP embedding for prompt, or zero vector if CLIP unavailable."""
        if self._clip_model is None or self._clip_processor is None:
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)
        try:
            import torch
            inputs = self._clip_processor(
                text=[prompt], return_tensors="pt", padding=True
            )
            with torch.no_grad():
                text_features = self._clip_model.get_text_features(**inputs)
            emb = text_features.cpu().numpy()[0]
            if len(emb) != EMBEDDING_DIM:
                out = np.zeros(EMBEDDING_DIM, dtype=np.float32)
                out[: min(len(emb), EMBEDDING_DIM)] = emb[: EMBEDDING_DIM]
                return out
            return emb.astype(np.float32)
        except Exception:
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)

    def _get_optimizations(self, prompt: str, insights: Dict[str, Any]) -> Dict[str, Any]:
        """Get learned optimizations to apply."""
        applied: List[str] = []
        parameters: Dict[str, Any] = {}

        success_rate = insights.get("success_rate", 0.0)
        similar_count = insights.get("similar_count", 0)
        if success_rate >= 0.7 and similar_count >= 5:
            scales = insights.get("best_controlnet_scales")
            if scales:
                parameters["controlnet_conditioning_scale"] = scales
                applied.append(
                    f"Learned ControlNet scales: {[f'{x:.2f}' for x in scales]}"
                )

        if insights.get("avg_iterations", 0) > 2.5:
            parameters["max_iterations"] = 4
            applied.append("Increased max iterations (complex prompt pattern)")

        return {"applied": applied, "parameters": parameters}

    def _create_experience(
        self,
        prompt: str,
        prompt_embedding: np.ndarray,
        result: Dict[str, Any],
        scene_graph: Dict[str, Any],
    ) -> GenerationExperience:
        """Create experience record from generation result."""
        exp_id = create_experience_id(prompt, datetime.utcnow().isoformat())

        quality = scene_graph.get("quality_requirements") or {}
        person_count = quality.get("person_count_exact", 0)
        scene_complexity = self._estimate_complexity(scene_graph)
        entities = scene_graph.get("entities", [])

        has_weather = any(
            _entity_type(e) == "weather" for e in entities
        )
        has_fantasy = any(
            _entity_type(e) in ("mythical_creature", "magical_object")
            for e in entities
        )

        iterations = result.get("iterations", [])
        final_iter = iterations[-1] if iterations else None
        if final_iter is None:
            val_scores = {}
            issues_types: List[str] = []
            fix_types: List[str] = []
        else:
            meta = getattr(final_iter, "metadata", {}) or {}
            val_scores = meta.get("model_scores", {}) or {}
            issues_found = getattr(final_iter, "issues_found", []) or []
            issues_types = [
                (i.get("type") if isinstance(i, dict) else getattr(i, "type", ""))
                for i in issues_found
            ]
            fixes_applied = getattr(final_iter, "fixes_applied", []) or []
            fix_types = [
                (f.get("fix_type") if isinstance(f, dict) else getattr(f, "fix_type", ""))
                for f in fixes_applied
            ]

        failure_pattern = None
        success_pattern = None
        if not result.get("success", False):
            failure_pattern = self._identify_failure_pattern(result, scene_graph)
        else:
            success_pattern = self._identify_success_pattern(result, scene_graph)

        meta = result.get("metadata") or {}
        controlnet_scales = meta.get("controlnet_scales") or [0.6, 0.9, 0.4]
        guidance_scale = meta.get("guidance_scale", 7.5)
        reward_weight = meta.get("reward_weight", 0.3)

        return GenerationExperience(
            id=exp_id,
            timestamp=datetime.utcnow().isoformat(),
            prompt=prompt,
            prompt_embedding=prompt_embedding,
            person_count=person_count,
            scene_complexity=scene_complexity,
            has_weather=has_weather,
            has_fantasy=has_fantasy,
            iterations_needed=result.get("total_iterations", 0),
            final_score=result.get("final_score", 0.0),
            success=result.get("success", False),
            validation_scores=val_scores,
            issues_encountered=issues_types,
            fixes_applied=fix_types,
            controlnet_scales=controlnet_scales,
            guidance_scale=guidance_scale,
            reward_weight=reward_weight,
            failure_pattern=failure_pattern,
            success_pattern=success_pattern,
        )

    def _estimate_complexity(self, scene_graph: Dict[str, Any]) -> float:
        """Estimate scene complexity (0.0-1.0)."""
        complexity = 0.0
        entities = scene_graph.get("entities", [])
        complexity += min(len(entities) / 10.0, 0.4)
        constraints = scene_graph.get("constraints", [])
        complexity += min(len(constraints) / 10.0, 0.3)
        if any(_entity_type(e) == "weather" for e in entities):
            complexity += 0.15
        if any(
            _entity_type(e) in ("mythical_creature", "magical_object")
            for e in entities
        ):
            complexity += 0.15
        return min(complexity, 1.0)

    def _identify_failure_pattern(
        self, result: Dict[str, Any], scene_graph: Dict[str, Any]
    ) -> Optional[str]:
        """Identify what pattern caused failure."""
        iterations = result.get("iterations", [])
        if not iterations:
            return None
        final_iter = iterations[-1]
        issues_found = getattr(final_iter, "issues_found", []) or []
        issue_types = [
            (i.get("type") if isinstance(i, dict) else getattr(i, "type", ""))
            for i in issues_found
        ]
        if "face_count" in issue_types:
            entities = scene_graph.get("entities", [])
            if any(
                _entity_properties(e).get("name") == "umbrella"
                for e in entities
            ):
                return "umbrella_rain_occlusion"
        quality = scene_graph.get("quality_requirements") or {}
        person_count = quality.get("person_count_exact", 0)
        if person_count >= 4:
            return f"multi_person_{person_count}_plus"
        return None

    def _identify_success_pattern(
        self, result: Dict[str, Any], scene_graph: Dict[str, Any]
    ) -> Optional[str]:
        """Identify what made this succeed."""
        quality = scene_graph.get("quality_requirements") or {}
        person_count = quality.get("person_count_exact", 0)
        if person_count >= 3:
            return f"multi_person_success_{person_count}"
        return "standard_success"

    def _learn_from_result(
        self,
        experience: GenerationExperience,
        similar_experiences: List[Tuple[GenerationExperience, float]],
    ) -> None:
        """Learn from generation result via preference pairs."""
        for similar_exp, distance in similar_experiences:
            if distance >= 100:
                continue
            if experience.final_score > similar_exp.final_score:
                self.preference_learner.add_preference_pair(
                    experience, similar_exp
                )
            elif similar_exp.final_score > experience.final_score:
                self.preference_learner.add_preference_pair(
                    similar_exp, experience
                )

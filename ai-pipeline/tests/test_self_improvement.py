"""
Tests for self-improvement components: ExperienceMemory, PreferenceLearning, SelfImprovementEngine.
"""

import pytest
import numpy as np
from datetime import datetime

try:
    from services.experience_memory import ExperienceMemory, GenerationExperience
    from services.preference_learning import PreferenceLearning
    from services.self_improvement_engine import SelfImprovementEngine
except ImportError:
    from ai_pipeline.services.experience_memory import ExperienceMemory, GenerationExperience
    from ai_pipeline.services.preference_learning import PreferenceLearning
    from ai_pipeline.services.self_improvement_engine import SelfImprovementEngine


def _make_experience(
    exp_id: str,
    prompt: str = "Test prompt",
    embedding: np.ndarray = None,
    person_count: int = 2,
    final_score: float = 0.85,
    success: bool = True,
    controlnet_scales=None,
) -> GenerationExperience:
    if embedding is None:
        embedding = np.random.rand(512).astype("float32")
    if controlnet_scales is None:
        controlnet_scales = [0.6, 0.9, 0.4]
    return GenerationExperience(
        id=exp_id,
        timestamp=datetime.utcnow().isoformat(),
        prompt=prompt,
        prompt_embedding=embedding,
        person_count=person_count,
        scene_complexity=0.5,
        has_weather=False,
        has_fantasy=False,
        iterations_needed=2,
        final_score=final_score,
        success=success,
        validation_scores={"anatomy": 0.9, "physics": 0.8},
        issues_encountered=[],
        fixes_applied=[],
        controlnet_scales=controlnet_scales,
        guidance_scale=7.5,
        reward_weight=0.3,
    )


class TestExperienceMemory:
    """Test experience memory system."""

    def test_memory_initialization(self, tmp_path):
        """Test memory initializes."""
        memory = ExperienceMemory(storage_dir=str(tmp_path / "test_memory"))
        assert len(memory.experiences) == 0
        # Index may be None when FAISS is not installed (numpy fallback)
        assert getattr(memory, "experiences", None) is not None

    def test_add_and_retrieve_experience(self, tmp_path):
        """Test adding and retrieving experiences."""
        memory = ExperienceMemory(storage_dir=str(tmp_path / "test_memory"))
        exp = _make_experience("test_001", final_score=0.85, success=True)
        memory.add_experience(exp)
        assert len(memory.experiences) == 1
        assert memory.experiences[0].id == "test_001"

    def test_find_similar_experiences(self, tmp_path):
        """Test similarity search."""
        memory = ExperienceMemory(storage_dir=str(tmp_path / "test_memory"))
        base_embedding = np.random.rand(512).astype("float32")

        for i in range(5):
            embedding = base_embedding + np.random.rand(512).astype("float32") * 0.1
            exp = _make_experience(
                f"test_{i:03d}",
                prompt=f"Test prompt {i}",
                embedding=embedding,
                final_score=0.8 + i * 0.02,
            )
            memory.add_experience(exp)

        similar = memory.find_similar_experiences(base_embedding, k=3)
        assert len(similar) >= 1
        assert len(similar) <= 3

    def test_get_statistics(self, tmp_path):
        """Test memory statistics."""
        memory = ExperienceMemory(storage_dir=str(tmp_path / "test_memory"))
        memory.add_experience(_make_experience("s1", final_score=0.9))
        memory.add_experience(_make_experience("s2", final_score=0.7))
        stats = memory.get_statistics()
        assert stats["total_experiences"] == 2
        assert 0 <= stats["success_rate"] <= 1
        assert 0 <= stats["avg_score"] <= 1


class TestPreferenceLearning:
    """Test preference learning."""

    def test_preference_learning_init(self):
        """Test preference learner initializes."""
        learner = PreferenceLearning()
        assert learner.preference_pairs == []
        assert "controlnet_scales" in learner.learned_preferences

    def test_add_preference_pair(self):
        """Test adding preference pairs."""
        learner = PreferenceLearning()
        better = _make_experience(
            "better",
            final_score=0.90,
            success=True,
            controlnet_scales=[0.7, 0.95, 0.5],
        )
        worse = _make_experience(
            "worse",
            final_score=0.70,
            success=False,
        )
        learner.add_preference_pair(better, worse)
        # Score diff 0.20 >= 0.05 so pair is added
        assert len(learner.preference_pairs) >= 1

    def test_get_recommended_parameters(self):
        """Test getting recommended parameters from learned preferences."""
        learner = PreferenceLearning()
        better = _make_experience(
            "b",
            person_count=2,
            final_score=0.92,
            controlnet_scales=[0.65, 0.92, 0.45],
        )
        worse = _make_experience("w", person_count=2, final_score=0.65)
        learner.add_preference_pair(better, worse)
        params = learner.get_recommended_parameters(
            person_count=2,
            scene_complexity=0.5,
            has_weather=False,
            has_fantasy=False,
        )
        assert "controlnet_scales" in params
        assert "confidence" in params
        assert "guidance_scale" in params
        assert params["sample_count"] >= 1


class TestSelfImprovementEngine:
    """Test self-improvement engine."""

    def test_engine_initialization(self, tmp_path):
        """Test engine initializes (no CLIP required)."""
        engine = SelfImprovementEngine(storage_dir=str(tmp_path / "test_si"))
        assert engine.memory is not None
        assert engine.preference_learner is not None

    def test_generate_with_learning_mock(self, tmp_path):
        """Test generate_with_learning with mock refinement engine."""
        engine = SelfImprovementEngine(storage_dir=str(tmp_path / "test_si"))

        class MockRefinement:
            def generate_perfect(self, prompt, **kwargs):
                return {
                    "image": None,
                    "iterations": [],
                    "final_score": 0.75,
                    "total_iterations": 1,
                    "success": False,
                    "scene_graph": {
                        "quality_requirements": {"person_count_exact": 1},
                        "entities": [],
                        "constraints": [],
                    },
                    "metadata": {},
                }

        result = engine.generate_with_learning(
            MockRefinement(), "One person standing"
        )
        assert "self_improvement" in result
        assert "experience_id" in result["self_improvement"]
        assert result["self_improvement"]["memory_size"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:asyncio"])

"""
Experience Memory System - Stores generation history for learning.

Stores:
1. Successful generations (prompt patterns that work)
2. Failed generations (what went wrong and how it was fixed)
3. Preference rankings (which variations are better)
4. Edge cases (unusual prompts and their solutions)

Uses FAISS for efficient similarity search when available; falls back to numpy L2.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import dataclasses
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np  # type: ignore[reportMissingImports]

try:
    import faiss  # type: ignore[reportMissingImports]

    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


@dataclass
class GenerationExperience:
    """Single generation experience record."""

    id: str
    timestamp: str
    prompt: str
    prompt_embedding: np.ndarray

    # Scene information
    person_count: int
    scene_complexity: float  # 0.0-1.0
    has_weather: bool
    has_fantasy: bool

    # Generation results
    iterations_needed: int
    final_score: float
    success: bool

    # Validation details
    validation_scores: Dict[str, float]
    issues_encountered: List[str]
    fixes_applied: List[str]

    # What worked / didn't work
    controlnet_scales: List[float]
    guidance_scale: float
    reward_weight: float

    # Learnings
    failure_pattern: Optional[str] = None
    success_pattern: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        data = asdict(self)
        emb = data["prompt_embedding"]
        data["prompt_embedding"] = emb.tolist() if hasattr(emb, "tolist") else list(emb)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationExperience":
        """Reconstruct from dict."""
        data = dict(data)
        emb = data.get("prompt_embedding")
        if emb is not None and not isinstance(emb, np.ndarray):
            data["prompt_embedding"] = np.array(emb, dtype=np.float32)
        # Drop any extra keys not in dataclass
        field_names = {f.name for f in dataclasses.fields(cls)}
        data = {k: v for k, v in data.items() if k in field_names}
        return cls(**data)


def _default_embedding(dim: int = 512) -> np.ndarray:
    """Return zero embedding when no encoder available."""
    return np.zeros(dim, dtype=np.float32)


class ExperienceMemory:
    """
    Memory system for storing and retrieving generation experiences.

    Features:
    - Fast similarity search via FAISS (or numpy fallback)
    - Persistent storage (disk)
    - Pattern extraction
    - Success/failure analysis
    """

    EMBEDDING_DIM = 512

    def __init__(self, storage_dir: str = "data/experience_memory") -> None:
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        self.embedding_dim = self.EMBEDDING_DIM
        self.experiences: List[GenerationExperience] = []
        self.id_to_index: Dict[str, int] = {}
        self.failure_patterns: Dict[str, List[str]] = {}
        self.success_patterns: Dict[str, List[str]] = {}

        if HAS_FAISS:
            self.index = faiss.IndexFlatL2(self.embedding_dim)
            self._use_faiss = True
        else:
            self.index = None
            self._use_faiss = False

        self._load_from_disk()
        # Optional: print(f"Experience Memory initialized: {len(self.experiences)} experiences loaded")

    def add_experience(self, experience: GenerationExperience) -> None:
        """Add new generation experience to memory."""
        self.experiences.append(experience)
        idx = len(self.experiences) - 1
        self.id_to_index[experience.id] = idx

        embedding = np.asarray(experience.prompt_embedding, dtype=np.float32).flatten()
        if len(embedding) != self.embedding_dim:
            pad = np.zeros(self.embedding_dim, dtype=np.float32)
            pad[: min(len(embedding), self.embedding_dim)] = embedding[
                : self.embedding_dim
            ]
            embedding = pad
        if self._use_faiss and self.index is not None:
            self.index.add(embedding.reshape(1, -1))

        if experience.failure_pattern:
            self.failure_patterns.setdefault(experience.failure_pattern, []).append(
                experience.id
            )
        if experience.success_pattern:
            self.success_patterns.setdefault(experience.success_pattern, []).append(
                experience.id
            )

        if len(self.experiences) % 10 == 0:
            self._save_to_disk()

    def find_similar_experiences(
        self,
        prompt_embedding: np.ndarray,
        k: int = 5,
        min_score: Optional[float] = None,
    ) -> List[Tuple[GenerationExperience, float]]:
        """Find similar past experiences via embedding similarity."""
        if len(self.experiences) == 0:
            return []

        k = min(k, len(self.experiences))
        embedding = np.asarray(prompt_embedding, dtype=np.float32).reshape(1, -1)
        if embedding.shape[1] != self.embedding_dim:
            emb = np.zeros((1, self.embedding_dim), dtype=np.float32)
            emb[0, : min(embedding.shape[1], self.embedding_dim)] = embedding[
                0, : min(embedding.shape[1], self.embedding_dim)
            ]
            embedding = emb

        if self._use_faiss and self.index is not None:
            distances, indices = self.index.search(embedding, k)
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if 0 <= idx < len(self.experiences):
                    exp = self.experiences[idx]
                    if min_score is None or exp.final_score >= min_score:
                        results.append((exp, float(dist)))
            return results

        # Numpy fallback: L2 distance to all
        emb_list = []
        for e in self.experiences:
            emb = np.asarray(e.prompt_embedding, dtype=np.float32).flatten()
            if len(emb) != self.embedding_dim:
                pad = np.zeros(self.embedding_dim, dtype=np.float32)
                pad[: min(len(emb), self.embedding_dim)] = emb[: self.embedding_dim]
                emb = pad
            emb_list.append(emb)
        all_embeddings = np.array(emb_list, dtype=np.float32)
        q = embedding.flatten()
        if len(q) != self.embedding_dim:
            qq = np.zeros(self.embedding_dim, dtype=np.float32)
            qq[: min(len(q), self.embedding_dim)] = q[: self.embedding_dim]
            q = qq
        dists = np.linalg.norm(all_embeddings - q, axis=1)
        order = np.argsort(dists)[:k]
        results = []
        for idx in order:
            exp = self.experiences[idx]
            if min_score is None or exp.final_score >= min_score:
                results.append((exp, float(dists[idx])))
        return results

    def get_failure_patterns_for_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        """Get known failure patterns for similar prompts."""
        patterns: List[Dict[str, Any]] = []
        prompt_lower = prompt.lower()

        if "umbrella" in prompt_lower and "rain" in prompt_lower:
            pattern_key = "umbrella_rain_occlusion"
            if pattern_key in self.failure_patterns:
                exp_ids = self.failure_patterns[pattern_key]
                example_fixes = self._get_fixes_for_experiences(exp_ids[:3])
                patterns.append(
                    {
                        "pattern": pattern_key,
                        "count": len(exp_ids),
                        "example_fixes": example_fixes,
                        "severity": "high",
                    }
                )

        person_match = re.search(r"(\d+)\s+(people|children|kids|family)", prompt_lower)
        if person_match:
            count = int(person_match.group(1))
            if count >= 4:
                pattern_key = f"multi_person_{count}_plus"
                if pattern_key in self.failure_patterns:
                    exp_ids = self.failure_patterns[pattern_key]
                    example_fixes = self._get_fixes_for_experiences(exp_ids[:3])
                    patterns.append(
                        {
                            "pattern": pattern_key,
                            "count": len(exp_ids),
                            "example_fixes": example_fixes,
                            "severity": "high" if count >= 5 else "medium",
                        }
                    )

        return patterns

    def get_success_insights(self, prompt_embedding: np.ndarray) -> Dict[str, Any]:
        """Get insights from similar successful generations."""
        similar = self.find_similar_experiences(prompt_embedding, k=20, min_score=0.85)
        default = {
            "avg_iterations": 2.5,
            "best_controlnet_scales": [0.6, 0.9, 0.4],
            "best_guidance_scale": 7.5,
            "success_rate": 0.0,
        }
        if not similar:
            return default

        successful = [(exp, d) for exp, d in similar if exp.success]
        if not successful:
            return {
                **default,
                "success_rate": 0.0,
                "similar_count": len(similar),
            }

        avg_iterations = float(
            np.mean([exp.iterations_needed for exp, _ in successful])
        )
        scales_arr = np.array([exp.controlnet_scales for exp, _ in successful])
        best_scales = np.mean(scales_arr, axis=0).tolist()
        best_guidance = float(np.mean([exp.guidance_scale for exp, _ in successful]))
        success_rate = len(successful) / len(similar)

        return {
            "avg_iterations": avg_iterations,
            "best_controlnet_scales": best_scales,
            "best_guidance_scale": best_guidance,
            "success_rate": success_rate,
            "similar_count": len(similar),
        }

    def _rebuild_faiss_index(self) -> None:
        """Rebuild FAISS index from current experiences."""
        if not self._use_faiss or not self.experiences:
            return
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        for exp in self.experiences:
            emb = np.asarray(exp.prompt_embedding, dtype=np.float32).flatten()
            if len(emb) != self.embedding_dim:
                pad = np.zeros(self.embedding_dim, dtype=np.float32)
                pad[: min(len(emb), self.embedding_dim)] = emb[: self.embedding_dim]
                emb = pad
            self.index.add(emb.reshape(1, -1))

    def _get_fixes_for_experiences(self, exp_ids: List[str]) -> List[str]:
        """Get list of fixes applied in given experiences."""
        fixes: set = set()
        for exp_id in exp_ids:
            if exp_id in self.id_to_index:
                exp = self.experiences[self.id_to_index[exp_id]]
                fixes.update(exp.fixes_applied)
        return list(fixes)

    def _save_to_disk(self) -> None:
        """Save memory to disk."""
        experiences_data = [exp.to_dict() for exp in self.experiences]
        exp_path = os.path.join(self.storage_dir, "experiences.json")
        with open(exp_path, "w") as f:
            json.dump(experiences_data, f, indent=2)

        if self._use_faiss and self.index is not None:
            index_path = os.path.join(self.storage_dir, "embeddings.index")
            faiss.write_index(self.index, index_path)

        pattern_path = os.path.join(self.storage_dir, "patterns.json")
        with open(pattern_path, "w") as f:
            json.dump(
                {
                    "failure_patterns": self.failure_patterns,
                    "success_patterns": self.success_patterns,
                },
                f,
                indent=2,
            )

    def _load_from_disk(self) -> None:
        """Load memory from disk."""
        exp_path = os.path.join(self.storage_dir, "experiences.json")
        index_path = os.path.join(self.storage_dir, "embeddings.index")
        pattern_path = os.path.join(self.storage_dir, "patterns.json")

        if os.path.exists(exp_path):
            with open(exp_path, "r") as f:
                experiences_data = json.load(f)
            self.experiences = [
                GenerationExperience.from_dict(d) for d in experiences_data
            ]
            self.id_to_index = {exp.id: i for i, exp in enumerate(self.experiences)}

        if self._use_faiss:
            if os.path.exists(index_path) and len(self.experiences) > 0:
                try:
                    self.index = faiss.read_index(index_path)
                except Exception:
                    self._rebuild_faiss_index()
            else:
                self.index = faiss.IndexFlatL2(self.embedding_dim)
                if len(self.experiences) > 0:
                    self._rebuild_faiss_index()

        if os.path.exists(pattern_path):
            with open(pattern_path, "r") as f:
                data = json.load(f)
                self.failure_patterns = data.get("failure_patterns", {})
                self.success_patterns = data.get("success_patterns", {})

    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        if not self.experiences:
            return {
                "total_experiences": 0,
                "success_rate": 0.0,
                "avg_score": 0.0,
                "avg_iterations": 0.0,
                "failure_patterns_known": 0,
                "success_patterns_known": 0,
            }
        successes = sum(1 for exp in self.experiences if exp.success)
        avg_score = float(np.mean([exp.final_score for exp in self.experiences]))
        avg_iters = float(np.mean([exp.iterations_needed for exp in self.experiences]))
        return {
            "total_experiences": len(self.experiences),
            "success_rate": successes / len(self.experiences),
            "avg_score": avg_score,
            "avg_iterations": avg_iters,
            "failure_patterns_known": len(self.failure_patterns),
            "success_patterns_known": len(self.success_patterns),
        }


def create_experience_id(prompt: str, timestamp: Optional[str] = None) -> str:
    """Create a unique ID for an experience record."""
    ts = timestamp or datetime.utcnow().isoformat()
    raw = f"{prompt}|{ts}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

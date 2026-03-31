"""
Reward Aggregator for RLHF / DDPO-style continuous improvement.
Aggregates anatomy + aesthetics + surprise; PPO fine-tuning loop placeholder; FAISS memory for failure patterns.
P0: Task 6 — +20% reward scores after 1000 generations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from .guided_diffusion_controlnet import RewardModel
except ImportError:
    RewardModel = None


@dataclass
class AggregatedReward:
    """Single aggregated reward from anatomy, physics, aesthetics, constraint, surprise."""

    total: float  # 0–1 weighted sum
    anatomy: float
    physics: float
    aesthetics: float
    constraint_satisfaction: float
    surprise: float
    weights: Dict[str, float] = field(default_factory=dict)


DEFAULT_WEIGHTS = {
    "anatomy": 0.3,
    "physics": 0.2,
    "aesthetics": 0.2,
    "constraint_satisfaction": 0.2,
    "surprise": 0.1,
}


class RewardAggregator:
    """
    Aggregate multi-objective rewards for RL fine-tuning.
    Generation → Self-Evaluation → RL Fine-Tuning → Memory Storage → Enhanced Logic.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        self.history: List[AggregatedReward] = []
        self._max_history = 10_000

    def aggregate(self, rewards: Dict[str, float]) -> AggregatedReward:
        """Compute weighted total from reward dict (anatomy, physics, aesthetics, constraint_satisfaction, surprise)."""
        total = 0.0
        components: Dict[str, float] = {}
        for key, w in self.weights.items():
            v = rewards.get(key, 0.5)
            components[key] = v
            total += w * v
        agg = AggregatedReward(
            total=min(1.0, total),
            anatomy=components.get("anatomy", 0.5),
            physics=components.get("physics", 0.5),
            aesthetics=components.get("aesthetics", 0.5),
            constraint_satisfaction=components.get("constraint_satisfaction", 0.5),
            surprise=components.get("surprise", 0.5),
            weights=dict(self.weights),
        )
        self.history.append(agg)
        if len(self.history) > self._max_history:
            self.history = self.history[-self._max_history :]
        return agg

    def average_reward_over_last(self, n: int = 100) -> float:
        """Average total reward over last n entries (for +20% metric)."""
        if not self.history or n <= 0:
            return 0.0
        recent = self.history[-n:]
        return sum(a.total for a in recent) / len(recent)

    def improvement_since(self, n_ago: int = 1000) -> Optional[float]:
        """Return (current_avg - past_avg) / past_avg when past_avg > 0 (e.g. +0.2 = +20%)."""
        if len(self.history) < 2 * n_ago:
            return None
        past = self.history[-2 * n_ago : -n_ago]
        current = self.history[-n_ago:]
        if not past or not current:
            return None
        past_avg = sum(a.total for a in past) / len(past)
        current_avg = sum(a.total for a in current) / len(current)
        if past_avg <= 0:
            return None
        return (current_avg - past_avg) / past_avg


# PPO fine-tuning loop: placeholder (real impl would use diffusers/trl or custom DDPO)
def ppo_fine_tuning_step(
    model: Any,
    rewards_batch: List[Dict[str, float]],
    learning_rate: float = 1e-5,
) -> Dict[str, float]:
    """Placeholder: one PPO/DDPO fine-tuning step. Returns loss dict."""
    if not rewards_batch:
        return {"loss": 0.0, "reward_mean": 0.0}
    agg = RewardAggregator()
    totals = [agg.aggregate(r).total for r in rewards_batch]
    return {"loss": 0.0, "reward_mean": sum(totals) / len(totals)}


# FAISS memory for failure patterns: placeholder (real impl would use faiss + embeddings)
class FailureMemory:
    """Store failure patterns for retrieval; placeholder without FAISS."""

    def __init__(self, max_size: int = 5000):
        self.max_size = max_size
        self.entries: List[Dict[str, Any]] = []

    def add(
        self,
        prompt: str,
        failed_rules: List[str],
        consensus: Any,
        context: Optional[Dict] = None,
    ) -> None:
        self.entries.append(
            {
                "prompt": prompt,
                "failed_rules": failed_rules,
                "consensus": consensus,
                "context": context or {},
            }
        )
        if len(self.entries) > self.max_size:
            self.entries = self.entries[-self.max_size :]

    def search_similar(self, prompt: str, k: int = 5) -> List[Dict[str, Any]]:
        """Placeholder: return last k entries; real impl would use FAISS + prompt embeddings."""
        return self.entries[-k:] if self.entries else []

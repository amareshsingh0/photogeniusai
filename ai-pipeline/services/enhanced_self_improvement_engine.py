"""
Enhanced Self-Improvement Engine
=================================
Extends the base SelfImprovementEngine (RLHF-style + FAISS memory)
with **per-category** performance tracking and automatic parameter tuning.

Every time an image is generated and validated, we log:
    - category, sub_category, style, medium
    - final_score
    - which parameters (strength, iterations, negative prompt tweaks) were used
    - whether the generation needed refinement iterations

Over time the engine learns:
    - Optimal img2img strength per category
    - Best iteration count per category
    - Which negative prompt tokens actually improve scores
    - Which style tokens correlate with higher validator scores

This data is stored in DynamoDB (production) or a local JSON file (dev).
"""

from __future__ import annotations

import json
import os
import statistics
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class GenerationRecord:
    """One completed generation event — everything we learned from it."""

    job_id: str
    timestamp: float
    category: str
    sub_category: str
    style: str
    medium: str
    tier: str  # standard / premium / perfect
    final_score: float  # tri-model validation score 0-1
    iterations_used: int
    max_iterations: int
    parameters: Dict[str, Any]  # the full set of params that were used
    negative_prompt_tokens: List[str]  # which tokens were in the neg prompt
    positive_prompt_tokens: List[str]  # which tokens were in the pos prompt
    had_refinement: bool  # did iterative refinement kick in?
    refinement_delta: float = 0.0  # how much refinement improved the score


@dataclass
class CategoryStats:
    """Running statistics for one category."""

    category: str
    total_generations: int = 0
    scores: List[float] = field(default_factory=list)
    avg_score: float = 0.0
    median_score: float = 0.0
    avg_iterations: float = 0.0
    refinement_rate: float = 0.0  # fraction that needed refinement
    best_parameters: Dict[str, Any] = field(default_factory=dict)
    worst_parameters: Dict[str, Any] = field(default_factory=dict)
    # Token effectiveness: token → (times_used, sum_of_scores_when_used)
    token_effectiveness: Dict[str, Tuple[int, float]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Storage adapter  (DynamoDB in prod, local JSON in dev)
# ---------------------------------------------------------------------------


class LocalStorageAdapter:
    """Dev-mode storage: reads/writes a single JSON file."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or os.path.join(
            tempfile.gettempdir(), "photogenius_learning.json"
        )
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        except OSError:
            pass
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def save_record(self, record: GenerationRecord) -> None:
        records = self._data.setdefault("records", [])
        records.append(
            {
                "job_id": record.job_id,
                "timestamp": record.timestamp,
                "category": record.category,
                "sub_category": record.sub_category,
                "style": record.style,
                "medium": record.medium,
                "tier": record.tier,
                "final_score": record.final_score,
                "iterations_used": record.iterations_used,
                "max_iterations": record.max_iterations,
                "parameters": record.parameters,
                "negative_prompt_tokens": record.negative_prompt_tokens,
                "positive_prompt_tokens": record.positive_prompt_tokens,
                "had_refinement": record.had_refinement,
                "refinement_delta": record.refinement_delta,
            }
        )
        self._save()

    def get_records_for_category(self, category: str, limit: int = 200) -> List[Dict]:
        records = self._data.get("records", [])
        filtered = [r for r in records if r.get("category") == category]
        return filtered[-limit:]  # most recent

    def get_all_category_names(self) -> List[str]:
        records = self._data.get("records", [])
        return list({r["category"] for r in records if r.get("category")})


class DynamoDBStorageAdapter:
    """
    Production storage via boto3 DynamoDB.
    Assumes table 'PhotoGenius-Learning' with partition key 'job_id'
    and GSI 'category-timestamp-index'.
    """

    def __init__(self, table_name: str = "PhotoGenius-Learning") -> None:
        try:
            import boto3

            self.dynamodb = boto3.resource("dynamodb")
            self.table = self.dynamodb.Table(table_name)  # type: ignore[reportAttributeAccessIssue]
        except Exception as e:
            raise RuntimeError(
                "DynamoDBStorageAdapter requires boto3 and AWS credentials"
            ) from e

    def save_record(self, record: GenerationRecord) -> None:
        self.table.put_item(
            Item={
                "job_id": record.job_id,
                "timestamp": str(record.timestamp),
                "category": record.category,
                "sub_category": record.sub_category,
                "style": record.style,
                "medium": record.medium,
                "tier": record.tier,
                "final_score": record.final_score,
                "iterations_used": record.iterations_used,
                "max_iterations": record.max_iterations,
                "parameters": json.dumps(record.parameters),
                "negative_prompt_tokens": record.negative_prompt_tokens,
                "positive_prompt_tokens": record.positive_prompt_tokens,
                "had_refinement": record.had_refinement,
                "refinement_delta": record.refinement_delta,
            }
        )

    def get_records_for_category(self, category: str, limit: int = 200) -> List[Dict]:
        from boto3.dynamodb.conditions import Key

        resp = self.table.query(
            IndexName="category-timestamp-index",
            KeyConditionExpression=Key("category").eq(category),
            ScanIndexForward=False,
            Limit=limit,
        )
        items = resp.get("Items", [])
        # Normalize: parameters may be JSON string
        out = []
        for item in items:
            r = dict(item)
            if "parameters" in r and isinstance(r["parameters"], str):
                try:
                    r["parameters"] = json.loads(r["parameters"])
                except json.JSONDecodeError:
                    r["parameters"] = {}
            if "final_score" in r and not isinstance(r["final_score"], (int, float)):
                try:
                    r["final_score"] = float(r["final_score"])
                except (TypeError, ValueError):
                    r["final_score"] = 0.0
            if "refinement_delta" in r and not isinstance(
                r["refinement_delta"], (int, float)
            ):
                try:
                    r["refinement_delta"] = float(r["refinement_delta"])
                except (TypeError, ValueError):
                    r["refinement_delta"] = 0.0
            out.append(r)
        return out

    def get_all_category_names(self) -> List[str]:
        resp = self.table.scan(ProjectionExpression="category")
        return list({item["category"] for item in resp.get("Items", [])})


# ---------------------------------------------------------------------------
# Enhanced Self-Improvement Engine
# ---------------------------------------------------------------------------


class EnhancedSelfImprovementEngine:
    """
    Learns from every generation to make future ones better.

    Responsibilities:
        1. Log every completed generation
        2. Compute running stats per category
        3. Recommend optimal parameters for a new generation based on history
        4. Identify which prompt tokens actually help vs. hurt scores
    """

    def __init__(
        self,
        storage: Optional[Any] = None,
        use_dynamo: bool = False,
        storage_path: Optional[str] = None,
    ) -> None:
        if storage is not None:
            self.storage = storage
        elif use_dynamo:
            self.storage = DynamoDBStorageAdapter()
        else:
            self.storage = LocalStorageAdapter(path=storage_path)

        self._category_stats_cache: Dict[str, CategoryStats] = {}
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 300.0  # 5 minutes

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_generation(
        self,
        job_id: str,
        category: str,
        sub_category: str,
        style: str,
        medium: str,
        tier: str,
        final_score: float,
        iterations_used: int,
        max_iterations: int,
        parameters: Dict[str, Any],
        positive_tokens: List[str],
        negative_tokens: List[str],
        had_refinement: bool = False,
        refinement_delta: float = 0.0,
    ) -> None:
        """Call this after every successful (or attempted) generation."""
        record = GenerationRecord(
            job_id=job_id,
            timestamp=time.time(),
            category=category,
            sub_category=sub_category,
            style=style,
            medium=medium,
            tier=tier,
            final_score=float(final_score),
            iterations_used=int(iterations_used),
            max_iterations=int(max_iterations),
            parameters=dict(parameters),
            negative_prompt_tokens=list(negative_tokens),
            positive_prompt_tokens=list(positive_tokens),
            had_refinement=bool(had_refinement),
            refinement_delta=float(refinement_delta),
        )
        self.storage.save_record(record)
        self._cache_timestamp = 0.0

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_category_stats(self, category: str) -> CategoryStats:
        """Compute (or return cached) stats for a category."""
        self._refresh_cache_if_needed()
        return self._category_stats_cache.get(
            category, CategoryStats(category=category)
        )

    def get_all_stats(self) -> Dict[str, CategoryStats]:
        """All categories with data."""
        self._refresh_cache_if_needed()
        return dict(self._category_stats_cache)

    def _refresh_cache_if_needed(self) -> None:
        now = time.time()
        if now - self._cache_timestamp < self._cache_ttl:
            return
        categories = self.storage.get_all_category_names()
        new_cache: Dict[str, CategoryStats] = {}
        for cat in categories:
            records = self.storage.get_records_for_category(cat)
            new_cache[cat] = self._compute_stats(cat, records)
        self._category_stats_cache = new_cache
        self._cache_timestamp = now

    def _compute_stats(self, category: str, records: List[Dict]) -> CategoryStats:
        if not records:
            return CategoryStats(category=category)

        def _float(r: Dict, key: str, default: float = 0.0) -> float:
            v = r.get(key, default)
            if isinstance(v, (int, float)):
                return float(v)
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        scores = [_float(r, "final_score") for r in records]
        iterations_list = [int(r.get("iterations_used", 1)) for r in records]
        refinement_flags = [bool(r.get("had_refinement", False)) for r in records]

        token_eff: Dict[str, List[float]] = defaultdict(list)
        for r in records:
            score = _float(r, "final_score")
            for t in r.get("positive_prompt_tokens", []):
                if t:
                    token_eff[str(t)].append(score)
            for t in r.get("negative_prompt_tokens", []):
                if t:
                    token_eff[f"NEG:{t}"].append(score)

        best_rec = max(records, key=lambda r: _float(r, "final_score"))
        worst_rec = min(records, key=lambda r: _float(r, "final_score"))

        def _params(rec: Dict) -> Dict[str, Any]:
            p = rec.get("parameters", {})
            if isinstance(p, str):
                try:
                    return json.loads(p)
                except json.JSONDecodeError:
                    return {}
            return dict(p) if p else {}

        best_params = _params(best_rec)
        worst_params = _params(worst_rec)

        return CategoryStats(
            category=category,
            total_generations=len(records),
            scores=scores,
            avg_score=statistics.mean(scores),
            median_score=statistics.median(scores),
            avg_iterations=statistics.mean(iterations_list),
            refinement_rate=sum(refinement_flags) / len(refinement_flags),
            best_parameters=best_params,
            worst_parameters=worst_params,
            token_effectiveness={
                token: (len(s_list), sum(s_list)) for token, s_list in token_eff.items()
            },
        )

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def recommend_parameters(
        self, category: str, style: str, tier: str
    ) -> Dict[str, Any]:
        """
        Given a category + style + tier, return recommended generation parameters
        based on what worked best historically. Falls back to defaults when no history.
        """
        stats = self.get_category_stats(category)
        if stats.total_generations == 0:
            return self._default_parameters(category, style, tier)

        params = dict(stats.best_parameters)
        if tier == "standard":
            params["max_iterations"] = max(1, min(params.get("max_iterations", 2), 2))
            params["cfg_scale"] = params.get("cfg_scale", 7.5)
        elif tier == "premium":
            params["max_iterations"] = max(2, min(params.get("max_iterations", 3), 3))
            params["cfg_scale"] = params.get("cfg_scale", 8.0)
        elif tier == "perfect":
            params["max_iterations"] = max(3, min(params.get("max_iterations", 5), 5))
            params["cfg_scale"] = params.get("cfg_scale", 9.0)

        if stats.refinement_rate > 0.5:
            params["max_iterations"] = params.get("max_iterations", 3) + 1
        return params

    def get_effective_tokens(
        self, category: str, top_n: int = 10
    ) -> Tuple[List[str], List[str]]:
        """
        Return (best_positive_tokens, best_negative_tokens) for a category
        based on correlation with high scores.
        """
        stats = self.get_category_stats(category)
        if stats.total_generations == 0:
            return [], []

        cat_avg = stats.avg_score
        pos_tokens: List[Tuple[str, float]] = []
        neg_tokens: List[Tuple[str, float]] = []

        for token, (count, score_sum) in stats.token_effectiveness.items():
            if count < 3:
                continue
            token_avg = score_sum / count
            if token.startswith("NEG:"):
                neg_tokens.append((token[4:], token_avg))
            else:
                pos_tokens.append((token, token_avg))

        pos_tokens.sort(key=lambda x: x[1], reverse=True)
        neg_tokens.sort(key=lambda x: x[1], reverse=True)
        return (
            [t for t, _ in pos_tokens[:top_n]],
            [t for t, _ in neg_tokens[:top_n]],
        )

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    @staticmethod
    def _default_parameters(category: str, style: str, tier: str) -> Dict[str, Any]:
        """Sensible defaults when we have no history for a category."""
        base: Dict[str, Any] = {
            "guidance_scale": 7.5,
            "num_inference_steps": 50,
            "img2img_strength": 0.65,
            "denoising_strength": 0.75,
        }
        category_defaults: Dict[str, Dict[str, Any]] = {
            "portrait": {
                "guidance_scale": 7.0,
                "num_inference_steps": 60,
                "img2img_strength": 0.6,
            },
            "landscape": {
                "guidance_scale": 8.0,
                "num_inference_steps": 55,
                "img2img_strength": 0.7,
            },
            "product": {
                "guidance_scale": 7.5,
                "num_inference_steps": 50,
                "img2img_strength": 0.6,
            },
            "illustration": {
                "guidance_scale": 8.5,
                "num_inference_steps": 60,
                "img2img_strength": 0.7,
            },
            "3d_render": {
                "guidance_scale": 9.0,
                "num_inference_steps": 65,
                "img2img_strength": 0.75,
            },
            "technical": {
                "guidance_scale": 7.0,
                "num_inference_steps": 55,
                "img2img_strength": 0.55,
            },
        }
        base.update(category_defaults.get(category, {}))

        tier_steps = {"standard": 40, "premium": 55, "perfect": 75}
        tier_iters = {"standard": 2, "premium": 3, "perfect": 5}
        base["num_inference_steps"] = tier_steps.get(tier, base["num_inference_steps"])
        base["max_iterations"] = tier_iters.get(tier, 3)
        base["cfg_scale"] = {"standard": 7.5, "premium": 8.0, "perfect": 9.0}.get(
            tier, 7.5
        )
        return base


__all__ = [
    "GenerationRecord",
    "CategoryStats",
    "LocalStorageAdapter",
    "DynamoDBStorageAdapter",
    "EnhancedSelfImprovementEngine",
]

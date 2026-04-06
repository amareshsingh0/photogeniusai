"""
Learning Engine — Continuous Quality Improvement

Logs every generation decision + outcome.
Analyzes patterns to improve agent recommendations over time.

Philosophy:
- "What worked, why, for whom?"
- "Patterns emerge from volume, not intuition"
- "The system that learns is the system that wins"

Storage: PostgreSQL (LearningLog table via Prisma)
Analysis: Real-time pattern detection + recommendations
Feedback Loop: User thumbs up/down + quality scores → agent insights
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Literal

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Learning Engine Configuration
# ══════════════════════════════════════════════════════════════════════════════

LEARNING_ENABLED = os.getenv("LEARNING_ENGINE_ENABLED", "true").lower() == "true"
MIN_SAMPLES_FOR_RECOMMENDATION = int(os.getenv("LEARNING_MIN_SAMPLES", "100"))
CONFIDENCE_THRESHOLD = float(os.getenv("LEARNING_CONFIDENCE_THRESHOLD", "0.75"))

# ══════════════════════════════════════════════════════════════════════════════
# Learning Log Data Model (matches Prisma schema)
# ══════════════════════════════════════════════════════════════════════════════

class LearningLog:
    """
    Single generation learning log entry.
    Stores: input → decisions → quality → user feedback
    """
    def __init__(
        self,
        user_prompt: str,
        bucket: str,
        platform: str,
        aesthetic: Optional[str],
        creative_concept: str,
        visual_decree_id: str,
        layout_variant: str,
        model_used: str,
        quality_score: float,
        dimension_scores: Dict,
        beast_gates_passed: int,
        user_feedback: Optional[str],
        generation_time_ms: int,
        cost_usd: float,
        revision_cycles: int,
    ):
        self.timestamp = datetime.utcnow()
        self.user_prompt = user_prompt
        self.bucket = bucket
        self.platform = platform
        self.aesthetic = aesthetic
        self.creative_concept = creative_concept
        self.visual_decree_id = visual_decree_id
        self.layout_variant = layout_variant
        self.model_used = model_used
        self.quality_score = quality_score
        self.dimension_scores = dimension_scores
        self.beast_gates_passed = beast_gates_passed
        self.user_feedback = user_feedback
        self.generation_time_ms = generation_time_ms
        self.cost_usd = cost_usd
        self.revision_cycles = revision_cycles

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "user_prompt": self.user_prompt,
            "bucket": self.bucket,
            "platform": self.platform,
            "aesthetic": self.aesthetic,
            "creative_concept": self.creative_concept,
            "visual_decree_id": self.visual_decree_id,
            "layout_variant": self.layout_variant,
            "model_used": self.model_used,
            "quality_score": self.quality_score,
            "dimension_scores": self.dimension_scores,
            "beast_gates_passed": self.beast_gates_passed,
            "user_feedback": self.user_feedback,
            "generation_time_ms": self.generation_time_ms,
            "cost_usd": self.cost_usd,
            "revision_cycles": self.revision_cycles,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Learning Engine Core
# ══════════════════════════════════════════════════════════════════════════════

class LearningEngine:
    """
    Continuous learning system that improves agent decisions over time.

    Capabilities:
    1. Log every generation (decisions + quality + feedback)
    2. Analyze patterns (model performance, aesthetic trends, etc.)
    3. Provide real-time recommendations to agents
    4. Track quality improvements over time
    """

    def __init__(self, prisma_client=None):
        self.prisma = prisma_client
        self._in_memory_logs: List[LearningLog] = []  # Fallback if DB unavailable

    async def log_generation(
        self,
        brief: Dict,
        quality_result: Dict,
        generation_time_ms: int,
        cost_usd: float = 0.0,
        user_feedback: Optional[str] = None,
    ) -> bool:
        """
        Log a complete generation cycle.

        Args:
            brief: Full design brief from design_agent_chain
            quality_result: Quality Critic output (dimensions + gates + score)
            generation_time_ms: Total generation time
            cost_usd: API cost for this generation
            user_feedback: Optional user feedback (thumbs_up, thumbs_down, neutral)

        Returns:
            True if logged successfully, False otherwise
        """
        if not LEARNING_ENABLED:
            return False

        try:
            # Extract data from brief
            triage = brief.get("triage", {})
            creative = brief.get("creative", {})
            creative_bible = brief.get("creative_bible", {})
            design_decree = brief.get("design_decree", {})
            layout_variants = brief.get("_layout_variants", {})

            log_entry = LearningLog(
                user_prompt=brief.get("triage", {}).get("original_prompt", "")[:500],
                bucket=triage.get("industry", "general"),
                platform=triage.get("platform", "instagram"),
                aesthetic=creative_bible.get("aesthetic_direction", {}).get("code", None),
                creative_concept=creative_bible.get("emotional_territory", "")[:200],
                visual_decree_id=design_decree.get("composition_law", "hero_dominant"),
                layout_variant=layout_variants.get("winner", "safe"),
                model_used=brief.get("_model_preference", "flux_2_pro"),
                quality_score=quality_result.get("overall_score", 0.0),
                dimension_scores=quality_result.get("dimensions", {}),
                beast_gates_passed=sum(
                    1 for gate in quality_result.get("beast_gates", {}).values()
                    if gate.get("passed", False)
                ),
                user_feedback=user_feedback,
                generation_time_ms=generation_time_ms,
                cost_usd=cost_usd,
                revision_cycles=quality_result.get("revision_cycle", 0),
            )

            # Store in database (async)
            if self.prisma:
                try:
                    await self._store_in_db(log_entry)
                except Exception as e:
                    logger.error(f"[LearningEngine] DB storage failed: {e}")
                    self._in_memory_logs.append(log_entry)  # Fallback
            else:
                # No Prisma client, use in-memory fallback
                self._in_memory_logs.append(log_entry)

            logger.info(
                f"[LearningEngine] Logged: bucket={log_entry.bucket}, "
                f"aesthetic={log_entry.aesthetic}, variant={log_entry.layout_variant}, "
                f"quality={log_entry.quality_score:.1f}, gates={log_entry.beast_gates_passed}/10"
            )
            return True

        except Exception as e:
            logger.exception(f"[LearningEngine] log_generation failed: {e}")
            return False

    async def _store_in_db(self, log_entry: LearningLog):
        """Store log entry in PostgreSQL via Prisma."""
        # TODO: Wire Prisma client when DB schema is deployed
        # await self.prisma.learninglog.create(data=log_entry.to_dict())
        logger.debug(f"[LearningEngine] DB storage: {log_entry.to_dict()}")

    async def get_recommendation(
        self,
        bucket: str,
        platform: str,
        aesthetic: Optional[str] = None,
    ) -> Dict:
        """
        Get learned recommendations for this context.

        Returns:
        {
            "aesthetic_recommendation": "ai_native",
            "confidence": 0.87,
            "rationale": "Tech + Gen Z + Instagram: ai_native has 9.2 avg score (2.3k samples)",
            "model_preference": "flux_2_pro",
            "expected_quality": 8.9,
            "layout_variant_preference": "bold",
            "sample_count": 2300
        }
        """
        if not LEARNING_ENABLED:
            return {"confidence": 0.0, "rationale": "Learning engine disabled"}

        try:
            # Query logs matching this context
            matching_logs = self._query_logs(bucket, platform, aesthetic)

            if len(matching_logs) < MIN_SAMPLES_FOR_RECOMMENDATION:
                return {
                    "confidence": 0.0,
                    "rationale": f"Insufficient data ({len(matching_logs)} samples, need {MIN_SAMPLES_FOR_RECOMMENDATION})",
                    "sample_count": len(matching_logs),
                }

            # Analyze patterns
            avg_quality = sum(log.quality_score for log in matching_logs) / len(matching_logs)

            # Model preference (highest avg quality)
            model_scores = {}
            for log in matching_logs:
                if log.model_used not in model_scores:
                    model_scores[log.model_used] = []
                model_scores[log.model_used].append(log.quality_score)

            best_model = max(
                model_scores.items(),
                key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0
            )[0] if model_scores else "flux_2_pro"

            # Layout variant preference
            variant_scores = {}
            for log in matching_logs:
                if log.layout_variant not in variant_scores:
                    variant_scores[log.layout_variant] = []
                variant_scores[log.layout_variant].append(log.quality_score)

            best_variant = max(
                variant_scores.items(),
                key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0
            )[0] if variant_scores else "safe"

            # Aesthetic recommendation (if not provided)
            aesthetic_recommendation = aesthetic
            if not aesthetic:
                aesthetic_counts = {}
                for log in matching_logs:
                    if log.aesthetic:
                        aesthetic_counts[log.aesthetic] = aesthetic_counts.get(log.aesthetic, 0) + 1
                if aesthetic_counts:
                    aesthetic_recommendation = max(aesthetic_counts.items(), key=lambda x: x[1])[0]

            confidence = min(len(matching_logs) / (MIN_SAMPLES_FOR_RECOMMENDATION * 2), 1.0)

            return {
                "aesthetic_recommendation": aesthetic_recommendation,
                "confidence": confidence,
                "rationale": (
                    f"{bucket.capitalize()} + {platform}: "
                    f"{aesthetic_recommendation or 'N/A'} has {avg_quality:.1f} avg quality "
                    f"({len(matching_logs)} samples)"
                ),
                "model_preference": best_model,
                "expected_quality": avg_quality,
                "layout_variant_preference": best_variant,
                "sample_count": len(matching_logs),
            }

        except Exception as e:
            logger.exception(f"[LearningEngine] get_recommendation failed: {e}")
            return {"confidence": 0.0, "rationale": f"Error: {e}"}

    def _query_logs(
        self,
        bucket: str,
        platform: str,
        aesthetic: Optional[str] = None,
    ) -> List[LearningLog]:
        """Query in-memory logs matching context."""
        matching = []
        for log in self._in_memory_logs:
            if log.bucket == bucket and log.platform == platform:
                if aesthetic is None or log.aesthetic == aesthetic:
                    matching.append(log)
        return matching

    async def get_analytics(self, days: int = 30) -> Dict:
        """
        Get learning analytics for the past N days.

        Returns:
        {
            "total_generations": 15420,
            "avg_quality_score": 8.3,
            "beast_gates_pass_rate": 0.87,
            "top_aesthetics": [
                {"code": "ai_native", "count": 3200, "avg_quality": 8.9},
                {"code": "quiet_luxury_loud", "count": 2800, "avg_quality": 8.7},
            ],
            "top_models": [
                {"model": "flux_2_pro", "count": 7200, "avg_quality": 8.8},
            ],
            "layout_variant_distribution": {
                "safe": 8200,
                "bold": 5100,
                "disruptive": 2120
            },
            "quality_trend": "improving"  # improving | stable | declining
        }
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            recent_logs = [log for log in self._in_memory_logs if log.timestamp >= cutoff]

            if not recent_logs:
                return {"total_generations": 0, "message": "No data"}

            total = len(recent_logs)
            avg_quality = sum(log.quality_score for log in recent_logs) / total
            avg_gates = sum(log.beast_gates_passed for log in recent_logs) / total

            # Top aesthetics
            aesthetic_stats = {}
            for log in recent_logs:
                if log.aesthetic:
                    if log.aesthetic not in aesthetic_stats:
                        aesthetic_stats[log.aesthetic] = {"count": 0, "scores": []}
                    aesthetic_stats[log.aesthetic]["count"] += 1
                    aesthetic_stats[log.aesthetic]["scores"].append(log.quality_score)

            top_aesthetics = [
                {
                    "code": aesthetic,
                    "count": stats["count"],
                    "avg_quality": sum(stats["scores"]) / len(stats["scores"]),
                }
                for aesthetic, stats in aesthetic_stats.items()
            ]
            top_aesthetics.sort(key=lambda x: x["count"], reverse=True)

            # Top models
            model_stats = {}
            for log in recent_logs:
                if log.model_used not in model_stats:
                    model_stats[log.model_used] = {"count": 0, "scores": []}
                model_stats[log.model_used]["count"] += 1
                model_stats[log.model_used]["scores"].append(log.quality_score)

            top_models = [
                {
                    "model": model,
                    "count": stats["count"],
                    "avg_quality": sum(stats["scores"]) / len(stats["scores"]),
                }
                for model, stats in model_stats.items()
            ]
            top_models.sort(key=lambda x: x["count"], reverse=True)

            # Layout variant distribution
            variant_counts = {}
            for log in recent_logs:
                variant_counts[log.layout_variant] = variant_counts.get(log.layout_variant, 0) + 1

            return {
                "total_generations": total,
                "avg_quality_score": round(avg_quality, 2),
                "avg_beast_gates_passed": round(avg_gates, 1),
                "beast_gates_pass_rate": round(avg_gates / 10, 2),
                "top_aesthetics": top_aesthetics[:5],
                "top_models": top_models[:5],
                "layout_variant_distribution": variant_counts,
                "quality_trend": "stable",  # TODO: Compare with previous period
            }

        except Exception as e:
            logger.exception(f"[LearningEngine] get_analytics failed: {e}")
            return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

_learning_engine_singleton: Optional[LearningEngine] = None


def get_learning_engine(prisma_client=None) -> LearningEngine:
    """Get or create Learning Engine singleton."""
    global _learning_engine_singleton
    if _learning_engine_singleton is None:
        _learning_engine_singleton = LearningEngine(prisma_client=prisma_client)
        logger.info("[LearningEngine] Initialized (enabled=%s)", LEARNING_ENABLED)
    return _learning_engine_singleton


async def log_generation_async(
    brief: Dict,
    quality_result: Dict,
    generation_time_ms: int,
    cost_usd: float = 0.0,
    user_feedback: Optional[str] = None,
) -> bool:
    """
    Public API: Log a generation cycle.

    Usage:
    ```python
    from app.services.smart.learning_engine import log_generation_async

    await log_generation_async(
        brief=design_brief,
        quality_result=critique,
        generation_time_ms=int((time.time() - t0) * 1000),
        cost_usd=0.15,
        user_feedback="thumbs_up"  # or None
    )
    ```
    """
    engine = get_learning_engine()
    return await engine.log_generation(brief, quality_result, generation_time_ms, cost_usd, user_feedback)


async def get_recommendation_async(
    bucket: str,
    platform: str,
    aesthetic: Optional[str] = None,
) -> Dict:
    """
    Public API: Get learned recommendations for context.

    Usage:
    ```python
    from app.services.smart.learning_engine import get_recommendation_async

    rec = await get_recommendation_async(
        bucket="tech",
        platform="instagram",
        aesthetic="ai_native"
    )
    # rec["model_preference"] → "flux_2_pro"
    # rec["layout_variant_preference"] → "bold"
    # rec["expected_quality"] → 8.9
    ```
    """
    engine = get_learning_engine()
    return await engine.get_recommendation(bucket, platform, aesthetic)


async def get_analytics_async(days: int = 30) -> Dict:
    """
    Public API: Get learning analytics.

    Usage:
    ```python
    from app.services.smart.learning_engine import get_analytics_async

    analytics = await get_analytics_async(days=30)
    # analytics["total_generations"] → 15420
    # analytics["avg_quality_score"] → 8.3
    # analytics["top_aesthetics"] → [...]
    ```
    """
    engine = get_learning_engine()
    return await engine.get_analytics(days)

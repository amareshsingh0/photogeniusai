"""
User Preference Analyzer – Learn and adapt to user preferences over time.

Tracks:
- Variant selections, ratings, downloads, shares
- Visual style, surprise level, lighting, emotion from selections
- Model preferences (MJ, Flux, DALL-E)

Provides:
- Personalized defaults (style, surprise, variant order)
- Cold start handling (global defaults for new users)
- Preference drift detection
- Privacy-preserving aggregates only
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.advanced_classifier import (
    EmotionalTone,
    LightingStyle,
    SurpriseLevel,
    VisualStyle,
)
from services.observability import StructuredLogger, trace_function

logger = StructuredLogger(__name__)


def _utcnow() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


@dataclass
class UserInteraction:
    """Single user interaction event."""

    user_id: str
    timestamp: datetime

    action_type: str  # "select", "rate", "regenerate", "download", "share"

    prompt: str
    variant_index: int  # 0-5
    variant_style: str  # "cinematic", "cool_edgy", etc.

    rating: Optional[int] = None  # 1-5 stars

    visual_style: Optional[VisualStyle] = None
    surprise_level: Optional[SurpriseLevel] = None
    lighting: Optional[LightingStyle] = None
    emotion: Optional[EmotionalTone] = None


@dataclass
class UserPreferenceProfile:
    """Learned user preferences (aggregates only)."""

    user_id: str

    preferred_visual_styles: Counter = field(default_factory=Counter)
    preferred_surprise_levels: Counter = field(default_factory=Counter)
    preferred_lighting: Counter = field(default_factory=Counter)
    preferred_emotions: Counter = field(default_factory=Counter)

    variant_selection_counts: Counter = field(default_factory=Counter)
    model_preferences: Counter = field(default_factory=Counter)

    total_interactions: int = 0
    first_seen: datetime = field(default_factory=_utcnow)
    last_seen: datetime = field(default_factory=_utcnow)

    profile_confidence: float = 0.0  # 0-1

    def get_default_style(self) -> VisualStyle:
        """Most preferred visual style."""
        if self.preferred_visual_styles:
            most_common = self.preferred_visual_styles.most_common(1)[0]
            try:
                return VisualStyle(most_common[0])
            except ValueError:
                pass
        return VisualStyle.CINEMATIC

    def get_default_surprise(self) -> SurpriseLevel:
        """Preferred surprise level."""
        if self.preferred_surprise_levels:
            most_common = self.preferred_surprise_levels.most_common(1)[0]
            try:
                return SurpriseLevel(most_common[0])
            except ValueError:
                pass
        return SurpriseLevel.MODERATE

    def get_recommended_variant_order(self) -> List[int]:
        """Variant order by most selected (0-5 indices)."""
        if self.variant_selection_counts:
            ordered = sorted(
                self.variant_selection_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            return [int(k) for k, _ in ordered]

        return [1, 5, 0, 2, 3, 4]  # Default: Cinematic (2), Personalized (6→5), etc.


class UserPreferenceAnalyzer:
    """Learn and adapt to user preferences over time."""

    def __init__(self, db_session: Any = None) -> None:
        """
        Initialize analyzer.

        Args:
            db_session: Optional DB session for persistence (e.g. API app).
        """
        self.db = db_session
        self.user_profiles: Dict[str, UserPreferenceProfile] = {}
        self.interaction_history: Dict[str, List[UserInteraction]] = defaultdict(list)
        logger.info("UserPreferenceAnalyzer initialized")

    def _style_from_value(self, value: Any) -> Optional[VisualStyle]:
        """Coerce value to VisualStyle."""
        if value is None:
            return None
        if isinstance(value, VisualStyle):
            return value
        try:
            return VisualStyle(str(value))
        except ValueError:
            return None

    def _surprise_from_value(self, value: Any) -> Optional[SurpriseLevel]:
        """Coerce value to SurpriseLevel."""
        if value is None:
            return None
        if isinstance(value, SurpriseLevel):
            return value
        try:
            return SurpriseLevel(str(value))
        except ValueError:
            return None

    def _lighting_from_value(self, value: Any) -> Optional[LightingStyle]:
        """Coerce value to LightingStyle."""
        if value is None:
            return None
        if isinstance(value, LightingStyle):
            return value
        try:
            return LightingStyle(str(value))
        except ValueError:
            return None

    def _emotion_from_value(self, value: Any) -> Optional[EmotionalTone]:
        """Coerce value to EmotionalTone."""
        if value is None:
            return None
        if isinstance(value, EmotionalTone):
            return value
        try:
            return EmotionalTone(str(value))
        except ValueError:
            return None

    @trace_function("preferences.track_interaction")  # type: ignore[misc]
    def track_interaction(
        self,
        user_id: str,
        action_type: str,
        prompt: str,
        variant_index: int,
        variant_style: str,
        rating: Optional[int] = None,
        style_analysis: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> None:
        """
        Track user interaction.

        Args:
            user_id: User ID
            action_type: "select", "rate", "regenerate", "download", "share"
            prompt: Original prompt
            variant_index: Which variant was chosen (0-5)
            variant_style: Style of chosen variant
            rating: Optional 1-5 rating
            style_analysis: Optional dict with visual_style, surprise_level, lighting, emotion
            model_name: Optional model used (e.g. flux, dall-e)
        """
        interaction = UserInteraction(
            user_id=user_id,
            timestamp=_utcnow(),
            action_type=action_type,
            prompt=prompt,
            variant_index=variant_index,
            variant_style=variant_style,
            rating=rating,
        )

        if style_analysis:
            interaction.visual_style = self._style_from_value(
                style_analysis.get("visual_style")
            )
            interaction.surprise_level = self._surprise_from_value(
                style_analysis.get("surprise_level")
            )
            interaction.lighting = self._lighting_from_value(
                style_analysis.get("lighting")
            )
            interaction.emotion = self._emotion_from_value(
                style_analysis.get("emotion")
            )

        self.interaction_history[user_id].append(interaction)
        if len(self.interaction_history[user_id]) > 100:
            self.interaction_history[user_id] = self.interaction_history[user_id][
                -100:
            ]

        self._update_profile(user_id, interaction, model_name=model_name)

        if self.db is not None:
            self._persist_interaction(interaction)

        logger.info(
            "Interaction tracked",
            user_id=user_id,
            action=action_type,
            variant=variant_index,
            style=variant_style,
        )

    def _update_profile(
        self,
        user_id: str,
        interaction: UserInteraction,
        model_name: Optional[str] = None,
    ) -> None:
        """Update user profile from interaction."""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserPreferenceProfile(user_id=user_id)

        profile = self.user_profiles[user_id]
        weight = self._get_interaction_weight(interaction.action_type)

        if interaction.rating is not None and interaction.rating >= 4:
            weight = max(weight, 2)

        profile.variant_selection_counts[str(interaction.variant_index)] += weight

        if interaction.visual_style is not None:
            profile.preferred_visual_styles[interaction.visual_style.value] += weight
        if interaction.surprise_level is not None:
            profile.preferred_surprise_levels[interaction.surprise_level.value] += weight
        if interaction.lighting is not None:
            profile.preferred_lighting[interaction.lighting.value] += weight
        if interaction.emotion is not None:
            profile.preferred_emotions[interaction.emotion.value] += weight

        if model_name:
            profile.model_preferences[model_name.lower()] += weight

        profile.total_interactions += 1
        profile.last_seen = _utcnow()
        profile.profile_confidence = min(
            1.0, math.log10(profile.total_interactions + 1) / 2.0
        )

        logger.debug(
            "Profile updated",
            user_id=user_id,
            total_interactions=profile.total_interactions,
            confidence=round(profile.profile_confidence, 2),
        )

    def _get_interaction_weight(self, action_type: str) -> int:
        """Weight for interaction type."""
        weights = {
            "download": 5,
            "share": 4,
            "rate": 3,
            "select": 2,
            "regenerate": 1,
        }
        return weights.get(action_type, 1)

    @trace_function("preferences.get_profile")  # type: ignore[misc]
    def get_profile(
        self,
        user_id: str,
        min_confidence: float = 0.3,
    ) -> Optional[UserPreferenceProfile]:
        """Get user profile if confidence >= min_confidence."""
        if user_id not in self.user_profiles:
            logger.info("No profile found for user", user_id=user_id)
            return None

        profile = self.user_profiles[user_id]
        if profile.profile_confidence < min_confidence:
            logger.info(
                "Profile confidence too low",
                user_id=user_id,
                confidence=profile.profile_confidence,
                min_required=min_confidence,
            )
            return None

        logger.info(
            "Profile retrieved",
            user_id=user_id,
            confidence=profile.profile_confidence,
            interactions=profile.total_interactions,
        )
        return profile

    @trace_function("preferences.get_personalized_defaults")  # type: ignore[misc]
    def get_personalized_defaults(self, user_id: str) -> Dict[str, Any]:
        """Get personalized default settings (cold start = global defaults)."""
        profile = self.get_profile(user_id, min_confidence=0.3)

        if profile is None:
            return {
                "default_style": VisualStyle.CINEMATIC,
                "default_surprise": SurpriseLevel.MODERATE,
                "default_lighting": LightingStyle.GOLDEN,
                "default_emotion": EmotionalTone.SERENE,
                "variant_order": [1, 5, 0, 2, 3, 4],
                "confidence": 0.0,
            }

        default_lighting = LightingStyle.GOLDEN
        if profile.preferred_lighting:
            mc = profile.preferred_lighting.most_common(1)[0][0]
            try:
                default_lighting = LightingStyle(mc)
            except ValueError:
                pass

        default_emotion = EmotionalTone.SERENE
        if profile.preferred_emotions:
            mc = profile.preferred_emotions.most_common(1)[0][0]
            try:
                default_emotion = EmotionalTone(mc)
            except ValueError:
                pass

        return {
            "default_style": profile.get_default_style(),
            "default_surprise": profile.get_default_surprise(),
            "default_lighting": default_lighting,
            "default_emotion": default_emotion,
            "variant_order": profile.get_recommended_variant_order(),
            "confidence": profile.profile_confidence,
        }

    @trace_function("preferences.analyze_trends")  # type: ignore[misc]
    def analyze_user_trends(
        self,
        user_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Analyze preference trends and drift over time."""
        if user_id not in self.interaction_history:
            return {}

        cutoff = _utcnow() - timedelta(days=days)
        recent = [
            i
            for i in self.interaction_history[user_id]
            if i.timestamp >= cutoff
        ]

        if not recent:
            return {}

        style_trend = Counter(
            i.visual_style.value for i in recent if i.visual_style is not None
        )
        surprise_trend = Counter(
            i.surprise_level.value for i in recent if i.surprise_level is not None
        )

        older = [
            i
            for i in self.interaction_history[user_id]
            if i.timestamp < cutoff
        ]
        drift_detected = False
        if older and len(recent) >= 10:
            old_styles = Counter(
                i.visual_style.value for i in older if i.visual_style is not None
            )
            if old_styles and style_trend:
                old_top = old_styles.most_common(1)[0][0]
                new_top = style_trend.most_common(1)[0][0]
                if old_top != new_top:
                    drift_detected = True

        return {
            "total_interactions": len(recent),
            "style_distribution": dict(style_trend),
            "surprise_distribution": dict(surprise_trend),
            "drift_detected": drift_detected,
            "most_active_time": self._get_most_active_time(recent),
        }

    def _get_most_active_time(self, interactions: List[UserInteraction]) -> str:
        """Most active time of day (morning/afternoon/evening/night)."""
        hour_counts = Counter(i.timestamp.hour for i in interactions)
        if not hour_counts:
            return "unknown"
        most_common_hour = hour_counts.most_common(1)[0][0]
        if 6 <= most_common_hour < 12:
            return "morning"
        if 12 <= most_common_hour < 18:
            return "afternoon"
        if 18 <= most_common_hour < 22:
            return "evening"
        return "night"

    def _persist_interaction(self, interaction: UserInteraction) -> None:
        """Persist interaction to DB if session and model available."""
        if self.db is None:
            return
        try:
            from database.models import UserInteractionLog  # type: ignore[import-not-found]

            prompt_hash = hashlib.md5(interaction.prompt.encode()).hexdigest()
            log = UserInteractionLog(
                user_id=interaction.user_id,
                timestamp=interaction.timestamp,
                action_type=interaction.action_type,
                prompt_hash=prompt_hash,
                variant_index=interaction.variant_index,
                variant_style=interaction.variant_style,
                rating=interaction.rating,
                metadata={
                    "visual_style": (
                        interaction.visual_style.value
                        if interaction.visual_style
                        else None
                    ),
                    "surprise_level": (
                        interaction.surprise_level.value
                        if interaction.surprise_level
                        else None
                    ),
                },
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.debug("Persist interaction skipped (no DB model or error): %s", e)


# ==================== CONVENIENCE ====================

_default_analyzer: Optional[UserPreferenceAnalyzer] = None


def get_default_preference_analyzer() -> UserPreferenceAnalyzer:
    """Get or create default analyzer (in-memory only)."""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = UserPreferenceAnalyzer()
    return _default_analyzer

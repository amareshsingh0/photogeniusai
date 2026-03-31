"""
Feedback Learning Engine v2 - Self-improving AI generation system.

The system LEARNS from every generation and user interaction:

1. PROMPT INTELLIGENCE: Analyze what prompt patterns work best per mode
   - Extract keywords, style words, composition hints
   - Track which prompt patterns get 4-5 star ratings
   - Auto-suggest prompt improvements for future users

2. CROSS-USER AGGREGATION: All users improve the system
   - Global mode effectiveness scores (which modes produce best results)
   - Global model effectiveness (which model is best per category)
   - Category-specific parameter tuning (after 1000+ images, auto-optimize)

3. AUTO-TUNING MILESTONES:
   - After 100 images per mode → start adjusting guidance/steps defaults
   - After 500 images per category → optimize model selection
   - After 1000 images total → full parameter auto-optimization
   - Continuous improvement: every 100 new feedbacks triggers recalculation

4. PER-USER PERSONALIZATION:
   - Style preferences (warm/cool, vibrant/muted)
   - CFG preference (higher/lower detail)
   - Mode affinities (what they generate most + rate highest)
   - Best configs replay (reuse winning parameter combinations)

Storage: JSON files (no external DB dependency), upgradeable to Redis/Postgres.
"""

import json
import logging
import time
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)

FEEDBACK_DIR = Path("/tmp/photogenius_feedback")

# ======================================================================
# Auto-tuning milestones
# ======================================================================
MILESTONE_MODE_TUNING = 100      # Start tuning per-mode after 100 images
MILESTONE_CATEGORY_TUNING = 500  # Optimize model selection after 500
MILESTONE_FULL_OPTIMIZATION = 1000  # Full auto-optimization
RECALC_INTERVAL = 100            # Recalculate every 100 new feedbacks


@dataclass
class FeedbackEntry:
    """Single piece of user feedback on a generated image."""
    timestamp: float = 0.0
    user_id: str = ''
    prompt: str = ''
    mode: str = ''
    sub_mode: str = ''
    category: str = ''
    quality_tier: str = ''
    model_used: str = ''
    steps: int = 0
    guidance_scale: float = 0.0
    sampler: str = ''
    seed: int = 0
    pipeline_score: float = 0.0
    aesthetic_score: float = 0.0
    technical_score: float = 0.0
    user_rating: float = 0.0
    liked: Optional[bool] = None
    downloaded: bool = False
    shared: bool = False
    regenerated: bool = False
    time_spent_viewing: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class UserPreferences:
    """Learned preferences for a specific user."""
    user_id: str = ''
    total_ratings: int = 0
    avg_rating: float = 0.0
    mode_ratings: Dict[str, float] = field(default_factory=dict)
    mode_counts: Dict[str, int] = field(default_factory=dict)
    preferred_guidance_offset: float = 0.0
    preferred_steps_offset: int = 0
    preferred_warmth: str = 'neutral'
    preferred_saturation: str = 'normal'
    category_ratings: Dict[str, float] = field(default_factory=dict)
    best_configs: List[Dict] = field(default_factory=list)
    # Prompt intelligence per user
    favorite_keywords: Dict[str, float] = field(default_factory=dict)
    last_updated: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PromptPattern:
    """A prompt pattern that consistently produces good results."""
    keywords: List[str] = field(default_factory=list)
    avg_rating: float = 0.0
    count: int = 0
    best_mode: str = ''
    best_model: str = ''
    best_guidance: float = 0.0
    best_steps: int = 0


@dataclass
class CategoryInsight:
    """Learned insights for a specific image category."""
    category: str = ''
    total_images: int = 0
    avg_rating: float = 0.0
    # Best performing model for this category
    model_ratings: Dict[str, float] = field(default_factory=dict)
    model_counts: Dict[str, int] = field(default_factory=dict)
    best_model: str = ''
    # Optimal parameter ranges (learned from high-rated images)
    optimal_guidance: float = 0.0
    optimal_steps: int = 0
    optimal_sampler: str = ''
    # Prompt patterns that work
    top_keywords: List[str] = field(default_factory=list)
    # Tuned flag
    is_tuned: bool = False


@dataclass
class GlobalOptimization:
    """Global auto-tuning state across all users."""
    total_images: int = 0
    total_feedback: int = 0
    last_recalc_at: int = 0
    # Per-mode optimized defaults (overrides generation_strategy presets)
    mode_overrides: Dict[str, Dict] = field(default_factory=dict)
    # Per-category best model
    category_best_model: Dict[str, str] = field(default_factory=dict)
    # Per-model effectiveness across modes
    model_effectiveness: Dict[str, float] = field(default_factory=dict)
    # Milestone flags
    milestone_100_reached: bool = False
    milestone_500_reached: bool = False
    milestone_1000_reached: bool = False


# ======================================================================
# Prompt analysis utilities
# ======================================================================

# Style words that indicate quality preferences
STYLE_KEYWORDS = {
    'cinematic', 'dramatic', 'moody', 'vibrant', 'ethereal', 'dark',
    'bright', 'soft', 'sharp', 'detailed', 'minimalist', 'elegant',
    'rustic', 'modern', 'vintage', 'retro', 'futuristic', 'surreal',
    'dreamy', 'bold', 'subtle', 'warm', 'cool', 'neon', 'pastel',
    'golden', 'silver', 'glowing', 'misty', 'foggy', 'clear',
    'high contrast', 'low key', 'high key', 'bokeh', 'macro',
}

# Composition keywords
COMPOSITION_KEYWORDS = {
    'close up', 'wide angle', 'aerial', 'bird eye', 'top down',
    'side view', 'front view', 'three quarter', 'full body',
    'headshot', 'portrait', 'landscape', 'panoramic', 'symmetrical',
    'rule of thirds', 'centered', 'framed', 'silhouette',
}

# Quality indicator words
QUALITY_KEYWORDS = {
    'professional', '8k', '4k', 'ultra hd', 'masterpiece',
    'best quality', 'highly detailed', 'award winning', 'studio',
    'photorealistic', 'hyperrealistic', 'raw photo', 'dslr',
}

SIGNAL_WEIGHTS = {
    'user_rating': 1.0,
    'liked': 0.6,
    'downloaded': 0.4,
    'shared': 0.5,
    'regenerated': -0.3,
    'time_viewed': 0.2,
}

MIN_FEEDBACK_FOR_LEARNING = 5
MAX_ENTRIES_PER_USER = 500


def extract_prompt_keywords(prompt: str) -> List[str]:
    """Extract meaningful keywords from a prompt for pattern matching."""
    prompt_lower = prompt.lower().strip()
    words = re.findall(r'[a-z]+(?:\s+[a-z]+)?', prompt_lower)

    keywords = []
    for w in words:
        w = w.strip()
        if len(w) < 3:
            continue
        if w in {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'are', 'was',
                 'were', 'been', 'being', 'have', 'has', 'had', 'does', 'did', 'will',
                 'would', 'could', 'should', 'may', 'might', 'shall', 'can', 'need',
                 'must', 'not', 'but', 'yet', 'nor', 'each', 'every', 'all', 'any',
                 'image', 'photo', 'picture', 'generate', 'create', 'make'}:
            continue
        keywords.append(w)

    return keywords[:20]  # Max 20 keywords


class FeedbackLearningEngine:
    """Self-improving generation system that learns from every interaction.

    Three levels of learning:
    1. Per-user: Personal style preferences
    2. Per-category: Which model/params work best for portraits vs landscapes etc.
    3. Global: System-wide optimization milestones
    """

    def __init__(self):
        self._entries: Dict[str, List[FeedbackEntry]] = defaultdict(list)
        self._user_prefs: Dict[str, UserPreferences] = {}
        self._category_insights: Dict[str, CategoryInsight] = {}
        self._global: GlobalOptimization = GlobalOptimization()
        self._prompt_patterns: Dict[str, PromptPattern] = {}
        self._keyword_ratings: Dict[str, List[float]] = defaultdict(list)
        self._global_avg_rating: float = 3.0
        self._total_feedback: int = 0

    # ─── Core Feedback Recording ───────────────────────────────

    def record_feedback(
        self,
        user_id: str,
        prompt: str,
        mode: str,
        sub_mode: str = '',
        category: str = '',
        quality_tier: str = 'STANDARD',
        model_used: str = '',
        steps: int = 0,
        guidance_scale: float = 0.0,
        sampler: str = '',
        seed: int = 0,
        pipeline_score: float = 0.0,
        aesthetic_score: float = 0.0,
        technical_score: float = 0.0,
        user_rating: float = 0.0,
        liked: Optional[bool] = None,
        downloaded: bool = False,
        shared: bool = False,
        regenerated: bool = False,
        time_spent_viewing: float = 0.0,
    ) -> Dict:
        """Record feedback and trigger all learning systems."""
        entry = FeedbackEntry(
            timestamp=time.time(), user_id=user_id, prompt=prompt,
            mode=mode, sub_mode=sub_mode, category=category,
            quality_tier=quality_tier, model_used=model_used,
            steps=steps, guidance_scale=guidance_scale, sampler=sampler,
            seed=seed, pipeline_score=pipeline_score,
            aesthetic_score=aesthetic_score, technical_score=technical_score,
            user_rating=user_rating, liked=liked, downloaded=downloaded,
            shared=shared, regenerated=regenerated,
            time_spent_viewing=time_spent_viewing,
        )

        composite = self._compute_composite_score(entry)

        # Store entry
        self._entries[user_id].append(entry)
        if len(self._entries[user_id]) > MAX_ENTRIES_PER_USER:
            self._entries[user_id] = self._entries[user_id][-MAX_ENTRIES_PER_USER:]

        self._total_feedback += 1
        self._global.total_feedback = self._total_feedback

        if composite is not None:
            # Level 1: User preferences
            self._update_user_preferences(user_id, entry, composite)

            # Level 2: Category insights
            self._update_category_insights(entry, composite)

            # Level 3: Prompt intelligence
            self._update_prompt_intelligence(entry, composite)

            # Level 4: Global optimization
            self._update_global_optimization(entry, composite)

            # Check milestones
            self._check_milestones()

        logger.info(
            f"Feedback recorded: user={user_id}, mode={mode}, "
            f"model={model_used}, rating={user_rating}, "
            f"total={self._total_feedback}"
        )

        return {
            'recorded': True,
            'total_user_feedback': len(self._entries[user_id]),
            'user_avg_rating': self._user_prefs.get(user_id, UserPreferences()).avg_rating,
            'global_total': self._total_feedback,
            'milestones': {
                '100_mode_tuning': self._global.milestone_100_reached,
                '500_category_tuning': self._global.milestone_500_reached,
                '1000_full_optimization': self._global.milestone_1000_reached,
            },
        }

    # ─── Generation Adjustments (used by orchestrator) ─────────

    def get_generation_adjustments(
        self,
        user_id: str,
        mode: str,
        sub_mode: str = '',
        quality: str = 'STANDARD',
    ) -> Dict:
        """Get learned adjustments combining user + global intelligence."""
        adjustments = {
            'guidance_offset': 0.0,
            'steps_offset': 0,
            'preferred_sampler': None,
            'preferred_model': None,
            'warmth_preference': 'neutral',
            'saturation_preference': 'normal',
            'confidence': 0.0,
            'prompt_boost_keywords': [],
            'source': 'none',
        }

        mode_key = f"{mode}_{sub_mode}" if sub_mode else mode

        # === Global optimization (affects everyone) ===
        if self._global.milestone_100_reached:
            mode_override = self._global.mode_overrides.get(mode_key) or self._global.mode_overrides.get(mode)
            if mode_override:
                adjustments['guidance_offset'] = mode_override.get('guidance_offset', 0)
                adjustments['steps_offset'] = mode_override.get('steps_offset', 0)
                if mode_override.get('sampler'):
                    adjustments['preferred_sampler'] = mode_override['sampler']
                adjustments['source'] = 'global_mode_tuning'
                adjustments['confidence'] = 0.4

        # === Category-level model suggestion ===
        if self._global.milestone_500_reached:
            # Find what category maps to, suggest best model
            for cat, insight in self._category_insights.items():
                if insight.is_tuned and insight.best_model:
                    adjustments['preferred_model'] = insight.best_model

        # === User-specific (overrides global with higher confidence) ===
        user_prefs = self._user_prefs.get(user_id)
        if user_prefs and user_prefs.total_ratings >= MIN_FEEDBACK_FOR_LEARNING:
            user_confidence = min(1.0, user_prefs.total_ratings / 50.0)

            if user_confidence > adjustments['confidence']:
                adjustments['guidance_offset'] = user_prefs.preferred_guidance_offset
                adjustments['steps_offset'] = user_prefs.preferred_steps_offset
                adjustments['warmth_preference'] = user_prefs.preferred_warmth
                adjustments['saturation_preference'] = user_prefs.preferred_saturation
                adjustments['confidence'] = user_confidence
                adjustments['source'] = 'user_preferences'

            # Add prompt boost keywords from user's best patterns
            if user_prefs.favorite_keywords:
                top_kw = sorted(
                    user_prefs.favorite_keywords.items(),
                    key=lambda x: x[1], reverse=True
                )[:5]
                adjustments['prompt_boost_keywords'] = [k for k, v in top_kw if v >= 4.0]

        return adjustments

    # ─── Query Methods ───────────────────────────────────────

    def get_user_profile(self, user_id: str) -> Dict:
        """Get a user's learned preference profile."""
        prefs = self._user_prefs.get(user_id)
        if not prefs:
            return {'user_id': user_id, 'has_profile': False, 'total_ratings': 0}

        return {
            'user_id': user_id,
            'has_profile': True,
            'total_ratings': prefs.total_ratings,
            'avg_rating': round(prefs.avg_rating, 2),
            'top_modes': self._get_top_modes(prefs, 5),
            'top_categories': self._get_top_categories(prefs, 5),
            'favorite_keywords': dict(sorted(
                prefs.favorite_keywords.items(),
                key=lambda x: x[1], reverse=True
            )[:10]),
            'style_preferences': {
                'warmth': prefs.preferred_warmth,
                'saturation': prefs.preferred_saturation,
                'guidance_offset': round(prefs.preferred_guidance_offset, 2),
                'steps_offset': prefs.preferred_steps_offset,
            },
            'best_configs': prefs.best_configs[:5],
            'confidence': min(1.0, prefs.total_ratings / 50.0),
        }

    def get_global_stats(self) -> Dict:
        """Get global feedback and learning statistics."""
        return {
            'total_feedback': self._total_feedback,
            'total_users': len(self._user_prefs),
            'global_avg_rating': round(self._global_avg_rating, 2),
            'milestones': {
                '100_mode_tuning': self._global.milestone_100_reached,
                '500_category_tuning': self._global.milestone_500_reached,
                '1000_full_optimization': self._global.milestone_1000_reached,
            },
            'category_insights': {
                cat: {
                    'total_images': ins.total_images,
                    'avg_rating': round(ins.avg_rating, 2),
                    'best_model': ins.best_model,
                    'is_tuned': ins.is_tuned,
                    'optimal_guidance': round(ins.optimal_guidance, 2),
                    'optimal_steps': ins.optimal_steps,
                }
                for cat, ins in sorted(
                    self._category_insights.items(),
                    key=lambda x: x[1].total_images, reverse=True
                )[:15]
            },
            'mode_overrides': self._global.mode_overrides,
            'top_prompt_keywords': self._get_global_top_keywords(10),
        }

    def get_category_insight(self, category: str) -> Dict:
        """Get detailed learning for a specific category."""
        ins = self._category_insights.get(category)
        if not ins:
            return {'category': category, 'total_images': 0, 'is_tuned': False}

        return {
            'category': category,
            'total_images': ins.total_images,
            'avg_rating': round(ins.avg_rating, 2),
            'best_model': ins.best_model,
            'model_rankings': {
                m: {'avg_rating': round(r, 2), 'count': ins.model_counts.get(m, 0)}
                for m, r in sorted(ins.model_ratings.items(), key=lambda x: x[1], reverse=True)
            },
            'optimal_params': {
                'guidance': round(ins.optimal_guidance, 2),
                'steps': ins.optimal_steps,
                'sampler': ins.optimal_sampler,
            },
            'top_keywords': ins.top_keywords[:10],
            'is_tuned': ins.is_tuned,
        }

    # ─── Level 1: User Preference Learning ─────────────────────

    def _update_user_preferences(self, user_id: str, entry: FeedbackEntry, composite: float):
        """Update individual user preferences."""
        if user_id not in self._user_prefs:
            self._user_prefs[user_id] = UserPreferences(user_id=user_id)

        prefs = self._user_prefs[user_id]
        prefs.total_ratings += 1
        alpha = 1.0 / prefs.total_ratings
        prefs.avg_rating = prefs.avg_rating * (1 - alpha) + composite * alpha

        # Mode ratings
        mode_key = f"{entry.mode}_{entry.sub_mode}" if entry.sub_mode else entry.mode
        prev_count = prefs.mode_counts.get(mode_key, 0)
        prev_rating = prefs.mode_ratings.get(mode_key, 3.0)
        new_count = prev_count + 1
        prefs.mode_ratings[mode_key] = (prev_rating * prev_count + composite) / new_count
        prefs.mode_counts[mode_key] = new_count

        # Category ratings
        if entry.category:
            prev_cat = prefs.category_ratings.get(entry.category, 3.0)
            prefs.category_ratings[entry.category] = (prev_cat + composite) / 2

        # Guidance preference learning
        if entry.guidance_scale > 0:
            if composite >= 4.0:
                if entry.guidance_scale > 6.0:
                    prefs.preferred_guidance_offset = min(1.0, prefs.preferred_guidance_offset + 0.05)
                elif entry.guidance_scale < 4.0:
                    prefs.preferred_guidance_offset = max(-1.0, prefs.preferred_guidance_offset - 0.05)
            elif composite <= 2.0:
                if entry.guidance_scale > 6.0:
                    prefs.preferred_guidance_offset = max(-1.0, prefs.preferred_guidance_offset - 0.05)
                elif entry.guidance_scale < 4.0:
                    prefs.preferred_guidance_offset = min(1.0, prefs.preferred_guidance_offset + 0.05)

        # Steps preference learning
        if entry.steps > 0:
            if composite >= 4.0 and entry.steps > 30:
                prefs.preferred_steps_offset = min(10, prefs.preferred_steps_offset + 1)
            elif composite >= 4.0 and entry.steps < 15:
                prefs.preferred_steps_offset = max(-10, prefs.preferred_steps_offset - 1)

        # Keyword preference per user
        if composite >= 3.5:
            keywords = extract_prompt_keywords(entry.prompt)
            for kw in keywords:
                prev = prefs.favorite_keywords.get(kw, 3.0)
                prefs.favorite_keywords[kw] = (prev + composite) / 2

        # Best configs
        if composite >= 4.5:
            prefs.best_configs.append({
                'mode': entry.mode, 'model': entry.model_used,
                'steps': entry.steps, 'guidance': entry.guidance_scale,
                'sampler': entry.sampler, 'score': round(composite, 2),
            })
            if len(prefs.best_configs) > 20:
                prefs.best_configs = sorted(
                    prefs.best_configs, key=lambda x: x['score'], reverse=True
                )[:20]

        prefs.last_updated = time.time()

    # ─── Level 2: Category Insight Learning ─────────────────────

    def _update_category_insights(self, entry: FeedbackEntry, composite: float):
        """Update category-level insights (which model/params work best)."""
        if not entry.category:
            return

        cat = entry.category
        if cat not in self._category_insights:
            self._category_insights[cat] = CategoryInsight(category=cat)

        ins = self._category_insights[cat]
        ins.total_images += 1

        # Update avg rating
        alpha = 1.0 / ins.total_images
        ins.avg_rating = ins.avg_rating * (1 - alpha) + composite * alpha

        # Track model performance per category
        if entry.model_used:
            prev_count = ins.model_counts.get(entry.model_used, 0)
            prev_rating = ins.model_ratings.get(entry.model_used, 3.0)
            new_count = prev_count + 1
            ins.model_ratings[entry.model_used] = (prev_rating * prev_count + composite) / new_count
            ins.model_counts[entry.model_used] = new_count

        # Track optimal params from high-rated images
        if composite >= 4.0:
            if entry.guidance_scale > 0:
                if ins.optimal_guidance == 0:
                    ins.optimal_guidance = entry.guidance_scale
                else:
                    ins.optimal_guidance = ins.optimal_guidance * 0.9 + entry.guidance_scale * 0.1
            if entry.steps > 0:
                if ins.optimal_steps == 0:
                    ins.optimal_steps = entry.steps
                else:
                    ins.optimal_steps = int(ins.optimal_steps * 0.9 + entry.steps * 0.1)
            if entry.sampler:
                ins.optimal_sampler = entry.sampler

        # Track top keywords for this category
        if composite >= 3.5:
            keywords = extract_prompt_keywords(entry.prompt)
            for kw in keywords:
                if kw not in ins.top_keywords:
                    ins.top_keywords.append(kw)
            ins.top_keywords = ins.top_keywords[:30]

        # Auto-tune when enough data
        if ins.total_images >= MILESTONE_CATEGORY_TUNING and not ins.is_tuned:
            self._tune_category(cat)

    def _tune_category(self, category: str):
        """Auto-tune a category after reaching enough images."""
        ins = self._category_insights.get(category)
        if not ins or ins.total_images < MILESTONE_CATEGORY_TUNING:
            return

        # Find best model
        if ins.model_ratings:
            best = max(ins.model_ratings.items(), key=lambda x: x[1])
            ins.best_model = best[0]
            self._global.category_best_model[category] = best[0]
            logger.info(
                f"MILESTONE: Category '{category}' tuned! "
                f"Best model: {best[0]} (rating={best[1]:.2f}, "
                f"images={ins.total_images})"
            )

        ins.is_tuned = True

    # ─── Level 3: Prompt Intelligence ─────────────────────────

    def _update_prompt_intelligence(self, entry: FeedbackEntry, composite: float):
        """Learn which prompt keywords produce the best results."""
        keywords = extract_prompt_keywords(entry.prompt)

        for kw in keywords:
            self._keyword_ratings[kw].append(composite)
            # Keep only last 200 ratings per keyword
            if len(self._keyword_ratings[kw]) > 200:
                self._keyword_ratings[kw] = self._keyword_ratings[kw][-200:]

    def _get_global_top_keywords(self, n: int) -> List[Dict]:
        """Get globally top-performing keywords."""
        keyword_scores = []
        for kw, ratings in self._keyword_ratings.items():
            if len(ratings) >= 5:
                avg = sum(ratings) / len(ratings)
                keyword_scores.append({
                    'keyword': kw, 'avg_rating': round(avg, 2), 'count': len(ratings),
                })
        return sorted(keyword_scores, key=lambda x: x['avg_rating'], reverse=True)[:n]

    def get_prompt_suggestions(self, mode: str, category: str = '') -> List[str]:
        """Get prompt keyword suggestions based on learning."""
        suggestions = []

        # Category-specific keywords
        ins = self._category_insights.get(category)
        if ins and ins.top_keywords:
            suggestions.extend(ins.top_keywords[:5])

        # Global high-performing keywords
        top_global = self._get_global_top_keywords(10)
        for entry in top_global:
            if entry['keyword'] not in suggestions and entry['avg_rating'] >= 4.0:
                suggestions.append(entry['keyword'])

        return suggestions[:10]

    # ─── Level 4: Global Optimization ─────────────────────────

    def _update_global_optimization(self, entry: FeedbackEntry, composite: float):
        """Update global learning state."""
        self._global.total_images += 1

        # Update global avg
        n = self._total_feedback
        self._global_avg_rating = (self._global_avg_rating * (n - 1) + composite) / n if n > 0 else composite

        # Track model effectiveness globally
        if entry.model_used:
            prev = self._global.model_effectiveness.get(entry.model_used, 3.0)
            self._global.model_effectiveness[entry.model_used] = (prev * 0.95 + composite * 0.05)

    def _check_milestones(self):
        """Check and trigger auto-tuning milestones."""
        total = self._total_feedback

        # Milestone 1: 100 images → start per-mode tuning
        if total >= MILESTONE_MODE_TUNING and not self._global.milestone_100_reached:
            self._global.milestone_100_reached = True
            self._recalculate_mode_overrides()
            logger.info(f"MILESTONE REACHED: {MILESTONE_MODE_TUNING} images! Mode tuning activated.")

        # Milestone 2: 500 images → category-level model selection
        if total >= MILESTONE_CATEGORY_TUNING and not self._global.milestone_500_reached:
            self._global.milestone_500_reached = True
            for cat in self._category_insights:
                self._tune_category(cat)
            logger.info(f"MILESTONE REACHED: {MILESTONE_CATEGORY_TUNING} images! Category tuning activated.")

        # Milestone 3: 1000 images → full system optimization
        if total >= MILESTONE_FULL_OPTIMIZATION and not self._global.milestone_1000_reached:
            self._global.milestone_1000_reached = True
            self._full_system_optimization()
            logger.info(f"MILESTONE REACHED: {MILESTONE_FULL_OPTIMIZATION} images! Full optimization activated.")

        # Periodic recalculation
        if total - self._global.last_recalc_at >= RECALC_INTERVAL:
            self._recalculate_mode_overrides()
            self._global.last_recalc_at = total

    def _recalculate_mode_overrides(self):
        """Recalculate optimal parameters per mode from all feedback data."""
        mode_data: Dict[str, List[Tuple[float, FeedbackEntry]]] = defaultdict(list)

        for user_entries in self._entries.values():
            for entry in user_entries:
                composite = self._compute_composite_score(entry)
                if composite is not None:
                    mode_key = f"{entry.mode}_{entry.sub_mode}" if entry.sub_mode else entry.mode
                    mode_data[mode_key].append((composite, entry))

        for mode_key, data in mode_data.items():
            if len(data) < 20:
                continue

            # Find high-rated entries (top 30%)
            sorted_data = sorted(data, key=lambda x: x[0], reverse=True)
            top_count = max(5, len(sorted_data) // 3)
            top_entries = sorted_data[:top_count]

            # Average the params of top-rated entries
            guidances = [e.guidance_scale for _, e in top_entries if e.guidance_scale > 0]
            steps_list = [e.steps for _, e in top_entries if e.steps > 0]
            samplers = [e.sampler for _, e in top_entries if e.sampler]

            override = {}
            if guidances:
                avg_guidance = sum(guidances) / len(guidances)
                default_guidance = 4.5
                override['guidance_offset'] = round(avg_guidance - default_guidance, 2)
            if steps_list:
                avg_steps = sum(steps_list) / len(steps_list)
                default_steps = 20
                override['steps_offset'] = int(round(avg_steps - default_steps))
            if samplers:
                most_common = Counter(samplers).most_common(1)[0][0]
                override['sampler'] = most_common

            if override:
                self._global.mode_overrides[mode_key] = override

        logger.info(f"Mode overrides recalculated: {len(self._global.mode_overrides)} modes tuned")

    def _full_system_optimization(self):
        """Full system optimization at 1000+ images."""
        # Tune all categories
        for cat in self._category_insights:
            self._tune_category(cat)

        # Recalculate mode overrides
        self._recalculate_mode_overrides()

        # Log system state
        logger.info(
            f"FULL OPTIMIZATION COMPLETE: "
            f"{self._total_feedback} feedbacks, "
            f"{len(self._user_prefs)} users, "
            f"{len(self._category_insights)} categories, "
            f"{len(self._global.mode_overrides)} mode overrides, "
            f"{len(self._global.category_best_model)} category->model mappings"
        )

    # ─── Composite Score ───────────────────────────────────────

    def _compute_composite_score(self, entry: FeedbackEntry) -> Optional[float]:
        """Compute composite feedback score (1-5) from all signals."""
        score = 0.0
        weight_sum = 0.0

        if entry.user_rating > 0:
            score += entry.user_rating * SIGNAL_WEIGHTS['user_rating']
            weight_sum += SIGNAL_WEIGHTS['user_rating']

        if entry.liked is not None:
            like_score = 4.5 if entry.liked else 1.5
            score += like_score * SIGNAL_WEIGHTS['liked']
            weight_sum += SIGNAL_WEIGHTS['liked']

        if entry.downloaded:
            score += 4.0 * SIGNAL_WEIGHTS['downloaded']
            weight_sum += SIGNAL_WEIGHTS['downloaded']

        if entry.shared:
            score += 5.0 * SIGNAL_WEIGHTS['shared']
            weight_sum += SIGNAL_WEIGHTS['shared']

        if entry.regenerated:
            score += 2.0 * abs(SIGNAL_WEIGHTS['regenerated'])
            weight_sum += abs(SIGNAL_WEIGHTS['regenerated'])

        if entry.time_spent_viewing > 3.0:
            view_score = min(4.5, 3.0 + entry.time_spent_viewing / 10.0)
            score += view_score * SIGNAL_WEIGHTS['time_viewed']
            weight_sum += SIGNAL_WEIGHTS['time_viewed']

        if weight_sum == 0:
            return None
        return score / weight_sum

    # ─── Helpers ───────────────────────────────────────────────

    def _get_top_modes(self, prefs: UserPreferences, n: int) -> List[Dict]:
        modes = [
            {'mode': k, 'avg_rating': round(v, 2), 'count': prefs.mode_counts.get(k, 0)}
            for k, v in prefs.mode_ratings.items()
            if prefs.mode_counts.get(k, 0) >= 2
        ]
        return sorted(modes, key=lambda x: x['avg_rating'], reverse=True)[:n]

    def _get_top_categories(self, prefs: UserPreferences, n: int) -> List[Dict]:
        cats = [
            {'category': k, 'avg_rating': round(v, 2)}
            for k, v in prefs.category_ratings.items()
        ]
        return sorted(cats, key=lambda x: x['avg_rating'], reverse=True)[:n]

    # ─── Persistence ──────────────────────────────────────────

    async def save_to_disk(self):
        """Persist all learning data to disk."""
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

        # Save user preferences
        prefs_data = {uid: prefs.to_dict() for uid, prefs in self._user_prefs.items()}
        (FEEDBACK_DIR / 'user_preferences.json').write_text(
            json.dumps(prefs_data, indent=2, default=str)
        )

        # Save category insights
        cat_data = {cat: asdict(ins) for cat, ins in self._category_insights.items()}
        (FEEDBACK_DIR / 'category_insights.json').write_text(
            json.dumps(cat_data, indent=2, default=str)
        )

        # Save global optimization state
        global_data = asdict(self._global)
        (FEEDBACK_DIR / 'global_optimization.json').write_text(
            json.dumps(global_data, indent=2, default=str)
        )

        # Save keyword ratings
        kw_data = {k: ratings[-50:] for k, ratings in self._keyword_ratings.items()}
        (FEEDBACK_DIR / 'keyword_ratings.json').write_text(
            json.dumps(kw_data, indent=2)
        )

        logger.info(
            f"Learning data saved: {len(self._user_prefs)} users, "
            f"{len(self._category_insights)} categories, "
            f"{self._total_feedback} total feedback"
        )

    async def load_from_disk(self):
        """Load persisted learning data."""
        # Load user preferences
        prefs_file = FEEDBACK_DIR / 'user_preferences.json'
        if prefs_file.exists():
            try:
                data = json.loads(prefs_file.read_text())
                for uid, pdata in data.items():
                    prefs = UserPreferences(**{
                        k: v for k, v in pdata.items()
                        if k in UserPreferences.__dataclass_fields__
                    })
                    self._user_prefs[uid] = prefs
            except Exception as e:
                logger.error(f"Failed to load user preferences: {e}")

        # Load category insights
        cat_file = FEEDBACK_DIR / 'category_insights.json'
        if cat_file.exists():
            try:
                data = json.loads(cat_file.read_text())
                for cat, cdata in data.items():
                    ins = CategoryInsight(**{
                        k: v for k, v in cdata.items()
                        if k in CategoryInsight.__dataclass_fields__
                    })
                    self._category_insights[cat] = ins
            except Exception as e:
                logger.error(f"Failed to load category insights: {e}")

        # Load global optimization
        global_file = FEEDBACK_DIR / 'global_optimization.json'
        if global_file.exists():
            try:
                data = json.loads(global_file.read_text())
                self._global = GlobalOptimization(**{
                    k: v for k, v in data.items()
                    if k in GlobalOptimization.__dataclass_fields__
                })
                self._total_feedback = self._global.total_feedback
            except Exception as e:
                logger.error(f"Failed to load global optimization: {e}")

        # Load keyword ratings
        kw_file = FEEDBACK_DIR / 'keyword_ratings.json'
        if kw_file.exists():
            try:
                data = json.loads(kw_file.read_text())
                for k, v in data.items():
                    self._keyword_ratings[k] = v
            except Exception as e:
                logger.error(f"Failed to load keyword ratings: {e}")

        logger.info(
            f"Learning data loaded: {len(self._user_prefs)} users, "
            f"{len(self._category_insights)} categories"
        )


# Singleton
feedback_learning = FeedbackLearningEngine()

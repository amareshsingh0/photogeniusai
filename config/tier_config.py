"""
Tier configuration and credit cost calculation.

Used by TierEnforcer (apps/api) and orchestrator for resolution caps,
identity limits, feature gates, and credit deduction.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, Optional

__all__ = [
    "SubscriptionTier",
    "TIER_LIMITS",
    "get_tier_limits",
    "calculate_credit_cost",
    "normalize_tier",
]


class SubscriptionTier(str, Enum):
    FREE = "free"
    HOBBY = "hobby"
    PRO = "pro"
    STUDIO = "studio"
    ENTERPRISE = "enterprise"


TIER_LIMITS: Dict[SubscriptionTier, Dict[str, Any]] = {
    SubscriptionTier.FREE: {
        "max_resolution": 1024,
        "max_identities": 0,
        "max_images_per_gen": 4,
        "max_gens_per_day": 10,
        "credit_cost_multiplier": 1.0,
        "features": {
            "api_access": False,
            "realtime": False,
            "ultra_high_res": False,
            "creative_engine": False,
            "composition": False,
            "refinement": True,
            "batch_generation": False,
            "custom_lora": False,
            "watermark_free": False,
        },
        "credits_per_month": 100,
    },
    SubscriptionTier.HOBBY: {
        "max_resolution": 1024,
        "max_identities": 1,
        "max_images_per_gen": 4,
        "max_gens_per_day": 50,
        "credit_cost_multiplier": 0.9,
        "features": {
            "api_access": False,
            "realtime": True,
            "ultra_high_res": False,
            "creative_engine": True,
            "composition": False,
            "refinement": True,
            "batch_generation": False,
            "custom_lora": False,
            "watermark_free": True,
        },
        "credits_per_month": 500,
    },
    SubscriptionTier.PRO: {
        "max_resolution": 2048,
        "max_identities": 5,
        "max_images_per_gen": 8,
        "max_gens_per_day": 200,
        "credit_cost_multiplier": 0.8,
        "features": {
            "api_access": True,
            "realtime": True,
            "ultra_high_res": True,
            "creative_engine": True,
            "composition": True,
            "refinement": True,
            "batch_generation": True,
            "custom_lora": True,
            "watermark_free": True,
        },
        "credits_per_month": 2000,
    },
    SubscriptionTier.STUDIO: {
        "max_resolution": 4096,
        "max_identities": -1,
        "max_images_per_gen": 16,
        "max_gens_per_day": -1,
        "credit_cost_multiplier": 0.7,
        "features": {
            "api_access": True,
            "realtime": True,
            "ultra_high_res": True,
            "creative_engine": True,
            "composition": True,
            "refinement": True,
            "batch_generation": True,
            "custom_lora": True,
            "watermark_free": True,
            "priority_queue": True,
        },
        "credits_per_month": 10000,
    },
    SubscriptionTier.ENTERPRISE: {
        "max_resolution": 4096,
        "max_identities": -1,
        "max_images_per_gen": 32,
        "max_gens_per_day": -1,
        "credit_cost_multiplier": 0.6,
        "features": {
            "api_access": True,
            "realtime": True,
            "ultra_high_res": True,
            "creative_engine": True,
            "composition": True,
            "refinement": True,
            "batch_generation": True,
            "custom_lora": True,
            "watermark_free": True,
            "priority_queue": True,
            "white_label": True,
            "dedicated_support": True,
        },
        "credits_per_month": -1,
    },
}

# Map DB/API tier strings (e.g. FAST, PREMIUM) to SubscriptionTier
TIER_ALIASES: Dict[str, SubscriptionTier] = {
    "free": SubscriptionTier.FREE,
    "hobby": SubscriptionTier.HOBBY,
    "fast": SubscriptionTier.HOBBY,
    "pro": SubscriptionTier.PRO,
    "premium": SubscriptionTier.PRO,
    "studio": SubscriptionTier.STUDIO,
    "enterprise": SubscriptionTier.ENTERPRISE,
}


def normalize_tier(tier: Optional[str]) -> SubscriptionTier:
    """Map tier string to SubscriptionTier. Default FREE."""
    if not tier:
        return SubscriptionTier.FREE
    k = str(tier).lower().strip()
    return TIER_ALIASES.get(k, SubscriptionTier.FREE)


def get_tier_limits(tier: SubscriptionTier) -> Dict[str, Any]:
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE]).copy()


def calculate_credit_cost(
    tier: SubscriptionTier,
    num_images: int,
    resolution: int,
    quality_tier: str,
    use_identity: bool,
) -> int:
    """
    Credit cost for a generation.

    Base: 1 per image. Resolution: 1.5× >1024, 2× >2048.
    Quality: 1× FAST/STANDARD, 1.2× BALANCED, 1.5× PREMIUM, 2× ULTRA.
    Identity: +0.5 per image. Tier discount applied last.
    """
    base = float(num_images)
    if resolution > 2048:
        base *= 2.0
    elif resolution > 1024:
        base *= 1.5
    q = {
        "FAST": 1.0,
        "STANDARD": 1.0,
        "BALANCED": 1.2,
        "PREMIUM": 1.5,
        "ULTRA": 2.0,
    }
    base *= q.get((quality_tier or "").upper(), 1.0)
    if use_identity:
        base += num_images * 0.5
    limits = get_tier_limits(tier)
    mult = limits.get("credit_cost_multiplier", 1.0)
    return max(1, int(math.ceil(base * mult)))

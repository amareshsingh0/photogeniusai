"""
Tier-based limits and credit enforcement.

Uses config.tier_config for limits and cost calculation.
Enforces resolution, identity, daily gens, feature access, credits.
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import text  # type: ignore[reportMissingImports]
from sqlalchemy.ext.asyncio import AsyncSession  # type: ignore[reportMissingImports]

from config.tier_config import (
    SubscriptionTier,
    TIER_LIMITS,
    get_tier_limits,
    calculate_credit_cost,
    normalize_tier,
)

logger = logging.getLogger(__name__)

# Set True via DISABLE_CREDIT_DEDUCTION=1 to bypass deduction (dev). Default: deduction enabled.
SKIP_CREDIT_DEDUCTION = os.environ.get("DISABLE_CREDIT_DEDUCTION", "").strip() in ("1", "true", "yes")


async def fetch_user_context(
    db: AsyncSession,
    clerk_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch user id, tier, credits_balance, identity_count, today_generations.
    Uses raw SQL; users table has id, clerk_id, credits_balance. tier if present else 'free'.
    """
    r = await db.execute(
        text("""
            SELECT id, credits_balance FROM users
            WHERE clerk_id = :clerk_id
        """),
        {"clerk_id": clerk_id},
    )
    row = r.fetchone()
    if not row:
        return None
    user_id = row.id
    tier_val = "free"
    # Identity count (identities table)
    rc = await db.execute(
        text("""
            SELECT COUNT(*) FROM identities
            WHERE user_id = :user_id AND (is_deleted IS NOT TRUE OR is_deleted IS NULL)
        """),
        {"user_id": user_id},
    )
    identity_count = rc.scalar() or 0
    # Today's generations (generation_usage); ignore if table missing
    today = date.today().isoformat()
    try:
        ru = await db.execute(
            text("""
                SELECT count FROM generation_usage
                WHERE user_id = :user_id AND usage_date = :d
            """),
            {"user_id": user_id, "d": today},
        )
        row_u = ru.fetchone()
        today_gens = int(getattr(row_u, "count", 0) or 0)
    except Exception:
        today_gens = 0
    return {
        "user_id": user_id,
        "clerk_id": clerk_id,
        "tier": tier_val,
        "credits_balance": int(row.credits_balance or 0),
        "identity_count": identity_count,
        "today_generations": today_gens,
    }


def check_and_enforce(
    user_ctx: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Check tier limits and credits. Returns {allowed, reason?, cost, upgrade_tier?, add_credits_url?}.
    """
    tier = normalize_tier(user_ctx.get("tier"))
    limits = get_tier_limits(tier)
    width = int(params.get("width") or 1024)
    height = int(params.get("height") or 1024)
    requested_res = max(width, height)
    max_res = limits["max_resolution"]
    if requested_res > max_res:
        return {
            "allowed": False,
            "reason": f"Resolution {requested_res}px exceeds {tier.value} tier limit ({max_res}px). Upgrade to access higher resolutions.",
            "upgrade_tier": "pro" if tier == SubscriptionTier.HOBBY else "studio",
        }
    if params.get("identity_id"):
        identity_count = int(user_ctx.get("identity_count") or 0)
        max_id = limits["max_identities"]
        if max_id >= 0 and identity_count >= max_id:
            return {
                "allowed": False,
                "reason": f"Identity limit reached ({max_id} for {tier.value} tier). Upgrade to create more identities.",
                "upgrade_tier": "hobby" if tier == SubscriptionTier.FREE else "pro",
            }
    max_gens = limits["max_gens_per_day"]
    if max_gens > 0:
        today_gens = int(user_ctx.get("today_generations") or 0)
        if today_gens >= max_gens:
            return {
                "allowed": False,
                "reason": f"Daily generation limit reached ({max_gens}). Resets at midnight UTC.",
                "upgrade_tier": "pro" if tier in (SubscriptionTier.FREE, SubscriptionTier.HOBBY) else "studio",
            }
    features = limits.get("features") or {}
    quality = (params.get("quality_tier") or "BALANCED").upper()
    if quality == "FAST" and not features.get("realtime", True):
        return {
            "allowed": False,
            "reason": "Realtime generation requires Hobby tier or higher.",
            "upgrade_tier": "hobby",
        }
    if requested_res > 2048 and not features.get("ultra_high_res", False):
        return {
            "allowed": False,
            "reason": "4K generation requires Pro tier or higher.",
            "upgrade_tier": "pro",
        }
    if params.get("style") and not features.get("creative_engine", True):
        return {
            "allowed": False,
            "reason": "Style presets require Hobby tier or higher.",
            "upgrade_tier": "hobby",
        }
    num_images = int(params.get("num_images") or params.get("num_candidates") or 2)
    if num_images > limits["max_images_per_gen"]:
        return {
            "allowed": False,
            "reason": f"Max {limits['max_images_per_gen']} images per generation for {tier.value} tier.",
            "upgrade_tier": "pro" if tier in (SubscriptionTier.FREE, SubscriptionTier.HOBBY) else "studio",
        }
    cost = calculate_credit_cost(
        tier=tier,
        num_images=num_images,
        resolution=requested_res,
        quality_tier=quality,
        use_identity=bool(params.get("identity_id")),
    )
    balance = int(user_ctx.get("credits_balance") or 0)
    if balance < cost:
        return {
            "allowed": False,
            "reason": f"Insufficient credits. Need {cost}, have {balance}.",
            "cost": cost,
            "add_credits_url": "/pricing",
        }
    return {
        "allowed": True,
        "cost": cost,
        "limits": limits,
        "tier": tier,
    }


async def deduct_credits(
    db: AsyncSession,
    user_id: UUID,
    cost: int,
    generation_id: str,
) -> None:
    """Deduct credits and log transaction. No-op if SKIP_CREDIT_DEDUCTION."""
    if SKIP_CREDIT_DEDUCTION or cost <= 0:
        logger.info("[DEV] Credit deduction skipped: cost=%s", cost)
        return
    try:
        r = await db.execute(
            text("""
                UPDATE users
                SET credits_balance = credits_balance - :cost
                WHERE id = :user_id
                RETURNING credits_balance
            """),
            {"cost": cost, "user_id": str(user_id)},
        )
        row = r.fetchone()
        if not row:
            raise ValueError(f"User {user_id} not found for credit deduction")
        balance_after = int(row.credits_balance)
        await db.execute(
            text("""
                INSERT INTO credit_transactions
                (user_id, amount, transaction_type, description, balance_after, reference_id, created_at)
                VALUES (:user_id, :amount, 'generation', :desc, :balance_after, :ref, NOW())
            """),
            {
                "user_id": str(user_id),
                "amount": -cost,
                "desc": f"Image generation (ID: {generation_id})",
                "balance_after": balance_after,
                "ref": generation_id,
            },
        )
        await db.commit()
        logger.info("Deducted %d credits from user %s, balance=%d", cost, user_id, balance_after)
    except Exception as e:
        await db.rollback()
        raise


async def increment_generation_usage(db: AsyncSession, user_id: UUID) -> None:
    """Increment today's generation count for user. No-op if table missing. Caller commits."""
    today = date.today().isoformat()
    try:
        await db.execute(
            text("""
                INSERT INTO generation_usage (user_id, usage_date, count)
                VALUES (:user_id, :d, 1)
                ON CONFLICT (user_id, usage_date) DO UPDATE SET count = generation_usage.count + 1
            """),
            {"user_id": str(user_id), "d": today},
        )
    except Exception as e:
        logger.warning("generation_usage increment failed (table may not exist): %s", e)
        raise


async def apply_generation_charges(
    db: AsyncSession,
    user_id: UUID,
    cost: int,
    generation_id: str,
) -> None:
    """Deduct credits, log transaction, increment usage. Commits once. No-op if SKIP_CREDIT_DEDUCTION."""
    if SKIP_CREDIT_DEDUCTION or cost <= 0:
        logger.info("[DEV] Credit deduction skipped: cost=%s", cost)
        return
    try:
        r = await db.execute(
            text("""
                UPDATE users
                SET credits_balance = credits_balance - :cost
                WHERE id = :user_id
                RETURNING credits_balance
            """),
            {"cost": cost, "user_id": str(user_id)},
        )
        row = r.fetchone()
        if not row:
            raise ValueError(f"User {user_id} not found for credit deduction")
        balance_after = int(row.credits_balance)
        await db.execute(
            text("""
                INSERT INTO credit_transactions
                (user_id, amount, transaction_type, description, balance_after, reference_id, created_at)
                VALUES (:user_id, :amount, 'generation', :desc, :balance_after, :ref, NOW())
            """),
            {
                "user_id": str(user_id),
                "amount": -cost,
                "desc": f"Image generation (ID: {generation_id})",
                "balance_after": balance_after,
                "ref": generation_id,
            },
        )
        today = date.today().isoformat()
        try:
            await db.execute(
                text("""
                    INSERT INTO generation_usage (user_id, usage_date, count)
                    VALUES (:user_id, :d, 1)
                    ON CONFLICT (user_id, usage_date) DO UPDATE SET count = generation_usage.count + 1
                """),
                {"user_id": str(user_id), "d": today},
            )
        except Exception as ue:
            logger.warning("generation_usage increment failed (table may not exist): %s", ue)
        await db.commit()
        logger.info("Deducted %d credits from user %s, balance=%d", cost, user_id, balance_after)
    except Exception as e:
        await db.rollback()
        raise

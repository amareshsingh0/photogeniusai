"""
Brand Intelligence Service — Database CRUD operations

Handles:
1. Storing known brands (Nike, Apple, Coca-Cola, etc.)
2. User custom brand kits
3. Auto-load from database by brand name
4. Usage tracking
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Import Prisma client
try:
    from prisma import Prisma
    from prisma.models import BrandIntelligence
    _PRISMA_AVAILABLE = True
except ImportError as e:
    logger.warning("[brand_intel_service] Prisma not available: %s", e)
    _PRISMA_AVAILABLE = False


def _slugify(brand_name: str) -> str:
    """Convert brand name to URL-safe slug."""
    slug = brand_name.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


async def get_brand_by_name(brand_name: str) -> Optional[Dict]:
    """
    Load brand intelligence from database by brand name.

    Returns: Full brand_intelligence dict or None if not found.
    """
    if not _PRISMA_AVAILABLE or not brand_name:
        return None

    try:
        prisma = Prisma()
        await prisma.connect()

        brand_slug = _slugify(brand_name)

        # Try exact slug match first
        brand = await prisma.brandintelligence.find_unique(
            where={"brandSlug": brand_slug}
        )

        # Fallback: case-insensitive name match
        if not brand:
            brand = await prisma.brandintelligence.find_first(
                where={"brandName": {"equals": brand_name, "mode": "insensitive"}}
            )

        await prisma.disconnect()

        if not brand:
            return None

        # Convert Prisma model to dict
        return {
            "brand_name": brand.brandName,
            "palette": brand.palette,
            "typography": brand.typography,
            "equity_elements": brand.equityElements,
            "competitive_position": brand.competitivePosition,
            "seasonal_palettes": brand.seasonalPalettes,
            "primary_color": brand.primaryColor,
            "secondary_color": brand.secondaryColor,
            "logo_url": brand.logoUrl,
            "tagline": brand.tagline,
            "font_style": brand.fontStyle,
            "tone": brand.tone,
            "confidence_level": brand.confidenceLevel,
            "source_type": brand.sourceType,
        }

    except Exception as e:
        logger.error("[brand_intel_service] get_brand_by_name failed: %s", e)
        return None


async def save_brand_intelligence(
    brand_name: str,
    palette: Dict,
    typography: Optional[Dict] = None,
    equity_elements: Optional[Dict] = None,
    competitive_position: Optional[Dict] = None,
    seasonal_palettes: Optional[Dict] = None,
    primary_color: Optional[str] = None,
    secondary_color: Optional[str] = None,
    logo_url: Optional[str] = None,
    tagline: Optional[str] = None,
    font_style: Optional[str] = None,
    tone: Optional[str] = None,
    industry: Optional[str] = None,
    user_id: Optional[str] = None,
    is_global: bool = False,
    confidence_level: str = "inferred",
    source_type: str = "ai_generated",
) -> Optional[str]:
    """
    Save or update brand intelligence in database.

    Returns: brand_intelligence ID or None if failed.
    """
    if not _PRISMA_AVAILABLE or not brand_name:
        return None

    try:
        prisma = Prisma()
        await prisma.connect()

        brand_slug = _slugify(brand_name)

        # Check if exists
        existing = await prisma.brandintelligence.find_unique(
            where={"brandSlug": brand_slug}
        )

        if existing:
            # Update existing
            brand = await prisma.brandintelligence.update(
                where={"id": existing.id},
                data={
                    "palette": palette,
                    "typography": typography,
                    "equityElements": equity_elements,
                    "competitivePosition": competitive_position,
                    "seasonalPalettes": seasonal_palettes,
                    "primaryColor": primary_color,
                    "secondaryColor": secondary_color,
                    "logoUrl": logo_url,
                    "tagline": tagline,
                    "fontStyle": font_style,
                    "tone": tone,
                    "industry": industry,
                    "confidenceLevel": confidence_level,
                    "sourceType": source_type,
                    "updatedAt": datetime.utcnow(),
                }
            )
            logger.info("[brand_intel_service] Updated brand: %s", brand_name)
        else:
            # Create new
            brand = await prisma.brandintelligence.create(
                data={
                    "brandName": brand_name,
                    "brandSlug": brand_slug,
                    "industry": industry,
                    "userId": user_id,
                    "isGlobal": is_global,
                    "palette": palette,
                    "typography": typography,
                    "equityElements": equity_elements,
                    "competitivePosition": competitive_position,
                    "seasonalPalettes": seasonal_palettes,
                    "primaryColor": primary_color,
                    "secondaryColor": secondary_color,
                    "logoUrl": logo_url,
                    "tagline": tagline,
                    "fontStyle": font_style,
                    "tone": tone,
                    "confidenceLevel": confidence_level,
                    "sourceType": source_type,
                }
            )
            logger.info("[brand_intel_service] Created brand: %s", brand_name)

        await prisma.disconnect()
        return brand.id

    except Exception as e:
        logger.error("[brand_intel_service] save_brand_intelligence failed: %s", e)
        return None


async def increment_brand_usage(brand_name: str) -> None:
    """Track brand usage (increment usageCount, update lastUsedAt)."""
    if not _PRISMA_AVAILABLE or not brand_name:
        return

    try:
        prisma = Prisma()
        await prisma.connect()

        brand_slug = _slugify(brand_name)

        await prisma.brandintelligence.update_many(
            where={"brandSlug": brand_slug},
            data={
                "usageCount": {"increment": 1},
                "lastUsedAt": datetime.utcnow(),
            }
        )

        await prisma.disconnect()

    except Exception as e:
        logger.debug("[brand_intel_service] increment_brand_usage failed: %s", e)


async def list_global_brands(limit: int = 100) -> List[Dict]:
    """List all global known brands."""
    if not _PRISMA_AVAILABLE:
        return []

    try:
        prisma = Prisma()
        await prisma.connect()

        brands = await prisma.brandintelligence.find_many(
            where={"isGlobal": True},
            order_by={"usageCount": "desc"},
            take=limit,
        )

        await prisma.disconnect()

        return [
            {
                "brand_name": b.brandName,
                "brand_slug": b.brandSlug,
                "industry": b.industry,
                "primary_color": b.primaryColor,
                "usage_count": b.usageCount,
            }
            for b in brands
        ]

    except Exception as e:
        logger.error("[brand_intel_service] list_global_brands failed: %s", e)
        return []


async def list_user_brands(user_id: str, limit: int = 50) -> List[Dict]:
    """List user's custom brand kits."""
    if not _PRISMA_AVAILABLE or not user_id:
        return []

    try:
        prisma = Prisma()
        await prisma.connect()

        brands = await prisma.brandintelligence.find_many(
            where={"userId": user_id},
            order_by={"lastUsedAt": "desc"},
            take=limit,
        )

        await prisma.disconnect()

        return [
            {
                "brand_name": b.brandName,
                "brand_slug": b.brandSlug,
                "industry": b.industry,
                "primary_color": b.primaryColor,
                "logo_url": b.logoUrl,
                "last_used_at": b.lastUsedAt,
            }
            for b in brands
        ]

    except Exception as e:
        logger.error("[brand_intel_service] list_user_brands failed: %s", e)
        return []


async def delete_brand(brand_slug: str, user_id: Optional[str] = None) -> bool:
    """Delete brand (only user's own brands, not global)."""
    if not _PRISMA_AVAILABLE or not brand_slug:
        return False

    try:
        prisma = Prisma()
        await prisma.connect()

        # Only delete user's own brands or non-global brands
        where_clause = {"brandSlug": brand_slug, "isGlobal": False}
        if user_id:
            where_clause["userId"] = user_id

        await prisma.brandintelligence.delete_many(where=where_clause)

        await prisma.disconnect()
        return True

    except Exception as e:
        logger.error("[brand_intel_service] delete_brand failed: %s", e)
        return False


# Export
__all__ = [
    "get_brand_by_name",
    "save_brand_intelligence",
    "increment_brand_usage",
    "list_global_brands",
    "list_user_brands",
    "delete_brand",
]

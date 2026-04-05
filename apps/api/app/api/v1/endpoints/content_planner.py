"""
Content Planner API
POST /api/v1/content/plan — AI-generated 30-day content calendar
"""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import CurrentUserId
from app.core.security import require_auth
from app.services.agents.task_planner import generate_content_calendar

logger = logging.getLogger(__name__)
router = APIRouter()


class ContentPlanRequest(BaseModel):
    brand_name:    str           = Field(default="My Brand")
    brand_tone:    str           = Field(default="professional")
    industry:      str           = Field(default="Technology / SaaS")
    platform:      str           = Field(default="instagram")
    month:         int           = Field(default_factory=lambda: date.today().month, ge=1, le=12)
    year:          int           = Field(default_factory=lambda: date.today().year, ge=2024, le=2030)
    primary_color: Optional[str] = Field(default=None)
    custom_notes:  Optional[str] = Field(default=None, max_length=500)


class ContentPlanResponse(BaseModel):
    success:  bool = True
    calendar: list = []
    count:    int  = 0


@router.post(
    "/plan",
    response_model=ContentPlanResponse,
    summary="Generate 30-day content calendar",
)
async def create_content_plan(
    req: ContentPlanRequest,
    user_id: CurrentUserId,
) -> ContentPlanResponse:
    require_auth(user_id)
    try:
        calendar = generate_content_calendar(
            brand_name=req.brand_name,
            brand_tone=req.brand_tone,
            industry=req.industry,
            platform=req.platform,
            month=req.month,
            year=req.year,
            primary_color=req.primary_color,
            custom_notes=req.custom_notes,
        )
        return ContentPlanResponse(success=True, calendar=calendar, count=len(calendar))
    except Exception as e:
        logger.error("content_plan error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

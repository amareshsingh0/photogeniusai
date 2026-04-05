"""
AI Content Planner Agent
POST /api/v1/content/plan

Given brand info + platform + month → generate a 30-day content calendar as JSON.
Uses Gemini 2.5 Flash (same key as design_agent_chain).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PLATFORMS = {"instagram", "linkedin", "twitter", "facebook", "youtube", "general"}

_CONTENT_TYPES = [
    "product_showcase", "behind_the_scenes", "tip_or_tutorial",
    "testimonial", "promotion_sale", "announcement", "poll_question",
    "quote_card", "carousel", "reel_idea", "event_promo", "ugc_repost",
]

_SYSTEM_PROMPT = """You are a world-class social media content strategist and creative director.
Generate a 30-day content calendar that:
- Mixes content types to avoid repetition (max 3 of same type in a row)
- Aligns with the brand tone and industry
- Includes culturally relevant Indian festivals when appropriate
- Varies posting frequency (skip some days for breathing room)
- Each entry is actionable with a specific visual prompt for image generation

Return ONLY valid JSON in this exact schema (array of objects):
[
  {
    "date": "2026-04-01",
    "day_of_week": "Wednesday",
    "platform": "instagram",
    "content_type": "product_showcase",
    "prompt": "Photorealistic product shot of [product] on clean white marble surface...",
    "caption": "Introducing our newest...",
    "hashtags": ["#brand", "#product"],
    "cta": "Shop now",
    "is_festival": false,
    "festival_name": null
  }
]
Return only the JSON array, nothing else."""


def _call_gemini(prompt_text: str) -> str:
    """Call Gemini 2.5 Flash and return raw text response."""
    import urllib.request
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192},
        "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
    }).encode()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash-preview-04-17:generateContent?key={key}"
    )
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    return data["candidates"][0]["content"]["parts"][0]["text"]


def _parse_calendar(raw: str) -> List[Dict[str, Any]]:
    """Extract JSON array from Gemini response."""
    raw = raw.strip()
    # Strip markdown code fences
    for fence in ("```json", "```"):
        if raw.startswith(fence):
            raw = raw[len(fence):]
            break
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    result = json.loads(raw)
    if not isinstance(result, list):
        raise ValueError("Expected JSON array")
    return result


def _fallback_calendar(
    start_date: date,
    platform: str,
    brand_name: str,
) -> List[Dict[str, Any]]:
    """Generate a minimal deterministic calendar when Gemini is unavailable."""
    calendar = []
    types = _CONTENT_TYPES
    for i in range(30):
        d = start_date + timedelta(days=i)
        if d.weekday() == 6 and i % 7 != 0:  # skip some Sundays
            continue
        ct = types[i % len(types)]
        calendar.append({
            "date": d.isoformat(),
            "day_of_week": d.strftime("%A"),
            "platform": platform,
            "content_type": ct,
            "prompt": f"{brand_name} {ct.replace('_', ' ')} for {d.strftime('%B %d')}",
            "caption": f"[Edit caption for {ct.replace('_', ' ')}]",
            "hashtags": [f"#{brand_name.lower().replace(' ', '')}", f"#{ct.replace('_', '')}"],
            "cta": "Learn more",
            "is_festival": False,
            "festival_name": None,
        })
    return calendar


def generate_content_calendar(
    brand_name: str,
    brand_tone: str,
    industry: str,
    platform: str,
    month: int,
    year: int,
    primary_color: Optional[str] = None,
    custom_notes: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Main entry point. Returns 30-day content calendar as a list of dicts.
    Falls back to deterministic placeholder calendar on any error.
    """
    platform = platform.lower() if platform.lower() in _PLATFORMS else "general"
    start_date = date(year, month, 1)

    user_prompt = (
        f"Brand: {brand_name}\n"
        f"Industry: {industry}\n"
        f"Tone: {brand_tone}\n"
        f"Platform: {platform}\n"
        f"Month: {start_date.strftime('%B %Y')}\n"
        f"Primary color: {primary_color or 'not specified'}\n"
        f"Additional notes: {custom_notes or 'none'}\n\n"
        f"Generate a 30-day content calendar starting {start_date.isoformat()}."
    )

    try:
        raw = _call_gemini(user_prompt)
        return _parse_calendar(raw)
    except Exception as exc:
        logger.warning("task_planner Gemini error — using fallback: %s", exc)
        return _fallback_calendar(start_date, platform, brand_name)

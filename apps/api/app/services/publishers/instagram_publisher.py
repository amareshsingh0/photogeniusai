"""
Instagram Publisher — Meta Graph API

Supports:
  - Single image post (most common)
  - Story (container + publish)

OAuth flow (delegated to frontend — we only store access_token):
  User.preferences.integrations.instagram = {
    access_token: str,
    user_id: str (IG Business Account ID),
    expires_at: ISO timestamp,
  }

Usage:
    publisher = InstagramPublisher(access_token, ig_user_id)
    result = await publisher.post_image(image_url, caption)
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.facebook.com/v19.0"


class InstagramPublisher:
    def __init__(self, access_token: str, ig_user_id: str):
        self.access_token = access_token
        self.ig_user_id   = ig_user_id

    async def post_image(
        self,
        image_url: str,
        caption: str,
        *,
        is_story: bool = False,
    ) -> dict:
        """
        Publish a single image to Instagram Business feed or Story.

        Step 1: Create media container → get container_id
        Step 2: Publish container → get media_id

        Returns: { success, media_id, permalink, error }
        """
        media_type = "IMAGE"
        params_create: dict = {
            "image_url":    image_url,
            "caption":      caption if not is_story else "",
            "media_type":   media_type,
            "access_token": self.access_token,
        }
        if is_story:
            params_create["media_type"] = "STORIES"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # ── Step 1: Create container ──────────────────────────────────────
            r1 = await client.post(
                f"{_GRAPH_BASE}/{self.ig_user_id}/media",
                params=params_create,
            )
            r1.raise_for_status()
            container_id = r1.json().get("id")
            if not container_id:
                return {"success": False, "error": f"No container id: {r1.text}"}

            # ── Step 2: Publish ───────────────────────────────────────────────
            r2 = await client.post(
                f"{_GRAPH_BASE}/{self.ig_user_id}/media_publish",
                params={
                    "creation_id":  container_id,
                    "access_token": self.access_token,
                },
            )
            r2.raise_for_status()
            media_id = r2.json().get("id")

            # ── Step 3: Fetch permalink ───────────────────────────────────────
            permalink = ""
            if media_id:
                try:
                    r3 = await client.get(
                        f"{_GRAPH_BASE}/{media_id}",
                        params={"fields": "permalink", "access_token": self.access_token},
                    )
                    permalink = r3.json().get("permalink", "")
                except Exception:
                    pass

            logger.info("[instagram] published media_id=%s permalink=%s", media_id, permalink)
            return {
                "success":   True,
                "media_id":  media_id,
                "permalink": permalink,
                "platform":  "instagram",
            }

    async def verify_token(self) -> bool:
        """Quick token validity check."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"{_GRAPH_BASE}/me",
                    params={"access_token": self.access_token, "fields": "id,name"},
                )
                return r.status_code == 200
        except Exception:
            return False

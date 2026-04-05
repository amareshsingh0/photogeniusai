"""
LinkedIn Publisher — LinkedIn API v2

Supports:
  - Single image post (ugcPosts)

OAuth flow (delegated to frontend — we only store access_token):
  User.preferences.integrations.linkedin = {
    access_token: str,
    person_urn: str (urn:li:person:xxxxx),
    expires_at: ISO timestamp,
  }

Usage:
    publisher = LinkedInPublisher(access_token, person_urn)
    result = await publisher.post_image(image_url, text)
"""
from __future__ import annotations

import base64
import logging

import httpx

logger = logging.getLogger(__name__)

_LI_API = "https://api.linkedin.com/v2"
_LI_UPLOAD = "https://api.linkedin.com/rest"


class LinkedInPublisher:
    def __init__(self, access_token: str, person_urn: str):
        self.access_token = access_token
        self.person_urn   = person_urn  # e.g. "urn:li:person:AaBbCcDd"

    def _headers(self) -> dict:
        return {
            "Authorization":  f"Bearer {self.access_token}",
            "Content-Type":   "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202310",
        }

    async def _upload_image(self, client: httpx.AsyncClient, image_url: str) -> str:
        """
        Upload image to LinkedIn Asset API and return asset URN.

        Step 1: Register upload
        Step 2: PUT binary to upload URL
        Step 3: Return asset URN
        """
        # ── Step 1: Register ─────────────────────────────────────────────────
        reg_payload = {
            "registerUploadRequest": {
                "owner": self.person_urn,
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "serviceRelationships": [
                    {"identifier": "urn:li:userGeneratedContent", "relationshipType": "OWNER"}
                ],
            }
        }
        r1 = await client.post(
            f"{_LI_API}/assets?action=registerUpload",
            headers=self._headers(),
            json=reg_payload,
        )
        r1.raise_for_status()
        data = r1.json()
        upload_url = data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn = data["value"]["asset"]

        # ── Step 2: Fetch image bytes ─────────────────────────────────────────
        img_resp = await client.get(image_url, follow_redirects=True, timeout=30.0)
        img_resp.raise_for_status()

        # ── Step 3: Upload binary ─────────────────────────────────────────────
        r3 = await client.put(
            upload_url,
            content=img_resp.content,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type":  img_resp.headers.get("content-type", "image/jpeg"),
            },
        )
        r3.raise_for_status()

        return asset_urn

    async def post_image(self, image_url: str, text: str) -> dict:
        """
        Publish a single image post to LinkedIn feed.

        Returns: { success, post_id, error }
        """
        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                asset_urn = await self._upload_image(client, image_url)
            except Exception as e:
                logger.error("[linkedin] image upload failed: %s", e)
                return {"success": False, "error": f"Image upload failed: {e}"}

            post_payload = {
                "author": self.person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text[:3000]},  # LinkedIn 3000 char limit
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "media":  asset_urn,
                            }
                        ],
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            }

            r = await client.post(
                f"{_LI_API}/ugcPosts",
                headers=self._headers(),
                json=post_payload,
            )
            r.raise_for_status()
            post_id = r.headers.get("x-restli-id", "")
            logger.info("[linkedin] published post_id=%s", post_id)
            return {"success": True, "post_id": post_id, "platform": "linkedin"}

    async def verify_token(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"{_LI_API}/me",
                    headers=self._headers(),
                )
                return r.status_code == 200
        except Exception:
            return False

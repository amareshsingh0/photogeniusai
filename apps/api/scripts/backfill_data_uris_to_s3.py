"""
One-shot backfill: walk every Generation row, find data:image/...;base64 URIs
in selectedOutputUrl + outputUrls, upload them to S3, and replace with HTTPS.

Run from apps/api root with the API venv active:
    cd /home/ubuntu/PhotoGenius-AI/apps/api
    source venv/bin/activate
    python scripts/backfill_data_uris_to_s3.py

Idempotent — already-HTTPS URLs are skipped. Safe to re-run.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
import uuid
from typing import List, Optional

# Make the app package importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prisma import Prisma  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backfill")


def _is_data_uri(s: object) -> bool:
    return isinstance(s, str) and s.startswith("data:image")


def _mime_and_ext(data_uri: str) -> tuple[str, str]:
    header = data_uri[: data_uri.find(",")].lower()
    if "png" in header:
        return "image/png", "png"
    if "jpeg" in header or "jpg" in header:
        return "image/jpeg", "jpg"
    if "webp" in header:
        return "image/webp", "webp"
    return "image/png", "png"


async def _upload_one(s3, data_uri: str) -> Optional[str]:
    """Decode + upload + return HTTPS URL. None on failure."""
    try:
        comma = data_uri.find(",")
        if comma == -1:
            return None
        mime, ext = _mime_and_ext(data_uri)
        img_bytes = base64.b64decode(data_uri[comma + 1:])
        s3_key = f"generations/{uuid.uuid4()}.{ext}"
        await s3.upload_file_async(file_data=img_bytes, s3_key=s3_key, content_type=mime)
        bucket = s3.bucket
        region = getattr(s3, "region", None) or os.getenv("AWS_REGION", "us-east-1")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
    except Exception as exc:
        logger.error("upload failed: %s", exc)
        return None


def _normalize_output_urls(value) -> List[str]:
    """outputUrls may be a JSON-encoded string OR a list. Normalize to list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            return [value]
    return []


async def main(dry_run: bool = False, limit: Optional[int] = None):
    from app.services.storage.s3_service import get_s3_service
    s3 = get_s3_service()
    if not getattr(s3, "bucket", None) or not getattr(s3, "access_key", None):
        logger.error("S3 not configured. Set S3_BUCKET_NAME / S3_ACCESS_KEY / S3_SECRET_KEY first.")
        return

    prisma = Prisma()
    await prisma.connect()

    # Find rows that have any data URI in either column
    where = {
        "OR": [
            {"selectedOutputUrl": {"startsWith": "data:image"}},
            # outputUrls is JSON — can't filter directly; we'll scan in Python
        ],
    }
    candidates = await prisma.generation.find_many(
        where=where,
        order={"createdAt": "desc"},
        take=limit if limit else None,
    )
    logger.info("scanning %d candidate rows (selectedOutputUrl is data URI)", len(candidates))

    # Also scan rows whose selectedOutputUrl is HTTPS but outputUrls JSON contains data URIs.
    # Cheap heuristic: read all rows and filter in Python for the outputUrls path.
    if not limit:
        all_rows = await prisma.generation.find_many(order={"createdAt": "desc"})
        extra = [
            r for r in all_rows
            if r.id not in {c.id for c in candidates}
            and any(_is_data_uri(u) for u in _normalize_output_urls(r.outputUrls))
        ]
        if extra:
            logger.info("+ %d more rows where outputUrls JSON holds a data URI", len(extra))
            candidates.extend(extra)

    fixed = 0
    failed = 0
    skipped = 0

    for row in candidates:
        new_selected = row.selectedOutputUrl
        new_urls = _normalize_output_urls(row.outputUrls)

        # Selected URL
        if _is_data_uri(new_selected):
            if dry_run:
                logger.info("[dry-run] would upload selected for row %s", row.id)
                new_selected = "<dry-run-placeholder>"
            else:
                uploaded = await _upload_one(s3, new_selected)
                if uploaded:
                    new_selected = uploaded
                else:
                    failed += 1
                    continue

        # outputUrls list
        replaced_any = False
        for i, u in enumerate(list(new_urls)):
            if _is_data_uri(u):
                if dry_run:
                    new_urls[i] = "<dry-run-placeholder>"
                    replaced_any = True
                else:
                    uploaded = await _upload_one(s3, u)
                    if uploaded:
                        new_urls[i] = uploaded
                        replaced_any = True

        if new_selected == row.selectedOutputUrl and not replaced_any:
            skipped += 1
            continue

        if dry_run:
            fixed += 1
            continue

        try:
            await prisma.generation.update(
                where={"id": row.id},
                data={
                    "selectedOutputUrl": new_selected,
                    "outputUrls": json.dumps(new_urls),
                },
            )
            fixed += 1
            if fixed % 10 == 0:
                logger.info("fixed %d rows so far...", fixed)
        except Exception as exc:
            logger.error("DB update failed for row %s: %s", row.id, exc)
            failed += 1

    await prisma.disconnect()
    logger.info("DONE — fixed=%d  failed=%d  skipped=%d  total=%d", fixed, failed, skipped, len(candidates))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report counts, do not upload or write")
    parser.add_argument("--limit", type=int, help="cap candidate rows (test runs)")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit))

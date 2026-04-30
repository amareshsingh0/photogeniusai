"""
One-shot backfill: walk every Generation row that has a `data:image/...;base64`
URI in selectedOutputUrl or outputUrls, upload to S3, and replace with HTTPS.

Run from apps/api root with the API venv active:
    cd /home/ubuntu/PhotoGenius-AI/apps/api
    source venv/bin/activate
    python scripts/backfill_data_uris_to_s3.py

Idempotent — already-HTTPS URLs are skipped. Safe to re-run.

Strategy: never SELECT * on the Generation table — those rows can hold
multi-MB base64 strings. We use raw SQL with LEFT(...) to find candidates
cheaply, then fetch one full row at a time to process.
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

# Load .env.local + .env so DATABASE_URL / S3_* / FAL_KEY are available.
try:
    from dotenv import load_dotenv  # type: ignore
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _name in (".env.local", ".env"):
        _path = os.path.join(_here, _name)
        if os.path.exists(_path):
            load_dotenv(_path, override=False)
except ImportError:
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _name in (".env.local", ".env"):
        _path = os.path.join(_here, _name)
        if not os.path.exists(_path):
            continue
        with open(_path, "r", encoding="utf-8") as _fh:
            for _line in _fh:
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                _k = _k.strip()
                _v = _v.strip().strip('"').strip("'")
                if _k and _k not in os.environ:
                    os.environ[_k] = _v

from prisma import Prisma  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
# Hush httpx noise — one line per HTTP request is overwhelming when uploading
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
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
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            return [value]
    return []


async def _find_candidate_ids(prisma) -> List[str]:
    """Return IDs of rows that need backfill. Uses LEFT() so we never pull
    the giant base64 payload over the wire just to identify candidates."""
    rows = await prisma.query_raw(
        '''
        SELECT id FROM "Generation"
        WHERE LEFT("selectedOutputUrl", 12) = 'data:image/'
           OR "outputUrls"::text LIKE '%data:image/%'
        ORDER BY "createdAt" DESC
        '''
    )
    return [r["id"] for r in (rows or [])]


async def _process_one(prisma, s3, row_id: str, dry_run: bool) -> str:
    """Returns 'fixed' / 'skipped' / 'failed'."""
    row = await prisma.generation.find_unique(where={"id": row_id})
    if not row:
        return "skipped"

    new_selected = row.selectedOutputUrl
    new_urls = _normalize_output_urls(row.outputUrls)
    changed = False

    if _is_data_uri(new_selected):
        if dry_run:
            new_selected = "<dry-run-placeholder>"
            changed = True
        else:
            uploaded = await _upload_one(s3, new_selected)
            if uploaded:
                new_selected = uploaded
                changed = True
            else:
                return "failed"

    for i, u in enumerate(list(new_urls)):
        if _is_data_uri(u):
            if dry_run:
                new_urls[i] = "<dry-run-placeholder>"
                changed = True
            else:
                uploaded = await _upload_one(s3, u)
                if uploaded:
                    new_urls[i] = uploaded
                    changed = True

    if not changed:
        return "skipped"

    if dry_run:
        return "fixed"

    try:
        await prisma.generation.update(
            where={"id": row_id},
            data={
                "selectedOutputUrl": new_selected,
                "outputUrls": json.dumps(new_urls),
            },
        )
        return "fixed"
    except Exception as exc:
        logger.error("DB update failed for %s: %s", row_id, exc)
        return "failed"


async def main(dry_run: bool = False, limit: Optional[int] = None):
    from app.services.storage.s3_service import get_s3_service
    s3 = get_s3_service()
    if not getattr(s3, "bucket", None) or not getattr(s3, "access_key", None):
        logger.error("S3 not configured. Set S3_BUCKET_NAME / S3_ACCESS_KEY / S3_SECRET_KEY first.")
        return

    prisma = Prisma()
    await prisma.connect()

    logger.info("scanning DB for candidate rows (cheap LEFT() query)...")
    ids = await _find_candidate_ids(prisma)
    logger.info("found %d candidate rows with data URIs", len(ids))

    if limit:
        ids = ids[:limit]
        logger.info("processing first %d only (--limit)", len(ids))

    fixed = failed = skipped = 0
    for n, row_id in enumerate(ids, start=1):
        result = await _process_one(prisma, s3, row_id, dry_run)
        if   result == "fixed":   fixed   += 1
        elif result == "skipped": skipped += 1
        else:                     failed  += 1
        if n % 10 == 0:
            logger.info("progress: %d/%d  (fixed=%d failed=%d skipped=%d)",
                        n, len(ids), fixed, failed, skipped)

    await prisma.disconnect()
    logger.info("DONE — fixed=%d  failed=%d  skipped=%d  total=%d",
                fixed, failed, skipped, len(ids))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report counts, do not upload or write")
    parser.add_argument("--limit", type=int, help="cap candidate rows (test runs)")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit))

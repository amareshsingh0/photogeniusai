"""
S3/R2 storage service. Supports AWS S3, Cloudflare R2, and MinIO.
Uses boto3 (sync) and aioboto3 (async) for uploads/downloads.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO

import aioboto3  # type: ignore[reportMissingImports]
import boto3  # type: ignore[reportMissingImports]
from botocore.exceptions import ClientError  # type: ignore[reportMissingImports]

from app.core.config import get_settings

_settings = get_settings()


class S3Service:
    """S3-compatible storage (AWS S3, Cloudflare R2, MinIO)."""

    def __init__(self) -> None:
        s = get_settings()
        self.bucket = s.S3_BUCKET_NAME
        self.region = s.S3_REGION or "us-east-1"
        self.endpoint_url = s.S3_ENDPOINT or None
        self.access_key = s.S3_ACCESS_KEY
        self.secret_key = s.S3_SECRET_KEY

        # For R2, use "auto" region or default to "us-east-1"
        if self.region == "auto" and self.endpoint_url:
            self.region = "us-east-1"

        # Check if R2 (Cloudflare)
        self.is_r2 = self.endpoint_url and "r2.cloudflarestorage.com" in self.endpoint_url if self.endpoint_url else False

        # Sync client
        self._sync_client: boto3.client | None = None
        # Async session
        self._async_session: aioboto3.Session | None = None

    @property
    def sync_client(self) -> boto3.client:
        """Get or create sync S3 client."""
        if self._sync_client is None:
            self._sync_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )
        return self._sync_client

    @property
    def async_session(self) -> aioboto3.Session:
        """Get or create async S3 session."""
        if self._async_session is None:
            self._async_session = aioboto3.Session()
        return self._async_session

    def upload_file(
        self,
        file_path: str | Path,
        s3_key: str,
        content_type: str | None = None,
    ) -> str:
        """
        Upload file to S3/R2 (sync).
        Returns public URL or signed URL.
        """
        if not self.bucket or not self.access_key:
            raise ValueError("S3_BUCKET_NAME and S3_ACCESS_KEY required")

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self.sync_client.upload_file(
                str(file_path),
                self.bucket,
                s3_key,
                ExtraArgs=extra_args,
            )
            # Return public URL or presigned URL
            if self.is_r2:
                # R2: Use presigned URL (secure, works even if bucket is private)
                return self.generate_presigned_url(s3_key, expiration=3600)
            elif self.endpoint_url:
                # Custom endpoint (MinIO, etc.) - try presigned, fallback to direct
                try:
                    return self.generate_presigned_url(s3_key, expiration=3600)
                except Exception:
                    return f"{self.endpoint_url}/{self.bucket}/{s3_key}"
            # AWS S3: public URL (if bucket is public)
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{s3_key}"
        except ClientError as e:
            raise RuntimeError(f"S3 upload failed: {e}") from e

    async def upload_file_async(
        self,
        file_data: bytes | BinaryIO,
        s3_key: str,
        content_type: str | None = None,
    ) -> str:
        """
        Upload file to S3/R2 (async).
        Returns public URL or signed URL.
        """
        if not self.bucket or not self.access_key:
            raise ValueError("S3_BUCKET_NAME and S3_ACCESS_KEY required")

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            async with self.async_session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            ) as s3:
                if isinstance(file_data, bytes):
                    await s3.put_object(
                        Bucket=self.bucket,
                        Key=s3_key,
                        Body=file_data,
                        **extra_args,
                    )
                else:
                    await s3.upload_fileobj(
                        file_data,
                        self.bucket,
                        s3_key,
                        ExtraArgs=extra_args,
                    )

            # Return public URL or presigned URL
            if self.is_r2:
                # R2: Use presigned URL (secure, works even if bucket is private)
                return await self.generate_presigned_url_async(s3_key, expiration=3600)
            elif self.endpoint_url:
                # Custom endpoint (MinIO, etc.) - try presigned, fallback to direct
                try:
                    return await self.generate_presigned_url_async(s3_key, expiration=3600)
                except Exception:
                    return f"{self.endpoint_url}/{self.bucket}/{s3_key}"
            # AWS S3: public URL (if bucket is public)
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{s3_key}"
        except ClientError as e:
            raise RuntimeError(f"S3 upload failed: {e}") from e

    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate presigned URL for temporary access (sync).
        expiration: seconds (default 1 hour).
        """
        if not self.bucket or not self.access_key:
            raise ValueError("S3_BUCKET_NAME and S3_ACCESS_KEY required")

        try:
            url = self.sync_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            raise RuntimeError(f"Failed to generate presigned URL: {e}") from e

    async def generate_presigned_url_async(
        self,
        s3_key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate presigned URL (async).
        expiration: seconds (default 1 hour).
        """
        if not self.bucket or not self.access_key:
            raise ValueError("S3_BUCKET_NAME and S3_ACCESS_KEY required")

        try:
            async with self.async_session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            ) as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": s3_key},
                    ExpiresIn=expiration,
                )
                return url
        except ClientError as e:
            raise RuntimeError(f"Failed to generate presigned URL: {e}") from e

    def delete_file(self, s3_key: str) -> None:
        """Delete file from S3/R2 (sync)."""
        if not self.bucket or not self.access_key:
            raise ValueError("S3_BUCKET_NAME and S3_ACCESS_KEY required")

        try:
            self.sync_client.delete_object(Bucket=self.bucket, Key=s3_key)
        except ClientError as e:
            raise RuntimeError(f"S3 delete failed: {e}") from e

    async def delete_file_async(self, s3_key: str) -> None:
        """Delete file from S3/R2 (async)."""
        if not self.bucket or not self.access_key:
            raise ValueError("S3_BUCKET_NAME and S3_ACCESS_KEY required")

        try:
            async with self.async_session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            ) as s3:
                await s3.delete_object(Bucket=self.bucket, Key=s3_key)
        except ClientError as e:
            raise RuntimeError(f"S3 delete failed: {e}") from e

    def test_connection(self) -> bool:
        """Test S3/R2 connection (sync). Returns True if bucket is accessible."""
        if not self.bucket or not self.access_key:
            return False

        try:
            self.sync_client.head_bucket(Bucket=self.bucket)
            return True
        except ClientError:
            return False


# Singleton instance
_s3_service: S3Service | None = None


def get_s3_service() -> S3Service:
    """Get S3 service singleton."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service

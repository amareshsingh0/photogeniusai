"""
Gallery Cleanup Service - Auto-delete old generations

Features:
- Delete generations older than X days (default: 15)
- Delete images from S3
- Soft delete in database
- Preserve favorites
- Log cleanup statistics
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List
import boto3
from botocore.exceptions import ClientError


class GalleryCleanupService:
    """Automatically clean up old generations"""

    def __init__(self, delete_after_days: int = 15):
        """
        Initialize cleanup service

        Args:
            delete_after_days: Number of days to keep generations (default: 15)
        """
        self.delete_after_days = delete_after_days
        self.s3_client = boto3.client(
            's3',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self.bucket_name = os.getenv('S3_BUCKET', 'photogenius-images-dev')

    async def cleanup_old_generations(self, db) -> Dict:
        """
        Delete generations older than delete_after_days

        Process:
        1. Find old generations (created more than X days ago)
        2. Exclude favorites (users may want to keep them)
        3. Delete images from S3
        4. Soft delete in database
        5. Return cleanup statistics

        Args:
            db: Database session/client

        Returns:
            dict: Cleanup statistics
        """

        cutoff_date = datetime.utcnow() - timedelta(days=self.delete_after_days)

        print(f"🧹 Starting cleanup for generations older than {cutoff_date}")

        # Find old generations to delete
        # Note: Adjust this query based on your actual database client (Prisma, SQLAlchemy, etc.)
        try:
            old_generations = await db.generation.find_many(
                where={
                    'createdAt': {'lt': cutoff_date},
                    'isDeleted': False,
                    'isFavorite': False  # Preserve favorites
                }
            )
        except AttributeError:
            # Fallback for different ORM
            print("⚠️ Adjust database query for your ORM")
            return {'error': 'Database query needs adjustment for your ORM'}

        deleted_count = 0
        failed_count = 0
        freed_storage_bytes = 0

        for generation in old_generations:
            try:
                # Delete images from S3
                if generation.outputUrls:
                    storage_freed = await self._delete_images_from_s3(
                        generation.outputUrls
                    )
                    freed_storage_bytes += storage_freed

                # Soft delete in database
                await db.generation.update(
                    where={'id': generation.id},
                    data={
                        'isDeleted': True,
                        'deletedAt': datetime.utcnow()
                    }
                )

                deleted_count += 1
                print(f"   ✓ Deleted generation {generation.id}")

            except Exception as e:
                failed_count += 1
                print(f"   ✗ Failed to delete generation {generation.id}: {e}")
                continue

        freed_storage_mb = freed_storage_bytes / (1024 * 1024)

        result = {
            'success': True,
            'deleted_count': deleted_count,
            'failed_count': failed_count,
            'freed_storage_mb': round(freed_storage_mb, 2),
            'cutoff_date': cutoff_date.isoformat(),
            'delete_after_days': self.delete_after_days
        }

        print(f"[OK] Cleanup complete:")
        print(f"   Deleted: {deleted_count} generations")
        print(f"   Failed: {failed_count}")
        print(f"   Freed: {freed_storage_mb:.2f} MB")

        return result

    async def _delete_images_from_s3(self, urls: List[str]) -> int:
        """
        Delete images from S3

        Args:
            urls: List of S3 URLs

        Returns:
            int: Total bytes freed
        """
        total_bytes = 0

        for url in urls:
            try:
                # Extract S3 key from URL
                # Format: https://bucket.s3.region.amazonaws.com/key
                # or https://bucket.s3.amazonaws.com/key
                if '.s3.' in url:
                    key = url.split('.com/')[-1]
                else:
                    # Alternative format
                    key = url.split(f'{self.bucket_name}/')[-1]

                # Get object size before deleting
                try:
                    response = self.s3_client.head_object(
                        Bucket=self.bucket_name,
                        Key=key
                    )
                    total_bytes += response['ContentLength']
                except ClientError:
                    pass  # Object doesn't exist

                # Delete object
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key
                )

                print(f"      Deleted from S3: {key}")

            except Exception as e:
                print(f"      Failed to delete {url}: {e}")
                continue

        return total_bytes

    def _extract_s3_key(self, url: str) -> str:
        """
        Extract S3 key from URL

        Handles multiple URL formats:
        - https://bucket.s3.region.amazonaws.com/key
        - https://bucket.s3.amazonaws.com/key
        - https://s3.region.amazonaws.com/bucket/key

        Args:
            url: S3 URL

        Returns:
            str: S3 key
        """
        if '.s3.' in url:
            # Extract everything after .com/
            return url.split('.com/')[-1]
        elif 's3.' in url:
            # Format: https://s3.region.amazonaws.com/bucket/key
            parts = url.split('/')
            # Skip https://, s3.region.amazonaws.com, bucket
            return '/'.join(parts[4:])
        else:
            # Fallback: assume everything after bucket name
            return url.split(f'{self.bucket_name}/')[-1]

    async def get_storage_stats(self, db) -> Dict:
        """
        Get storage statistics

        Returns:
            dict: Storage stats
        """

        cutoff_date = datetime.utcnow() - timedelta(days=self.delete_after_days)

        # Count generations that will be deleted
        try:
            eligible_for_deletion = await db.generation.count(
                where={
                    'createdAt': {'lt': cutoff_date},
                    'isDeleted': False,
                    'isFavorite': False
                }
            )

            total_generations = await db.generation.count(
                where={'isDeleted': False}
            )

            favorites_count = await db.generation.count(
                where={
                    'isDeleted': False,
                    'isFavorite': True
                }
            )

            return {
                'total_generations': total_generations,
                'eligible_for_deletion': eligible_for_deletion,
                'favorites_protected': favorites_count,
                'deletion_cutoff_date': cutoff_date.isoformat(),
                'delete_after_days': self.delete_after_days
            }

        except AttributeError:
            return {'error': 'Database query needs adjustment for your ORM'}


# Configurable cleanup settings
DEFAULT_DELETE_AFTER_DAYS = int(os.getenv('GALLERY_DELETE_AFTER_DAYS', '15'))

# Create singleton instance
cleanup_service = GalleryCleanupService(delete_after_days=DEFAULT_DELETE_AFTER_DAYS)

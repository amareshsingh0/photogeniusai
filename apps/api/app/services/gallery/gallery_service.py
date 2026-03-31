"""
Gallery Service - CRUD operations for generations

Features:
- List user generations
- Get single generation
- Delete generation
- Toggle favorite
- Public gallery
- Pagination and filtering
"""

import os
from datetime import datetime
from typing import List, Optional, Dict
import boto3
from botocore.exceptions import ClientError


class GalleryService:
    """Gallery operations service"""

    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self.bucket_name = os.getenv('S3_BUCKET', 'photogenius-images-dev')

    async def list_user_generations(
        self,
        db,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        mode: Optional[str] = None,
        is_favorite: Optional[bool] = None
    ) -> Dict:
        """
        List generations for a user

        Args:
            db: Database client
            user_id: User ID
            limit: Max results (default: 20, max: 100)
            offset: Skip N results
            mode: Filter by generation mode
            is_favorite: Filter by favorite status

        Returns:
            dict: {generations: [...], total: int, limit: int, offset: int}
        """

        # Build where clause
        where = {
            'userId': user_id,
            'isDeleted': False
        }

        if mode:
            where['mode'] = mode.upper()

        if is_favorite is not None:
            where['isFavorite'] = is_favorite

        # Query generations
        try:
            generations = await db.generation.find_many(
                where=where,
                order_by={'createdAt': 'desc'},
                skip=offset,
                take=min(limit, 100),  # Cap at 100
                include={
                    'identity': True  # Include identity if used
                }
            )

            total = await db.generation.count(where=where)

            return {
                'generations': generations,
                'total': total,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + len(generations)) < total
            }

        except AttributeError as e:
            print(f"Database query error: {e}")
            return {
                'generations': [],
                'total': 0,
                'error': 'Database query needs adjustment for your ORM'
            }

    async def get_public_gallery(
        self,
        db,
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
        style: Optional[str] = None
    ) -> Dict:
        """
        Get public gallery - approved, public generations

        Args:
            db: Database client
            limit: Max results
            offset: Skip N results
            category: Filter by category (portrait, landscape, etc.)
            style: Filter by style (cinematic, artistic, etc.)

        Returns:
            dict: {generations: [...], total: int}
        """

        where = {
            'isPublic': True,
            'isDeleted': False,
            'galleryModeration': 'APPROVED'
        }

        if category:
            where['galleryCategory'] = category

        if style:
            where['galleryStyle'] = style

        try:
            # Order by likes for featured content
            generations = await db.generation.find_many(
                where=where,
                order_by=[
                    {'galleryLikesCount': 'desc'},
                    {'createdAt': 'desc'}
                ],
                skip=offset,
                take=min(limit, 100)
            )

            total = await db.generation.count(where=where)

            return {
                'generations': generations,
                'total': total,
                'limit': limit,
                'offset': offset
            }

        except AttributeError:
            return {'generations': [], 'total': 0}

    async def get_generation(
        self,
        db,
        generation_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get single generation

        Args:
            db: Database client
            generation_id: Generation ID
            user_id: User ID (for ownership check)

        Returns:
            Generation object or None
        """

        try:
            generation = await db.generation.find_unique(
                where={'id': generation_id},
                include={
                    'identity': True,
                    'user': {'select': {'id': True, 'name': True}}
                }
            )

            if not generation:
                return None

            # Check access
            if user_id:
                # Owner can always access
                if generation.userId == user_id:
                    return generation

            # Public generations accessible to all
            if generation.isPublic and not generation.isDeleted:
                return generation

            # Access denied
            return None

        except AttributeError:
            return None

    async def delete_generation(
        self,
        db,
        generation_id: str,
        user_id: str
    ) -> Dict:
        """
        Soft delete a generation

        Args:
            db: Database client
            generation_id: Generation ID
            user_id: User ID (must be owner)

        Returns:
            dict: Success status
        """

        try:
            # Get generation
            generation = await db.generation.find_unique(
                where={'id': generation_id}
            )

            if not generation:
                return {'success': False, 'error': 'Generation not found'}

            # Check ownership
            if generation.userId != user_id:
                return {'success': False, 'error': 'Access denied'}

            # Already deleted
            if generation.isDeleted:
                return {'success': False, 'error': 'Already deleted'}

            # Delete images from S3
            if generation.outputUrls:
                await self._delete_images_from_s3(generation.outputUrls)

            # Soft delete in database
            await db.generation.update(
                where={'id': generation_id},
                data={
                    'isDeleted': True,
                    'deletedAt': datetime.utcnow()
                }
            )

            return {'success': True, 'message': 'Generation deleted'}

        except Exception as e:
            print(f"Delete error: {e}")
            return {'success': False, 'error': str(e)}

    async def toggle_favorite(
        self,
        db,
        generation_id: str,
        user_id: str
    ) -> Dict:
        """
        Toggle favorite status

        Args:
            db: Database client
            generation_id: Generation ID
            user_id: User ID (must be owner)

        Returns:
            dict: New favorite status
        """

        try:
            generation = await db.generation.find_unique(
                where={'id': generation_id}
            )

            if not generation:
                return {'success': False, 'error': 'Generation not found'}

            if generation.userId != user_id:
                return {'success': False, 'error': 'Access denied'}

            new_favorite = not generation.isFavorite

            await db.generation.update(
                where={'id': generation_id},
                data={'isFavorite': new_favorite}
            )

            return {
                'success': True,
                'is_favorite': new_favorite
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _delete_images_from_s3(self, urls: List[str]) -> bool:
        """
        Delete images from S3

        Args:
            urls: List of S3 URLs

        Returns:
            bool: Success status
        """

        for url in urls:
            try:
                # Extract key from URL
                key = self._extract_s3_key(url)

                # Delete object
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key
                )

                print(f"Deleted from S3: {key}")

            except ClientError as e:
                print(f"S3 delete error: {e}")
                continue

        return True

    def _extract_s3_key(self, url: str) -> str:
        """Extract S3 key from URL"""
        if '.s3.' in url:
            return url.split('.com/')[-1]
        return url.split(f'{self.bucket_name}/')[-1]


# Singleton instance
gallery_service = GalleryService()

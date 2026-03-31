"""
PhotoGenius AI - Post-Processing Lambda

Upscales image (PIL 2x when RealESRGAN not available), uploads to S3, returns URL.
Cost: ~$0.002 per image. Can be extended with EFS + RealESRGAN layer.
"""

import json
import os
import base64
import uuid
import boto3
from io import BytesIO

S3_BUCKET = os.environ.get("S3_BUCKET", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
UPSCALE_FACTOR = int(os.environ.get("UPSCALE_FACTOR", "2"))

s3_client = boto3.client("s3")


def _upscale_pil(image_bytes: bytes, factor: int = 2) -> bytes:
    """Upscale using PIL (bicubic). Use RealESRGAN on EFS for production 4x."""
    try:
        from PIL import Image

        img = Image.open(BytesIO(image_bytes))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        w, h = img.size
        new_size = (w * factor, h * factor)
        upscaled = img.resize(new_size, Image.Resampling.LANCZOS)
        out = BytesIO()
        upscaled.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return image_bytes


def lambda_handler(event, context):
    """
    Input: body { image_base64, generation_id }
    Output: { image_url, generation_id }
    """
    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        image_b64 = body.get("image_base64", "")
        generation_id = body.get("generation_id", str(uuid.uuid4()))

        if not image_b64 or not S3_BUCKET:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Missing image_base64 or S3_BUCKET", "image_url": ""}),
            }

        image_bytes = base64.b64decode(image_b64)
        if UPSCALE_FACTOR > 1:
            image_bytes = _upscale_pil(image_bytes, UPSCALE_FACTOR)

        key = f"generations/{generation_id}.png"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=image_bytes,
            ContentType="image/png",
        )

        image_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"image_url": image_url, "generation_id": generation_id}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e), "image_url": ""}),
        }

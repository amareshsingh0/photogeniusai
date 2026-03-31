"""
PhotoGenius AI - Post-Processing Lambda (full: RealESRGAN + CodeFormer)

When EFS is mounted at /mnt/efs with RealESRGAN_x4plus.pth and codeformer.pth:
  - Upscale 4x with RealESRGAN
  - Face restoration with CodeFormer
  - Final enhancements (sharpening, CLAHE, film grain)

When EFS/models not available: falls back to PIL 2x upscale + S3 upload (same as handler.py).
"""

import json
import os
import base64
import uuid
import boto3
import io
import numpy as np

s3_client = boto3.client("s3")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
EFS_MODELS = "/mnt/efs"
REALESRGAN_PATH = os.path.join(EFS_MODELS, "RealESRGAN_x4plus.pth")
CODEFORMER_PATH = os.path.join(EFS_MODELS, "codeformer.pth")

REALESRGAN_MODEL = None
CODEFORMER_MODEL = None
CV2_AVAILABLE = False
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    pass


def load_models():
    """Load RealESRGAN and CodeFormer from EFS when available."""
    global REALESRGAN_MODEL, CODEFORMER_MODEL
    if REALESRGAN_MODEL is not None:
        return
    if not os.path.exists(REALESRGAN_PATH):
        print("RealESRGAN not found on EFS, using PIL fallback")
        return
    try:
        from realesrgan import RealESRGANer
        from basicsr.archs.rrdbnet_arch import RRDBNet
        net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        REALESRGAN_MODEL = RealESRGANer(
            scale=4,
            model_path=REALESRGAN_PATH,
            model=net,
            tile=256,
            tile_pad=10,
            pre_pad=0,
            half=True,
        )
        print("RealESRGAN loaded")
    except Exception as e:
        print(f"RealESRGAN load failed: {e}")
    if not os.path.exists(CODEFORMER_PATH):
        return
    try:
        from codeformer import CodeFormer
        CODEFORMER_MODEL = CodeFormer(model_path=CODEFORMER_PATH, upscale=1, bg_upsampler=None)
        print("CodeFormer loaded")
    except Exception as e:
        print(f"CodeFormer load failed: {e}")


def restore_faces(image, model):
    """Restore faces using CodeFormer (requires cv2)."""
    if not CV2_AVAILABLE or model is None:
        return image
    try:
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) == 0:
            return image
        for (x, y, w, h) in faces:
            padding = int(w * 0.2)
            x1, y1 = max(0, x - padding), max(0, y - padding)
            x2, y2 = min(image.shape[1], x + w + padding), min(image.shape[0], y + h + padding)
            face_region = image[y1:y2, x1:x2]
            restored = model.restore(face_region, weight=0.7)
            if restored is not None and restored.size > 0:
                image[y1:y2, x1:x2] = restored
        return image
    except Exception as e:
        print(f"Face restore failed: {e}")
        return image


def apply_final_enhancements(image):
    """Sharpening, CLAHE, subtle saturation, film grain."""
    if not CV2_AVAILABLE:
        return image
    try:
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32) * 0.2
        sharpened = cv2.filter2D(image, -1, kernel)
        lab = cv2.cvtColor(sharpened, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)
        hsv = cv2.cvtColor(enhanced, cv2.COLOR_RGB2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.05, 0, 255)
        final = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
        grain = np.random.normal(0, 2, final.shape).astype(np.float32)
        final = np.clip(final.astype(np.float32) + grain, 0, 255).astype(np.uint8)
        return final
    except Exception as e:
        print(f"Enhancements failed: {e}")
        return image


def _pil_upscale(image_bytes, factor=2):
    """Fallback: PIL LANCZOS upscale."""
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    upscaled = img.resize((w * factor, h * factor), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    upscaled.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def lambda_handler(event, context):
    """
    Steps when EFS available: decode → RealESRGAN 4x → CodeFormer → enhancements → S3.
    Fallback: decode → PIL 2x → S3.
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

        load_models()
        image_data = base64.b64decode(image_b64)

        if REALESRGAN_MODEL is not None:
            from PIL import Image
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            img_array = np.array(image)
            upscaled, _ = REALESRGAN_MODEL.enhance(img_array, outscale=4)
            restored = restore_faces(upscaled, CODEFORMER_MODEL)
            final_array = apply_final_enhancements(restored)
            final_image = Image.fromarray(final_array)
            buffer = io.BytesIO()
            final_image.save(buffer, format="PNG", optimize=True)
            image_bytes = buffer.getvalue()
            width, height = final_image.width, final_image.height
        else:
            image_bytes = _pil_upscale(image_data, 2)
            from PIL import Image
            final_image = Image.open(io.BytesIO(image_bytes))
            width, height = final_image.width, final_image.height

        s3_key = f"generations/{generation_id}/final.png"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=image_bytes,
            ContentType="image/png",
            CacheControl="max-age=31536000",
        )
        image_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({
                "image_url": image_url,
                "generation_id": generation_id,
                "size": {"width": width, "height": height},
            }),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e), "image_url": ""}),
        }

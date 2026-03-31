"""
PhotoGenius AI - Refinement Lambda

Image refinement (img2img-style editing) via PIL. Accepts image URL or base64,
parses modification intent from natural language, applies global adjustments
(brightness, contrast, saturation, sharpness) or simple style fallbacks
(grayscale, vintage, blur, sharpen), uploads result to S3, returns refined URL.

API: POST /refine
Input:  { image_url?, image_base64?, instruction, strength?, seed? }
Output: { refined_url, modification_applied, metadata }
"""

import json
import os
import base64
import uuid
import re
import boto3
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
S3_BUCKET = os.environ.get("S3_BUCKET", "photogenius-images-dev")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
s3_client = boto3.client("s3", region_name=AWS_REGION)

# ---------------------------------------------------------------------------
# Lightweight intent parsing (embedded from image_modification_engine)
# ---------------------------------------------------------------------------

BRIGHTNESS_KEYWORDS = {
    "brighter": 0.3, "more bright": 0.3, "lighten": 0.3, "lighter": 0.3,
    "increase brightness": 0.4, "make it light": 0.3, "more light": 0.25,
    "darker": -0.3, "more dark": -0.3, "darken": -0.35, "dim": -0.3,
    "decrease brightness": -0.4, "make it dark": -0.35, "less light": -0.25,
}
CONTRAST_KEYWORDS = {
    "more contrast": 0.3, "increase contrast": 0.35, "high contrast": 0.4,
    "less contrast": -0.3, "decrease contrast": -0.35, "low contrast": -0.3, "flat": -0.25,
}
SATURATION_KEYWORDS = {
    "more saturated": 0.3, "saturate": 0.3, "vibrant": 0.35, "colorful": 0.25,
    "increase saturation": 0.4, "desaturate": -0.35, "less saturated": -0.3,
    "muted": -0.3, "pastel": -0.25, "grey": -0.4, "gray": -0.4,
}
SHARPNESS_KEYWORDS = {
    "sharper": 0.3, "sharpen": 0.35, "more sharp": 0.3, "crisp": 0.25,
    "blur": -0.35, "blurry": -0.3, "soft": -0.25, "soften": -0.3,
}
STYLE_FALLBACK_KEYWORDS = [
    "black and white", "noir", "monochrome", "grayscale", "b&w",
    "vintage", "sepia", "blur", "soft", "sharp", "crisp",
]


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _parse_instruction(instruction: str) -> Tuple[str, Dict[str, float]]:
    """
    Returns (mod_type, adjustments).
    mod_type: "global" | "style" | "unclear"
    adjustments: dict of global_adjustments for "global"; empty for "style"/"unclear".
    """
    instr = (instruction or "").lower().strip()
    if not instr:
        return "unclear", {}

    adjustments = {}
    for kw, val in BRIGHTNESS_KEYWORDS.items():
        if kw in instr:
            adjustments["brightness"] = val
            break
    for kw, val in CONTRAST_KEYWORDS.items():
        if kw in instr:
            adjustments["contrast"] = val
            break
    for kw, val in SATURATION_KEYWORDS.items():
        if kw in instr:
            adjustments["saturation"] = val
            break
    for kw, val in SHARPNESS_KEYWORDS.items():
        if kw in instr:
            adjustments["sharpness"] = val
            break

    if adjustments:
        return "global", adjustments
    for kw in STYLE_FALLBACK_KEYWORDS:
        if kw in instr:
            return "style", {"style_hint": instr}
    return "unclear", {}


def _apply_global_pil(image, adjustments: Dict[str, float], strength: float):
    """Apply brightness/contrast/saturation/sharpness via PIL. strength scales deltas."""
    try:
        from PIL import Image, ImageEnhance
    except ImportError:
        return image
    if not hasattr(image, "copy"):
        return image
    img = image.copy()
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    if img.mode == "L":
        img = img.convert("RGB")

    scale = _clamp(float(strength), 0.1, 1.0) if strength is not None else 1.0
    for key, delta in adjustments.items():
        if key == "style_hint":
            continue
        factor = 1.0 + (float(delta) * scale)
        factor = _clamp(factor, 0.1, 3.0)
        if key == "brightness":
            img = ImageEnhance.Brightness(img).enhance(factor)
        elif key == "contrast":
            img = ImageEnhance.Contrast(img).enhance(factor)
        elif key == "saturation":
            img = ImageEnhance.Color(img).enhance(factor)
        elif key == "sharpness":
            img = ImageEnhance.Sharpness(img).enhance(factor)
    return img


def _apply_style_fallback_pil(image, instruction: str):
    """Grayscale, vintage/sepia, blur, sharpen via PIL."""
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        return image
    if not hasattr(image, "copy"):
        return image
    img = image.copy()
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    instr = (instruction or "").lower()

    if any(k in instr for k in ["black and white", "noir", "monochrome", "grayscale", "b&w"]):
        img = img.convert("L").convert("RGB")
    elif any(k in instr for k in ["vintage", "sepia"]):
        img = img.convert("L").convert("RGB")
        r, g, b = img.split()
        r = r.point(lambda x: min(x + 40, 255))
        g = g.point(lambda x: min(x + 20, 255))
        b = b.point(lambda x: max(x - 20, 0))
        img = Image.merge("RGB", (r, g, b))
    elif any(k in instr for k in ["blur", "soft"]):
        img = img.filter(ImageFilter.GaussianBlur(radius=2))
    elif any(k in instr for k in ["sharp", "crisp"]):
        img = img.filter(ImageFilter.SHARPEN)
    return img


# ---------------------------------------------------------------------------
# Image load / save
# ---------------------------------------------------------------------------


def _parse_s3_from_url(image_url: str) -> Optional[Tuple[str, str]]:
    """Return (bucket, key) from s3://bucket/key or https://bucket.s3.region.amazonaws.com/key."""
    if not image_url or not isinstance(image_url, str):
        return None
    url = image_url.strip()
    if url.startswith("s3://"):
        parts = url[5:].split("/", 1)
        if len(parts) == 2:
            return (parts[0], parts[1])
        return None
    m = re.match(r"https?://([^.]+)\.s3\.[^/]+\.amazonaws\.com/(.+)", url)
    if m:
        return (m.group(1), m.group(2).lstrip("/"))
    return None


def download_image_from_input(
    image_url: Optional[str],
    image_base64: Optional[str],
    bucket: str,
) -> Tuple[bytes, Optional[str]]:
    """
    Get image bytes from image_url (S3) or image_base64.
    Returns (image_bytes, error_message). error_message is set on failure.
    """
    if image_url:
        parsed = _parse_s3_from_url(image_url)
        if parsed:
            b, k = parsed
            try:
                resp = s3_client.get_object(Bucket=b, Key=k)
                return (resp["Body"].read(), None)
            except Exception as e:
                return (b"", f"S3 download failed: {str(e)}")
        # If image_url looks like a key (no scheme), treat as key in default bucket
        if not image_url.startswith("http") and not image_url.startswith("s3:"):
            try:
                resp = s3_client.get_object(Bucket=bucket, Key=image_url.strip("/"))
                return (resp["Body"].read(), None)
            except Exception as e:
                return (b"", f"S3 download failed: {str(e)}")
        return (b"", "Unsupported image_url format; use s3://bucket/key or S3 key")
    if image_base64:
        try:
            return (base64.b64decode(image_base64), None)
        except Exception as e:
            return (b"", f"Invalid base64: {str(e)}")
    return (b"", "Provide either image_url or image_base64")


def load_pil_image(image_bytes: bytes):
    """Load PIL Image from bytes. Raises on invalid image."""
    from PIL import Image
    img = Image.open(BytesIO(image_bytes))
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    return img


def save_pil_to_bytes(image) -> bytes:
    """Save PIL image to PNG bytes."""
    from PIL import Image
    buf = BytesIO()
    if hasattr(image, "save"):
        image.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    raise ValueError("Not a PIL image")


def upload_refined_to_s3(image_bytes: bytes, bucket: str) -> str:
    """Upload PNG bytes to S3 refined/{uuid}.png; return public URL."""
    key = f"refined/{uuid.uuid4().hex}.png"
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=image_bytes,
        ContentType="image/png",
    )
    return f"https://{bucket}.s3.{AWS_REGION}.amazonaws.com/{key}"


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Refinement Lambda: modify image by instruction and return refined image URL.

    Expected input (body JSON):
        image_url (optional): S3 URL (s3://bucket/key) or S3 key in S3_BUCKET
        image_base64 (optional): base64-encoded image
        instruction (required): e.g. "make it brighter", "add more contrast", "black and white"
        strength (optional): 0.1–1.0, default 0.7 (how strong the modification is)
        seed (optional): ignored for PIL path; reserved for future img2img

    Returns (200):
        refined_url: URL of the refined image in S3
        modification_applied: short description of what was done
        metadata: { mod_type, instruction, strength }

    Errors:
        400: Missing image_url/image_base64 or instruction; invalid image; unclear instruction
        500: S3 upload failure or internal error
    """
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    try:
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", event) or {}

        image_url = body.get("image_url") or body.get("refinement_image_url")
        image_base64 = body.get("image_base64", "")
        instruction = (body.get("instruction") or body.get("refinement_request") or "").strip()
        strength = body.get("strength")
        if strength is not None:
            try:
                strength = _clamp(float(strength), 0.1, 1.0)
            except (TypeError, ValueError):
                strength = 0.7
        else:
            strength = 0.7
        seed = body.get("seed")

        if not instruction:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({
                    "error": "instruction is required",
                    "refined_url": None,
                    "modification_applied": None,
                    "metadata": None,
                }),
            }

        image_bytes, err = download_image_from_input(image_url, image_base64, S3_BUCKET)
        if err:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({
                    "error": err,
                    "refined_url": None,
                    "modification_applied": None,
                    "metadata": None,
                }),
            }

        if not image_bytes:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({
                    "error": "Invalid or empty image",
                    "refined_url": None,
                    "modification_applied": None,
                    "metadata": None,
                }),
            }

        try:
            pil_image = load_pil_image(image_bytes)
        except Exception as e:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({
                    "error": f"Invalid image data: {str(e)}",
                    "refined_url": None,
                    "modification_applied": None,
                    "metadata": None,
                }),
            }

        mod_type, adjustments = _parse_instruction(instruction)
        if mod_type == "unclear":
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({
                    "error": "Unclear modification instruction; try e.g. 'make it brighter', 'more contrast', 'black and white'",
                    "refined_url": None,
                    "modification_applied": None,
                    "metadata": {"instruction": instruction},
                }),
            }

        if mod_type == "global":
            modified = _apply_global_pil(pil_image, adjustments, strength)
            modification_applied = "global: " + ", ".join(
                f"{k}={adjustments[k]:.2f}" for k in sorted(adjustments.keys()) if k != "style_hint"
            )
        else:
            modified = _apply_style_fallback_pil(pil_image, instruction)
            modification_applied = f"style: {instruction[:80]}"

        try:
            out_bytes = save_pil_to_bytes(modified)
        except Exception as e:
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({
                    "error": f"Failed to encode image: {str(e)}",
                    "refined_url": None,
                    "modification_applied": modification_applied,
                    "metadata": {"mod_type": mod_type, "instruction": instruction, "strength": strength},
                }),
            }

        if not S3_BUCKET:
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({
                    "error": "S3_BUCKET not configured",
                    "refined_url": None,
                    "modification_applied": modification_applied,
                    "metadata": {"mod_type": mod_type},
                }),
            }

        try:
            refined_url = upload_refined_to_s3(out_bytes, S3_BUCKET)
        except Exception as e:
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({
                    "error": f"S3 upload failed: {str(e)}",
                    "refined_url": None,
                    "modification_applied": modification_applied,
                    "metadata": {"mod_type": mod_type},
                }),
            }

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "refined_url": refined_url,
                "modification_applied": modification_applied,
                "metadata": {
                    "mod_type": mod_type,
                    "instruction": instruction,
                    "strength": strength,
                    "seed": seed,
                },
            }),
        }
    except json.JSONDecodeError as e:
        return {
            "statusCode": 400,
            "headers": headers,
            "body": json.dumps({
                "error": f"Invalid JSON body: {str(e)}",
                "refined_url": None,
                "modification_applied": None,
                "metadata": None,
            }),
        }
    except Exception as e:
        print(f"Refinement error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({
                "error": str(e),
                "refined_url": None,
                "modification_applied": None,
                "metadata": None,
            }),
        }

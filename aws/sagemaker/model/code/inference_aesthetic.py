"""
SageMaker inference entrypoint for aesthetic reward model.

Loads learned aesthetic model; scores image (base64) → score_0_1, score_0_10.
Target: inference <100ms per image.
"""

import base64
import json
import os
import time
from io import BytesIO

# Engine: same package (copy aesthetic_model.py to this folder when packaging)
try:
    from aesthetic_model import load_pretrained, predict
except ImportError:
    load_pretrained = None
    predict = None


def model_fn(model_dir):
    """Load aesthetic reward model from model_dir."""
    print("Loading aesthetic model from:", model_dir)
    if load_pretrained is None:
        raise ImportError("aesthetic_model not found; add it to the SageMaker code package")
    ckpt = os.path.join(model_dir, "aesthetic_reward_model.pth")
    if not os.path.isfile(ckpt):
        ckpt = os.path.join(model_dir, "aesthetic_predictor_production.pth")
    if not os.path.isfile(ckpt):
        raise FileNotFoundError(f"No checkpoint in {model_dir}")
    model = load_pretrained(ckpt, model_dir, "cuda" if __import__("torch").cuda.is_available() else "cpu")
    return {"model": model, "device": "cuda" if __import__("torch").cuda.is_available() else "cpu"}


def input_fn(request_body, content_type="application/json"):
    """Parse input: { "image_base64": "..." }."""
    if content_type not in ("application/json", "application/x-json", None, ""):
        raise ValueError(f"Unsupported content type: {content_type}")
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    data = json.loads(request_body or "{}")
    b64 = data.get("image_base64")
    if not b64:
        raise ValueError("image_base64 required")
    raw = base64.b64decode(b64)
    from PIL import Image
    img = Image.open(BytesIO(raw)).convert("RGB")
    return {"image": img}


def predict_fn(input_data, model):
    """Score image; return score_0_1 and inference_time."""
    m = model["model"]
    device = model.get("device", "cuda")
    img = input_data["image"]
    start = time.perf_counter()
    score_0_1 = predict(m, img, device)
    elapsed = time.perf_counter() - start
    score_0_10 = min(10.0, max(0.0, score_0_1 * 10.0))
    return {"score_0_1": float(score_0_1), "score_0_10": round(score_0_10, 2), "inference_time_ms": round(elapsed * 1000, 2)}


def output_fn(prediction, content_type="application/json"):
    """Return JSON with score_0_1, score_0_10, inference_time_ms."""
    return json.dumps(prediction)

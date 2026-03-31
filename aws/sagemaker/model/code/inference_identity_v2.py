"""
SageMaker inference entrypoint for Identity Engine V2 (multi-path face consistency).

AWS only (no Modal). Loads InstantID (+ optional FaceAdapter/PhotoMaker) at startup.
Input: prompt (required), face_image_base64 (required), identity_embedding? (optional),
  identity_method (instantid|faceadapter|photomaker|ensemble), negative_prompt?, width?, height?, seed?
Output: image_base64, similarity, path, guaranteed, error?
"""

import base64
import json
import os
import time
import traceback
from io import BytesIO

import numpy as np
from PIL import Image

# Engine lives in same package (copy identity_engine_v2_aws.py to this folder when packaging)
try:
    from identity_engine_v2_aws import IdentityEngineV2, GenerationResult, result_to_base64
except ImportError:
    IdentityEngineV2 = None
    GenerationResult = None
    result_to_base64 = None


def model_fn(model_dir):
    """
    Load Identity Engine V2 (InstantID + optional FaceAdapter/PhotoMaker).
    MODEL_DIR is typically /opt/ml/model; InstantID and SDXL paths from env or model_dir.
    """
    print("Loading Identity Engine V2 from:", model_dir)
    if IdentityEngineV2 is None:
        raise ImportError("identity_engine_v2_aws not found; add it to the SageMaker code package")

    engine = IdentityEngineV2(model_dir=model_dir)
    engine.load_all()
    return {"engine": engine, "device": "cuda" if __import__("torch").cuda.is_available() else "cpu"}


def input_fn(request_body, content_type="application/json"):
    """Parse and validate input: prompt, face_image_base64 (required for identity), method, etc."""
    if content_type not in ("application/json", "application/x-json", None, ""):
        raise ValueError(f"Unsupported content type: {content_type}")

    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    data = json.loads(request_body or "{}")

    prompt = data.get("prompt")
    if not prompt or not str(prompt).strip():
        raise ValueError("'prompt' is required")

    face_b64 = data.get("face_image_base64") or data.get("reference_face_base64")
    if not face_b64:
        raise ValueError("'face_image_base64' or 'reference_face_base64' is required for identity generation")

    try:
        face_bytes = base64.b64decode(face_b64)
        face_image = Image.open(BytesIO(face_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid face_image_base64: {e}") from e

    identity_embedding = data.get("identity_embedding")
    if identity_embedding is not None and not isinstance(identity_embedding, (list, tuple)):
        raise ValueError("identity_embedding must be a list of floats")
    if identity_embedding is not None:
        identity_embedding = np.array(identity_embedding, dtype=np.float32)

    method = (data.get("identity_method") or data.get("method") or "ensemble").lower()
    if method not in ("instantid", "faceadapter", "photomaker", "ensemble"):
        method = "ensemble"

    return {
        "prompt": str(prompt).strip(),
        "face_image": face_image,
        "identity_embedding": identity_embedding if identity_embedding is not None else np.zeros(512, dtype=np.float32),
        "method": method,
        "negative_prompt": data.get("negative_prompt", ""),
        "width": int(data.get("width", 1024)),
        "height": int(data.get("height", 1024)),
        "num_inference_steps": int(data.get("num_inference_steps", 45)),
        "guidance_scale": float(data.get("guidance_scale", 7.5)),
        "seed": data.get("seed"),
    }


def predict_fn(input_data, model):
    """Run Identity Engine V2 generation and return result."""
    engine = model["engine"]
    result = {
        "image_base64": None,
        "similarity": 0.0,
        "path": "",
        "guaranteed": False,
        "error": None,
        "inference_time": 0.0,
    }

    start = time.time()
    try:
        gen_result = engine.generate_with_identity(
            prompt=input_data["prompt"],
            identity_embedding=input_data["identity_embedding"],
            face_image=input_data["face_image"],
            method=input_data["method"],
            negative_prompt=input_data.get("negative_prompt", ""),
            width=input_data.get("width", 1024),
            height=input_data.get("height", 1024),
            num_inference_steps=input_data.get("num_inference_steps", 45),
            guidance_scale=input_data.get("guidance_scale", 7.5),
            seed=input_data.get("seed"),
        )
        result["inference_time"] = time.time() - start

        if gen_result.error:
            result["error"] = gen_result.error
            return result

        result["image_base64"] = result_to_base64(gen_result)
        result["similarity"] = float(gen_result.similarity)
        result["path"] = gen_result.path
        result["guaranteed"] = bool(gen_result.guaranteed)
        if gen_result.scores:
            result["scores"] = gen_result.scores
        print(f"Identity V2: path={gen_result.path} similarity={gen_result.similarity:.3f} guaranteed={gen_result.guaranteed}")
    except Exception as e:
        result["error"] = f"{str(e)}\n{traceback.format_exc()}"
        result["inference_time"] = time.time() - start
        print(f"Identity V2 predict failed: {result['error']}")

    return result


def output_fn(prediction, content_type="application/json"):
    """Return JSON with image_base64, similarity, path, guaranteed, error."""
    out = {
        "image_base64": prediction.get("image_base64"),
        "similarity": prediction.get("similarity", 0.0),
        "path": prediction.get("path", ""),
        "guaranteed": prediction.get("guaranteed", False),
        "inference_time": prediction.get("inference_time", 0.0),
        "error": prediction.get("error"),
    }
    if prediction.get("scores"):
        out["scores"] = prediction["scores"]
    return json.dumps(out)

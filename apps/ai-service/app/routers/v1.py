"""
API v1 routes.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException  # type: ignore[reportMissingImports]
from pydantic import BaseModel  # type: ignore[reportMissingImports]

from app.models.generation import V1GenerateRequest, V1GenerateResponse  # type: ignore[reportAttributeAccessIssue]
from app.services.safety.dual_pipeline import (  # type: ignore[reportAttributeAccessIssue]
    pre_generation_check,
    post_generation_check,
)
from app.services.identity import load_identity
from app.services.ai.sdxl_pipeline import generate_with_mode

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Training models
# ---------------------------------------------------------------------------

class TrainRequest(BaseModel):
    user_id: str
    identity_id: str
    photo_urls: list[str]


class TrainResponse(BaseModel):
    success: bool
    message: str
    identity_id: Optional[str] = None


@router.post("/generate", response_model=V1GenerateResponse)
async def generate_image(req: V1GenerateRequest) -> V1GenerateResponse:
    """Main generation endpoint."""

    # 1. Pre-generation safety check
    safety_check = await pre_generation_check(
        user_id=req.user_id,
        prompt=req.prompt,
        mode=req.mode,
    )

    if not safety_check["allowed"]:
        return V1GenerateResponse(
            images=[],
            error=True,
            violations=safety_check["violations"],
        )

    # 2. Load identity (LoRA + face embedding)
    identity = await load_identity(req.identity_id)

    # 3. Generate images
    images = await generate_with_mode(
        prompt=req.prompt,
        mode=req.mode,
        identity=identity,
        num_outputs=2,
    )

    # 4. Post-generation safety check
    safe_images: list[str] = []
    for img in images:
        post_check = await post_generation_check(
            generated_image_path=img,
            mode=req.mode,
        )
        if post_check["safe"]:
            safe_images.append(img)

    return V1GenerateResponse(images=safe_images, error=False)


# ---------------------------------------------------------------------------
# Training endpoint
# ---------------------------------------------------------------------------

# In-memory training status store (replace with DB/Redis in production)
_training_status: dict[str, dict] = {}


def get_training_status(identity_id: str) -> dict | None:
    return _training_status.get(identity_id)


async def _run_training(identity_id: str, user_id: str, photo_urls: list[str]) -> None:
    """Background task that simulates training steps.

    In production this would call the actual LoRA training pipeline on GPU.
    """
    steps = [
        ("Uploading photos", 5),
        ("Validating images", 15),
        ("Detecting faces", 25),
        ("Preprocessing", 35),
        ("Generating captions", 50),
        ("Training model", 80),
        ("Extracting embeddings", 90),
        ("Finalizing", 100),
    ]

    for step_name, progress in steps:
        _training_status[identity_id] = {
            "identity_id": identity_id,
            "status": "TRAINING",
            "progress": progress,
            "message": step_name,
        }
        # Simulate work (replace with real GPU training)
        delay = 3.0 if step_name == "Training model" else 1.0
        await asyncio.sleep(delay)

    _training_status[identity_id] = {
        "identity_id": identity_id,
        "status": "COMPLETED",
        "progress": 100,
        "message": "Training complete",
    }
    logger.info("Training completed for identity %s", identity_id)


@router.post("/identities/{identity_id}/train", response_model=TrainResponse)
async def train_identity(
    identity_id: str,
    req: TrainRequest,
    background_tasks: BackgroundTasks,
) -> TrainResponse:
    """Start LoRA training for an identity."""
    if not req.photo_urls:
        raise HTTPException(status_code=400, detail="No photo URLs provided")

    existing = get_training_status(identity_id)
    if existing and existing.get("status") == "TRAINING":
        return TrainResponse(
            success=False,
            message="Training already in progress",
            identity_id=identity_id,
        )

    # Launch training in background
    _training_status[identity_id] = {
        "identity_id": identity_id,
        "status": "TRAINING",
        "progress": 0,
        "message": "Starting training...",
    }
    background_tasks.add_task(_run_training, identity_id, req.user_id, req.photo_urls)

    return TrainResponse(
        success=True,
        message="Training started successfully",
        identity_id=identity_id,
    )


@router.get("/identities/{identity_id}/training-status")
async def training_status(identity_id: str) -> dict:
    """Poll training progress for an identity."""
    status = get_training_status(identity_id)
    if not status:
        raise HTTPException(status_code=404, detail="No training found for this identity")
    return status

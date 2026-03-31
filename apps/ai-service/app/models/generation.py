from pydantic import BaseModel  # type: ignore[reportMissingImports]
from typing import Literal


class GenerationRequest(BaseModel):
    prompt: str
    mode: Literal["realism", "creative", "romantic"] = "realism"
    identity_id: str | None = None
    preset: str | None = None
    num_outputs: int = 1


class PreviewResponse(BaseModel):
    preview_image: str
    message: str
    estimated_time: str
    quality_level: str


class FullQualityResponse(BaseModel):
    final_image: str
    message: str


class V1GenerateRequest(BaseModel):
    """Request body for POST /api/v1/generate."""
    identity_id: str
    prompt: str
    mode: Literal["realism", "creative", "romantic"] = "realism"
    user_id: str


class V1GenerateResponse(BaseModel):
    """Response for POST /api/v1/generate."""
    images: list[str]
    error: bool = False
    violations: list[str] | None = None

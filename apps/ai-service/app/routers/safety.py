from fastapi import APIRouter  # type: ignore[reportMissingImports]
from pydantic import BaseModel  # type: ignore[reportMissingImports]

router = APIRouter()


class ModerationRequest(BaseModel):
    prompt: str
    image_url: str | None = None


@router.post("/moderate")
async def moderate(req: ModerationRequest):
    # Dual pipeline: prompt_sanitizer -> nsfw_classifier / age_estimator
    return {"allowed": True, "reason": "placeholder"}

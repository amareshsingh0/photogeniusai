from fastapi import APIRouter  # type: ignore[reportMissingImports]

router = APIRouter()


@router.post("/lora")
async def train_lora():
    # LoRA training pipeline (RunPod/Modal GPU)
    return {"status": "placeholder", "message": "Connect LoRA trainer to GPU compute"}

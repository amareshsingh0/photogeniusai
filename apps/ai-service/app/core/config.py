import os
from pathlib import Path

from pydantic_settings import BaseSettings  # type: ignore[reportMissingImports]

# Load from apps/ai-service/.env.local (fallback to .env if .env.local doesn't exist)
_AI_SERVICE_DIR = Path(__file__).resolve().parents[2]  # core -> app -> ai-service
_ENV_FILE = _AI_SERVICE_DIR / ".env.local"
if not _ENV_FILE.exists():
    _ENV_FILE = _AI_SERVICE_DIR / ".env"


class Settings(BaseSettings):
    ai_service_url: str = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8001")
    database_url: str = os.getenv("DATABASE_URL", "")
    redis_url: str = os.getenv("REDIS_URL", "")
    huggingface_token: str = os.getenv("HUGGINGFACE_TOKEN", "")
    runpod_api_key: str = os.getenv("RUNPOD_API_KEY", "")
    s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "")
    s3_access_key: str = os.getenv("S3_ACCESS_KEY", "")
    s3_secret_key: str = os.getenv("S3_SECRET_KEY", "")
    s3_region: str = os.getenv("S3_REGION", "us-east-1")
    s3_endpoint: str = os.getenv("S3_ENDPOINT", "")

    # Modal GPU settings
    modal_app_name: str = os.getenv("MODAL_APP_NAME", "photogenius-ai")
    modal_gpu_type: str = os.getenv("MODAL_GPU_TYPE", "A10G")
    modal_gpu_timeout: int = int(os.getenv("MODAL_GPU_TIMEOUT", "600"))
    modal_gpu_memory: int = int(os.getenv("MODAL_GPU_MEMORY", "16384"))
    modal_volume_name: str = os.getenv("MODAL_VOLUME_NAME", "photogenius-models")
    modal_lora_volume: str = os.getenv("MODAL_LORA_VOLUME", "photogenius-loras")

    # Model settings
    model_cache_dir: str = os.getenv("MODEL_CACHE_DIR", "/root/.cache/huggingface")
    sdxl_model_id: str = os.getenv("SDXL_MODEL_ID", "stabilityai/stable-diffusion-xl-base-1.0")
    sdxl_turbo_model_id: str = os.getenv("SDXL_TURBO_MODEL_ID", "stabilityai/sdxl-turbo")

    # LoRA training
    lora_rank: int = int(os.getenv("LORA_RANK", "32"))
    lora_alpha: int = int(os.getenv("LORA_ALPHA", "32"))
    lora_train_steps: int = int(os.getenv("LORA_TRAIN_STEPS", "1000"))
    lora_learning_rate: float = float(os.getenv("LORA_LEARNING_RATE", "1e-4"))
    lora_batch_size: int = int(os.getenv("LORA_BATCH_SIZE", "1"))
    lora_resolution: int = int(os.getenv("LORA_RESOLUTION", "1024"))

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "protected_namespaces": ("settings_",),  # Allow model_ prefix for our fields
    }


settings = Settings()

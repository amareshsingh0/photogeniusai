"""
PhotoGenius AI – Complete type-safe configuration with Pydantic.
Validates all environment variables on startup.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import List, Optional

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load from apps/api/.env.local (fallback to .env if .env.local doesn't exist)
_API_DIR = Path(__file__).resolve().parents[2]  # core -> app -> api
_ENV_FILE = _API_DIR / ".env.local"
if not _ENV_FILE.exists():
    _ENV_FILE = _API_DIR / ".env"


class Settings(BaseSettings):
    """
    Application settings with validation.
    All required fields must be set in production.
    """

    # ==================== Application ====================
    APP_NAME: str = "PhotoGenius AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(False, env="DEBUG")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")

    # ==================== API ====================
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = Field(default=["http://localhost:3000"], env="ALLOWED_ORIGINS")

    # ==================== Database ====================
    DATABASE_URL: Optional[PostgresDsn] = Field(default=None, env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = Field(10, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(20, env="DATABASE_MAX_OVERFLOW")

    # ==================== Redis ====================
    REDIS_URL: str = Field(default="redis://localhost:6379", env="REDIS_URL")

    # ==================== Authentication ====================
    CLERK_SECRET_KEY: str = Field(default="", env="CLERK_SECRET_KEY")
    JWT_SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32), env="JWT_SECRET_KEY"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # ==================== AWS S3 / R2 Storage ====================
    # Support both AWS_* and legacy S3_* env vars for backward compatibility
    AWS_ACCESS_KEY_ID: str = Field(default="", env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = Field(default="", env="AWS_SECRET_ACCESS_KEY")
    S3_ACCESS_KEY: str = Field(
        default="", env="S3_ACCESS_KEY"
    )  # Legacy - maps to AWS_ACCESS_KEY_ID
    S3_SECRET_KEY: str = Field(
        default="", env="S3_SECRET_KEY"
    )  # Legacy - maps to AWS_SECRET_ACCESS_KEY
    AWS_REGION: str = Field("us-east-1", env="AWS_REGION")
    S3_REGION: str = Field("auto", env="S3_REGION")  # Legacy - maps to AWS_REGION
    S3_BUCKET_NAME: str = Field(default="", env="S3_BUCKET_NAME")
    S3_ENDPOINT: Optional[str] = Field(None, env="S3_ENDPOINT")
    CLOUDFRONT_DOMAIN: Optional[str] = Field(None, env="CLOUDFRONT_DOMAIN")

    @model_validator(mode="after")
    def resolve_aws_credentials(self) -> "Settings":
        """Resolve AWS credentials from legacy S3_* vars if AWS_* not set"""
        # If AWS_* not set but S3_* is set, use S3_* values
        if not self.AWS_ACCESS_KEY_ID and self.S3_ACCESS_KEY:
            object.__setattr__(self, "AWS_ACCESS_KEY_ID", self.S3_ACCESS_KEY)
        if not self.AWS_SECRET_ACCESS_KEY and self.S3_SECRET_KEY:
            object.__setattr__(self, "AWS_SECRET_ACCESS_KEY", self.S3_SECRET_KEY)
        if self.S3_REGION and self.S3_REGION != "auto" and self.AWS_REGION == "us-east-1":
            object.__setattr__(self, "AWS_REGION", self.S3_REGION)
        return self

    # ==================== AI/ML ====================
    HUGGINGFACE_TOKEN: str = Field(default="", env="HUGGINGFACE_TOKEN")
    MODAL_TOKEN_ID: Optional[str] = Field(None, env="MODAL_TOKEN_ID")
    MODAL_TOKEN_SECRET: Optional[str] = Field(None, env="MODAL_TOKEN_SECRET")

    # Model Paths
    SDXL_MODEL_PATH: str = "stabilityai/stable-diffusion-xl-base-1.0"
    INSTANTID_MODEL_PATH: str = "InstantX/InstantID"

    # Generation Defaults
    DEFAULT_NUM_INFERENCE_STEPS: int = 30
    DEFAULT_GUIDANCE_SCALE: float = 7.5
    DEFAULT_IMAGE_SIZE: int = 1024

    # ==================== Safety ====================
    ENABLE_SAFETY_CHECKS: bool = Field(True, env="ENABLE_SAFETY_CHECKS")
    NSFW_THRESHOLD_REALISM: float = 0.60
    NSFW_THRESHOLD_CREATIVE: float = 0.70
    NSFW_THRESHOLD_ROMANTIC: float = 0.30
    MAX_USER_STRIKES: int = 3

    # ==================== Rate Limiting ====================
    RATE_LIMIT_GENERATION: str = "10/minute"
    RATE_LIMIT_TRAINING: str = "3/hour"
    RATE_LIMIT_UPLOAD: str = "20/minute"

    # ==================== Credits ====================
    CREDIT_COST_REALISM: int = 1
    CREDIT_COST_CREATIVE: int = 3
    CREDIT_COST_ROMANTIC: int = 3
    FREE_TIER_INITIAL_CREDITS: int = 15

    # ==================== Payments ====================
    STRIPE_SECRET_KEY: Optional[str] = Field(None, env="STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(None, env="STRIPE_WEBHOOK_SECRET")
    RAZORPAY_KEY_ID: Optional[str] = Field(None, env="RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET: Optional[str] = Field(None, env="RAZORPAY_KEY_SECRET")

    # ==================== Monitoring ====================
    SENTRY_DSN: Optional[str] = Field(None, env="SENTRY_DSN")
    SENTRY_ENVIRONMENT: str = Field("development", env="SENTRY_ENVIRONMENT")
    SENTRY_TRACES_SAMPLE_RATE: float = Field(1.0, env="SENTRY_TRACES_SAMPLE_RATE")

    # ==================== WebSocket ====================
    WEBSOCKET_PING_INTERVAL: int = 25
    WEBSOCKET_PING_TIMEOUT: int = 60

    # ==================== File Upload ====================
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_REFERENCE_PHOTOS: int = 20
    MIN_REFERENCE_PHOTOS: int = 8
    ALLOWED_IMAGE_FORMATS: List[str] = ["jpg", "jpeg", "png", "webp"]

    # ==================== Training ====================
    LORA_TRAINING_STEPS: int = 1000
    LORA_LEARNING_RATE: float = 1e-4
    LORA_RANK: int = 64

    # ==================== GPU Workers ====================
    # Worker Provider: "aws" (default, SageMaker/Lambda). "modal" and "runpod" are legacy/optional.
    GPU_WORKER_PRIMARY: str = Field("aws", env="GPU_WORKER_PRIMARY")
    GPU_WORKER_FALLBACK: Optional[str] = Field(None, env="GPU_WORKER_FALLBACK")

    # AWS GPU Configuration (SageMaker / Lambda)
    SAGEMAKER_ENDPOINT: Optional[str] = Field(None, env="SAGEMAKER_ENDPOINT")
    AWS_LAMBDA_GENERATION_URL: Optional[str] = Field(None, env="AWS_LAMBDA_GENERATION_URL")
    AWS_LAMBDA_TRAINING_URL: Optional[str] = Field(None, env="AWS_LAMBDA_TRAINING_URL")
    AWS_LAMBDA_SAFETY_URL: Optional[str] = Field(None, env="AWS_LAMBDA_SAFETY_URL")

    # RunPod Configuration
    RUNPOD_API_KEY: Optional[str] = Field(None, env="RUNPOD_API_KEY")
    RUNPOD_GENERATION_ENDPOINT: Optional[str] = Field(None, env="RUNPOD_GENERATION_ENDPOINT")
    RUNPOD_TRAINING_ENDPOINT: Optional[str] = Field(None, env="RUNPOD_TRAINING_ENDPOINT")

    # Task Queue Configuration
    TASK_QUEUE_MAX_CONCURRENT: int = Field(10, env="TASK_QUEUE_MAX_CONCURRENT")
    TASK_QUEUE_CLEANUP_HOURS: int = Field(24, env="TASK_QUEUE_CLEANUP_HOURS")

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    def get_credit_cost(self, mode: str) -> int:
        costs = {
            "REALISM": self.CREDIT_COST_REALISM,
            "CREATIVE": self.CREDIT_COST_CREATIVE,
            "ROMANTIC": self.CREDIT_COST_ROMANTIC,
        }
        return costs.get(mode.upper(), 1)

    def get_nsfw_threshold(self, mode: str) -> float:
        thresholds = {
            "REALISM": self.NSFW_THRESHOLD_REALISM,
            "CREATIVE": self.NSFW_THRESHOLD_CREATIVE,
            "ROMANTIC": self.NSFW_THRESHOLD_ROMANTIC,
        }
        return thresholds.get(mode.upper(), 0.60)


# Create global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
        validate_settings(_settings)
    return _settings


def validate_settings(settings: Settings) -> None:
    """Validate critical settings and log warnings."""
    errors = []
    warnings = []

    # In production, all critical fields are required
    if settings.is_production:
        # Check database
        if not settings.DATABASE_URL:
            errors.append("DATABASE_URL is required in production")

        # Check auth
        if not settings.CLERK_SECRET_KEY:
            errors.append("CLERK_SECRET_KEY is required in production")

        # Check storage (support both AWS_* and legacy S3_*)
        access_key = settings.AWS_ACCESS_KEY_ID or settings.S3_ACCESS_KEY
        secret_key = settings.AWS_SECRET_ACCESS_KEY or settings.S3_SECRET_KEY
        if not all([access_key, secret_key, settings.S3_BUCKET_NAME]):
            errors.append("AWS S3 credentials incomplete - required in production")

    # In development, warn about missing optional fields
    else:
        # Check database
        if not settings.DATABASE_URL:
            warnings.append("DATABASE_URL not set - using default local connection")

        # Check auth
        if not settings.CLERK_SECRET_KEY:
            warnings.append("CLERK_SECRET_KEY not set - authentication may not work")

        # Check storage (support both AWS_* and legacy S3_*)
        access_key = settings.AWS_ACCESS_KEY_ID or settings.S3_ACCESS_KEY
        secret_key = settings.AWS_SECRET_ACCESS_KEY or settings.S3_SECRET_KEY
        if not all([access_key, secret_key, settings.S3_BUCKET_NAME]):
            warnings.append("AWS S3 credentials incomplete - file uploads will fail")

    # Check AI (warning only - optional for development)
    if not settings.HUGGINGFACE_TOKEN:
        warnings.append("HUGGINGFACE_TOKEN not set - model downloads may fail")

    # Check payments (warning only)
    if not settings.STRIPE_SECRET_KEY:
        warnings.append("STRIPE_SECRET_KEY not set - payments disabled")

    # Log results
    if errors:
        raise ValueError(
            f"Critical configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    if warnings:
        print("[WARNING] Configuration warnings:")
        for w in warnings:
            print(f"  - {w}")

"""Common API response schemas."""
from pydantic import BaseModel  # type: ignore[reportMissingImports]


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None

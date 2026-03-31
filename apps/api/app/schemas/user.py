"""User request/response schemas."""
from pydantic import BaseModel  # type: ignore[reportMissingImports]


class UserOut(BaseModel):
    id: str
    email: str | None
    name: str | None

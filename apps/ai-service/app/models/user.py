from pydantic import BaseModel  # type: ignore[reportMissingImports]
from datetime import datetime


class UserBase(BaseModel):
    email: str


class User(UserBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

"""
FastAPI dependencies: DB session, auth, pagination.
"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUserId = Annotated[str | None, Depends(get_current_user_id)]

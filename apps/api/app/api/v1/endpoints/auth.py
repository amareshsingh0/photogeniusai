"""Auth endpoints: token, session."""
from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore[reportMissingImports]
from sqlalchemy import text, select  # type: ignore[reportMissingImports]
from sqlalchemy.ext.asyncio import AsyncSession  # type: ignore[reportMissingImports]
from app.core.security import RequireAuth
from app.schemas.user import UserOut
from app.core.database import get_db

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def get_me(
    user_id: str = RequireAuth,
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user profile from database
    Requires Bearer token with Clerk JWT
    """
    # Query user from database using Clerk ID
    # Note: This assumes users table has clerk_id column (snake_case in DB)
    result = await db.execute(
        text("""
            SELECT id, email, name
            FROM users
            WHERE clerk_id = :clerk_id
        """),
        {"clerk_id": user_id}
    )
    
    row = result.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database"
        )
    
    return UserOut(
        id=str(row.id),
        email=row.email,
        name=row.name,
    )


@router.get("/check-credits/{amount}")
async def check_credits(
    amount: int,
    user_id: str = RequireAuth,
    db: AsyncSession = Depends(get_db)
):
    """
    Check if user has sufficient credits
    Requires Bearer token with Clerk JWT
    
    NOTE: Credit checks are DISABLED during development/testing phase
    """
    # DEVELOPMENT MODE: Skip credit checks for testing
    SKIP_CREDIT_CHECKS = True  # Set to False to enable credit checks
    
    if amount < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive"
        )
    
    # Query user's credit balance
    result = await db.execute(
        text("""
            SELECT credits_balance, is_banned
            FROM users
            WHERE clerk_id = :clerk_id
        """),
        {"clerk_id": user_id}
    )
    
    row = result.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    credits_balance = row.credits_balance
    is_banned = row.is_banned
    
    if is_banned:
        return {
            "can_proceed": False,
            "reason": "Account banned",
            "current_balance": credits_balance,
            "required": amount,
        }
    
    # Skip credit check in development mode
    if SKIP_CREDIT_CHECKS:
        print(f"[DEV] Credit check skipped - required: {amount}, user: {user_id}")
        return {
            "can_proceed": True,
            "current_balance": credits_balance,
            "required": amount,
            "reason": None,
        }
    
    can_proceed = credits_balance >= amount
    
    return {
        "can_proceed": can_proceed,
        "current_balance": credits_balance,
        "required": amount,
        "reason": None if can_proceed else "Insufficient credits",
    }

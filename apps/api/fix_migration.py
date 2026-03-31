"""
Helper script to fix Alembic migration state if table already exists.
Run this if you get 'DuplicateTableError' when running migrations.
"""
import asyncio
from sqlalchemy import text  # type: ignore[reportMissingImports]
from app.core.database import AsyncSessionLocal
from alembic.config import Config  # type: ignore[reportMissingImports]
from alembic import command  # type: ignore[reportMissingImports,reportAttributeAccessIssue]
from alembic.script import ScriptDirectory  # type: ignore[reportMissingImports]


async def check_and_stamp_migration():
    """Check if table exists and stamp migration if needed."""
    async with AsyncSessionLocal() as session:
        # Check if table exists
        result = await session.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'safety_audit_logs')")
        )
        table_exists = result.scalar()
        
        if table_exists:
            print("✓ Table 'safety_audit_logs' exists")
            
            # Check if migration is already stamped
            result = await session.execute(
                text("SELECT version_num FROM alembic_version")
            )
            current_version = result.scalar()
            
            if current_version != '001_safety_audit':
                print(f"Current Alembic version: {current_version}")
                print("Stamping migration '001_safety_audit'...")
                # Note: This requires running `alembic stamp 001_safety_audit` manually
                print("Please run: alembic stamp 001_safety_audit")
            else:
                print("✓ Migration already stamped")
        else:
            print("✗ Table 'safety_audit_logs' does not exist")
            print("Run: alembic upgrade head")


if __name__ == "__main__":
    asyncio.run(check_and_stamp_migration())

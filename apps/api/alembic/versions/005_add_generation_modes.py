"""Add new GenerationMode enum values (CINEMATIC, FASHION, COOL_EDGY, ARTISTIC, MAX_SURPRISE)

Revision ID: 005
Revises: 004
Create Date: 2026-02-01

Adds all AI pipeline types to the generation mode enum so backend can accept
and store generations for: CINEMATIC, FASHION, COOL_EDGY, ARTISTIC, MAX_SURPRISE.
Works with Prisma-created enum (GenerationMode) or SQLAlchemy (generationmode).
"""

from alembic import op  # type: ignore[reportAttributeAccessIssue]

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

NEW_VALUES = ["CINEMATIC", "FASHION", "COOL_EDGY", "ARTISTIC", "MAX_SURPRISE"]


def upgrade() -> None:
    """Add new values to GenerationMode enum. Works with Prisma (GenerationMode) or SQLAlchemy (generationmode)."""
    op.execute("""
        DO $$
        DECLARE
            typ text;
            v text;
        BEGIN
            SELECT t.typname INTO typ FROM pg_type t
            WHERE t.typtype = 'e' AND t.typname IN ('GenerationMode', 'generationmode') LIMIT 1;
            IF typ IS NOT NULL THEN
                FOREACH v IN ARRAY ARRAY['CINEMATIC', 'FASHION', 'COOL_EDGY', 'ARTISTIC', 'MAX_SURPRISE'] LOOP
                    EXECUTE format('ALTER TYPE %I ADD VALUE IF NOT EXISTS %L', typ, v);
                END LOOP;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """PostgreSQL does not support removing enum values easily."""
    pass

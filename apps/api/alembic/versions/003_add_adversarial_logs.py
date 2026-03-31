"""add adversarial_logs table

Revision ID: 003_adversarial_logs
Revises: 002_credit_usage
Create Date: 2026-01-29

"""
from alembic import op  # type: ignore[reportAttributeAccessIssue]
import sqlalchemy as sa  # type: ignore[reportMissingImports]
from sqlalchemy.dialects import postgresql  # type: ignore[reportMissingImports]

revision = "003_adversarial_logs"
down_revision = "002_credit_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'adversarial_logs') THEN
                CREATE TABLE adversarial_logs (
                    id SERIAL NOT NULL,
                    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    prompt TEXT NOT NULL,
                    detections JSONB,
                    sanitized_prompt TEXT,
                    was_blocked VARCHAR(10) NOT NULL DEFAULT 'false',
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (id)
                );
                CREATE INDEX idx_adversarial_user_timestamp ON adversarial_logs(user_id, timestamp);
                CREATE INDEX idx_adversarial_timestamp ON adversarial_logs(timestamp);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS adversarial_logs CASCADE;")

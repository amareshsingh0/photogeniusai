"""add credit_transactions and generation_usage

Revision ID: 002_credit_usage
Revises: 001_safety_audit
Create Date: 2026-01-29

"""
from alembic import op  # type: ignore[reportAttributeAccessIssue]
import sqlalchemy as sa  # type: ignore[reportMissingImports]
from sqlalchemy.dialects import postgresql  # type: ignore[reportMissingImports]

revision = "002_credit_usage"
down_revision = "001_safety_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'credit_transactions') THEN
                CREATE TABLE credit_transactions (
                    id SERIAL NOT NULL,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    amount INTEGER NOT NULL,
                    transaction_type VARCHAR(50) NOT NULL,
                    description VARCHAR(500),
                    balance_after INTEGER NOT NULL,
                    reference_id VARCHAR(255),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (id)
                );
                CREATE INDEX idx_credit_transactions_user ON credit_transactions(user_id);
                CREATE INDEX idx_credit_transactions_created ON credit_transactions(created_at);
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'generation_usage') THEN
                CREATE TABLE generation_usage (
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    usage_date DATE NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, usage_date)
                );
                CREATE INDEX idx_generation_usage_date ON generation_usage(usage_date);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS generation_usage CASCADE;")
    op.execute("DROP TABLE IF EXISTS credit_transactions CASCADE;")

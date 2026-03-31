"""add safety audit logs table

Revision ID: 001_safety_audit
Revises: 
Create Date: 2026-01-26 21:00:00.000000

"""
from alembic import op  # type: ignore[reportAttributeAccessIssue]
import sqlalchemy as sa  # type: ignore[reportMissingImports]
from sqlalchemy.dialects import postgresql  # type: ignore[reportMissingImports]

# revision identifiers, used by Alembic.
revision = '001_safety_audit'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if table exists and create if not (using raw SQL to avoid transaction issues)
    op.execute('''
        DO $$
        BEGIN
            -- Create table if it doesn't exist
            IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'safety_audit_logs') THEN
                CREATE TABLE safety_audit_logs (
                    id SERIAL NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    stage VARCHAR(50),
                    action VARCHAR(50),
                    user_id VARCHAR(255),
                    generation_id VARCHAR(255),
                    violations JSONB,
                    scores JSONB,
                    prompt TEXT,
                    image_url TEXT,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    metadata JSONB,
                    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    PRIMARY KEY (id)
                );
            END IF;
        END $$;
    ''')
    
    # Create indexes separately (only if table exists and has the columns)
    # Check if table has required columns before creating indexes
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'safety_audit_logs' 
            AND column_name = 'user_id'
        )
    """))
    has_columns = result.scalar()
    
    if has_columns:
        # Create indexes if they don't exist
        op.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_user') THEN
                    CREATE INDEX idx_safety_audit_user ON safety_audit_logs(user_id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_generation') THEN
                    CREATE INDEX idx_safety_audit_generation ON safety_audit_logs(generation_id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_timestamp') THEN
                    CREATE INDEX idx_safety_audit_timestamp ON safety_audit_logs(timestamp);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_expires') THEN
                    CREATE INDEX idx_safety_audit_expires ON safety_audit_logs(expires_at);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_event_type') THEN
                    CREATE INDEX idx_safety_audit_event_type ON safety_audit_logs(event_type);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_user_timestamp') THEN
                    CREATE INDEX idx_safety_audit_user_timestamp ON safety_audit_logs(user_id, timestamp);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_generation_timestamp') THEN
                    CREATE INDEX idx_safety_audit_generation_timestamp ON safety_audit_logs(generation_id, timestamp);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_event_timestamp') THEN
                    CREATE INDEX idx_safety_audit_event_timestamp ON safety_audit_logs(event_type, timestamp);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_violations') THEN
                    CREATE INDEX idx_safety_audit_violations ON safety_audit_logs USING GIN (violations);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_scores') THEN
                    CREATE INDEX idx_safety_audit_scores ON safety_audit_logs USING GIN (scores);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_safety_audit_metadata') THEN
                    CREATE INDEX idx_safety_audit_metadata ON safety_audit_logs USING GIN (metadata);
                END IF;
            END $$;
        ''')


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_safety_audit_metadata', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_scores', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_violations', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_event_timestamp', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_generation_timestamp', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_user_timestamp', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_event_type', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_expires', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_timestamp', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_generation', table_name='safety_audit_logs')
    op.drop_index('idx_safety_audit_user', table_name='safety_audit_logs')
    
    # Drop table
    op.drop_table('safety_audit_logs')

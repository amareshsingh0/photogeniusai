"""Make identityId nullable in generations table

Revision ID: 004
Revises: 003_add_adversarial_logs
Create Date: 2026-01-30

This migration makes the identityId column nullable in the generations table
to support non-identity based generations (general image generation without
face consistency).
"""

from alembic import op  # type: ignore[reportAttributeAccessIssue]
import sqlalchemy as sa  # type: ignore[reportMissingImports]

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003_adversarial_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make identityId nullable in generations table"""

    # Drop the existing foreign key constraint
    op.drop_constraint(
        'generations_identityId_fkey',
        'generations',
        type_='foreignkey'
    )

    # Alter the column to be nullable
    op.alter_column(
        'generations',
        'identityId',
        existing_type=sa.UUID(),
        nullable=True
    )

    # Re-create the foreign key constraint with nullable support
    op.create_foreign_key(
        'generations_identityId_fkey',
        'generations',
        'identities',
        ['identityId'],
        ['id'],
        ondelete='RESTRICT'
    )

    # Add index for faster queries on non-identity generations (quoted column for PostgreSQL)
    op.execute(
        'CREATE INDEX ix_generations_identityId_null ON generations ("identityId") WHERE "identityId" IS NULL'
    )


def downgrade() -> None:
    """Revert identityId to non-nullable (will fail if NULL values exist)"""

    # Drop the partial index
    op.execute('DROP INDEX IF EXISTS ix_generations_identityId_null')

    # Drop foreign key
    op.drop_constraint(
        'generations_identityId_fkey',
        'generations',
        type_='foreignkey'
    )

    # Make column non-nullable (will fail if NULL values exist)
    op.alter_column(
        'generations',
        'identityId',
        existing_type=sa.UUID(),
        nullable=False
    )

    # Re-create foreign key
    op.create_foreign_key(
        'generations_identityId_fkey',
        'generations',
        'identities',
        ['identityId'],
        ['id'],
        ondelete='RESTRICT'
    )

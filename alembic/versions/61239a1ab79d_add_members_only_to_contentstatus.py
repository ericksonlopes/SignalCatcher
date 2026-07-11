"""add MEMBERS_ONLY to ContentStatus

Revision ID: 61239a1ab79d
Revises: 71d99b3e6db4
Create Date: 2026-07-10 22:14:49.203431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61239a1ab79d'
down_revision: Union[str, Sequence[str], None] = '71d99b3e6db4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new enum value to PostgreSQL
    op.execute("ALTER TYPE contentstatus ADD VALUE 'MEMBERS_ONLY'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres doesn't easily support dropping ENUM values.
    pass

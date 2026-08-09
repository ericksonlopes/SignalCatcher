"""Add DELETED to contentstep enum

Revision ID: 474bbaa347d1
Revises: c3e3d4c6d21e
Create Date: 2026-08-08 21:10:37.348125

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '474bbaa347d1'
down_revision: Union[str, Sequence[str], None] = 'c3e3d4c6d21e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Disable transaction to allow ALTER TYPE
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'DELETED'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL does not easily support dropping an enum value.
    pass

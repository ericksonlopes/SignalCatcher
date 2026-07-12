"""add COPYRIGHT_REMOVED to contentstatus

Revision ID: 39c21a6249cc
Revises: 871e2c7eaf91
Create Date: 2026-07-11 17:17:41.658253

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39c21a6249cc'
down_revision: Union[str, Sequence[str], None] = '871e2c7eaf91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE contentstatus ADD VALUE IF NOT EXISTS 'COPYRIGHT_REMOVED'")


def downgrade() -> None:
    """Downgrade schema."""
    pass

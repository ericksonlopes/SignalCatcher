"""add PRIVATE_VIDEO to contentstatus

Revision ID: 871e2c7eaf91
Revises: 336413857350
Create Date: 2026-07-11 16:50:17.416092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '871e2c7eaf91'
down_revision: Union[str, Sequence[str], None] = '336413857350'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE contentstatus ADD VALUE IF NOT EXISTS 'PRIVATE_VIDEO'")


def downgrade() -> None:
    """Downgrade schema."""
    pass

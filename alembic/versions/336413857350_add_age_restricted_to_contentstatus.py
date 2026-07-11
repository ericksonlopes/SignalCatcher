"""add AGE_RESTRICTED to contentstatus

Revision ID: 336413857350
Revises: 61239a1ab79d
Create Date: 2026-07-11 12:35:47.072901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '336413857350'
down_revision: Union[str, Sequence[str], None] = '61239a1ab79d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE contentstatus ADD VALUE IF NOT EXISTS 'AGE_RESTRICTED'")


def downgrade() -> None:
    """Downgrade schema."""
    pass

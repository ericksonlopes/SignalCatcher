"""add ACCOUNT_TERMINATED to contentstatus

Revision ID: 1889415f2735
Revises: 39c21a6249cc
Create Date: 2026-07-11 23:53:06.680272

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1889415f2735'
down_revision: Union[str, Sequence[str], None] = '39c21a6249cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE contentstatus ADD VALUE IF NOT EXISTS 'ACCOUNT_TERMINATED'")


def downgrade() -> None:
    """Downgrade schema."""
    pass

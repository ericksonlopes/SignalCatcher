"""Add REPROCESSING to ContentStep enum

Revision ID: c3e3d4c6d21e
Revises: bf15f631b939
Create Date: 2026-08-08 20:10:02.500698

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e3d4c6d21e'
down_revision: Union[str, Sequence[str], None] = 'bf15f631b939'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres requires ALTER TYPE to be outside a transaction block
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'REPROCESSING'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an ENUM type easily.
    pass

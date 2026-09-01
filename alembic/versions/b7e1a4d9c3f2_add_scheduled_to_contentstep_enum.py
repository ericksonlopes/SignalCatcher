"""Add SCHEDULED to ContentStep enum

Revision ID: b7e1a4d9c3f2
Revises: a1c4e9b7d520
Create Date: 2026-09-01 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e1a4d9c3f2'
down_revision: Union[str, Sequence[str], None] = 'a1c4e9b7d520'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres requires ALTER TYPE to run outside a transaction block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'SCHEDULED'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an ENUM type easily.
    pass

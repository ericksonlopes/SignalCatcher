"""Add diarization steps to contentstep enum

Revision ID: a5b693182f1c
Revises: e0b00fb5e6a5
Create Date: 2026-08-13 22:56:42.932773

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5b693182f1c'
down_revision: Union[str, Sequence[str], None] = 'e0b00fb5e6a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'PENDING'")
        op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'TRANSCRIPTION'")
        op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'ALIGNMENT'")
        op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'DIARIZATION'")


def downgrade() -> None:
    """Downgrade schema."""
    pass

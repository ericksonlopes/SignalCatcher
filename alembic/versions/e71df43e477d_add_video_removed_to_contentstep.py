"""add_video_removed_to_contentstep

Revision ID: e71df43e477d
Revises: 321883853f85
Create Date: 2026-08-07 17:52:48.795634

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e71df43e477d'
down_revision: Union[str, Sequence[str], None] = '321883853f85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE contentstep ADD VALUE 'VIDEO_REMOVED'")


def downgrade() -> None:
    """Downgrade schema."""
    pass

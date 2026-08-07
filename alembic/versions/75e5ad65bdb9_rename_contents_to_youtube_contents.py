"""rename_contents_to_youtube_contents

Revision ID: 75e5ad65bdb9
Revises: 1889415f2735
Create Date: 2026-08-07 12:38:28.770222

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '75e5ad65bdb9'
down_revision: Union[str, Sequence[str], None] = '1889415f2735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('contents', 'youtube_contents')
    op.execute('ALTER INDEX ix_contents_external_id RENAME TO ix_youtube_contents_external_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('ALTER INDEX ix_youtube_contents_external_id RENAME TO ix_contents_external_id')
    op.rename_table('youtube_contents', 'contents')

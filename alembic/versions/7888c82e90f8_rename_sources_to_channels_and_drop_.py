"""rename_sources_to_channels_and_drop_platform

Revision ID: 7888c82e90f8
Revises: d1b88777f017
Create Date: 2026-08-07 21:51:29.509676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7888c82e90f8'
down_revision: Union[str, Sequence[str], None] = 'd1b88777f017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename table to preserve data
    op.rename_table('monitored_sources', 'youtube_monitored_channels')
    
    # Drop the source_platform column
    op.drop_column('youtube_monitored_channels', 'source_platform')


def downgrade() -> None:
    """Downgrade schema."""
    # Add the column back
    op.add_column('youtube_monitored_channels', sa.Column('source_platform', sa.VARCHAR(), nullable=True))
    
    # Rename table back
    op.rename_table('youtube_monitored_channels', 'monitored_sources')

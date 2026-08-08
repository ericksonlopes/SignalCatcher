"""rename content_tracking to step_tracking

Revision ID: bf15f631b939
Revises: a22060bc6f25
Create Date: 2026-08-08 10:52:36.571478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf15f631b939'
down_revision: Union[str, Sequence[str], None] = 'a22060bc6f25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('content_tracking', 'step_tracking')
    op.execute("ALTER INDEX ix_content_tracking_entity_id RENAME TO ix_step_tracking_entity_id")
    op.execute("ALTER INDEX ix_content_tracking_entity_type RENAME TO ix_step_tracking_entity_type")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER INDEX ix_step_tracking_entity_type RENAME TO ix_content_tracking_entity_type")
    op.execute("ALTER INDEX ix_step_tracking_entity_id RENAME TO ix_content_tracking_entity_id")
    op.rename_table('step_tracking', 'content_tracking')

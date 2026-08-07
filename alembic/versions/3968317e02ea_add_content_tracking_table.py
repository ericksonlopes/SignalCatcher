"""add content_tracking table

Revision ID: 3968317e02ea
Revises: 886b855642ed
Create Date: 2026-08-07 14:36:03.812821

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3968317e02ea"
down_revision: Union[str, Sequence[str], None] = "886b855642ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "content_tracking",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("previous_step", sa.String(), nullable=True),
        sa.Column("new_step", sa.String(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("details", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_content_tracking_entity_id"),
        "content_tracking",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_tracking_entity_type"),
        "content_tracking",
        ["entity_type"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_content_tracking_entity_type"), table_name="content_tracking"
    )
    op.drop_index(op.f("ix_content_tracking_entity_id"), table_name="content_tracking")
    op.drop_table("content_tracking")

"""Remove the unused dedicated DemoGraph worker heartbeat."""

import sqlalchemy as sa

from alembic import op

revision = "da2026100202"
down_revision = "da2026100201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("demograph_worker")


def downgrade() -> None:
    op.create_table(
        "demograph_worker",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )

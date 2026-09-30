"""Store progress within the current diarization stage."""

import sqlalchemy as sa

from alembic import op

revision = "d942e72b109a"
down_revision = "c8a4126f90d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("diarization", sa.Column("progress_percent", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("diarization", "progress_percent")

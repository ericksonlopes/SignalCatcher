"""Order diarization requests and allow replacing the current execution."""

from alembic import op
import sqlalchemy as sa

revision = "f39ca82610b4"
down_revision = "e82b104d39ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("diarization", sa.Column("queued_at", sa.DateTime(), nullable=True))
    op.add_column("diarization", sa.Column("queue_priority", sa.Integer(), server_default="0", nullable=False))
    op.execute("UPDATE diarization SET queued_at = created_at")


def downgrade() -> None:
    op.drop_column("diarization", "queue_priority")
    op.drop_column("diarization", "queued_at")

"""Track diarization worker ownership and detect interrupted processing."""

from alembic import op
import sqlalchemy as sa

revision = "e82b104d39ac"
down_revision = "d942e72b109a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("diarization", sa.Column("worker_token", sa.String(), nullable=True))
    op.add_column("diarization", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("diarization", "lease_expires_at")
    op.drop_column("diarization", "worker_token")

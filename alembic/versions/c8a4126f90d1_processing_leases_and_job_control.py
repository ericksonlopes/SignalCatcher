"""Add content reservations, retry/deletion queues and worker telemetry."""

from alembic import op
import sqlalchemy as sa

revision = "c8a4126f90d1"
down_revision = "b7e1a4d9c3f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in [
        sa.Column("lease_token", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deletion_attempt_count", sa.Integer(), nullable=False, server_default="0"),
    ]:
        op.add_column("youtube_contents", column)
    op.create_index("ix_youtube_processing_queue", "youtube_contents", ["step", "next_retry_at", "id"])
    op.create_index("ix_youtube_deletion_queue", "youtube_contents", ["deletion_requested", "next_retry_at"])
    op.create_table(
        "job_control",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("running", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requested_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("last_duration_seconds", sa.Float()),
        sa.Column("last_error", sa.String()),
        sa.Column("runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("job_control")
    op.drop_index("ix_youtube_deletion_queue", table_name="youtube_contents")
    op.drop_index("ix_youtube_processing_queue", table_name="youtube_contents")
    for name in [
        "deletion_attempt_count", "deletion_requested", "next_retry_at", "attempt_count",
        "lease_expires_at", "lease_token",
    ]:
        op.drop_column("youtube_contents", name)

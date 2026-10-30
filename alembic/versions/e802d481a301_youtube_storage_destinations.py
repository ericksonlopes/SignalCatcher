"""Persistent storage destinations, Drive inventory, transfers and history."""

import sqlalchemy as sa

from alembic import op

revision = "e802d481a301"
down_revision = "b984a2acc7e4"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind in (
        ("storage_location", sa.String(10)),
        ("storage_mode", sa.String(10)),
        ("staging_path", sa.String()),
        ("storage_size", sa.BigInteger()),
        ("storage_verified_at", sa.DateTime(timezone=True)),
        ("drive_file_id", sa.String()),
        ("drive_url", sa.String()),
    ):
        op.add_column("youtube_contents", sa.Column(name, kind, nullable=True))
    op.create_index(
        "ix_youtube_contents_storage_location", "youtube_contents", ["storage_location"]
    )
    op.create_table(
        "youtube_storage_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("uploads_paused", sa.Boolean(), nullable=False),
        sa.Column("max_upload_mib_per_second", sa.Float()),
        sa.Column("drive_ready", sa.Boolean(), nullable=False),
        sa.Column("drive_info", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("catalog_error", sa.Text()),
        sa.Column("catalog_updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        sa.text(
            "INSERT INTO youtube_storage_settings "
            "(id, mode, uploads_paused, drive_ready, drive_info) "
            "VALUES (1, 'BOTH', false, false, '{}')"
        )
    )
    op.create_table(
        "youtube_drive_backups",
        sa.Column("content_id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("file_id", sa.String(), unique=True),
        sa.Column("web_url", sa.Text()),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("md5", sa.String(32)),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "youtube_storage_transfers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(10), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("bytes_transferred", sa.BigInteger(), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("session_uri", sa.Text()),
        sa.Column("lease_token", sa.String()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_youtube_storage_transfer_queue",
        "youtube_storage_transfers",
        ["status", "next_retry_at", "id"],
    )
    op.create_index(
        "uq_youtube_storage_transfer",
        "youtube_storage_transfers",
        ["content_id", "operation"],
        unique=True,
    )
    op.create_table(
        "youtube_storage_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("previous_location", sa.String(10)),
        sa.Column("new_location", sa.String(10)),
        sa.Column("details", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_youtube_storage_event_content",
        "youtube_storage_events",
        ["content_id", "id"],
    )


def downgrade():
    for table in (
        "youtube_storage_events",
        "youtube_storage_transfers",
        "youtube_drive_backups",
        "youtube_storage_settings",
    ):
        op.drop_table(table)
    op.drop_index("ix_youtube_contents_storage_location", table_name="youtube_contents")
    for name in (
        "drive_url",
        "drive_file_id",
        "storage_verified_at",
        "storage_size",
        "staging_path",
        "storage_mode",
        "storage_location",
    ):
        op.drop_column("youtube_contents", name)

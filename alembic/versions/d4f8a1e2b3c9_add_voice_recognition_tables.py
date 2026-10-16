"""add_voice_recognition_tables

Revision ID: d4f8a1e2b3c9
Revises: c7c9ce3f01a1
Create Date: 2026-10-15 20:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from src.core.config.settings import settings

# revision identifiers, used by Alembic.
revision: str = "d4f8a1e2b3c9"
down_revision: str | Sequence[str] | None = "c7c9ce3f01a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "speaker_profiles",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("samples_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        if_not_exists=True,
    )
    op.create_index(
        "ix_speaker_profiles_name",
        "speaker_profiles",
        ["name"],
        unique=True,
        if_not_exists=True,
    )

    op.create_table(
        "voice_samples",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column(
            "speaker_id",
            sa.String(),
            sa.ForeignKey("speaker_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("speaker_label", sa.String(length=100), nullable=True),
        sa.Column("start_time", sa.Float(), nullable=True),
        sa.Column("end_time", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "embedding", Vector(settings.VOICE_EMBEDDING_DIMENSION), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        if_not_exists=True,
    )
    op.create_index(
        "ix_voice_samples_speaker_id",
        "voice_samples",
        ["speaker_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_voice_samples_source",
        "voice_samples",
        ["source_type", "source_id"],
        if_not_exists=True,
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_voice_samples_embedding_hnsw "
        "ON voice_samples USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.drop_table("voice_samples")
    op.drop_table("speaker_profiles")

"""add_voice_sample_review_curation_fields

Revision ID: e1a2b3c4d5e6
Revises: d4f8a1e2b3c9
Create Date: 2026-10-19 12:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from src.core.config.settings import settings

# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "d4f8a1e2b3c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add pending_count and centroid vector to speaker_profiles
    op.add_column(
        "speaker_profiles",
        sa.Column("pending_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "speaker_profiles",
        sa.Column(
            "centroid",
            Vector(settings.VOICE_EMBEDDING_DIMENSION),
            nullable=True,
        ),
    )

    # 2. Add curation fields to voice_samples
    op.add_column(
        "voice_samples",
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="PENDING_REVIEW",
        ),
    )
    op.add_column(
        "voice_samples",
        sa.Column("clip_path", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "voice_samples",
        sa.Column("quality", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "voice_samples",
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "voice_samples",
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
    )

    # 3. Create indexes for querying samples by status
    op.create_index(
        "ix_voice_samples_status",
        "voice_samples",
        ["status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_voice_samples_speaker_status",
        "voice_samples",
        ["speaker_id", "status"],
        if_not_exists=True,
    )

    # 4. As decided by user: "revisar do zero"
    # Existing samples are set to PENDING_REVIEW, samples_count is reset to 0,
    # and pending_count is updated to the number of existing samples.
    op.execute("UPDATE voice_samples SET status = 'PENDING_REVIEW' WHERE status IS NULL OR status = '';")
    op.execute(
        """
        UPDATE speaker_profiles sp
        SET samples_count = 0,
            pending_count = COALESCE((
                SELECT COUNT(*) FROM voice_samples vs
                WHERE vs.speaker_id = sp.id AND vs.status = 'PENDING_REVIEW'
            ), 0);
        """
    )


def downgrade() -> None:
    op.drop_index("ix_voice_samples_speaker_status", table_name="voice_samples")
    op.drop_index("ix_voice_samples_status", table_name="voice_samples")
    op.drop_column("voice_samples", "embedding_model")
    op.drop_column("voice_samples", "reviewed_at")
    op.drop_column("voice_samples", "quality")
    op.drop_column("voice_samples", "clip_path")
    op.drop_column("voice_samples", "status")
    op.drop_column("speaker_profiles", "centroid")
    op.drop_column("speaker_profiles", "pending_count")

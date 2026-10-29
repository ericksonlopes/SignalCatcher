"""Voice enrollment and identification requests."""
from alembic import op
import sqlalchemy as sa

revision = "a10428voice01"
down_revision = "b984a2acc7e4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("voice_people", sa.Column("id", sa.String(), primary_key=True), sa.Column("name", sa.String(), nullable=False))
    op.create_table("voice_jobs",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("request_key", sa.String(), unique=True, nullable=False),
        sa.Column("kind", sa.String(), nullable=False), sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False), sa.Column("state", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False), sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.String()), sa.Column("token", sa.String()), sa.Column("lease", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_voice_jobs_task_id", "voice_jobs", ["task_id"])
    op.create_index("ix_voice_jobs_state", "voice_jobs", ["state"])
    op.create_table("voice_samples", sa.Column("id", sa.String(), primary_key=True),
        sa.Column("person_id", sa.String(), nullable=False), sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("start", sa.Float(), nullable=False), sa.Column("end", sa.Float(), nullable=False),
        sa.Column("model", sa.String(), nullable=False), sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("video_path", sa.String(), nullable=False), sa.Column("audio_path", sa.String(), nullable=False))
    op.create_index("ix_voice_samples_person_id", "voice_samples", ["person_id"])
    op.create_table("voice_assignments", sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), nullable=False), sa.Column("version", sa.String(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=False), sa.Column("person_id", sa.String()),
        sa.UniqueConstraint("task_id", "version", "speaker"))
    op.create_index("ix_voice_assignments_task_id", "voice_assignments", ["task_id"])


def downgrade():
    for table in ("voice_assignments", "voice_samples", "voice_jobs", "voice_people"):
        op.drop_table(table)

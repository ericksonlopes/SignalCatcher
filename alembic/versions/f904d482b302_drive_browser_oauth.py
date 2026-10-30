"""Short-lived, single-use browser OAuth state with PKCE."""

import sqlalchemy as sa

from alembic import op

revision = "f904d482b302"
down_revision = "e802d481a301"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "youtube_drive_oauth_sessions",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("code_verifier", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("youtube_drive_oauth_sessions")

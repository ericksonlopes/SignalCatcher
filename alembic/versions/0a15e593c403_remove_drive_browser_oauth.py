"""Remove browser OAuth state; Drive uses the server's service-account key."""

import sqlalchemy as sa

from alembic import op

revision = "0a15e593c403"
down_revision = "f904d482b302"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("youtube_drive_oauth_sessions", if_exists=True)


def downgrade():
    op.create_table(
        "youtube_drive_oauth_sessions",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("code_verifier", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )

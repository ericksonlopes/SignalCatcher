"""rename status to step

Revision ID: 886b855642ed
Revises: db287817074c
Create Date: 2026-08-07 14:27:01.408131

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "886b855642ed"
down_revision: Union[str, Sequence[str], None] = "db287817074c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename the column
    op.alter_column("youtube_contents", "status", new_column_name="step")

    # In PostgreSQL, we can rename the type if it exists
    # And add new values if necessary, or just rely on SQLAlchemy handling it as a string enum
    op.execute("ALTER TYPE contentstatus RENAME TO contentstep")
    op.execute(
        "ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'PENDING_METADATA_EXTRACTION'"
    )
    op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'EXTRACTING_METADATA'")
    op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'COMPLETED'")


def downgrade() -> None:
    # Rename back
    op.alter_column("youtube_contents", "step", new_column_name="status")

    op.execute("ALTER TYPE contentstep RENAME TO contentstatus")

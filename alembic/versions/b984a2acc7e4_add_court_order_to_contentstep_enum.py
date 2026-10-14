"""add_court_order_to_contentstep_enum

Revision ID: b984a2acc7e4
Revises: f39ca82610b4
Create Date: 2026-10-14 17:35:03.307713

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b984a2acc7e4"
down_revision: str | Sequence[str] | None = "f39ca82610b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE contentstep ADD VALUE IF NOT EXISTS 'COURT_ORDER'")


def downgrade() -> None:
    """Downgrade schema."""
    pass

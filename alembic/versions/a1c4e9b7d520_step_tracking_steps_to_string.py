"""step_tracking steps to string

The step_tracking table is polymorphic: `entity_type` tells whether a row describes a
youtube_contents transition or a diarization transition. Typing `previous_step` and
`new_step` with the `contentstep` enum therefore bound a shared table to one module's
state machine, and any diarization step missing from that enum (CANCELLED, for one)
could not be stored at all, so those transitions were dropped silently.

This widens both columns to VARCHAR, which preserves every existing value.

Revision ID: a1c4e9b7d520
Revises: d07f807ea0f1
Create Date: 2026-08-31

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1c4e9b7d520"
down_revision = "d07f807ea0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widening an enum column to text: every current value is still representable, so no
    # row can be lost. postgresql_using casts the enum to its label.
    op.alter_column(
        "step_tracking",
        "previous_step",
        existing_type=sa.Enum(name="contentstep"),
        type_=sa.String(),
        existing_nullable=True,
        postgresql_using="previous_step::text",
    )
    op.alter_column(
        "step_tracking",
        "new_step",
        existing_type=sa.Enum(name="contentstep"),
        type_=sa.String(),
        existing_nullable=False,
        postgresql_using="new_step::text",
    )


def downgrade() -> None:
    # Narrowing back to the enum only succeeds while every stored value is a member of
    # `contentstep`. Rows written after the upgrade with a diarization-only step, such as
    # CANCELLED, make this fail by design rather than discarding history.
    op.alter_column(
        "step_tracking",
        "new_step",
        existing_type=sa.String(),
        type_=sa.Enum(name="contentstep"),
        existing_nullable=False,
        postgresql_using="new_step::contentstep",
    )
    op.alter_column(
        "step_tracking",
        "previous_step",
        existing_type=sa.String(),
        type_=sa.Enum(name="contentstep"),
        existing_nullable=True,
        postgresql_using="previous_step::contentstep",
    )

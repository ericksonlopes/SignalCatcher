"""Durable DemoGraph catalog, pipeline queue and observed schemas."""

import sqlalchemy as sa

from alembic import op

revision = "da2026100201"
down_revision = "f39ca82610b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demograph_datasets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
    )
    op.create_table(
        "demograph_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("extraction_id", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("completed_stages", sa.JSON(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("schema_stale", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    for column in ("extraction_id", "status"):
        op.create_index(f"ix_demograph_runs_{column}", "demograph_runs", [column])
    op.create_table(
        "demograph_artifacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("extraction_id", sa.String(), sa.ForeignKey("demograph_runs.id"), nullable=False),
        sa.Column(
            "dataset_id", sa.String(), sa.ForeignKey("demograph_datasets.id"), nullable=False
        ),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("checksum", sa.String(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("records", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_schema", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("extraction_id", "path"),
    )
    for column in ("extraction_id", "dataset_id"):
        op.create_index(f"ix_demograph_artifacts_{column}", "demograph_artifacts", [column])
    op.create_table(
        "demograph_issues",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("demograph_runs.id"), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_demograph_issues_run_id", "demograph_issues", ["run_id"])
    op.create_table(
        "demograph_schemas",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("demograph_runs.id")),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
    )
    op.create_table(
        "demograph_worker",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
    )
    datasets = sa.table(
        "demograph_datasets", sa.column("id", sa.String()), sa.column("source", sa.String())
    )
    op.bulk_insert(
        datasets,
        [
            {"id": item, "source": "CAMARA_DOS_DEPUTADOS"}
            for item in ("deputies", "votings", "votes", "histories", "topics")
        ],
    )


def downgrade() -> None:
    for table in (
        "demograph_worker",
        "demograph_schemas",
        "demograph_issues",
        "demograph_artifacts",
        "demograph_runs",
        "demograph_datasets",
    ):
        op.drop_table(table)

"""add_pgvector_and_vector_chunks

Revision ID: c7c9ce3f01a1
Revises: b984a2acc7e4
Create Date: 2026-10-15 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from src.core.config.settings import settings

# revision identifiers, used by Alembic.
revision: str = "c7c9ce3f01a1"
down_revision: str | Sequence[str] | None = "b984a2acc7e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create polymorphic vector_chunks table
    op.create_table(
        "vector_chunks",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(settings.EMBEDDING_DIMENSION), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # 3. Create B-tree indexes
    op.create_index(
        "ix_vector_chunks_source",
        "vector_chunks",
        ["source_type", "source_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_vector_chunks_parent_id",
        "vector_chunks",
        ["parent_id"],
        if_not_exists=True,
    )

    # 4. Create HNSW vector index with cosine distance operator
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vector_chunks_embedding_hnsw "
        "ON vector_chunks USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.drop_table("vector_chunks")

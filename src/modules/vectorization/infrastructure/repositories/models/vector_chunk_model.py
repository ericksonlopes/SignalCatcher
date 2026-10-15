import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text

from src.core.config.settings import settings
from src.core.database.connector import Base


def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class VectorChunkModel(Base):
    __tablename__ = "vector_chunks"
    __table_args__ = (
        Index(
            "ix_vector_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_vector_chunks_source", "source_type", "source_id"),
        Index("ix_vector_chunks_parent_id", "parent_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type = Column(String, nullable=False, index=True)
    source_id = Column(String, nullable=False, index=True)
    parent_id = Column(String, nullable=True, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=False)
    created_at = Column(DateTime, default=get_utc_now)

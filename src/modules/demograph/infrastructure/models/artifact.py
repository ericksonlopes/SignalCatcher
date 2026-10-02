from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.connector import Base


class ArtifactModel(Base):
    __tablename__ = "demograph_artifacts"
    __table_args__ = (UniqueConstraint("extraction_id", "path"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    extraction_id: Mapped[str] = mapped_column(ForeignKey("demograph_runs.id"), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("demograph_datasets.id"), index=True)
    path: Mapped[str] = mapped_column(String)
    format: Mapped[str] = mapped_column(String)
    checksum: Mapped[str] = mapped_column(String)
    bytes: Mapped[int] = mapped_column(Integer)
    records: Mapped[int] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(String)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    file_schema: Mapped[dict[str, Any]] = mapped_column(JSON)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON)

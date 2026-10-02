from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.connector import Base


class RunModel(Base):
    __tablename__ = "demograph_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    extraction_id: Mapped[str] = mapped_column(String, index=True)
    operation: Mapped[str] = mapped_column(String)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, index=True)
    stage: Mapped[str] = mapped_column(String, default="queued")
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    completed_stages: Mapped[list[str]] = mapped_column(JSON, default=list)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    schema_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

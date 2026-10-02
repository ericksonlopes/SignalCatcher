from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.connector import Base


class SchemaModel(Base):
    __tablename__ = "demograph_schemas"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("demograph_runs.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON)

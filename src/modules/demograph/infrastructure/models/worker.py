from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.connector import Base


class WorkerModel(Base):
    __tablename__ = "demograph_worker"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

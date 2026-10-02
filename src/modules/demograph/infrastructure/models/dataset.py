from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.connector import Base


class DatasetModel(Base):
    __tablename__ = "demograph_datasets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, default="CAMARA_DOS_DEPUTADOS")

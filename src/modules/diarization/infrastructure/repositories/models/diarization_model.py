import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, JSON, Integer
from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history

from src.core.database.connector import Base
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.infrastructure.repositories.models.step_tracking_model import (
    create_tracking_entry,
)


def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DiarizationModel(Base):
    __tablename__ = "diarization"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_path = Column(String, nullable=False)

    # Referência Externa
    entity_id = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)

    step = Column(
        String,
        nullable=False,
        default="PENDING",
        index=True,
    )  # PENDING, PROCESSING, COMPLETED, ERROR

    # Configuration
    language = Column(String, nullable=True)
    num_speakers = Column(Integer, nullable=True)
    min_speakers = Column(Integer, nullable=True)
    max_speakers = Column(Integer, nullable=True)
    model_size = Column(String, nullable=False, default="large-v2")

    # Results
    result_json = Column(JSON, nullable=True)  # Store actual diarization segments
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    @property
    def error_info(self):
        return self.error_message


# Add event listeners for step tracking
@event.listens_for(DiarizationModel, "after_insert")
def track_diarization_insert(mapper, connection, target):
    if target.step:
        try:
            step_enum = ContentStep(target.step)
            create_tracking_entry(mapper, connection, target, None, step_enum)
        except ValueError:
            pass


@event.listens_for(DiarizationModel, "after_update")
def track_diarization_update(mapper, connection, target):
    hist = get_history(target, "step")
    if hist.has_changes():
        old_step = hist.deleted[0] if hist.deleted else None
        new_step = hist.added[0] if hist.added else target.step

        if old_step != new_step:
            try:
                old_step_enum = ContentStep(old_step) if old_step else None
                new_step_enum = ContentStep(new_step)
                create_tracking_entry(
                    mapper, connection, target, old_step_enum, new_step_enum
                )
            except ValueError:
                pass

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, JSON, Integer
from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history

from src.core.database.connector import Base
from src.modules.diarization.domain.enums.diarization_step import DiarizationStep
from src.modules.youtube.infrastructure.repositories.models.step_tracking_model import (
    create_tracking_entry,
)

logger = logging.getLogger(__name__)


def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DiarizationModel(Base):
    __tablename__ = "diarization"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_path = Column(String, nullable=False)

    # Referência Externa
    entity_id = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)

    # Stored as text, with DiarizationStep as the source of truth for the valid values.
    step = Column(
        String,
        nullable=False,
        default=DiarizationStep.PENDING.value,
        index=True,
    )

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
def _validated_step(raw) -> str | None:
    """Returns the step name to record, warning instead of discarding unknown values.

    These listeners used to coerce the step into ContentStep inside a bare
    `except ValueError: pass`. Since CANCELLED is not a ContentStep, every cancellation
    lost its tracking entry without a trace.
    """
    if raw is None:
        return None
    try:
        return DiarizationStep(raw).name
    except ValueError:
        logger.warning(
            "Diarization step '%s' is not a known DiarizationStep; "
            "recording it in the tracking history as-is.",
            raw,
        )
        return str(raw)


@event.listens_for(DiarizationModel, "after_insert")
def track_diarization_insert(mapper, connection, target):
    # `mapper` is part of the SQLAlchemy event signature but unused here.
    if target.step:
        create_tracking_entry(
            connection, target, None, _validated_step(target.step)
        )


@event.listens_for(DiarizationModel, "after_update")
def track_diarization_update(mapper, connection, target):
    hist = get_history(target, "step")
    if hist.has_changes():
        old_step = hist.deleted[0] if hist.deleted else None
        new_step = hist.added[0] if hist.added else target.step

        if old_step != new_step:
            create_tracking_entry(
                connection,
                target,
                _validated_step(old_step),
                _validated_step(new_step),
            )

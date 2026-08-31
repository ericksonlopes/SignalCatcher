import enum
import logging

from sqlalchemy import Column, DateTime, Integer, String, event
from sqlalchemy.orm.attributes import get_history

from src.core.database.connector import Base
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
    get_brazil_time,
)

logger = logging.getLogger(__name__)


class StepTrackingModel(Base):
    __tablename__ = "step_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String, index=True, nullable=False)
    entity_type = Column(String, index=True, nullable=False)  # e.g., 'youtube_contents'

    # Plain strings rather than Enum(ContentStep). This table is polymorphic: the same
    # rows record transitions for youtube_contents and for diarization, which are two
    # different state machines. Typing it with one module's enum meant any diarization
    # step outside ContentStep could not be stored at all, so cancellations were
    # silently dropped.
    previous_step = Column(String, nullable=True)
    new_step = Column(String, nullable=False)

    changed_at = Column(DateTime, default=get_brazil_time, nullable=False)
    details = Column(
        String, nullable=True
    )  # Store any error messages or extra log context

    def __repr__(self):
        return f"<StepTrackingModel(entity_type='{self.entity_type}', entity_id={self.entity_id}, new_step='{self.new_step}')>"


def _step_name(step) -> str | None:
    """Normalises a step to the string stored in the tracking table.

    Accepts an Enum member or a plain string, so each module can keep its own enum
    without this table having to know about it.
    """
    if step is None:
        return None
    if isinstance(step, enum.Enum):
        return step.name
    return str(step)


def create_tracking_entry(connection, target, previous_step, new_step) -> None:
    new_step_name = _step_name(new_step)
    if new_step_name is None:
        logger.warning(
            "Skipping step tracking for %s id=%s: new_step is empty.",
            getattr(target, "__tablename__", "?"),
            getattr(target, "id", "?"),
        )
        return

    # Using the connection to execute an insert directly to avoid session state conflicts during flush
    connection.execute(
        StepTrackingModel.__table__.insert().values(
            entity_id=str(target.id),
            entity_type=target.__tablename__,
            previous_step=_step_name(previous_step),
            new_step=new_step_name,
            details=getattr(target, "error_info", None),
        )
    )


@event.listens_for(YoutubeContentModel, "after_insert")
def track_youtube_content_insert(mapper, connection, target):
    # `mapper` is part of the SQLAlchemy event signature but unused here.
    if hasattr(target, "step") and target.step:
        create_tracking_entry(connection, target, None, target.step)


@event.listens_for(YoutubeContentModel, "after_update")
def track_youtube_content_update(mapper, connection, target):
    # Check if the step column was updated
    hist = get_history(target, "step")
    if hist.has_changes():
        # hist.deleted contains the old values
        previous_step = hist.deleted[0] if hist.deleted else None
        # hist.added contains the new values
        new_step = hist.added[0] if hist.added else target.step

        if previous_step != new_step:
            create_tracking_entry(connection, target, previous_step, new_step)

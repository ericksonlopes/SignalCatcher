from sqlalchemy import Column, Integer, String, DateTime, Enum

from src.core.database.connector import Base
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    get_brazil_time,
)


class StepTrackingModel(Base):
    __tablename__ = "step_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, index=True, nullable=False)
    entity_type = Column(String, index=True, nullable=False)  # e.g., 'youtube_contents'

    previous_step = Column(Enum(ContentStep), nullable=True)
    new_step = Column(Enum(ContentStep), nullable=False)

    changed_at = Column(DateTime, default=get_brazil_time, nullable=False)
    details = Column(
        String, nullable=True
    )  # Store any error messages or extra log context

    def __repr__(self):
        return f"<StepTrackingModel(entity_type='{self.entity_type}', entity_id={self.entity_id}, new_step='{self.new_step}')>"


from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)


def create_tracking_entry(mapper, connection, target, previous_step, new_step):
    tracking = StepTrackingModel(
        entity_id=target.id,
        entity_type=target.__tablename__,
        previous_step=previous_step,
        new_step=new_step,
        details=getattr(target, "error_info", None),
    )
    # Using the connection to execute an insert directly to avoid session state conflicts during flush
    connection.execute(
        StepTrackingModel.__table__.insert().values(
            entity_id=tracking.entity_id,
            entity_type=tracking.entity_type,
            previous_step=(
                tracking.previous_step.name if tracking.previous_step else None
            ),
            new_step=tracking.new_step.name,
            details=tracking.details,
        )
    )


@event.listens_for(YoutubeContentModel, "after_insert")
def track_youtube_content_insert(mapper, connection, target):
    if hasattr(target, "step") and target.step:
        create_tracking_entry(mapper, connection, target, None, target.step)


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
            create_tracking_entry(mapper, connection, target, previous_step, new_step)

from sqlalchemy import func

from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.youtube_content_repository import IYoutubeContentRepository
from src.domain.models.youtube_content_entity import YoutubeContentEntity
from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.mappers.youtube_content_mapper import YoutubeContentMapper
from src.infrastructure.repositories.models.step_tracking_model import StepTrackingModel
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel


class YoutubeContentRepository(IYoutubeContentRepository):
    def __init__(self, logger: ILogger):
        self.logger = logger

    def exists_by_external_id(self, external_id: str) -> bool:
        try:
            with ConnectorPostgres() as session:
                exists = session.query(YoutubeContentModel.id).filter_by(external_id=external_id).first()

                return exists is not None
        except Exception as e:
            self.logger.error(f"Error checking if content exists by external_id '{external_id}': {e}",
                              context={"external_id": external_id, "error": str(e)})
            raise

    def get_by_external_id(self, external_id: str) -> 'YoutubeContentEntity | None':
        try:
            with ConnectorPostgres() as session:
                model = session.query(YoutubeContentModel).filter_by(external_id=external_id).first()
                if model:
                    return YoutubeContentMapper.to_domain(model)
                return None
        except Exception as e:
            self.logger.error(f"Error fetching content by external_id '{external_id}': {e}",
                              context={"external_id": external_id, "error": str(e)})
            raise

    def create(self, youtube_content_entity: YoutubeContentEntity) -> YoutubeContentEntity:
        try:
            with ConnectorPostgres() as session:
                new_content = YoutubeContentMapper.to_model(youtube_content_entity)
                session.add(new_content)
                session.commit()
                session.refresh(new_content)
                return YoutubeContentMapper.to_domain(new_content)
        except Exception as e:
            self.logger.error(f"Error creating content '{youtube_content_entity.external_id}': {e}",
                              context={"external_id": youtube_content_entity.external_id, "error": str(e)})
            raise

    def get_paginated(self, page: int, limit: int) -> tuple[list[YoutubeContentEntity], int]:
        try:
            with ConnectorPostgres() as session:
                offset = (page - 1) * limit
                query = session.query(YoutubeContentModel).order_by(YoutubeContentModel.created_at.desc())
                total = query.count()
                items = query.offset(offset).limit(limit).all()
                return [YoutubeContentMapper.to_domain(item) for item in items], total
        except Exception as e:
            self.logger.error(f"Error fetching paginated contents: {e}", context={"error": str(e)})
            raise

    def count_by_step(self) -> dict[str, int]:
        try:
            with ConnectorPostgres() as session:
                counts = session.query(
                    YoutubeContentModel.step, func.count(YoutubeContentModel.id)
                ).group_by(YoutubeContentModel.step).all()
                return {step.name: count for step, count in counts}
        except Exception as e:
            self.logger.error(f"Error counting by step: {e}", context={"error": str(e)})
            raise

    def get_first_by_step(self, step: 'ContentStep') -> 'YoutubeContentEntity | None':
        try:
            with ConnectorPostgres() as session:
                model = session.query(YoutubeContentModel).filter(YoutubeContentModel.step == step).first()
                if model:
                    return YoutubeContentMapper.to_domain(model)
                return None
        except Exception as e:
            self.logger.error(f"Error fetching first content by step '{step}': {e}", context={"error": str(e)})
            raise

    def update(self, youtube_content_entity: YoutubeContentEntity) -> YoutubeContentEntity:
        try:
            with ConnectorPostgres() as session:
                # Find the existing model
                model = session.query(YoutubeContentModel).filter(YoutubeContentModel.id == youtube_content_entity.id).first()
                if not model:
                    raise ValueError(f"Content with id {youtube_content_entity.id} not found.")

                # Update the model fields
                model.step = youtube_content_entity.step
                model.raw_metadata = youtube_content_entity.raw_metadata
                model.thumbnail = youtube_content_entity.thumbnail
                model.duration = youtube_content_entity.duration
                model.categories = youtube_content_entity.categories
                model.tags = youtube_content_entity.tags
                model.error_info = getattr(youtube_content_entity, 'error_info', None) # if entity has it
                model.published_at = getattr(youtube_content_entity, 'published_at', None)

                session.commit()
                session.refresh(model)
                return YoutubeContentMapper.to_domain(model)
        except Exception as e:
            self.logger.error(f"Error updating content '{youtube_content_entity.id}': {e}", context={"error": str(e)})
            raise

    def reset_stuck_steps(self, stuck_step: 'ContentStep', pending_step: 'ContentStep') -> int:
        try:
            with ConnectorPostgres() as session:
                stuck_items = session.query(YoutubeContentModel).filter(YoutubeContentModel.step == stuck_step).all()
                count = len(stuck_items)
                if count > 0:
                    for item in stuck_items:
                        item.step = pending_step
                    session.commit()
                return count
        except Exception as e:
            self.logger.error(f"Error resetting stuck steps from {stuck_step.name} to {pending_step.name}: {e}")
            raise

    def get_tracking_by_external_id(self, external_id: str) -> list[StepTrackingModel]:
        try:
            with ConnectorPostgres() as session:
                query = (
                    session.query(StepTrackingModel)
                    .join(
                        YoutubeContentModel,
                        StepTrackingModel.entity_id == YoutubeContentModel.id,
                    )
                    .filter(YoutubeContentModel.external_id == external_id)
                    .filter(StepTrackingModel.entity_type == "youtube_contents")
                    .order_by(StepTrackingModel.changed_at.asc())
                )
                return query.all()
        except Exception as e:
            self.logger.error(
                f"Error fetching tracking for external_id '{external_id}': {e}",
                context={"external_id": external_id, "error": str(e)},
            )
            raise


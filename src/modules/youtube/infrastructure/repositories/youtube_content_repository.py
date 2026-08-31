from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.entities.youtube_content_entity import (
    YoutubeContentEntity,
)
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.interfaces.repositories.youtube_content_repository import (
    IYoutubeContentRepository,
)
from src.modules.youtube.infrastructure.repositories.mappers.youtube_content_mapper import (
    YoutubeContentMapper,
)
from src.modules.youtube.infrastructure.repositories.models.step_tracking_model import (
    StepTrackingModel,
)
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)


class YoutubeContentRepository(IYoutubeContentRepository):
    """Persistence for YouTube content.

    Takes part in the caller's transaction: writes flush but never commit, so the
    unit of work decides when the operation is complete. Flushing matters because the
    session is configured with autoflush=False, so pending changes would otherwise be
    invisible to later queries inside the same transaction.
    """

    def __init__(self, session: Session, logger: ILogger):
        self.session = session
        self.logger = logger

    def exists_by_external_id(self, external_id: str) -> bool:
        try:
            exists = (
                self.session.query(YoutubeContentModel.id)
                .filter_by(external_id=external_id)
                .first()
            )

            return exists is not None
        except Exception as e:
            self.logger.error(
                f"Error checking if content exists by external_id '{external_id}': {e}",
                context={"external_id": external_id, "error": str(e)},
            )
            raise

    def get_by_external_id(self, external_id: str) -> YoutubeContentEntity | None:
        try:
            model = (
                self.session.query(YoutubeContentModel)
                .filter_by(external_id=external_id)
                .first()
            )
            if model:
                return YoutubeContentMapper.to_domain(model)
            return None
        except Exception as e:
            self.logger.error(
                f"Error fetching content by external_id '{external_id}': {e}",
                context={"external_id": external_id, "error": str(e)},
            )
            raise

    def create(
        self, youtube_content_entity: YoutubeContentEntity
    ) -> YoutubeContentEntity:
        try:
            new_content = YoutubeContentMapper.to_model(youtube_content_entity)
            self.session.add(new_content)
            self.session.flush()
            self.session.refresh(new_content)
            return YoutubeContentMapper.to_domain(new_content)
        except Exception as e:
            self.logger.error(
                f"Error creating content '{youtube_content_entity.external_id}': {e}",
                context={
                    "external_id": youtube_content_entity.external_id,
                    "error": str(e),
                },
            )
            raise

    def get_paginated(
        self,
        page: int,
        limit: int,
        step: str | None = None,
        search: str | None = None,
        channel: str | None = None,
    ) -> tuple[list[YoutubeContentEntity], int]:
        try:
            offset = (page - 1) * limit
            query = self.session.query(YoutubeContentModel).order_by(
                YoutubeContentModel.created_at.desc()
            )
            if step:
                query = query.filter(YoutubeContentModel.step == step)
            if search:
                query = query.filter(YoutubeContentModel.title.ilike(f"%{search}%"))
            if channel:
                query = query.filter(YoutubeContentModel.origin.ilike(f"%{channel}%"))
            total = query.count()
            items = query.offset(offset).limit(limit).all()
            return [YoutubeContentMapper.to_domain(item) for item in items], total

        except Exception as e:
            self.logger.error(
                f"Error fetching paginated contents: {e}", context={"error": str(e)}
            )
            raise

    def count_by_step(self) -> dict[str, int]:
        try:
            counts = (
                self.session.query(
                    YoutubeContentModel.step, func.count(YoutubeContentModel.id)
                )
                .group_by(YoutubeContentModel.step)
                .all()
            )
            return {step.name: count for step, count in counts}
        except Exception as e:
            self.logger.error(f"Error counting by step: {e}", context={"error": str(e)})
            raise

    def get_first_by_step(self, step: ContentStep) -> YoutubeContentEntity | None:
        try:
            model = (
                self.session.query(YoutubeContentModel)
                .filter(YoutubeContentModel.step == step)
                .first()
            )
            if model:
                return YoutubeContentMapper.to_domain(model)
            return None
        except Exception as e:
            self.logger.error(
                f"Error fetching first content by step '{step}': {e}",
                context={"error": str(e)},
            )
            raise

    def get_all_by_step(self, step: ContentStep) -> list[YoutubeContentEntity]:
        try:
            models = (
                self.session.query(YoutubeContentModel)
                .filter(YoutubeContentModel.step == step)
                .order_by(YoutubeContentModel.created_at.asc())
                .all()
            )
            return [YoutubeContentMapper.to_domain(model) for model in models]
        except Exception as e:
            self.logger.error(
                f"Error fetching all contents by step '{step}': {e}",
                context={"error": str(e)},
            )
            raise

    def get_many_by_external_ids(
        self, external_ids: list[str]
    ) -> dict[str, YoutubeContentEntity]:
        if not external_ids:
            return {}
        try:
            models = (
                self.session.query(YoutubeContentModel)
                .filter(YoutubeContentModel.external_id.in_(external_ids))
                .all()
            )
            return {
                model.external_id: YoutubeContentMapper.to_domain(model)
                for model in models
            }
        except Exception as e:
            self.logger.error(
                f"Error fetching contents by external_ids: {e}",
                context={"error": str(e)},
            )
            raise

    def find_external_ids_by_search(self, term: str) -> list[str]:
        if not term:
            return []
        try:
            pattern = f"%{term}%"
            rows = (
                self.session.query(YoutubeContentModel.external_id)
                .filter(
                    or_(
                        YoutubeContentModel.title.ilike(pattern),
                        YoutubeContentModel.origin.ilike(pattern),
                    )
                )
                .all()
            )
            return [row[0] for row in rows if row[0]]
        except Exception as e:
            self.logger.error(
                f"Error searching external_ids for '{term}': {e}",
                context={"error": str(e)},
            )
            raise

    def update(
        self, youtube_content_entity: YoutubeContentEntity
    ) -> YoutubeContentEntity:
        try:
            # Find the existing model
            model = (
                self.session.query(YoutubeContentModel)
                .filter(YoutubeContentModel.id == youtube_content_entity.id)
                .first()
            )
            if not model:
                raise ValueError(
                    f"Content with id {youtube_content_entity.id} not found."
                )

            # Update the model fields
            model.step = youtube_content_entity.step
            model.raw_metadata = youtube_content_entity.raw_metadata
            model.thumbnail = youtube_content_entity.thumbnail
            model.duration = youtube_content_entity.duration
            model.categories = youtube_content_entity.categories
            model.tags = youtube_content_entity.tags
            model.origin = youtube_content_entity.origin
            model.file_path = youtube_content_entity.file_path
            model.error_info = youtube_content_entity.error_info
            model.published_at = youtube_content_entity.published_at

            self.session.flush()
            self.session.refresh(model)
            return YoutubeContentMapper.to_domain(model)
        except Exception as e:
            self.logger.error(
                f"Error updating content '{youtube_content_entity.id}': {e}",
                context={"error": str(e)},
            )
            raise

    def reset_stuck_steps(
        self, stuck_step: ContentStep, pending_step: ContentStep
    ) -> int:
        """Moves rows parked in a processing step back to a pending step.

        With the unit of work in place, an in-process failure can no longer strand a
        row: the transaction rolls back. This remains useful for the case a
        transaction cannot cover, namely the process being killed outright (container
        restart, OOM) while a step was in flight.
        """
        try:
            stuck_items = (
                self.session.query(YoutubeContentModel)
                .filter(YoutubeContentModel.step == stuck_step)
                .all()
            )
            count = len(stuck_items)
            if count > 0:
                for item in stuck_items:
                    item.step = pending_step
                self.session.flush()
            return count
        except Exception as e:
            self.logger.error(
                f"Error resetting stuck steps from {stuck_step.name} to {pending_step.name}: {e}"
            )
            raise

    def get_tracking_by_external_id(self, external_id: str) -> list[StepTrackingModel]:
        try:
            query = (
                self.session.query(StepTrackingModel)
                .join(
                    YoutubeContentModel,
                    StepTrackingModel.entity_id
                    == cast(YoutubeContentModel.id, String),
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

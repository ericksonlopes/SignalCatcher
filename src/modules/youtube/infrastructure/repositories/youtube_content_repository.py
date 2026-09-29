from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from src.core.config.settings import settings
from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.entities.youtube_content_entity import (
    YoutubeContentEntity,
)
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.interfaces.repositories.youtube_content_repository import (
    IYoutubeContentRepository,
)
from src.modules.youtube.domain.processing import ContentBusyError, LeaseLostError
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
                self.session.query(YoutubeContentModel).filter_by(external_id=external_id).first()
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

    def create(self, youtube_content_entity: YoutubeContentEntity) -> YoutubeContentEntity:
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
            self.logger.error(f"Error fetching paginated contents: {e}", context={"error": str(e)})
            raise

    def count_by_step(self) -> dict[str, int]:
        try:
            counts = (
                self.session.query(YoutubeContentModel.step, func.count(YoutubeContentModel.id))
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

    def get_many_by_external_ids(self, external_ids: list[str]) -> dict[str, YoutubeContentEntity]:
        if not external_ids:
            return {}
        try:
            models = (
                self.session.query(YoutubeContentModel)
                .filter(YoutubeContentModel.external_id.in_(external_ids))
                .all()
            )
            return {model.external_id: YoutubeContentMapper.to_domain(model) for model in models}
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

    def update(self, youtube_content_entity: YoutubeContentEntity) -> YoutubeContentEntity:
        try:
            # Find the existing model
            model = (
                self.session.query(YoutubeContentModel)
                .filter(YoutubeContentModel.id == youtube_content_entity.id)
                .populate_existing()
                .with_for_update()
                .first()
            )
            if not model:
                raise ValueError(f"Content with id {youtube_content_entity.id} not found.")

            token = youtube_content_entity.lease_token
            if token:
                if (
                    model.lease_token != token
                    or model.lease_expires_at is None
                    or model.lease_expires_at <= datetime.now(timezone.utc)
                ):
                    raise LeaseLostError("Content reservation no longer belongs to this executor.")
            elif model.lease_token or model.deletion_requested:
                raise ContentBusyError("Content is reserved or awaiting deletion.")

            # Update the model fields
            model.title = youtube_content_entity.title
            model.language = youtube_content_entity.language
            model.next_retry_at = youtube_content_entity.next_retry_at
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
            if model.step is ContentStep.ERROR or (model.deletion_requested and model.error_info):
                attempts = (
                    model.deletion_attempt_count
                    if model.deletion_requested
                    else model.attempt_count
                )
                delay = min(
                    settings.RETRY_BASE_SECONDS * 2 ** max(0, min(int(attempts) - 1, 30)),
                    settings.RETRY_MAX_SECONDS,
                )
                model.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            if model.step is ContentStep.COMPLETED and not model.deletion_requested:
                model.attempt_count = 0
                model.next_retry_at = None
            if model.step is ContentStep.DELETED:
                model.deletion_requested = False
                model.file_path = None
                model.next_retry_at = None

            self.session.flush()
            self.session.refresh(model)
            return YoutubeContentMapper.to_domain(model)
        except Exception as e:
            self.logger.error(
                f"Error updating content '{youtube_content_entity.id}': {e}",
                context={"error": str(e)},
            )
            raise

    def reset_stuck_steps(self, stuck_step: ContentStep, pending_step: ContentStep) -> int:
        """Recover expired reservations; active heartbeats are never reset."""
        now = datetime.now(timezone.utc)
        items = (
            self.session.query(YoutubeContentModel)
            .filter(
                YoutubeContentModel.step == stuck_step,
                or_(
                    YoutubeContentModel.lease_expires_at <= now,
                    YoutubeContentModel.lease_token.is_(None),
                ),
            )
            .with_for_update(skip_locked=True)
            .all()
        )
        for item in items:
            item.step = pending_step
            item.lease_token = None
            item.lease_expires_at = None
        self.session.flush()
        return len(items)

    def get_tracking_by_external_id(self, external_id: str) -> list[StepTrackingModel]:
        try:
            query = (
                self.session.query(StepTrackingModel)
                .join(
                    YoutubeContentModel,
                    StepTrackingModel.entity_id == cast(YoutubeContentModel.id, String),
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

    def claim_next(
        self,
        steps: list[ContentStep],
        processing_step: ContentStep | None,
        exclude_ids: set[str] | None = None,
        external_id: str | None = None,
        deletion: bool = False,
    ) -> YoutubeContentEntity | None:
        now = datetime.now(timezone.utc)
        query = self.session.query(YoutubeContentModel).filter(
            YoutubeContentModel.lease_token.is_(None),
            YoutubeContentModel.deletion_requested == deletion,
            or_(
                YoutubeContentModel.next_retry_at.is_(None),
                YoutubeContentModel.next_retry_at <= now,
            ),
        )
        if deletion:
            query = query.filter(
                YoutubeContentModel.deletion_attempt_count < settings.MAX_PROCESSING_ATTEMPTS
            )
        else:
            query = query.filter(YoutubeContentModel.step.in_(steps))
            if processing_step is ContentStep.EXTRACTING_METADATA:
                query = query.filter(
                    YoutubeContentModel.attempt_count < settings.MAX_PROCESSING_ATTEMPTS
                )
        if exclude_ids:
            query = query.filter(YoutubeContentModel.external_id.notin_(exclude_ids))
        if external_id:
            query = query.filter(YoutubeContentModel.external_id == external_id)
        model = query.order_by(YoutubeContentModel.id).with_for_update(skip_locked=True).first()
        if model is None:
            return None
        model.lease_token = str(uuid4())
        model.lease_expires_at = now + timedelta(seconds=settings.PROCESSING_LEASE_SECONDS)
        model.next_retry_at = None
        if deletion:
            model.deletion_attempt_count += 1
        elif processing_step is ContentStep.EXTRACTING_METADATA:
            model.attempt_count += 1
        if processing_step:
            model.step = processing_step
        self.session.flush()
        return YoutubeContentMapper.to_domain(model)

    def renew_lease(self, external_id: str, token: str) -> bool:
        now = datetime.now(timezone.utc)
        count = (
            self.session.query(YoutubeContentModel)
            .filter(
                YoutubeContentModel.external_id == external_id,
                YoutubeContentModel.lease_token == token,
                YoutubeContentModel.lease_expires_at > now,
            )
            .update(
                {
                    YoutubeContentModel.lease_expires_at: now
                    + timedelta(seconds=settings.PROCESSING_LEASE_SECONDS)
                },
                synchronize_session=False,
            )
        )
        return count == 1

    def release_lease(self, external_id: str, token: str) -> None:
        (
            self.session.query(YoutubeContentModel)
            .filter_by(external_id=external_id, lease_token=token)
            .update(
                {YoutubeContentModel.lease_token: None, YoutubeContentModel.lease_expires_at: None},
                synchronize_session=False,
            )
        )

    def _get_command_target(self, external_id: str) -> YoutubeContentModel | None:
        model = (
            self.session.query(YoutubeContentModel)
            .filter_by(external_id=external_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if model is not None and model.lease_token:
            raise ContentBusyError(
                "Content is being processed; retry the command after it finishes."
            )
        return model

    def request_reprocessing(self, external_id: str) -> bool:
        model = self._get_command_target(external_id)
        if model is None:
            return False
        if model.deletion_requested or model.step is ContentStep.DELETED:
            raise ContentBusyError("Deleted content cannot be reprocessed.")
        model.step = ContentStep.REPROCESSING
        model.attempt_count = 0
        model.next_retry_at = None
        model.error_info = None
        self.session.flush()
        return True

    def request_deletion(self, external_id: str) -> bool:
        model = self._get_command_target(external_id)
        if model is None:
            return False
        if model.step is ContentStep.DELETED:
            return True
        model.deletion_requested = True
        model.deletion_attempt_count = 0
        model.next_retry_at = None
        self.session.flush()
        return True

    def recover_expired_leases(self) -> int:
        now = datetime.now(timezone.utc)
        models = (
            self.session.query(YoutubeContentModel)
            .filter(
                or_(
                    YoutubeContentModel.lease_expires_at <= now,
                    (YoutubeContentModel.lease_token.is_(None))
                    & (
                        YoutubeContentModel.step.in_(
                            [ContentStep.EXTRACTING_METADATA, ContentStep.DOWNLOADING]
                        )
                    ),
                )
            )
            .with_for_update(skip_locked=True)
            .limit(100)
            .all()
        )
        for model in models:
            if model.step is ContentStep.EXTRACTING_METADATA:
                model.step = ContentStep.PENDING_METADATA_EXTRACTION
            elif model.step is ContentStep.DOWNLOADING:
                model.step = ContentStep.PENDING_DOWNLOAD
            model.lease_token = None
            model.lease_expires_at = None
        self.session.flush()
        return len(models)

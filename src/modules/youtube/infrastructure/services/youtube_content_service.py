from typing import Any

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.entities.youtube_content_entity import (
    YoutubeContentEntity,
)
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.interfaces.repositories.youtube_content_repository import (
    IYoutubeContentRepository,
)
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)


class YoutubeContentService(IYoutubeContentService):
    def __init__(self, repository: IYoutubeContentRepository, logger: ILogger):
        self.repository = repository
        self.logger = logger

    def add_new_content(
        self, external_id: str, title: str, url: str, origin: str
    ) -> YoutubeContentEntity:
        if self.repository.exists_by_external_id(external_id):
            self.logger.warning(
                f"Content with external_id {external_id} already exists."
            )
            raise ValueError("Content already exists.")

        content = YoutubeContentEntity(
            external_id=external_id,
            title=title,
            url=url,
            origin=origin,
            step=ContentStep.STARTED,
        )

        created_content = self.repository.create(content)

        # Immediate state transition in business logic
        created_content.step = ContentStep.PENDING_METADATA_EXTRACTION
        self.repository.update(created_content)

        self.logger.info(
            f"New content created: {created_content.title} ({created_content.id})"
        )
        return created_content

    def exists_by_external_id(self, external_id: str) -> bool:
        return self.repository.exists_by_external_id(external_id)

    def get_by_external_id(self, external_id: str) -> YoutubeContentEntity | None:
        return self.repository.get_by_external_id(external_id)

    def update_content(self, content: YoutubeContentEntity) -> YoutubeContentEntity:
        return self.repository.update(content)

    def update_content_step(
        self, content: YoutubeContentEntity, step: ContentStep
    ) -> YoutubeContentEntity:
        content.step = step
        return self.repository.update(content)

    def get_first_by_step(self, step: ContentStep) -> YoutubeContentEntity | None:
        return self.repository.get_first_by_step(step)

    def get_all_by_step(self, step: ContentStep) -> list[YoutubeContentEntity]:
        return self.repository.get_all_by_step(step)

    def reset_stuck_steps(
        self, stuck_step: ContentStep, pending_step: ContentStep
    ) -> int:
        return self.repository.reset_stuck_steps(
            stuck_step=stuck_step, pending_step=pending_step
        )

    def count_by_step(self) -> dict[str, int]:
        return self.repository.count_by_step()

    def get_paginated(
        self, page: int, limit: int, step: str | None = None, search: str | None = None
    ) -> tuple[list[YoutubeContentEntity], int]:
        return self.repository.get_paginated(
            page=page, limit=limit, step=step, search=search
        )

    def get_tracking_by_external_id(self, external_id: str) -> list[Any]:
        return self.repository.get_tracking_by_external_id(external_id)

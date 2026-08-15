from abc import ABC, abstractmethod
from typing import Any

from src.modules.youtube.domain.entities.youtube_content_entity import (
    YoutubeContentEntity,
)
from src.modules.youtube.domain.enums.content_step import ContentStep


class IYoutubeContentService(ABC):
    @abstractmethod
    def add_new_content(
        self, external_id: str, title: str, url: str, origin: str
    ) -> YoutubeContentEntity:
        pass

    @abstractmethod
    def exists_by_external_id(self, external_id: str) -> bool:
        pass

    @abstractmethod
    def get_by_external_id(self, external_id: str) -> YoutubeContentEntity | None:
        pass

    @abstractmethod
    def update_content(self, content: YoutubeContentEntity) -> YoutubeContentEntity:
        pass

    @abstractmethod
    def update_content_step(
        self, content: YoutubeContentEntity, step: ContentStep
    ) -> YoutubeContentEntity:
        pass

    @abstractmethod
    def get_first_by_step(self, step: ContentStep) -> YoutubeContentEntity | None:
        pass

    @abstractmethod
    def get_all_by_step(self, step: ContentStep) -> list[YoutubeContentEntity]:
        pass

    @abstractmethod
    def reset_stuck_steps(
        self, stuck_step: ContentStep, pending_step: ContentStep
    ) -> int:
        pass

    @abstractmethod
    def count_by_step(self) -> dict[str, int]:
        pass

    @abstractmethod
    def get_paginated(
        self, page: int, limit: int, step: str | None = None, search: str | None = None, channel: str | None = None
    ) -> tuple[list[YoutubeContentEntity], int]:
        pass


    @abstractmethod
    def get_tracking_by_external_id(self, external_id: str) -> list[Any]:
        pass

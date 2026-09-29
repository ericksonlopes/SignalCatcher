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
    def get_many_by_external_ids(self, external_ids: list[str]) -> dict[str, YoutubeContentEntity]:
        """Batch lookup, so a caller can enrich a page with a single query."""
        pass

    @abstractmethod
    def find_external_ids_by_search(self, term: str) -> list[str]:
        """Lets another module filter by title/origin without joining these tables."""
        pass

    @abstractmethod
    def reset_stuck_steps(self, stuck_step: ContentStep, pending_step: ContentStep) -> int:
        pass

    @abstractmethod
    def count_by_step(self) -> dict[str, int]:
        pass

    @abstractmethod
    def get_paginated(
        self,
        page: int,
        limit: int,
        step: str | None = None,
        search: str | None = None,
        channel: str | None = None,
    ) -> tuple[list[YoutubeContentEntity], int]:
        pass

    @abstractmethod
    def get_tracking_by_external_id(self, external_id: str) -> list[Any]:
        pass

    @abstractmethod
    def claim_next(
        self,
        steps: list[ContentStep],
        processing_step: ContentStep | None,
        exclude_ids: set[str] | None = None,
        external_id: str | None = None,
        deletion: bool = False,
    ) -> YoutubeContentEntity | None: ...

    @abstractmethod
    def renew_lease(self, external_id: str, token: str) -> bool: ...

    @abstractmethod
    def release_lease(self, external_id: str, token: str) -> None: ...

    @abstractmethod
    def request_reprocessing(self, external_id: str) -> bool: ...

    @abstractmethod
    def request_deletion(self, external_id: str) -> bool: ...

    @abstractmethod
    def recover_expired_leases(self) -> int: ...

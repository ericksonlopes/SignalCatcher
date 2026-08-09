from typing import Protocol

from src.domain.models.youtube_content_entity import YoutubeContentEntity


class IYoutubeContentRepository(Protocol):
    def exists_by_external_id(self, external_id: str) -> bool:
        """Checks if a content already exists by its external ID."""
        ...

    def get_by_external_id(self, external_id: str) -> 'YoutubeContentEntity | None':
        """Returns the content matching the given external ID."""
        ...

    def create(self, youtube_content_entity: YoutubeContentEntity) -> YoutubeContentEntity:
        """Saves a new content to the database."""
        ...

    def get_paginated(self, page: int, limit: int, step: str | None = None, search: str | None = None) -> tuple[list[YoutubeContentEntity], int]:
        """Returns a paginated list of contents and the total count."""
        ...

    def count_by_step(self) -> dict[str, int]:
        """Returns the distinct count of contents grouped by their step."""
        ...

    def get_first_by_step(self, step: 'ContentStep') -> 'YoutubeContentEntity | None':
        """Returns the first content matching the given step."""
        ...

    def update(self, youtube_content_entity: YoutubeContentEntity) -> YoutubeContentEntity:
        """Updates an existing content in the database."""
        ...

    def reset_stuck_steps(self, stuck_step: 'ContentStep', pending_step: 'ContentStep') -> int:
        """Resets contents stuck in a processing step back to a pending step, returning how many were updated."""
        ...

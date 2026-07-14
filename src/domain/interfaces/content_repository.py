from typing import Protocol

from src.domain.models.content_entity import ContentEntity


class IContentRepository(Protocol):
    def exists_by_external_id(self, external_id: str) -> bool:
        """Checks if a content already exists by its external ID."""
        ...

    def create(self, content_entity: ContentEntity) -> ContentEntity:
        """Saves a new content to the database."""
        ...

    def count_by_status(self) -> dict[str, int]:
        """Returns the distinct count of contents grouped by their status."""
        ...

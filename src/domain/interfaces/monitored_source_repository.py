from typing import Protocol, Optional
from src.domain.models.source_entity import SourceEntity

class IMonitoredSourceRepository(Protocol):
    def get_by_url(self, url: str) -> Optional[SourceEntity]:
        """Fetches a source by its URL."""
        ...

    def create(self, source_data: SourceEntity) -> SourceEntity:
        """Saves a new source to the database."""
        ...

    def get_all_active(self) -> list[SourceEntity]:
        """Fetches all active sources from the database."""
        ...

    def update(self, source_entity: SourceEntity) -> SourceEntity:
        """Updates an existing source in the database."""
        ...

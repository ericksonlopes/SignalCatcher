from typing import Protocol

from src.domain.models.source_entity import SourceEntity


class ISourceService(Protocol):
    def create_source(self, source_entity: SourceEntity) -> SourceEntity:
        """Creates and persists a source, validating necessary business rules in the infrastructure."""
        ...

from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.monitored_source_repository import IMonitoredSourceRepository
from src.domain.interfaces.source_service import ISourceService
from src.domain.models.source_entity import SourceEntity


class SourceService(ISourceService):
    def __init__(self, repository: IMonitoredSourceRepository, logger: ILogger):
        self.repository = repository
        self.logger = logger

    def create_source(self, source_entity: SourceEntity) -> SourceEntity:
        existing_source = self.repository.get_by_url(url=source_entity.url)
        if existing_source:
            self.logger.warning(f"Attempt to duplicate source: {source_entity.url}", context={"url": source_entity.url})
            raise ValueError("A source with this URL already exists.")

        new_source = self.repository.create(source_entity)

        self.logger.debug(f"New source created successfully: {new_source.name}", context={"source_id": new_source.id, "source_name": new_source.name})
        return new_source

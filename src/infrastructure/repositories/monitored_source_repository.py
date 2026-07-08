from typing import Optional

from src.application.interfaces.ilogger import ILogger
from src.domain.interfaces.monitored_source_repository import IMonitoredSourceRepository
from src.domain.models.source_entity import SourceEntity
from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.mappers.source_mapper import SourceMapper
from src.infrastructure.repositories.models.monitored_source import MonitoredSourceModel


class MonitoredSourceRepository(IMonitoredSourceRepository):
    def __init__(self, logger: ILogger):
        self.logger = logger

    def get_by_url(self, url: str) -> Optional[SourceEntity]:
        try:
            with ConnectorPostgres() as session:
                source = session.query(MonitoredSourceModel).filter_by(url=url).first()
                if source:
                    return SourceMapper.to_domain(source)
                return None
        except Exception as e:
            self.logger.error(f"Error getting source by url '{url}': {e}", context={"url": url, "error": str(e)})
            raise

    def create(self, source_data: SourceEntity) -> SourceEntity:
        try:
            with ConnectorPostgres() as session:
                new_source = SourceMapper.to_model(source_data)
                session.add(new_source)
                session.commit()
                session.refresh(new_source)
                return SourceMapper.to_domain(new_source)
        except Exception as e:
            self.logger.error(f"Error creating source '{source_data.url}': {e}",
                              context={"url": source_data.url, "error": str(e)})
            raise

    def get_all_active(self) -> list[SourceEntity]:
        try:
            with ConnectorPostgres() as session:
                sources = session.query(MonitoredSourceModel).filter_by(active=True).all()
                return [SourceMapper.to_domain(s) for s in sources]
        except Exception as e:
            self.logger.error(f"Error getting all active sources: {e}", context={"error": str(e)})
            raise

    def update(self, source_entity: SourceEntity) -> SourceEntity:
        try:
            with ConnectorPostgres() as session:
                model = session.query(MonitoredSourceModel).filter_by(id=source_entity.id).first()
                if model:
                    model.last_checked_at = source_entity.last_checked_at
                    model.active = source_entity.active
                    # Update other fields if necessary
                    session.commit()
                    session.refresh(model)
                    return SourceMapper.to_domain(model)
                return source_entity  # Or raise an exception
        except Exception as e:
            self.logger.error(f"Error updating source '{source_entity.id}': {e}",
                              context={"source_id": source_entity.id, "error": str(e)})
            raise

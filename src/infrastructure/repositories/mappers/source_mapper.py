from src.domain.models.source_entity import SourceEntity
from src.infrastructure.repositories.models.monitored_source import MonitoredSourceModel


class SourceMapper:
    @staticmethod
    def to_domain(model: MonitoredSourceModel) -> SourceEntity:
        return SourceEntity(
            id=model.id,
            name=model.name,
            url=model.url,
            source_platform=model.source_platform,
            active=model.active,
            created_at=model.created_at,
            last_checked_at=model.last_checked_at,
        )

    @staticmethod
    def to_model(entity: SourceEntity) -> MonitoredSourceModel:
        return MonitoredSourceModel(
            id=entity.id,
            name=entity.name,
            url=entity.url,
            source_platform=entity.source_platform,
            active=entity.active,
            created_at=entity.created_at,
            last_checked_at=entity.last_checked_at,
        )

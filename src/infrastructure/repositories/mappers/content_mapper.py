from src.domain.models.content_entity import ContentEntity
from src.infrastructure.repositories.models.content_model import ContentModel


class ContentMapper:
    @staticmethod
    def to_domain(model: ContentModel) -> ContentEntity:
        return ContentEntity(
            id=model.id,
            external_id=model.external_id,
            title=model.title,
            url=model.url,
            source_platform=model.source_platform,
            origin=model.origin,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(entity: ContentEntity) -> ContentModel:
        return ContentModel(
            id=entity.id,
            external_id=entity.external_id,
            title=entity.title,
            url=entity.url,
            source_platform=entity.source_platform,
            origin=entity.origin,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

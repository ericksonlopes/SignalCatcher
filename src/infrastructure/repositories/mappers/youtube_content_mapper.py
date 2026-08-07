from src.domain.models.youtube_content_entity import YoutubeContentEntity
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel


class YoutubeContentMapper:
    @staticmethod
    def to_domain(model: YoutubeContentModel) -> YoutubeContentEntity:
        return YoutubeContentEntity(
            id=model.id,
            external_id=model.external_id,
            title=model.title,
            url=model.url,
            source_platform=model.source_platform,
            origin=model.origin,
            step=model.step,
            raw_metadata=model.raw_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(entity: YoutubeContentEntity) -> YoutubeContentModel:
        return YoutubeContentModel(
            id=entity.id,
            external_id=entity.external_id,
            title=entity.title,
            url=entity.url,
            source_platform=entity.source_platform,
            origin=entity.origin,
            step=entity.step,
            raw_metadata=entity.raw_metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

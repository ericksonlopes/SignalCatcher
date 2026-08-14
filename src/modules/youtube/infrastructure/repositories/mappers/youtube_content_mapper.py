from src.modules.youtube.domain.entities.youtube_content_entity import (
    YoutubeContentEntity,
)
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)


class YoutubeContentMapper:
    @staticmethod
    def to_domain(model: YoutubeContentModel) -> YoutubeContentEntity:
        return YoutubeContentEntity(
            id=model.id,
            external_id=model.external_id,
            title=model.title,
            url=model.url,
            origin=model.origin,
            step=model.step,
            raw_metadata=model.raw_metadata,
            thumbnail=model.thumbnail,
            duration=model.duration,
            categories=model.categories,
            tags=model.tags,
            file_path=model.file_path,
            error_info=model.error_info,
            published_at=model.published_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            language=model.language,
        )

    @staticmethod
    def to_model(entity: YoutubeContentEntity) -> YoutubeContentModel:
        return YoutubeContentModel(
            id=entity.id,
            external_id=entity.external_id,
            title=entity.title,
            url=entity.url,
            origin=entity.origin,
            step=entity.step,
            raw_metadata=entity.raw_metadata,  # type: ignore
            thumbnail=entity.thumbnail,  # type: ignore
            duration=entity.duration,  # type: ignore
            categories=entity.categories,  # type: ignore
            tags=entity.tags,  # type: ignore
            file_path=entity.file_path,  # type: ignore
            error_info=entity.error_info,  # type: ignore
            created_at=entity.created_at,  # type: ignore
            updated_at=entity.updated_at,  # type: ignore
            language=entity.language,  # type: ignore
        )

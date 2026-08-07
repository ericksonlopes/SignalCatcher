from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.youtube_content_repository import IYoutubeContentRepository
from src.domain.models.youtube_content_entity import YoutubeContentEntity
from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.mappers.youtube_content_mapper import YoutubeContentMapper
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel


from sqlalchemy import func

class YoutubeContentRepository(IYoutubeContentRepository):
    def __init__(self, logger: ILogger):
        self.logger = logger

    def exists_by_external_id(self, external_id: str) -> bool:
        try:
            with ConnectorPostgres() as session:
                exists = session.query(YoutubeContentModel.id).filter_by(external_id=external_id).first()
                return exists is not None
        except Exception as e:
            self.logger.error(f"Error checking if content exists by external_id '{external_id}': {e}",
                              context={"external_id": external_id, "error": str(e)})
            raise

    def create(self, youtube_content_entity: YoutubeContentEntity) -> YoutubeContentEntity:
        try:
            with ConnectorPostgres() as session:
                new_content = YoutubeContentMapper.to_model(youtube_content_entity)
                session.add(new_content)
                session.commit()
                session.refresh(new_content)
                return YoutubeContentMapper.to_domain(new_content)
        except Exception as e:
            self.logger.error(f"Error creating content '{youtube_content_entity.external_id}': {e}",
                              context={"external_id": youtube_content_entity.external_id, "error": str(e)})
            raise

    def count_by_status(self) -> dict[str, int]:
        try:
            with ConnectorPostgres() as session:
                counts = session.query(
                    YoutubeContentModel.status, func.count(YoutubeContentModel.id)
                ).group_by(YoutubeContentModel.status).all()
                return {status.name: count for status, count in counts}
        except Exception as e:
            self.logger.error(f"Error counting by status: {e}", context={"error": str(e)})
            raise

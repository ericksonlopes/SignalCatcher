from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.content_repository import IContentRepository
from src.domain.models.content_entity import ContentEntity
from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.mappers.content_mapper import ContentMapper
from src.infrastructure.repositories.models.content_model import ContentModel


from sqlalchemy import func

class ContentRepository(IContentRepository):
    def __init__(self, logger: ILogger):
        self.logger = logger

    def exists_by_external_id(self, external_id: str) -> bool:
        try:
            with ConnectorPostgres() as session:
                exists = session.query(ContentModel.id).filter_by(external_id=external_id).first()
                return exists is not None
        except Exception as e:
            self.logger.error(f"Error checking if content exists by external_id '{external_id}': {e}",
                              context={"external_id": external_id, "error": str(e)})
            raise

    def create(self, content_entity: ContentEntity) -> ContentEntity:
        try:
            with ConnectorPostgres() as session:
                new_content = ContentMapper.to_model(content_entity)
                session.add(new_content)
                session.commit()
                session.refresh(new_content)
                return ContentMapper.to_domain(new_content)
        except Exception as e:
            self.logger.error(f"Error creating content '{content_entity.external_id}': {e}",
                              context={"external_id": content_entity.external_id, "error": str(e)})
            raise

    def count_by_status(self) -> dict[str, int]:
        try:
            with ConnectorPostgres() as session:
                counts = session.query(
                    ContentModel.status, func.count(ContentModel.id)
                ).group_by(ContentModel.status).all()
                return {status.name: count for status, count in counts}
        except Exception as e:
            self.logger.error(f"Error counting by status: {e}", context={"error": str(e)})
            raise

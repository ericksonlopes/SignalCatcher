from src.core.config.settings import settings
from src.core.logger.logger import logger
from src.modules.youtube.application.use_cases.jobs.delete_content_use_case import (
    DeleteContentUseCase,
)
from src.modules.youtube.infrastructure.services.content_storage import ContentStorage
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork


def delete_contents_job() -> None:
    use_case = DeleteContentUseCase(
        lambda: YoutubeUnitOfWork(logger=logger),
        ContentStorage(settings.DOWNLOAD_YOUTUBE_PATH),
        logger,
    )
    while use_case.execute():
        pass

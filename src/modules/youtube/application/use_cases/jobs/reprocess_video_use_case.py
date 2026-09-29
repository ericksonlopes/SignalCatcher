from collections.abc import Callable

from src.core.logger.interfaces import ILogger
from src.modules.youtube.application.use_cases.jobs.download_video_use_case import (
    DownloadVideoUseCase,
)
from src.modules.youtube.application.use_cases.jobs.extract_metadata_use_case import (
    ExtractMetadataUseCase,
)
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork


class ReprocessVideoUseCase:
    def __init__(
        self,
        uow_factory: Callable[[], IYoutubeUnitOfWork],
        scraper: IYouTubeScraper,
        output_path: str,
        logger: ILogger,
    ):
        self.extractor = ExtractMetadataUseCase(uow_factory, scraper, logger)
        self.downloader = DownloadVideoUseCase(uow_factory, scraper, output_path, logger)

    def execute(self, external_id: str) -> None:
        if self.extractor.execute(steps=[ContentStep.REPROCESSING], external_id=external_id):
            self.downloader.execute(external_id=external_id)

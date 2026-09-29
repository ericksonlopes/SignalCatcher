import os
from collections.abc import Callable

from src.core.logger.interfaces import ILogger
from src.core.utils.file_utils import format_storage_path
from src.modules.youtube.application.use_cases.jobs.content_lease import ContentLease
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.error_classifier import classify_youtube_error, is_bot_block
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork
from src.modules.youtube.domain.processing import LeaseLostError


class DownloadVideoUseCase:
    def __init__(
        self,
        uow_factory: Callable[[], IYoutubeUnitOfWork],
        scraper: IYouTubeScraper,
        output_path: str,
        logger: ILogger,
    ):
        self.uow_factory = uow_factory
        self.scraper = scraper
        self.output_path = output_path
        self.logger = logger

    def execute(self, external_id: str | None = None) -> bool:
        with self.uow_factory() as uow:
            content = uow.contents.claim_next(
                [ContentStep.PENDING_DOWNLOAD],
                ContentStep.DOWNLOADING,
                external_id=external_id,
            )
            uow.commit()
        if content is None:
            return False
        with ContentLease(self.uow_factory, content, self.logger) as lease:
            try:
                final_path = self.scraper.download_video(
                    url=content.url,
                    content_id=content.external_id,
                    origin=content.origin,
                    output_path=self.output_path,
                    progress_guard=lease.ensure_owned,
                )
                lease.ensure_owned()
                content.file_path = format_storage_path(
                    content.origin, os.path.basename(final_path)
                )
                content.error_info = None
                with self.uow_factory() as uow:
                    content.step = ContentStep.DOWNLOADED
                    content = uow.contents.update_content(content)
                    content.step = ContentStep.COMPLETED
                    uow.contents.update_content(content)
                    uow.commit()
            except LeaseLostError:
                raise
            except Exception as exc:
                lease.ensure_owned()
                content.error_info = str(exc)
                content.step = classify_youtube_error(str(exc))
                with self.uow_factory() as uow:
                    uow.contents.update_content(content)
                    uow.commit()
                self.logger.error(f"Download failed for {content.external_id}: {exc}")
                if content.step is ContentStep.ERROR and is_bot_block(str(exc)):
                    raise
        return True

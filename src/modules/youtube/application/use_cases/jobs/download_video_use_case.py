import os
from collections.abc import Callable
from pathlib import Path

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
        storage_mode: Callable[[], str] | None = None,
    ):
        self.uow_factory = uow_factory
        self.scraper = scraper
        self.output_path = output_path
        self.storage_mode = storage_mode
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
                mode = self.storage_mode() if self.storage_mode else "LOCAL"
                output_path = (
                    str(Path(self.output_path) / ".staging")
                    if mode == "DRIVE"
                    else self.output_path
                )
                final_path = self.scraper.download_video(
                    url=content.url,
                    content_id=content.external_id,
                    origin=content.origin,
                    output_path=output_path,
                    progress_guard=lease.ensure_owned,
                )
                lease.ensure_owned()
                stored_path = format_storage_path(content.origin, os.path.basename(final_path))
                content.storage_mode = mode
                content.storage_size = os.path.getsize(final_path)
                content.file_path = stored_path if mode != "DRIVE" else None
                content.staging_path = (
                    "/youtube/.staging/" + stored_path.removeprefix("/youtube/")
                    if mode == "DRIVE"
                    else None
                )
                content.error_info = None
                with self.uow_factory() as uow:
                    content.step = ContentStep.DOWNLOADED
                    content = uow.contents.update_content(content)
                    if mode != "DRIVE":
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
                if content.step is ContentStep.SCHEDULED:
                    self.logger.warning(
                        f"Video {content.external_id} is not available yet; "
                        "waiting for its premiere or live event. Download deferred.",
                        context={"reason": str(exc), "step": content.step.value},
                    )
                else:
                    self.logger.error(f"Download failed for {content.external_id}: {exc}")
                if content.step is ContentStep.ERROR and is_bot_block(str(exc)):
                    raise
        return True
